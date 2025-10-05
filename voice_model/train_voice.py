import os, numpy as np
from glob import glob
import librosa, joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "dataset")
OUT_DIR  = os.path.join(BASE_DIR, "artifacts")
os.makedirs(OUT_DIR, exist_ok=True)

LABELS = {"normal":0, "distress":1}

def featurize(path, sr_target=16000, n_mfcc=20):
    y, sr = librosa.load(path, sr=sr_target, mono=True)
    # pad/trim to 4 seconds for consistent features
    target_len = sr * 4
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]
    # MFCCs + simple stats (mean/std/min/max)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    feats = np.hstack([mfcc.mean(axis=1), mfcc.std(axis=1), mfcc.min(axis=1), mfcc.max(axis=1)])
    return feats

X, y = [], []
for cls, lab in LABELS.items():
    files = glob(os.path.join(DATA_DIR, cls, "*.wav"))
    for f in files:
        X.append(featurize(f))
        y.append(lab)

X = np.asarray(X, dtype=np.float32)
y = np.asarray(y, dtype=np.int64)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

model = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=300))
])
model.fit(X_train, y_train)

y_pred  = model.predict(X_test)
print("\nConfusion matrix:\n", confusion_matrix(y_test, y_pred))
print("\nReport:\n", classification_report(y_test, y_pred, target_names=["normal","distress"]))

# Save artifacts
joblib.dump(model, os.path.join(OUT_DIR, "voice_clf.joblib"))
np.save(os.path.join(OUT_DIR, "feat_cfg.npy"), np.array([20, 16000], dtype=np.int32))
print("\n✅ Saved: voice_model/artifacts/voice_clf.joblib (and feat_cfg.npy)")
