import { useState, useRef } from 'react';

export function useTtsQueue() {
  const [ttsQueueLength, setTtsQueueLength] = useState(0);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsChunksBuffer, setTtsChunksBuffer] = useState([]);
  const [userRequestedPlayback, setUserRequestedPlayback] = useState(false);
  const [autoPlayFailed, setAutoPlayFailed] = useState(false);

  const ttsQueueRef = useRef([]);
  const lastTtsItemRef = useRef(null);
  const ttsPlayingRef = useRef(false);
  const currentTtsFinishRef = useRef(null);
  const canplayTimeoutRef = useRef(null);

  function revokeTtsItemUrl(item) {
    if (item?.url && item.objectUrl) {
      URL.revokeObjectURL(item.url);
    }
  }

  function hasPlayableAudioPayload(data) {
    return Boolean(data?.audio_url || data?.audio_base64);
  }

  function clearTtsQueue() {
    if (currentTtsFinishRef.current) {
      const fn = currentTtsFinishRef.current;
      currentTtsFinishRef.current = null;
      fn();
    }
    if (canplayTimeoutRef.current) {
      window.clearTimeout(canplayTimeoutRef.current);
      canplayTimeoutRef.current = null;
    }
    ttsQueueRef.current = [];
    setTtsQueueLength(0);
    setTtsChunksBuffer([]);
    ttsPlayingRef.current = false;
    setTtsPlaying(false);
  }

  return {
    ttsQueueLength,
    setTtsQueueLength,
    ttsPlaying,
    setTtsPlaying,
    ttsChunksBuffer,
    setTtsChunksBuffer,
    userRequestedPlayback,
    setUserRequestedPlayback,
    autoPlayFailed,
    setAutoPlayFailed,
    ttsQueueRef,
    lastTtsItemRef,
    ttsPlayingRef,
    currentTtsFinishRef,
    canplayTimeoutRef,
    revokeTtsItemUrl,
    hasPlayableAudioPayload,
    clearTtsQueue,
  };
}
