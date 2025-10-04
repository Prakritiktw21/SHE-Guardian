# SHE-Guardian Backend

Run locally:
```
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
set TELEGRAM_TOKEN=your_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here
python server.py
```
Endpoints:
- `POST /loc`  -> {user, lat, lon, acc, ts}
- `POST /sos`  -> {user, coords:{latitude, longitude}}
- `POST /voice_score` -> multipart (placeholder until model integrated)
