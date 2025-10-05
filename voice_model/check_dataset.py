import os
import librosa
from glob import glob

# Base directory of your dataset
BASE = os.path.join(os.path.dirname(__file__), "dataset")
CLASSES = ["normal", "distress"]

def analyze_audio(path):
    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        duration = round(len(y) / sr, 2)
        return os.path.basename(path), sr, duration
    except Exception as e:
        return os.path.basename(path), None, f"ERROR: {e}"

if __name__ == "__main__":
    print("🎧 Checking dataset quality...\n")
    for cls in CLASSES:
        files = sorted(glob(os.path.join(BASE, cls, "*.wav")))
        print(f"[{cls.upper()}] Total: {len(files)} files")
        for f in files:
            name, sr, dur = analyze_audio(f)
            print(f"  - {name:30s}  SR={sr}  Duration={dur}s")
