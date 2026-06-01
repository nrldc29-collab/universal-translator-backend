import { useState, useRef, useEffect } from "react";
import { Audio } from "expo-av";
import { playTtsAudio } from "../services/audio-stream";
import * as SecureStore from "expo-secure-store";

const VOLUME_KEY = "tts_volume";
const SPEED_KEY = "tts_speed";
const MAX_QUEUE_SIZE = 50;
const MAX_RETRIES = 3;

export function useMobileTts() {
  const [ttsQueue, setTtsQueue] = useState([]);
  const [isPlayingTts, setIsPlayingTts] = useState(false);
  const [volume, setVolume] = useState(0.8);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [currentAudio, setCurrentAudio] = useState(null);
  const ttsQueueRef = useRef([]);
  const isPlayingTtsRef = useRef(false);
  const retryCountRef = useRef(0);
  const soundRef = useRef(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const storedVolume = await SecureStore.getItemAsync(VOLUME_KEY);
      const storedSpeed = await SecureStore.getItemAsync(SPEED_KEY);
      if (storedVolume !== null) setVolume(parseFloat(storedVolume));
      if (storedSpeed !== null) setPlaybackSpeed(parseFloat(storedSpeed));
    } catch (error) {
      console.error("Error loading TTS settings:", error);
    }
  }

  async function saveSettings() {
    try {
      await SecureStore.setItemAsync(VOLUME_KEY, volume.toString());
      await SecureStore.setItemAsync(SPEED_KEY, playbackSpeed.toString());
    } catch (error) {
      console.error("Error saving TTS settings:", error);
    }
  }

  async function updateVolume(newVolume) {
    const clampedVolume = Math.max(0, Math.min(1, newVolume));
    setVolume(clampedVolume);
    if (soundRef.current) {
      await soundRef.current.setVolumeAsync(clampedVolume);
    }
    await saveSettings();
  }

  async function updatePlaybackSpeed(newSpeed) {
    const clampedSpeed = Math.max(0.5, Math.min(2.0, newSpeed));
    setPlaybackSpeed(clampedSpeed);
    if (soundRef.current) {
      await soundRef.current.setRateAsync(clampedSpeed);
    }
    await saveSettings();
  }

  async function playNextTtsChunk() {
    if (ttsQueueRef.current.length === 0 || isPlayingTtsRef.current) {
      if (ttsQueueRef.current.length === 0) {
        setIsPlayingTts(false);
        isPlayingTtsRef.current = false;
        retryCountRef.current = 0;
      }
      return;
    }

    isPlayingTtsRef.current = true;
    setIsPlayingTts(true);

    const message = ttsQueueRef.current.shift();
    setTtsQueue([...ttsQueueRef.current]);
    setCurrentAudio(message);

    try {
      const success = await playTtsAudioWithSettings(message.audio_base64, message.mime_type);
      if (success) {
        retryCountRef.current = 0;
      } else {
        throw new Error("TTS playback failed");
      }
    } catch (error) {
      console.error("TTS playback error:", error);
      retryCountRef.current++;
      
      if (retryCountRef.current < MAX_RETRIES) {
        console.log(`Retrying TTS playback (${retryCountRef.current}/${MAX_RETRIES})`);
        ttsQueueRef.current.unshift(message);
        setTtsQueue([...ttsQueueRef.current]);
        setTimeout(() => playNextTtsChunk(), 500);
        return;
      } else {
        console.error("Max retries reached for TTS playback");
        retryCountRef.current = 0;
      }
    }

    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
    setCurrentAudio(null);

    if (ttsQueueRef.current.length > 0) {
      playNextTtsChunk();
    }
  }

  async function playTtsAudioWithSettings(audioBase64, mimeType) {
    try {
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }

      const { sound } = await Audio.Sound.createAsync(
        { uri: `data:${mimeType};base64,${audioBase64}` },
        { 
          shouldPlay: true,
          volume: volume,
          rate: playbackSpeed,
        },
        async (status) => {
          if (status.didJustFinish) {
            await sound.unloadAsync();
            soundRef.current = null;
          }
        }
      );

      soundRef.current = sound;
      return true;
    } catch (error) {
      console.error("Error playing TTS audio:", error);
      return false;
    }
  }

  function handleTtsChunk(message) {
    if (!message.audio_base64) return;
    
    if (ttsQueueRef.current.length >= MAX_QUEUE_SIZE) {
      console.warn("TTS queue full, dropping oldest chunk");
      ttsQueueRef.current.shift();
    }
    
    ttsQueueRef.current = [...ttsQueueRef.current, message];
    setTtsQueue(ttsQueueRef.current);
    
    if (!isPlayingTtsRef.current) {
      playNextTtsChunk();
    }
  }

  async function stopTtsPlayback() {
    if (soundRef.current) {
      await soundRef.current.stopAsync();
      await soundRef.current.unloadAsync();
      soundRef.current = null;
    }
    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
    setCurrentAudio(null);
  }

  function clearTtsQueue() {
    ttsQueueRef.current = [];
    setTtsQueue([]);
    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
    retryCountRef.current = 0;
    stopTtsPlayback();
  }

  return {
    ttsQueue,
    isPlayingTts,
    setIsPlayingTts,
    ttsQueueRef,
    isPlayingTtsRef,
    handleTtsChunk,
    playNextTtsChunk,
    clearTtsQueue,
    stopTtsPlayback,
    volume,
    setVolume: updateVolume,
    playbackSpeed,
    setPlaybackSpeed: updatePlaybackSpeed,
    currentAudio,
  };
}
