import { useState } from 'react';

export function useWsDebug(initialUrl = '') {
  const [wsDebug, setWsDebug] = useState({ url: initialUrl, close: '-', error: '-' });
  return { wsDebug, setWsDebug };
}
