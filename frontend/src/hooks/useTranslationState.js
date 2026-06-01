import { useState } from 'react';

export function useTranslationState() {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');

  return {
    text,
    setText,
    result,
    setResult,
    status,
    setStatus,
  };
}
