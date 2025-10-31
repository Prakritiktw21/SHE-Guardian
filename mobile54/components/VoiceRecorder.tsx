// components/VoiceRecorder.tsx
import React, { useState } from "react";
import { View, Button, Text, Alert, Platform } from "react-native";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import * as Location from "expo-location";

const BACKEND = "http://10.20.69.174:5000"; // ✅ replace with your Flask IP if needed

// --- Utility: Extract file extension ---
function extensionFromUri(uri?: string) {
  if (!uri) return "wav";
  const clean = uri.split("?")[0];
  const parts = clean.split(".");
  return parts.pop()?.toLowerCase() || "wav";
}

// --- Utility: Infer MIME type ---
function mimeTypeForExt(ext: string) {
  switch (ext) {
    case "m4a":
    case "aac":
      return "audio/mp4";
    case "caf":
      return "audio/x-caf";
    case "wav":
      return "audio/wav";
    case "mp3":
      return "audio/mpeg";
    case "ogg":
    case "oga":
      return "audio/ogg";
    case "flac":
      return "audio/flac";
    default:
      return "application/octet-stream";
  }
}

export default function VoiceRecorder() {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [status, setStatus] = useState<string>("Idle");

  // --- Start recording manually ---
  async function startRecord() {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        Alert.alert("Permission required", "Please allow microphone access");
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
      setStatus("🎙️ Recording... Tap again to stop");

    } catch (e) {
      console.log("Record error:", e);
      setStatus("Error starting recording");
    }
  }

  // --- Stop and analyze recording ---
  async function stopRecord() {
    try {
      if (!recording) return;
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);

      if (!uri) {
        setStatus("No audio file");
        return;
      }

      setStatus("Uploading...");

      // --- Get location (optional) ---
      let latitude: number | null = null;
      let longitude: number | null = null;
      try {
        const locPerm = await Location.requestForegroundPermissionsAsync();
        if (locPerm.granted) {
          const loc = await Location.getCurrentPositionAsync({});
          latitude = loc.coords.latitude;
          longitude = loc.coords.longitude;
        }
      } catch (e) {
        console.log("⚠️ Could not get location:", e);
      }

      // --- Handle Android content:// URI ---
      let uploadUri = uri;
      if (Platform.OS === "android" && uri.startsWith("content://")) {
        try {
          const ext = extensionFromUri(uri);
          const dest = `${FileSystem.cacheDirectory}recording.${ext}`;
          await FileSystem.copyAsync({ from: uri, to: dest });
          uploadUri = dest;
        } catch (e) {
          console.log("Failed to copy content URI to cache:", e);
        }
      }

      const ext = extensionFromUri(uploadUri);
      const mimeType = mimeTypeForExt(ext);
      const filename = `recording.${ext}`;

      // --- Upload to backend ---
      const formData = new FormData();
      formData.append("audio", {
        uri: uploadUri,
        name: filename,
        type: mimeType,
      } as any);
      formData.append("user", "prakriti");
      if (latitude && longitude) {
        formData.append("lat", String(latitude));
        formData.append("lon", String(longitude));
      }

      const res = await fetch(`${BACKEND}/voice_score`, {
        method: "POST",
        body: formData,
      });

      let j: any = null;
      try {
        j = await res.json();
      } catch (err) {
        const txt = await res.text().catch(() => "<no body>");
        throw new Error(`Server returned ${res.status}: ${txt}`);
      }

      if (j.ok) {
        const prob = j.distress_prob;
        setStatus(`✅ ${j.distress_label} (p=${prob.toFixed(2)})`);

        if (j.distress_label === "distress") {
          Alert.alert("🚨 Distress Detected", `Probability: ${prob.toFixed(2)}`);

          // Auto-SOS if distress_prob >= 0.8
          if (prob >= 0.8) {
            setStatus(`🚨 Auto-SOS triggered (p=${prob.toFixed(2)})`);
            await sendSOS(latitude, longitude);
          }
        }
      } else {
        setStatus(`Error: ${j.msg || JSON.stringify(j)}`);
      }
    } catch (e) {
      console.log("Upload error:", e);
      setStatus("Upload failed");
      Alert.alert("Upload failed", String(e));
    }
  }

  // --- SOS trigger ---
  async function sendSOS(lat?: number | null, lon?: number | null) {
    try {
      const coords = lat && lon ? { latitude: lat, longitude: lon } : null;
      const res = await fetch(`${BACKEND}/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: "prakriti", coords }),
      });
      const text = await res.text();
      console.log("Auto SOS response:", res.status, text);
      Alert.alert("🚨 Auto SOS Sent!", "Your distress has been reported.");
    } catch (e) {
      console.log("❌ Auto SOS error:", e);
      Alert.alert("Auto SOS failed", String(e));
    }
  }

  return (
    <View style={{ marginTop: 20 }}>
      <Button
        title={recording ? "⏹️ Stop Recording" : "🎙️ Record & Analyze Voice"}
        onPress={recording ? stopRecord : startRecord}
        color={recording ? "red" : undefined}
      />
      <Text style={{ marginTop: 10 }}>{status}</Text>
    </View>
  );
}
