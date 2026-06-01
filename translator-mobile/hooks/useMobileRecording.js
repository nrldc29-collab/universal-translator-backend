import { Audio } from "expo-av";
import { playTtsAudio } from "../services/audio-stream";

export function useMobileRecording({
  isConnected,
  sourceLanguage,
  targetLanguage,
  wsUrl,
  token,
  recording,
  setRecording,
  setStatus,
  setStatusType,
  setResult,
  isPlayingTtsRef,
  setIsPlayingTts,
}) {
  async function startRecording() {
    if (!isConnected) {
      setStatus("Connect to backend first");
      setStatusType("error");
      return;
    }
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        setStatus("Microphone permission denied");
        setStatusType("error");
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
      });
      const recordingOptions = Audio.RecordingOptionsPresets.HIGH_QUALITY;
      const { recording: newRecording } = await Audio.Recording.createAsync(recordingOptions);
      setRecording(newRecording);
      setStatus("Recording...");
      setStatusType("connecting");
    } catch (error) {
      setStatus("Could not start microphone: " + error.message);
      setStatusType("error");
    }
  }

  async function stopRecording() {
    if (!recording) return;
    try {
      setStatus("Uploading audio...");
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (!uri) {
        setStatus("No recording captured");
        setStatusType("warning");
        return;
      }
      await uploadAudio(uri);
    } catch (error) {
      setRecording(null);
      setStatus("Recording failed: " + error.message);
      setStatusType("error");
    }
  }

  async function uploadAudio(uri) {
    const form = new FormData();
    form.append("audio", { uri, name: "recording.m4a", type: "audio/m4a" });
    form.append("source_language", sourceLanguage);
    form.append("target_language", targetLanguage);
    form.append("synthesize_audio", "true");
    try {
      const response = await fetch(`${wsUrl}/translate/audio`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "multipart/form-data" },
        body: form,
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || "Translation failed");
        setStatusType("error");
        return;
      }
      setResult(data);
      setStatus("Audio translated");
      setStatusType("success");
      if (data.audio_base64) {
        try {
          isPlayingTtsRef.current = true;
          setIsPlayingTts(true);
          const ok = await playTtsAudio(data.audio_base64, data.mime_type || "audio/wav");
          if (!ok) {
            setStatus("TTS playback failed");
            setStatusType("error");
          }
        } finally {
          isPlayingTtsRef.current = false;
          setIsPlayingTts(false);
        }
      }
    } catch (error) {
      setStatus("Upload failed: " + error.message);
      setStatusType("error");
    }
  }

  return { startRecording, stopRecording, uploadAudio };
}
