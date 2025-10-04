import React, { useRef, useState } from "react";
import { View, Text, Button, Alert } from "react-native";
import * as Location from "expo-location";

const BACKEND = "http://192.168.29.143:5000"; // ✅ Your Flask IP

type Coords = { latitude: number; longitude: number; accuracy?: number };

export default function Home() {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [tracking, setTracking] = useState(false);
  const [message, setMessage] = useState<string>(""); // on-screen debug
  const watchRef = useRef<Location.LocationSubscription | null>(null);

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

  async function sendSOS() {
    try {
      const res = await fetch(`${BACKEND}/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: "prakriti", coords }),
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

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 22, fontWeight: "bold", marginBottom: 20 }}>🛡️ SHE-Guardian</Text>
      <Text>📍 Latitude: {coords?.latitude?.toFixed(6) ?? "-"}</Text>
      <Text>📍 Longitude: {coords?.longitude?.toFixed(6) ?? "-"}</Text>
      <Text>📏 Accuracy: {coords?.accuracy ? Math.round(coords.accuracy) + " m" : "-"}</Text>

      {/* single, visible debug line */}
      <Text style={{ color: "blue", marginVertical: 10 }}>
        {message}
      </Text>

      {!tracking ? (
        <Button title="Start Tracking" onPress={startTracking} />
      ) : (
        <Button title="Stop Tracking" onPress={stopTracking} />
      )}

      <View style={{ height: 16 }} />
      <Button title="🚨 Send SOS" color="red" onPress={sendSOS} />
    </View>
  );
}
