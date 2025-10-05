# SHE-Guardian: Flask backend (agents + alerts + voice endpoint)
import os
print("🚀 Running server.py from:", os.path.abspath(__file__), flush=True)

from flask import Flask, request, jsonify
import sqlite3, time, requests
from math import radians, sin, cos, asin, sqrt

# === Voice model imports ===
import joblib
import numpy as np
import librosa
import io
import soundfile as sf

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "events.db")

# --- Telegram alert config ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials missing; printing alert instead:\n", msg)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
    except Exception as e:
        print("[ERR] Telegram send failed:", e)

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS locs(
        id INTEGER PRIMARY KEY,
        user TEXT, ts INTEGER, lat REAL, lon REAL, acc REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts(
        id INTEGER PRIMARY KEY,
        user TEXT, ts INTEGER, type TEXT, summary TEXT)""")
    conn.commit(); conn.close()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dl/2)**2
    return 2 * R * asin(sqrt(a))

def stationary_time_seconds(user: str):
    conn = db()
    rows = conn.execute(
        "SELECT ts, lat, lon FROM locs WHERE user=? ORDER BY ts DESC LIMIT 10", (user,)
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        return 0
    lat0, lon0 = rows[0][1], rows[0][2]
    span = rows[0][0] - rows[-1][0]
    within = all(haversine(lat0, lon0, r[1], r[2]) < 15 for r in rows)
    return span if within else 0

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/hello")
def hello():
    return "hi"

@app.post("/loc")
def loc():
    data = request.get_json(force=True)
    user = data.get("user", "user")
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))
    acc = float(data.get("acc", 0))
    ts = int(data.get("ts", time.time()))
    conn = db()
    conn.execute("INSERT INTO locs(user, ts, lat, lon, acc) VALUES(?,?,?,?,?)",
                 (user, ts, lat, lon, acc))
    conn.commit(); conn.close()
    print(f"[LOC] {user} lat={lat:.6f} lon={lon:.6f} acc={acc} ts={ts}", flush=True)

    # simple rule: stationary > 180 sec
    st = stationary_time_seconds(user)
    if st > 180:
        osm = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
        send_telegram(f"⚠️ {user} stationary >3 min at {lat:.6f},{lon:.6f}\n{osm}")
        print(f"[ALERT] Stationary >3 min for {user}", flush=True)
    return jsonify(ok=True)

@app.post("/sos")
def sos():
    data = request.get_json(force=True)
    user = data.get("user", "user")
    coords = data.get("coords") or {}
    lat = coords.get("latitude", None)
    lon = coords.get("longitude", None)
    ts = int(time.time())
    summary = f"SOS from {user} at {lat},{lon} (ts={ts})."
    conn = db()
    conn.execute("INSERT INTO alerts(user, ts, type, summary) VALUES(?,?,?,?)",
                 (user, ts, "SOS", summary))
    conn.commit(); conn.close()
    print(f"[SOS] {user} lat={lat} lon={lon} ts={ts}", flush=True)
    osm = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}" if lat and lon else ""
    send_telegram(f"🚨 {summary}\n{osm}")
    return jsonify(ok=True)

# === ✅ Voice model loading ===
VOICE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "voice_model", "artifacts", "voice_clf.joblib")
FEAT_CFG_PATH   = os.path.join(os.path.dirname(__file__), "..", "voice_model", "artifacts", "feat_cfg.npy")

voice_model = None
n_mfcc, sr_target = 20, 16000
try:
    if os.path.exists(VOICE_MODEL_PATH):
        voice_model = joblib.load(VOICE_MODEL_PATH)
    if os.path.exists(FEAT_CFG_PATH):
        n_mfcc, sr_target = [int(x) for x in np.load(FEAT_CFG_PATH)]
    print(f"[VOICE] model loaded: {VOICE_MODEL_PATH}, n_mfcc={n_mfcc}, sr={sr_target}", flush=True)
except Exception as e:
    print("[VOICE] failed to load model:", e, flush=True)

def _featurize_wav_bytes(wav_bytes):
    y, sr = sf.read(io.BytesIO(wav_bytes), dtype='float32', always_2d=False)
    if sr != sr_target:
        y = librosa.resample(y, orig_sr=sr, target_sr=sr_target)
        sr = sr_target
    if y.ndim > 1:
        y = np.mean(y, axis=1)  # mono
    target_len = sr * 4
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    feats = np.hstack([mfcc.mean(axis=1), mfcc.std(axis=1), mfcc.min(axis=1), mfcc.max(axis=1)])
    return feats.reshape(1, -1)

# ✅ Real voice classification endpoint (logs + telegram + optional auto-SOS)
@app.post("/voice_score")
def voice_score():
    """
    Accepts: multipart/form-data with:
      - audio: WAV file (required)
      - user:  optional user id/name
      - lat, lon: optional coordinates (strings are fine)
    Returns: JSON { ok, distress_prob, distress_label }
    """
    if voice_model is None:
        return jsonify({"ok": False, "msg": "Voice model not loaded"}), 503
    if "audio" not in request.files:
        return jsonify({"ok": False, "msg": "Send form-data with key 'audio' and a .wav file"}), 400

    user = request.form.get("user", "user")
    lat  = request.form.get("lat",  None)
    lon  = request.form.get("lon",  None)

    try:
        feats = _featurize_wav_bytes(request.files["audio"].read())
        prob = float(voice_model.predict_proba(feats)[0, 1])
        label = "distress" if prob >= 0.6 else "normal"

        # 1) Log inference event
        ts = int(time.time())
        summary = f"Voice inference for {user}: {label} (p={prob:.2f})"
        conn = db()
        conn.execute(
            "INSERT INTO alerts(user, ts, type, summary) VALUES(?,?,?,?)",
            (user, ts, "VOICE", summary)
        )
        conn.commit(); conn.close()

        # 2) Build a map link if coords provided
        osm = ""
        if lat and lon:
            try:
                latf, lonf = float(lat), float(lon)
                osm = f"\nhttps://www.openstreetmap.org/?mlat={latf}&mlon={lonf}#map=18/{latf}/{lonf}"
            except:
                pass

        # 3) Notify on distress
        if label == "distress":
            send_telegram(f"🗣️ Voice distress detected for {user} (p={prob:.2f}){osm}")

        # 4) Auto-SOS if very confident
        if prob >= 0.85:
            ts2 = int(time.time())
            summary2 = f"AUTO-SOS (voice) for {user} at {lat},{lon} (p={prob:.2f})"
            conn = db()
            conn.execute(
                "INSERT INTO alerts(user, ts, type, summary) VALUES(?,?,?,?)",
                (user, ts2, "SOS", summary2)
            )
            conn.commit(); conn.close()
            send_telegram(f"🚨 {summary2}{osm}")

        return jsonify({"ok": True, "distress_prob": prob, "distress_label": label})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"audio parse/predict failed: {e}"}), 500

# --- Read recent alerts (handy for demo/report) ---
@app.get("/alerts")
def get_alerts():
    conn = db()
    rows = conn.execute(
        "SELECT id, user, ts, type, summary FROM alerts ORDER BY ts DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify([
        {"id": r[0], "user": r[1], "ts": r[2], "type": r[3], "summary": r[4]}
        for r in rows
    ])

# --- Telegram test endpoint ---
@app.route("/alert_test", methods=["GET"])
def alert_test():
    send_telegram("✅ Test alert from SHE-Guardian backend is working!")
    return jsonify({"ok": True, "msg": "Test alert sent to Telegram"})

if __name__ == "__main__":
    init_db()
    print("=== URL MAP ===", flush=True)
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods}  {rule}", flush=True)
    app.run(host="0.0.0.0", port=5000)
