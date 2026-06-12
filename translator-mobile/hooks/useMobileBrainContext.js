import { useState, useRef, useCallback } from "react";

const INITIAL_BRAIN_UI = {
  visible: false,
  message: "",
  mode: "",
  strategy: "",
  hints: {},
  repairOptions: [],
  highlightTerms: [],
  riskScore: null,
  skipTts: false,
  speakerShift: false,
  activeSpeakerLabel: "",
};

export function useMobileBrainContext() {
  const [semanticContext, setSemanticContext] = useState(null);
  const [emotionInfo, setEmotionInfo] = useState(null);
  const [conversationBrain, setConversationBrain] = useState(null);
  const [clarifyVisible, setClarifyVisible] = useState(false);
  const [clarifyMessage, setClarifyMessage] = useState("");
  const [brainUi, setBrainUi] = useState(INITIAL_BRAIN_UI);
  const brainHintsRef = useRef({});
  const brainPlanRef = useRef(null);

  const resetBrainRuntimeUi = useCallback(() => {
    brainHintsRef.current = {};
    brainPlanRef.current = null;
    setBrainUi(INITIAL_BRAIN_UI);
    setClarifyVisible(false);
    setClarifyMessage("");
  }, []);

  return {
    semanticContext,
    setSemanticContext,
    emotionInfo,
    setEmotionInfo,
    conversationBrain,
    setConversationBrain,
    clarifyVisible,
    setClarifyVisible,
    clarifyMessage,
    setClarifyMessage,
    brainUi,
    setBrainUi,
    brainHintsRef,
    brainPlanRef,
    resetBrainRuntimeUi,
  };
}
