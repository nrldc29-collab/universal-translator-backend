import { useState } from 'react';
import { readPersistedSourceLanguage, readPersistedTargetLanguage } from '../utils';

export function useLanguagePair() {
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish', ht: 'Haitian Creole' });
  const [sourceLanguageState, setSourceLanguageState] = useState(readPersistedSourceLanguage);
  const [targetLanguage, setTargetLanguageState] = useState(readPersistedTargetLanguage);

  const sourceLanguage = sourceLanguageState;

  const setSourceLanguage = (next) => {
    setSourceLanguageState(next);
    try { localStorage.setItem('sourceLanguage', next); } catch {}
  };

  const setTargetLanguage = (next) => {
    setTargetLanguageState(next);
    try { localStorage.setItem('targetLanguage', next); } catch {}
  };

  return {
    languages,
    setLanguages,
    sourceLanguage,
    setSourceLanguage,
    targetLanguage,
    setTargetLanguage,
  };
}
