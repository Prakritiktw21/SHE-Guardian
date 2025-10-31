import React, { useRef, useState, useEffect } from "react";
import { View, Text, Button, Alert, Platform } from "react-native";
import * as Location from "expo-location";
import { Audio } from "expo-av";
import VoiceRecorder from "../../components/VoiceRecorder";

const BACKEND = "http://10.20.69.174:5000"; // ✅ Flask backend IP

type Coords = { latitude: number; longitude: number; accuracy?: number };

export default function Home() {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [tracking, setTracking] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [lastCoords, setLastCoords] = useState<Coords | null>(null);
  const [lastMoveTime, setLastMoveTime] = useState<number>(Date.now());
  const watchRef = useRef<Location.LocationSubscription | null>(null);

  // ---------------------------
  // Start location tracking
  // ---------------------------
  async function startTracking() {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      Alert.alert("Permission denied", "Location permission is required.");
      return;
    }

    const sub = await Location.watchPositionAsync(
      { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 2 },
      async (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        setCoords({ latitude, longitude, accuracy });

        // --- Detect movement
        if (lastCoords) {
          const dist =
            Math.sqrt(
              Math.pow(latitude - lastCoords.latitude, 2) +
                Math.pow(longitude - lastCoords.longitude, 2)
            ) * 111139; // degrees to meters
          if (dist > 10) {
            setLastMoveTime(Date.now()); // moved more than 10 meters
          }
        }
        setLastCoords({ latitude, longitude });

        // --- Send location to backend
        try {
          const res = await fetch(`${BACKEND}/loc`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user: "prakriti",
              lat: latitude,
              lon: longitude,
              acc: accuracy,
              ts: Math.floor(Date.now() / 1000),
            }),
          });
          const text = await res.text();
          console.log("Location response:", res.status, text);
          setMessage(`📡 loc sent: ${res.status}`);
        } catch (e: any) {
          console.log("❌ Failed to send location:", e?.message || e);
          setMessage(`❌ loc error: ${e?.message || e}`);
        }
      }
    );

    watchRef.current = sub;
    setTracking(true);
  }

  function stopTracking() {
    if (watchRef.current) {
      watchRef.current.remove();
      watchRef.current = null;
    }
    setTracking(false);
    setMessage("🛑 Tracking stopped");
  }

  // ---------------------------
  // Manual SOS trigger
  // ---------------------------
  async function sendSOS(customCoords?: Coords | null) {
    try {
      const payload = { user: "prakriti", coords: customCoords ?? coords };
      const res = await fetch(`${BACKEND}/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      console.log("SOS response:", res.status, text);
      setMessage(`🚨 sos sent: ${res.status}`);
      Alert.alert("🚨 SOS sent!", "Your contacts have been notified.");
    } catch (e: any) {
      console.log("❌ SOS error:", e?.message || e);
      setMessage(`❌ sos error: ${e?.message || e}`);
      Alert.alert("Failed", "Could not send SOS.");
    }
  }

  // ---------------------------
  // 🧠 Auto “Are you okay?” Logic (No movement 2 mins)
useEffect(() => {
  let sosCancelled = false; // ✅ flag to cancel SOS if user responds

  const interval = setInterval(() => {
    const idleTime = (Date.now() - lastMoveTime) / 1000; // seconds since last move
    if (idleTime > 120) {
      clearInterval(interval);
      console.log("⚠️ No movement for 2 mins — asking user...");

      Alert.alert(
        "⚠️ Are you okay?",
        "No movement detected for 2 minutes.",
        [
          {
            text: "I'm fine",
            style: "cancel",
            onPress: () => {
              sosCancelled = true; // ✅ prevent SOS
              setLastMoveTime(Date.now());
              console.log("✅ User confirmed they're fine.");
            },
          },
        ]
      );

      // Auto SOS after 5 seconds if no response
      setTimeout(async () => {
        if (!sosCancelled) {
          console.log("🚨 No response — sending Auto SOS...");
          await sendSOS(coords);
          Alert.alert("🚨 Auto SOS Sent", "No response detected.");
        } else {
          console.log("🛑 SOS cancelled by user response.");
        }
      }, 5000);
    }
  }, 10000); // check every 10s

  return () => clearInterval(interval);
}, [lastMoveTime, coords]);

  // ---------------------------
  // Voice Recorder (inline)
  // ---------------------------
  const VoiceRecorder: React.FC = () => {
    const [recording, setRecording] = useState<Audio.Recording | null>(null);
    const [vstatus, setVStatus] = useState<string>("Idle");

    async function startRecord() {
      try {
        const perm = await Audio.requestPermissionsAsync();
        if (!perm.granted) {
          Alert.alert("Permission required", "Microphone permission is required.");
          return;
        }

        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });

        const rec = new Audio.Recording();
        await rec.prepareToRecordAsync(Audio.RECORDING_OPTIONS_PRESET_HIGH_QUALITY);
        await rec.startAsync();
        setRecording(rec);
        setVStatus("🎙️ Recording... Tap again to stop");
      } catch (e) {
        console.log("Record start error:", e);
        setVStatus("Record start failed");
      }
    }

    async function stopRecord(currentRec?: Audio.Recording) {
      try {
        const rec = currentRec ?? recording;
        if (!rec) return;
        await rec.stopAndUnloadAsync();
        const uri = rec.getURI();
        setRecording(null);

        if (!uri) {
          setVStatus("No audio captured");
          return;
        }

        setVStatus("Uploading...");
        const formData = new FormData();
        formData.append("audio", {
          uri,
          name: "sample.wav",
          type: "audio/wav",
        } as any);
        formData.append("user", "prakriti");
        if (coords) {
          formData.append("lat", String(coords.latitude));
          formData.append("lon", String(coords.longitude));
        }

        const res = await fetch(`${BACKEND}/voice_score`, {
          method: "POST",
          body: formData,
        });

        const j = await res.json();
        if (!res.ok || !j.ok) {
          setVStatus(`Server error: ${j?.msg ?? res.status}`);
          return;
        }

        const prob: number = Number(j.distress_prob ?? 0);
        const label: string = j.distress_label ?? "normal";
        setVStatus(`Result: ${label} (p=${prob.toFixed(2)})`);

        if (prob >= 0.8) {
          setMessage(`🚨 Auto-SOS: voice p=${prob.toFixed(2)}`);
          await sendSOS(coords);
        } else if (label === "distress") {
          Alert.alert("Distress detected", `Probability: ${prob.toFixed(2)}`);
        }
      } catch (e) {
        console.log("Upload / predict error:", e);
        setVStatus("Upload/predict failed");
      }
    }

    return (
      <View style={{ marginTop: 20 }}>
        <Button
          title={recording ? "⏹️ Stop Recording" : "🎙️ Record & Analyze Voice"}
          onPress={recording ? () => stopRecord() : startRecord}
          color={recording ? "red" : undefined}
        />
        <Text style={{ marginTop: 8 }}>{vstatus}</Text>
      </View>
    );
  };

  // ---------------------------
  // Render
  // ---------------------------
  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 22, fontWeight: "bold", marginBottom: 20 }}>🛡️ SHE-Guardian</Text>
      <Text>📍 Latitude: {coords?.latitude?.toFixed(6) ?? "-"}</Text>
      <Text>📍 Longitude: {coords?.longitude?.toFixed(6) ?? "-"}</Text>
      <Text>📏 Accuracy: {coords?.accuracy ? Math.round(coords.accuracy) + " m" : "-"}</Text>

      <Text style={{ color: "blue", marginVertical: 10 }}>{message}</Text>

      {!tracking ? (
        <Button title="Start Tracking" onPress={startTracking} />
      ) : (
        <Button title="Stop Tracking" onPress={stopTracking} />
      )}

      <View style={{ height: 16 }} />
      <Button title="🚨 Send SOS" color="red" onPress={() => sendSOS()} />

      {/* Voice recorder */}
      <VoiceRecorder />
    </View>
  );
}
