import { useRef } from 'react';

export function useHoldToTalk() {
  const holdToTalkTimerRef = useRef(null);
  const holdToTalkActiveRef = useRef(false);
  const holdToTalkReleasePendingRef = useRef(false);
  const ignoreNextMicClickRef = useRef(false);

  return {
    holdToTalkTimerRef,
    holdToTalkActiveRef,
    holdToTalkReleasePendingRef,
    ignoreNextMicClickRef,
  };
}
