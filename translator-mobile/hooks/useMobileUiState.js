import { useState } from 'react';

export function useMobileUiState() {
  const [result, setResult] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  return {
    result,
    setResult,
    showSettings,
    setShowSettings,
  };
}
