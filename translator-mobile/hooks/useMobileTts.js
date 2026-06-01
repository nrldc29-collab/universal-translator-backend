import { useState, useRef } from "react";
import { playTtsAudio } from "../services/audio-stream";

export function useMobileTts() {
  const [ttsQueue, setTtsQueue] = useState([]);
  const [isPlayingTts, setIsPlayingTts] = useState(false);
  const ttsQueueRef = useRef([]);
  const isPlayingTtsRef = useRef(false);

  async function playNextTtsChunk() {
    if (ttsQueueRef.current.length === 0 || isPlayingTtsRef.current) {
      if (ttsQueueRef.current.length === 0) {
        setIsPlayingTts(false);
        isPlayingTtsRef.current = false;
      }
      return;
    }

    isPlayingTtsRef.current = true;
    setIsPlayingTts(true);

    const message = ttsQueueRef.current.shift();
    setTtsQueue([...ttsQueueRef.current]);

    try {
      await playTtsAudio(message.audio_base64, message.mime_type);
    } catch (error) {
      console.error("TTS playback error:", error);
    }

    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);

    if (ttsQueueRef.current.length > 0) {
      playNextTtsChunk();
    }
  }

  function handleTtsChunk(message) {
    if (!message.audio_base64) return;
    ttsQueueRef.current = [...ttsQueueRef.current, message];
    setTtsQueue(ttsQueueRef.current);
    if (!isPlayingTtsRef.current) {
      playNextTtsChunk();
    }
  }

  function clearTtsQueue() {
    ttsQueueRef.current = [];
    setTtsQueue([]);
    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);
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
  };
}
