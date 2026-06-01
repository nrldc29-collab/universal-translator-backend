import { useState } from 'react';
import { normalizeSessionId, readInitialSessionId } from '../utils';

const SESSION_STORAGE_KEY = 'translator_session_id';

const INITIAL_SESSION_ID = (() => {
  const id = readInitialSessionId();
  localStorage.setItem(SESSION_STORAGE_KEY, id);
  return id;
})();

export function useStreamSession() {
  const [sessionId, setSessionIdState] = useState(INITIAL_SESSION_ID);
  const [sharedSession, setSharedSession] = useState(null);
  const [speakerMode, setSpeakerMode] = useState('auto');

  function updateSessionId(value) {
    const normalized = normalizeSessionId(value) || crypto.randomUUID();
    setSessionIdState(normalized);
    localStorage.setItem(SESSION_STORAGE_KEY, normalized);
  }

  return {
    sessionId,
    setSessionId: setSessionIdState,
    updateSessionId,
    sharedSession,
    setSharedSession,
    speakerMode,
    setSpeakerMode,
  };
}
