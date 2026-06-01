import { useState, useRef } from 'react';

const INITIAL_DUPLEX = {
  A: { active: false, transcript: '', translation: '', stage: 'Idle' },
  B: { active: false, transcript: '', translation: '', stage: 'Idle' },
};

export function useDuplexState() {
  const [duplex, setDuplex] = useState(INITIAL_DUPLEX);
  const duplexRefs = useRef({ A: {}, B: {} });

  function updateDuplexSpeaker(speaker, patch) {
    setDuplex((current) => ({
      ...current,
      [speaker]: { ...current[speaker], ...patch },
    }));
  }

  return { duplex, setDuplex, duplexRefs, updateDuplexSpeaker };
}
