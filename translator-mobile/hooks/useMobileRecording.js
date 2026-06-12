import { useState, useRef, useEffect } from "react";
import { Audio } from "expo-av";
import { playTtsAudio } from "../services/audio-stream";
import * as SecureStore from "expo-secure-store";

import { AUDIO_QUALITIES, AUDIO_QUALITY_KEY, buildRecordingOptions } from "../constants/audioQuality";

const MAX_RETRIES = 3;
const UPLOAD_TIMEOUT = 30000;

const AUDIO_QUALITIES_WITH_PRESETS = Object.fromEntries(
  Object.entries(AUDIO_QUALITIES).map(([key, quality]) => [
    key,
    {
      ...quality,
      preset: buildRecordingOptions(key),
    },
  ]),
);

export function useMobileRecording({
  isConnected,
  isStreaming = false,
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
  audioQuality: parentAudioQuality,
  shouldUpload,
}) {
  const [internalAudioQuality, setInternalAudioQuality] = useState("HIGH");
  const audioQuality = parentAudioQuality || internalAudioQuality;
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const retryCountRef = useRef(0);
  const uploadAbortRef = useRef(null);
  const uploadRetryDelayRef = useRef(null);
  const uploadEpochRef = useRef(0);

  function clearUploadRetryDelay() {
    if (uploadRetryDelayRef.current) {
      clearTimeout(uploadRetryDelayRef.current);
      uploadRetryDelayRef.current = null;
    }
  }

  useEffect(() => {
    if (parentAudioQuality) return undefined;
    loadAudioQuality();
    return () => {
      clearUploadRetryDelay();
      uploadAbortRef.current?.abort();
      uploadAbortRef.current = null;
    };
  }, [parentAudioQuality]);

  useEffect(() => () => {
    uploadEpochRef.current += 1;
    clearUploadRetryDelay();
    uploadAbortRef.current?.abort();
    uploadAbortRef.current = null;
  }, []);

  async function loadAudioQuality() {
    try {
      const storedQuality = await SecureStore.getItemAsync(AUDIO_QUALITY_KEY);
      if (storedQuality && AUDIO_QUALITIES_WITH_PRESETS[storedQuality]) {
        setInternalAudioQuality(storedQuality);
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
    if (!AUDIO_QUALITIES_WITH_PRESETS[quality]) return;
    if (!parentAudioQuality) {
      setInternalAudioQuality(quality);
      await saveAudioQuality(quality);
    }
  }

  async function startRecording() {
    if (!isConnected) {
      setStatus("Link the bridge first");
      setStatusType("error");
      return;
    }
    if (isStreaming) {
      setStatus("Pause the live bridge first");
      setStatusType("warning");
      return;
    }
    if (isUploading) {
      setStatus("Bridge upload in progress…");
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
      const recordingOptions = AUDIO_QUALITIES_WITH_PRESETS[audioQuality].preset;
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
    if (typeof shouldUpload === "function" && !shouldUpload()) {
      setIsUploading(false);
      setUploadProgress(0);
      return;
    }
    uploadEpochRef.current += 1;
    const epoch = uploadEpochRef.current;
    setIsUploading(true);
    setUploadProgress(0);
    retryCountRef.current = 0;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      if (epoch !== uploadEpochRef.current) return;
      if (typeof shouldUpload === "function" && !shouldUpload()) {
        setIsUploading(false);
        setUploadProgress(0);
        return;
      }
      try {
        setStatus(`Uploading audio... (${attempt + 1}/${MAX_RETRIES})`);
        setStatusType("connecting");

        const controller = new AbortController();
        uploadAbortRef.current = controller;
        const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT);

        const form = new FormData();
        form.append("audio", { uri, name: "recording.m4a", type: "audio/m4a" });
        form.append("source_language", sourceLanguage);
        form.append("target_language", targetLanguage);
        form.append("synthesize_audio", "true");

        const apiBase = String(wsUrl || "").trim().replace(/\/+$/, "");
        let response;
        try {
          response = await fetch(`${apiBase}/translate/audio`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
            },
            body: form,
            signal: controller.signal,
          });
        } finally {
          clearTimeout(timeoutId);
          if (uploadAbortRef.current === controller) {
            uploadAbortRef.current = null;
          }
        }

        if (epoch !== uploadEpochRef.current) return;

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
            setIsPlayingTts?.(true);
            const ok = await playTtsAudio(data.audio_base64, data.mime_type || "audio/wav");
            if (!ok) {
              setStatus("TTS playback failed");
              setStatusType("error");
            }
          } finally {
            isPlayingTtsRef.current = false;
            setIsPlayingTts?.(false);
          }
        }
        
        setIsUploading(false);
        return;
      } catch (error) {
        if (epoch !== uploadEpochRef.current) return;
        if (error?.name === "AbortError") {
          setIsUploading(false);
          setUploadProgress(0);
          return;
        }
        console.error(`Upload attempt ${attempt + 1} failed:`, error);
        
        if (attempt === MAX_RETRIES - 1) {
          setStatus(`Upload failed after ${MAX_RETRIES} attempts: ${error.message}`);
          setStatusType("error");
          setIsUploading(false);
          setUploadProgress(0);
        } else {
          const delay = Math.pow(2, attempt) * 1000;
          setStatus(`Retrying in ${delay / 1000}s...`);
          await new Promise((resolve) => {
            clearUploadRetryDelay();
            uploadRetryDelayRef.current = setTimeout(() => {
              uploadRetryDelayRef.current = null;
              resolve();
            }, delay);
          });
          if (epoch !== uploadEpochRef.current) {
            setIsUploading(false);
            return;
          }
          if (typeof shouldUpload === "function" && !shouldUpload()) {
            setIsUploading(false);
            setUploadProgress(0);
            return;
          }
        }
      }
    }
  }

  function cancelUpload() {
    uploadEpochRef.current += 1;
    clearUploadRetryDelay();
    uploadAbortRef.current?.abort();
    uploadAbortRef.current = null;
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
    AUDIO_QUALITIES: AUDIO_QUALITIES_WITH_PRESETS,
  };
}
