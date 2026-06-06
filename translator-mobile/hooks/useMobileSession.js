import { useState, useRef } from 'react';

export function useMobileSession({ defaultSource = 'en', defaultTarget = 'ht' } = {}) {
  const [sourceLanguage, setSourceLanguage] = useState(defaultSource);
  const [targetLanguage, setTargetLanguage] = useState(defaultTarget);

  const mobileDeviceIdRef = useRef('phone-' + Math.random().toString(36).slice(2));
  const mobileSessionIdRef = useRef('mobile-' + Date.now());

  return {
    sourceLanguage,
    setSourceLanguage,
    targetLanguage,
    setTargetLanguage,
    mobileDeviceIdRef,
    mobileSessionIdRef,
  };
}
