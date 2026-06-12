import { useState, useEffect, useRef } from 'react';

export function useConnectionStatus({ apiUrl, pollIntervalMs, onLanguages, onOffline }) {
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const onLanguagesRef = useRef(onLanguages);
  const onOfflineRef = useRef(onOffline);

  useEffect(() => {
    onLanguagesRef.current = onLanguages;
    onOfflineRef.current = onOffline;
  });

  useEffect(() => {
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
    let cancelled = false;
    fetch(`${apiUrl}/languages`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        onLanguagesRef.current?.(data.languages);
      })
      .catch(() => {
        if (cancelled) return;
        onOfflineRef.current?.();
        setConnectionStatus('offline');
      });
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
      try {
        const r = await fetch(`${apiUrl}/health`, { cache: 'no-store' });
        if (!r.ok) throw new Error('health check failed');
        const data = await r.json();
        if (cancelled) return;
        if (data.ready === false) {
          setConnectionStatus('warming');
          return;
        }
        setConnectionStatus('online');
      } catch {
        if (!cancelled) setConnectionStatus('offline');
      }
    };
    check();
    const timer = window.setInterval(check, pollIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [apiUrl, pollIntervalMs]);

  return { connectionStatus, setConnectionStatus };
}
