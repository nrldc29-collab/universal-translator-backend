import { useRef } from 'react';

export function useStreamRefs() {
  const mediaRecorderRef = useRef(null);
  const streamRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);
  const recordingStoppedRef = useRef(false);
  const streamFinalizePendingRef = useRef(false);
  const streamFinalizeTimerRef = useRef(null);
  const streamStartedAtRef = useRef(0);
  const streamRecordingStartedAtRef = useRef(0);
  const firstAudioSeenRef = useRef(false);
  const streamReconnectRef = useRef({ enabled: false, options: null, attempts: 0 });
  const streamReconnectTimerRef = useRef(null);
  const streamSafetyTimeoutRef = useRef(null);
  const resumeAfterTtsRef = useRef(false);

  return {
    mediaRecorderRef,
    streamRecorderRef,
    chunksRef,
    socketRef,
    recordingStoppedRef,
    streamFinalizePendingRef,
    streamFinalizeTimerRef,
    streamStartedAtRef,
    streamRecordingStartedAtRef,
    firstAudioSeenRef,
    streamReconnectRef,
    streamReconnectTimerRef,
    streamSafetyTimeoutRef,
    resumeAfterTtsRef,
  };
}
