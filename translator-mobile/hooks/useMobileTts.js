/* eslint-disable import/namespace */
import { useState, useRef, useEffect } from "react";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
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
  const [hasReplayAudio, setHasReplayAudio] = useState(false);
  const ttsQueueRef = useRef([]);
  const isPlayingTtsRef = useRef(false);
  const retryCountRef = useRef(0);
  const soundRef = useRef(null);
  const activePlaybackRef = useRef(null);
  const replayCaptureRef = useRef([]);
  const lastTtsMessagesRef = useRef([]);

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

  async function saveSettings(nextVolume = volume, nextSpeed = playbackSpeed) {
    try {
      await SecureStore.setItemAsync(VOLUME_KEY, nextVolume.toString());
      await SecureStore.setItemAsync(SPEED_KEY, nextSpeed.toString());
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
    await saveSettings(clampedVolume, playbackSpeed);
  }

  async function updatePlaybackSpeed(newSpeed) {
    const clampedSpeed = Math.max(0.5, Math.min(2.0, newSpeed));
    setPlaybackSpeed(clampedSpeed);
    if (soundRef.current) {
      await soundRef.current.setRateAsync(clampedSpeed, true);
    }
    await saveSettings(volume, clampedSpeed);
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
    const extension = mimeType?.includes("mpeg") || mimeType?.includes("mp3") ? "mp3" : "wav";
    const cacheDirectory = FileSystem["cacheDirectory"] || FileSystem["documentDirectory"] || "";
    const encodingType = FileSystem["EncodingType"]?.Base64 || "base64";
    const uri = `${cacheDirectory}tts-${Date.now()}-${Math.random().toString(36).slice(2)}.${extension}`;
    let playbackSound = null;

    try {
      await completeActivePlayback(false);
      await FileSystem.writeAsStringAsync(uri, audioBase64, {
        encoding: encodingType,
      });

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });

      return await new Promise(async (resolve) => {
        activePlaybackRef.current = { done: false, resolve, uri, sound: null };
        try {
          const { sound } = await Audio.Sound.createAsync(
            { uri },
            {
              shouldPlay: false,
              volume,
              rate: playbackSpeed,
              shouldCorrectPitch: true,
            }
          );
          playbackSound = sound;
          if (!activePlaybackRef.current || activePlaybackRef.current.done) {
            await sound.unloadAsync();
            resolve(false);
            return;
          }
          soundRef.current = sound;
          activePlaybackRef.current.sound = sound;
          sound.setOnPlaybackStatusUpdate((status) => {
            if (status?.didJustFinish) {
              completeActivePlayback(true);
            } else if (status?.isLoaded === false && status?.error) {
              completeActivePlayback(false);
            }
          });
          await sound.playAsync();
        } catch (error) {
          console.error("Error starting TTS audio:", error);
          if (playbackSound) {
            try {
              await playbackSound.unloadAsync();
            } catch {
              // Already unloaded.
            }
          }
          completeActivePlayback(false);
        }
      });
    } catch (error) {
      console.error("Error playing TTS audio:", error);
      await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
      return false;
    }
  }

  async function completeActivePlayback(success) {
    const activePlayback = activePlaybackRef.current;
    if (!activePlayback || activePlayback.done) return;

    activePlayback.done = true;
    activePlaybackRef.current = null;

    const activeSound = activePlayback.sound;
    if (soundRef.current === activeSound) {
      soundRef.current = null;
    }

    if (activeSound) {
      try {
        await activeSound.unloadAsync();
      } catch {
        // The sound may already be unloaded after a stop.
      }
    }
    if (activePlayback.uri) {
      await FileSystem.deleteAsync(activePlayback.uri, { idempotent: true }).catch(() => {});
    }
    activePlayback.resolve?.(success);
  }

  function handleTtsChunk(message) {
    if (!message.audio_base64) return;
    rememberReplayChunk(message);
    
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

  function rememberReplayChunk(message) {
    const total = Math.max(1, Number(message.total) || 1);
    const index = Math.max(1, Number(message.index) || replayCaptureRef.current.length + 1);
    if (index === 1 || total === 1) {
      replayCaptureRef.current = [];
    }

    replayCaptureRef.current = [
      ...replayCaptureRef.current.filter((item) => (Number(item.index) || 1) !== index),
      message,
    ].sort((a, b) => (Number(a.index) || 1) - (Number(b.index) || 1));

    const captured = total === 1 ? [message] : replayCaptureRef.current.slice(0, total);
    if (captured.length > 0) {
      lastTtsMessagesRef.current = captured;
      setHasReplayAudio(true);
    }
  }

  async function replayLastTts() {
    const messages = lastTtsMessagesRef.current.filter((message) => message?.audio_base64);
    if (messages.length === 0) return false;

    retryCountRef.current = 0;
    ttsQueueRef.current = [];
    setTtsQueue([]);

    if (isPlayingTtsRef.current) {
      await stopTtsPlayback();
    }

    isPlayingTtsRef.current = true;
    setIsPlayingTts(true);

    try {
      for (const message of messages) {
        setCurrentAudio(message);
        const played = await playTtsAudioWithSettings(message.audio_base64, message.mime_type);
        if (!played) return false;
      }
      return true;
    } finally {
      isPlayingTtsRef.current = false;
      setIsPlayingTts(false);
      setCurrentAudio(null);
    }
  }

  async function stopTtsPlayback() {
    retryCountRef.current = MAX_RETRIES;
    if (soundRef.current) {
      try {
        await soundRef.current.stopAsync();
      } catch {
        // Stop can fail if playback already ended.
      }
    }
    await completeActivePlayback(false);
    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
    setCurrentAudio(null);
  }

  function clearTtsQueue() {
    ttsQueueRef.current = [];
    setTtsQueue([]);
    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
    retryCountRef.current = MAX_RETRIES;
    stopTtsPlayback();
  }

  function clearReplayAudio() {
    replayCaptureRef.current = [];
    lastTtsMessagesRef.current = [];
    setHasReplayAudio(false);
  }

  return {
    ttsQueue,
    isPlayingTts,
    setIsPlayingTts,
    ttsQueueRef,
    isPlayingTtsRef,
    handleTtsChunk,
    playNextTtsChunk,
    replayLastTts,
    clearTtsQueue,
    clearReplayAudio,
    stopTtsPlayback,
    hasReplayAudio,
    volume,
    setVolume: updateVolume,
    playbackSpeed,
    setPlaybackSpeed: updatePlaybackSpeed,
    currentAudio,
  };
}
