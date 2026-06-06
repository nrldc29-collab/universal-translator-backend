import { useState, useRef } from 'react';
import { extractBrainPlan } from '../utils';

const INITIAL_BRAIN_UI = {
  visible: false,
  message: '',
  mode: '',
  strategy: '',
  hints: {},
  repairOptions: [],
  highlightTerms: [],
  riskScore: null,
};

export function useBrainState() {
  const [clarifyVisible, setClarifyVisible] = useState(false);
  const [clarifyMessage, setClarifyMessage] = useState('');
  const [confidenceWarningVisible, setConfidenceWarningVisible] = useState(false);
  const [confidenceWarningMessage, setConfidenceWarningMessage] = useState('');
  const [brainUi, setBrainUi] = useState(INITIAL_BRAIN_UI);
  const [conversationBrain, setConversationBrain] = useState('Idle');
  const [semanticContext, setSemanticContext] = useState({
    last_intent: 'statement',
    conversation_mood: 'neutral',
    topics: [],
  });

  const brainHintsRef = useRef({});
  const brainPlanRef = useRef(null);

  function shouldSkipBrainTts(payload = null) {
    const hints = payload ? extractBrainPlan(payload).hints : brainHintsRef.current;
    return Boolean(hints?.skip_tts || hints?.tts_mode === 'skip');
  }

  function resetBrainRuntimeUi() {
    brainHintsRef.current = {};
    brainPlanRef.current = null;
    setBrainUi((current) => ({
      ...current,
      visible: false,
      message: '',
      repairOptions: [],
      highlightTerms: [],
      skipTts: false,
      speakerShift: false,
    }));
  }

  return {
    clarifyVisible,
    setClarifyVisible,
    clarifyMessage,
    setClarifyMessage,
    confidenceWarningVisible,
    setConfidenceWarningVisible,
    confidenceWarningMessage,
    setConfidenceWarningMessage,
    brainUi,
    setBrainUi,
    conversationBrain,
    setConversationBrain,
    semanticContext,
    setSemanticContext,
    brainHintsRef,
    brainPlanRef,
    shouldSkipBrainTts,
    resetBrainRuntimeUi,
  };
}
