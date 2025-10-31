# backend/server.py
# SHE-Guardian: Flask backend (agents + alerts + voice endpoint)
import os, io, time, sqlite3, requests, tempfile, logging, traceback
from math import radians, sin, cos, asin, sqrt
from flask import Flask, request, jsonify
import joblib, numpy as np, librosa, soundfile as sf
from pydub import AudioSegment  # pip install pydub

# --- Try to load TensorFlow (optional, skip if not available) ---
try:
    from tensorflow.keras.models import load_model
    tf_available = True
except Exception as e:
    print("Using classic joblib model only.", e)
    tf_available = False

# --- Location Risk Agent ---
from agents.location_risk_agent import evaluate as evaluate_location_risk

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "events.db")

# --- Telegram config ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials missing; printing alert:\n", msg)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=6)
    except Exception as e:
        print("[ERR] Telegram send failed:", e)

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS locs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT, ts INTEGER, lat REAL, lon REAL, acc REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT, ts INTEGER, type TEXT,
        summary TEXT, reason TEXT, evidence TEXT
    )""")
    conn.commit(); conn.close()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dl / 2) ** 2
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

# -------------------------------------------------------------------
# Helper: Get last known location
# -------------------------------------------------------------------
def get_last_location(user: str):
    conn = db()
    row = conn.execute(
        "SELECT lat, lon FROM locs WHERE user=? ORDER BY ts DESC LIMIT 1", (user,)
    ).fetchone()
    conn.close()
    if row:
        return float(row[0]), float(row[1])
    return None, None

# -------------------------------------------------------------------
# Voice model loader
# -------------------------------------------------------------------
print("🔄 Loading voice models...", flush=True)
ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "voice_model", "artifacts")
CUSTOM_MODEL_PATH = os.path.join(ARTIFACT_DIR, "voice_clf.joblib")
CUSTOM_SCALER_PATH = os.path.join(ARTIFACT_DIR, "scaler_final_v3.joblib")
CUSTOM_FEAT_PATH = os.path.join(ARTIFACT_DIR, "feat_cfg.npy")
CREMA_MODEL_PATH = os.path.join(ARTIFACT_DIR, "voice_clf_final_v3.h5")
CREMA_SCALER_PATH = os.path.join(ARTIFACT_DIR, "scaler_final_v3.joblib")

voice_model_custom = None
voice_model_cremad = None
scaler_custom = None
scaler_cremad = None
n_mfcc, sr_target = 20, 16000

try:
    if os.path.exists(CUSTOM_MODEL_PATH):
        voice_model_custom = joblib.load(CUSTOM_MODEL_PATH)
        print(f"✅ Loaded CUSTOM voice model: {CUSTOM_MODEL_PATH}")
    if os.path.exists(CUSTOM_SCALER_PATH):
        scaler_custom = joblib.load(CUSTOM_SCALER_PATH)
        print(f"✅ Loaded CUSTOM scaler: {CUSTOM_SCALER_PATH}")
    if os.path.exists(CUSTOM_FEAT_PATH):
        n_mfcc, sr_target = [int(x) for x in np.load(CUSTOM_FEAT_PATH)]
except Exception as e:
    print("⚠️ Custom model load failed:", e)
    traceback.print_exc()

if tf_available and os.path.exists(CREMA_MODEL_PATH):
    try:
        voice_model_cremad = load_model(CREMA_MODEL_PATH)
        scaler_cremad = joblib.load(CREMA_SCALER_PATH)
        print(f"✅ Loaded CREMA-D backup model: {CREMA_MODEL_PATH}")
    except Exception as e:
        print("⚠️ Failed to load CREMA-D:", e)

if voice_model_custom is not None:
    active_model, active_scaler, active_flag = voice_model_custom, scaler_custom, "CUSTOM"
elif voice_model_cremad is not None:
    active_model, active_scaler, active_flag = voice_model_cremad, scaler_cremad, "CREMA-D"
else:
    active_model, active_scaler, active_flag = None, None, "NONE"

print(f"[VOICE] Active model: {active_flag}, n_mfcc={n_mfcc}, sr={sr_target}", flush=True)

# -------------------------------------------------------------------
# Voice utilities
# -------------------------------------------------------------------
def convert_to_wav_bytes(input_path):
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(sr_target).set_channels(1).set_sample_width(2)
    out_buf = io.BytesIO()
    audio.export(out_buf, format="wav")
    return out_buf.getvalue()

def _featurize_wav_bytes(wav_bytes):
    y, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    if sr != sr_target:
        y = librosa.resample(y, orig_sr=sr, target_sr=sr_target)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    target_len = sr_target * 4
    y = np.pad(y, (0, max(0, target_len - len(y))))[:target_len]
    mfcc = librosa.feature.mfcc(y=y, sr=sr_target, n_mfcc=n_mfcc)
    feats = np.hstack([mfcc.mean(1), mfcc.std(1), mfcc.min(1), mfcc.max(1)])
    return feats.reshape(1, -1)

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.post("/loc")
def loc():
    data = request.get_json(force=True)
    user = data.get("user", "user")
    lat, lon = float(data.get("lat", 0)), float(data.get("lon", 0))
    acc = float(data.get("acc", 0))
    ts = int(data.get("ts", time.time()))
    print(f"[LOC] {user} lat={lat} lon={lon} acc={acc} ts={ts}")

    conn = db()
    conn.execute("INSERT INTO locs(user, ts, lat, lon, acc) VALUES(?,?,?,?,?)",
                 (user, ts, lat, lon, acc))
    conn.commit(); conn.close()

    st = stationary_time_seconds(user)
    try:
        risk = evaluate_location_risk(user=user, lat=lat, lon=lon,
                                      stationary_seconds=st, ts=ts, voice_prob=None)
    except Exception as e:
        risk = {"action": "NONE", "reason": "agent_error", "evidence": str(e)}

    action = risk.get("action", "NONE")
    reason = risk.get("reason", "")
    evidence = risk.get("evidence", "")

    if action in ("AUTO_SOS", "NOTIFY"):
        conn = db()
        summary = f"{action} (location) for {user} at {lat},{lon} — reason={reason}"
        conn.execute("INSERT INTO alerts(user, ts, type, summary, reason, evidence) VALUES(?,?,?,?,?,?)",
                     (user, ts, action, summary, reason, evidence))
        conn.commit(); conn.close()

        if action == "AUTO_SOS":
            send_telegram(f"🚨 AUTO-SOS triggered by location for {user}\n{summary}\n"
                          f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}")
        elif action == "NOTIFY":
            send_telegram(f"ℹ️ Location notify for {user}\n{summary}")

    return jsonify({"ok": True, "risk_action": action, "reason": reason, "evidence": evidence})

@app.post("/voice_score")
def voice_score():
    global active_model, active_scaler, active_flag
    if active_model is None:
        return jsonify({"ok": False, "msg": "Voice model not loaded"}), 503
    if "audio" not in request.files:
        return jsonify({"ok": False, "msg": "Send form-data with key 'audio'"}), 400

    user = request.form.get("user", "user")
    lat, lon = request.form.get("lat"), request.form.get("lon")

    try:
        f = request.files["audio"]
        suffix = os.path.splitext(f.filename or "upload")[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(f.read()); tmp.flush(); tmp_path = tmp.name
        try:
            wav_bytes = convert_to_wav_bytes(tmp_path)
        except Exception as e:
            app.logger.error("Conversion failed: %s", e)
            with open(tmp_path, "rb") as fh: wav_bytes = fh.read()
        os.unlink(tmp_path)

        feats = _featurize_wav_bytes(wav_bytes)
        prob = float(active_model.predict_proba(feats)[0, 1]) if active_flag == "CUSTOM" \
            else float(active_model.predict(active_scaler.transform(feats), verbose=0)[0][0])
        label = "distress" if prob >= 0.6 else "normal"

        ts = int(time.time())
        conn = db()
        conn.execute("INSERT INTO alerts(user, ts, type, summary) VALUES(?,?,?,?)",
                     (user, ts, "VOICE", f"Voice inference: {label} (p={prob:.2f})"))
        conn.commit(); conn.close()

        if label == "distress":
            latf, lonf = None, None
            try:
                if lat and lon:
                    latf, lonf = float(lat), float(lon)
                else:
                    latf, lonf = get_last_location(user)
            except:
                pass
            osm = f"\nhttps://www.openstreetmap.org/?mlat={latf}&mlon={lonf}#map=18/{latf}/{lonf}" if latf and lonf else ""
            send_telegram(f"🗣️ Voice distress detected for {user} (p={prob:.2f}){osm}")

            if prob >= 0.75:
                ts2 = int(time.time())
                summary2 = f"AUTO-SOS (voice) for {user} at {latf},{lonf} (p={prob:.2f})"
                conn = db()
                conn.execute("INSERT INTO alerts(user, ts, type, summary, reason, evidence) VALUES(?,?,?,?,?,?)",
                             (user, ts2, "SOS", summary2, "voice_confident", f"p={prob:.2f}"))
                conn.commit(); conn.close()
                send_telegram(f"🚨 {summary2}{osm}")

        return jsonify({"ok": True, "distress_prob": prob, "distress_label": label})

    except Exception as e:
        app.logger.exception("Error in /voice_score")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.post("/sos")
def manual_sos():
    data = request.get_json(force=True, silent=True) or {}
    user = data.get("user", "user")
    coords = data.get("coords") or {}
    lat = coords.get("latitude") if isinstance(coords, dict) else None
    lon = coords.get("longitude") if isinstance(coords, dict) else None

    if not lat or not lon:
        lat, lon = get_last_location(user)

    ts = int(time.time())
    summary = f"🚨 Manual SOS from {user} at {lat},{lon}" if lat and lon else f"🚨 Manual SOS from {user} (no location)"
    print(f"[MANUAL SOS] {summary}")

    conn = db()
    conn.execute("INSERT INTO alerts(user, ts, type, summary, reason, evidence) VALUES(?,?,?,?,?,?)",
                 (user, ts, "SOS", summary, "manual_trigger", f"lat={lat},lon={lon}"))
    conn.commit(); conn.close()

    osm = f"\nhttps://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}" if lat and lon else ""
    send_telegram(f"{summary}{osm}")
    return jsonify({"ok": True, "msg": "SOS sent", "lat": lat, "lon": lon})

@app.get("/alert_test")
def alert_test():
    send_telegram("✅ Test alert from SHE-Guardian backend is working!")
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("🚀 Running server.py from:", os.path.abspath(__file__), flush=True)
    init_db()
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods}  {rule}", flush=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
