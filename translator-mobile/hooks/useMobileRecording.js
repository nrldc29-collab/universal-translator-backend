import { useState, useRef, useEffect } from "react";
import { Audio } from "expo-av";
import { playTtsAudio } from "../services/audio-stream";
import * as SecureStore from "expo-secure-store";

const AUDIO_QUALITY_KEY = "audio_quality";
const MAX_RETRIES = 3;
const UPLOAD_TIMEOUT = 30000;

const AUDIO_QUALITIES = {
  LOW: {
    preset: Audio.RecordingOptionsPresets.LOW_QUALITY,
    label: "Low Quality",
    description: "Smaller files, faster upload",
  },
  MEDIUM: {
    preset: Audio.RecordingOptionsPresets.MEDIUM_QUALITY,
    label: "Medium Quality",
    description: "Balanced quality and size",
  },
  HIGH: {
    preset: Audio.RecordingOptionsPresets.HIGH_QUALITY,
    label: "High Quality",
    description: "Best quality, larger files",
  },
};

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
  const [audioQuality, setAudioQuality] = useState("HIGH");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const retryCountRef = useRef(0);

  useEffect(() => {
    loadAudioQuality();
  }, []);

  async function loadAudioQuality() {
    try {
      const storedQuality = await SecureStore.getItemAsync(AUDIO_QUALITY_KEY);
      if (storedQuality && AUDIO_QUALITIES[storedQuality]) {
        setAudioQuality(storedQuality);
      }
    } catch (error) {
      console.error("Error loading audio quality setting:", error);
    }
  }

  async function saveAudioQuality(quality) {
    try {
      await SecureStore.setItemAsync(AUDIO_QUALITY_KEY, quality);
    } catch (error) {
      console.error("Error saving audio quality setting:", error);
    }
  }

  async function updateAudioQuality(quality) {
    if (AUDIO_QUALITIES[quality]) {
      setAudioQuality(quality);
      await saveAudioQuality(quality);
    }
  }

  async function startRecording() {
    if (!isConnected) {
      setStatus("Connect to backend first");
      setStatusType("error");
      return;
    }
    if (isUploading) {
      setStatus("Upload in progress, please wait");
      setStatusType("warning");
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
      const recordingOptions = AUDIO_QUALITIES[audioQuality].preset;
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
      setStatus("Processing audio...");
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
    setIsUploading(true);
    setUploadProgress(0);
    retryCountRef.current = 0;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        setStatus(`Uploading audio... (${attempt + 1}/${MAX_RETRIES})`);
        setStatusType("connecting");

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT);

        const form = new FormData();
        form.append("audio", { uri, name: "recording.m4a", type: "audio/m4a" });
        form.append("source_language", sourceLanguage);
        form.append("target_language", targetLanguage);
        form.append("synthesize_audio", "true");

        const response = await fetch(`${wsUrl}/translate/audio`, {
          method: "POST",
          headers: { 
            Authorization: `Bearer ${token}`, 
            "Content-Type": "multipart/form-data",
          },
          body: form,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`);
        }

        setResult(data);
        setStatus("Audio translated");
        setStatusType("success");
        setUploadProgress(100);

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
        
        setIsUploading(false);
        return;
      } catch (error) {
        console.error(`Upload attempt ${attempt + 1} failed:`, error);
        
        if (attempt === MAX_RETRIES - 1) {
          setStatus(`Upload failed after ${MAX_RETRIES} attempts: ${error.message}`);
          setStatusType("error");
          setIsUploading(false);
          setUploadProgress(0);
        } else {
          const delay = Math.pow(2, attempt) * 1000;
          setStatus(`Retrying in ${delay / 1000}s...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
  }

  function cancelUpload() {
    setIsUploading(false);
    setUploadProgress(0);
    setStatus("Upload cancelled");
    setStatusType("idle");
  }

  return { 
    startRecording, 
    stopRecording, 
    uploadAudio,
    cancelUpload,
    audioQuality,
    setAudioQuality: updateAudioQuality,
    isUploading,
    uploadProgress,
    AUDIO_QUALITIES,
  };
}
