import { useState } from 'react';

export function useMobileBrainContext() {
  const [semanticContext, setSemanticContext] = useState(null);
  const [emotionInfo, setEmotionInfo] = useState(null);
  const [conversationBrain, setConversationBrain] = useState(null);

  return {
    semanticContext,
    setSemanticContext,
    emotionInfo,
    setEmotionInfo,
    conversationBrain,
    setConversationBrain,
  };
}
