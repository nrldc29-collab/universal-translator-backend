import { useState, useRef } from 'react';
import { extractBrainPlan } from '../utils';
import { humanCertStep, shouldBlockTtsForCert, resolveConfidenceWarning } from '../utils/humanCertification';

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
  const [humanCertificationStep, setHumanCertificationStep] = useState('none');
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
    if (payload) {
      const hints = extractBrainPlan(payload).hints;
      if (Boolean(hints?.skip_tts || hints?.tts_mode === 'skip')) return true;
      if (payload?.stage === 'translation_safety') return true;
      if (shouldBlockTtsForCert(humanCertStep(payload))) return true;
      return false;
    }
    // Never block playback from stale brain hints alone — only active cert gate.
    if (shouldBlockTtsForCert(humanCertificationStep)) return true;
    return false;
  }

  function applyConfidenceSignals(payload = {}) {
    if (!payload || typeof payload !== 'object') return;
    const certStep = humanCertStep(payload);
    setHumanCertificationStep(certStep);
    const warning = resolveConfidenceWarning(payload);
    if (!warning) return;
    setConfidenceWarningVisible(true);
    setConfidenceWarningMessage(warning);
  }

  function resetBrainRuntimeUi() {
    brainHintsRef.current = {};
    brainPlanRef.current = null;
    setHumanCertificationStep('none');
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
    humanCertificationStep,
    setHumanCertificationStep,
    brainUi,
    setBrainUi,
    conversationBrain,
    setConversationBrain,
    semanticContext,
    setSemanticContext,
    brainHintsRef,
    brainPlanRef,
    shouldSkipBrainTts,
    applyConfidenceSignals,
    resetBrainRuntimeUi,
  };
}
