import { useState } from 'react';

export function usePipelineState() {
  const [partialTranscript, setPartialTranscript] = useState('');
  const [liveTranslation, setLiveTranslation] = useState('');
  const [pipelineStage, setPipelineStage] = useState('Idle');
  const [audioReplayAvailable, setAudioReplayAvailable] = useState(false);
  const [lastAudioError, setLastAudioError] = useState(null);

  return {
    partialTranscript,
    setPartialTranscript,
    liveTranslation,
    setLiveTranslation,
    pipelineStage,
    setPipelineStage,
    audioReplayAvailable,
    setAudioReplayAvailable,
    lastAudioError,
    setLastAudioError,
  };
}
