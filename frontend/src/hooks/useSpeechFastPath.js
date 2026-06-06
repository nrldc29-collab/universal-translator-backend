import { useRef } from 'react';

export function useSpeechFastPath() {
  const speechRecognitionRef = useRef(null);
  const speechFastPathActiveRef = useRef(false);
  const speechFinalTextRef = useRef('');
  const speechInterimTextRef = useRef('');
  const speechAssistSocketRef = useRef(null);
  const speechAssistRestartTimerRef = useRef(null);
  const speechAssistStopRequestedRef = useRef(false);
  const speechLastSentTextRef = useRef('');
  const speechLastSentAtRef = useRef(0);
  const speechUtteranceSeqRef = useRef(0);

  return {
    speechRecognitionRef,
    speechFastPathActiveRef,
    speechFinalTextRef,
    speechInterimTextRef,
    speechAssistSocketRef,
    speechAssistRestartTimerRef,
    speechAssistStopRequestedRef,
    speechLastSentTextRef,
    speechLastSentAtRef,
    speechUtteranceSeqRef,
  };
}
