import os
import glob
import csv
import argparse
import requests
import statistics as stats

def parse_args():
    p = argparse.ArgumentParser(
        description="Batch-test all WAV files against /voice_score and report metrics."
    )
    p.add_argument("--base", default=r"voice_model\dataset",
                   help="Dataset root folder containing 'normal' and 'distress' subfolders")
    p.add_argument("--url", default="http://127.0.0.1:5000/voice_score",
                   help="Flask endpoint (e.g., http://127.0.0.1:5000/voice_score or http://<LAN-IP>:5000/voice_score)")
    p.add_argument("--user", default="prakriti", help="User name to send with each request")
    p.add_argument("--lat", default="23.64748", help="Latitude to send")
    p.add_argument("--lon", default="88.12385", help="Longitude to send")
    p.add_argument("--threshold", type=float, default=0.60,
                   help="Decision threshold for distress label (prob >= threshold => distress)")
    p.add_argument("--csv", default="", help="Optional path to save per-file results as CSV")
    return p.parse_args()

def send_one(url, user, lat, lon, path):
    with open(path, "rb") as f:
        r = requests.post(
            url,
            files={"audio": ("sample.wav", f, "audio/wav")},
            data={"user": user, "lat": lat, "lon": lon}
        )
    try:
        j = r.json()
    except Exception:
        j = {"ok": False, "raw": r.text}
    return r.status_code, j

def main():
    args = parse_args()
    BASE = args.base
    URL  = args.url
    USER = args.user
    LAT  = args.lat
    LON  = args.lon
    THR  = args.threshold

    CLASSES = [("normal", 0), ("distress", 1)]  # (folder_name, true_label)

    results = []  # (fname, true_lab, pred_lab, prob, ok)
    print(f"🧪 Testing all files via {URL}")
    print(f"   base={BASE}  user={USER}  lat={LAT}  lon={LON}  threshold={THR:.2f}\n")

    for cname, true_lab in CLASSES:
        files = sorted(glob.glob(os.path.join(BASE, cname, "*.wav")))
        print(f"[{cname.upper()}] {len(files)} files")
        for p in files:
            code, j = send_one(URL, USER, LAT, LON, p)
            fname = os.path.basename(p)
            if code != 200 or not j.get("ok"):
                print(f"  - {fname:30s} -> ERROR: {j}")
                results.append((fname, true_lab, None, None, False))
                continue

            prob = float(j.get("distress_prob", 0.0))
            pred_lab = 1 if prob >= THR else 0
            label = "distress" if pred_lab == 1 else "normal"
            correct = (pred_lab == true_lab)
            print(f"  - {fname:30s} -> label={label:8s}  p={prob:0.3f}  {'✅' if correct else '❌'}")
            results.append((fname, true_lab, pred_lab, prob, True))

    # --- Summary metrics ---
    valid = [r for r in results if r[4]]
    if not valid:
        print("\nNo valid results collected.")
        return

    tp = sum(1 for _, t, p, _, _ in valid if t==1 and p==1)
    tn = sum(1 for _, t, p, _, _ in valid if t==0 and p==0)
    fp = sum(1 for _, t, p, _, _ in valid if t==0 and p==1)
    fn = sum(1 for _, t, p, _, _ in valid if t==1 and p==0)

    total = len(valid)
    acc = (tp+tn)/total if total else 0.0
    prec = tp/(tp+fp) if (tp+fp)>0 else 0.0
    rec  = tp/(tp+fn) if (tp+fn)>0 else 0.0
    f1   = 2*prec*rec/(prec+rec) if (prec+rec)>0 else 0.0

    # Per-class accuracy
    normals   = [r for r in valid if r[1]==0]
    distresses= [r for r in valid if r[1]==1]
    acc_norm  = sum(1 for r in normals if r[2]==0) / len(normals) if normals else 0.0
    acc_dist  = sum(1 for r in distresses if r[2]==1) / len(distresses) if distresses else 0.0

    distress_probs = [prob for (_, t, _, prob, _) in valid if t==1]
    normal_probs   = [prob for (_, t, _, prob, _) in valid if t==0]

    print("\n===== SUMMARY =====")
    print(f"Samples: {total}   (threshold={THR:.2f})")
    print(f"Confusion Matrix  (pred rows x true cols)")
    print(f"               true 0    true 1")
    print(f"pred 0 (normal)  {tn:5d}     {fn:5d}")
    print(f"pred 1 (dist)    {fp:5d}     {tp:5d}")
    print(f"\nOverall Accuracy : {acc:0.3f}")
    print(f"Precision (dist) : {prec:0.3f}")
    print(f"Recall    (dist) : {rec:0.3f}")
    print(f"F1-score  (dist) : {f1:0.3f}")
    print(f"Class Acc normal : {acc_norm:0.3f}")
    print(f"Class Acc distress: {acc_dist:0.3f}")
    if distress_probs:
        print(f"\nDistress probs: mean={stats.mean(distress_probs):0.3f}  min={min(distress_probs):0.3f}  max={max(distress_probs):0.3f}")
    if normal_probs:
        print(f"Normal probs  : mean={stats.mean(normal_probs):0.3f}  min={min(normal_probs):0.3f}  max={max(normal_probs):0.3f}")

    # Optional CSV export
    if args.csv:
        out = args.csv
        os.makedirs(os.path.dirname(out), exist_ok=True) if os.path.dirname(out) else None
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "true_label", "pred_label", "distress_prob", "ok"])
            for row in results:
                w.writerow(row)
        print(f"\n📝 Saved per-file results to {out}")

if __name__ == "__main__":
    main()
