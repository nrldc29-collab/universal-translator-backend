import { useState, useRef, useEffect } from 'react';

export function useMobileStreamState() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [recording, setRecording] = useState(null);
  const [partialTranscript, setPartialTranscript] = useState('');
  const [liveTranslation, setLiveTranslation] = useState('');

  const wsControlRef = useRef(null);
  const resumeAfterTtsRef = useRef(false);
  const isStreamingRef = useRef(false);

  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  return {
    isStreaming,
    setIsStreaming,
    recording,
    setRecording,
    partialTranscript,
    setPartialTranscript,
    liveTranslation,
    setLiveTranslation,
    wsControlRef,
    resumeAfterTtsRef,
    isStreamingRef,
  };
}
