# 🛡️ SHE-Guardian  
**Safety with Human-like Empowerment — Agentic AI + Voice ML + Mobile App**

SHE-Guardian is an **AI-powered safety system** that combines *voice emotion recognition*, *location intelligence*, and *Telegram-based SOS alerts* to assist users in distress situations.  
The system detects distress through speech, monitors user movement, and automatically alerts emergency contacts if risk is detected.

---

## 🚀 Features

### 🎙️ Voice Intelligence
- Real-time voice distress detection using **custom-trained ML model** (`voice_clf.joblib`)
- Automatic SOS trigger when distress probability ≥ 0.75
- Fallback to secondary (CREMA-D) model if TensorFlow is available
- Audio preprocessing with **librosa** (MFCC extraction)  

### 📍 Location Safety Agent
- Tracks user GPS coordinates via Expo mobile app  
- Detects stationary or isolated users at night  
- Triggers auto-SOS if the user remains stationary and is in a low-POI area  
- Location risk evaluated using **Overpass API (OpenStreetMap)**  

### 📲 Mobile App (Expo)
- Built with **React Native + Expo**  
- Records and analyzes voice in real-time  
- Sends periodic GPS updates to backend  
- Allows manual SOS trigger button  
- Works seamlessly over local Wi-Fi  

### 🧠 Flask Backend
- REST endpoints for `/voice_score`, `/loc`, `/sos`, and `/alerts`
- Integrates with Telegram for instant alerting  
- SQLite database to store user events and alerts  
- Auto-switches between models based on prediction confidence  

### 🔔 Telegram Alerts
- Sends two types of notifications:  
  - **🗣️ Distress detected** (voice-based alert)  
  - **🚨 AUTO-SOS triggered** (voice or location)  
- Includes direct map link for quick response  

---

## ⚙️ Architecture Overview

📱 Expo App (React Native)
├── VoiceRecorder.tsx → /voice_score
├── index.tsx → /loc + /sos
│
🌐 Flask Backend
├── server.py
│ ├── Voice Analysis (MFCC + ML)
│ ├── Auto-SOS logic
│ ├── Telegram integration
│ └── SQLite logging
│
🤖 Agents
└── location_risk_agent.py → Evaluates risk using POI density + stationary behavior


---

## 🧩 Installation Guide

### 1️⃣ Backend Setup

cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set TELEGRAM_TOKEN=your_bot_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here
python server.py

### 1️⃣ Mobile Setup

cd mobile
npm install
npx expo start

