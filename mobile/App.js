import React, { useState, useRef } from "react";
import { View, Text, Button, Alert } from "react-native";
import * as Location from "expo-location";

const BACKEND = "http://YOUR_LAPTOP_IP:5000"; // TODO: replace with your IP

export default function App() {
  const [coords, setCoords] = useState(null);
  const [tracking, setTracking] = useState(false);
  const watchRef = useRef(null);

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
          await fetch(`${BACKEND}/loc`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user: "prakriti",
              lat: latitude,
              lon: longitude,
              acc: accuracy,
              ts: Math.floor(Date.now()/1000),
            }),
          });
        } catch (e) {}
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
  }

  async function sendSOS() {
    try {
      await fetch(`${BACKEND}/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: "prakriti", coords }),
      });
      Alert.alert("SOS sent", "Contacts have been notified.");
    } catch (e) {
      Alert.alert("Failed", "Could not send SOS.");
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 20, fontWeight: "600" }}>SHE-Guardian</Text>
      <Text>Lat: {coords?.latitude?.toFixed(6) ?? "-"}</Text>
      <Text>Lon: {coords?.longitude?.toFixed(6) ?? "-"}</Text>
      <Text>Acc: {coords?.accuracy ? Math.round(coords.accuracy) + " m" : "-"}</Text>
      {!tracking ? (
        <Button title="Start Tracking" onPress={startTracking} />
      ) : (
        <Button title="Stop Tracking" onPress={stopTracking} />
      )}
      <View style={{ height: 8 }} />
      <Button title="SOS" color="red" onPress={sendSOS} />
    </View>
  );
}
