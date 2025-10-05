# test_voice_post.py
import requests
URL = "http://127.0.0.1:5000/voice_score"   # or http://192.168.29.143:5000
WAV = r"voice_model\dataset\distress\distress_03.wav"


with open(WAV, "rb") as f:
    r = requests.post(
        URL,
        files={"audio": ("sample.wav", f, "audio/wav")},
        data={"user":"prakriti","lat":"23.64748","lon":"88.12385"}
    )
print(r.status_code, r.text)
