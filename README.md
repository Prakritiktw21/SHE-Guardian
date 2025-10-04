# SHE-Guardian
**Safety with Human-like Empowerment — Agentic AI + Voice ML + Mobile App**

### What you get in v0
- 📱 Expo mobile app (GPS + SOS)
- 🧠 Flask backend (location logging + SOS + simple stationary rule + Telegram alerts)
- 🎙️ Voice ML placeholder endpoint (wire model later)

## Quick start

### Backend
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set TELEGRAM_TOKEN=your_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here
python server.py
```

### Mobile
```
cd mobile
npm install
npx expo start
```
Update `App.js` BACKEND URL to `http://YOUR_LAPTOP_IP:5000`.

### Notes
- Phone and laptop must be on the same Wi‑Fi.
- Telegram setup: create a bot with @BotFather, get token; send a message to the bot, then find your chat id via `getUpdates`.
