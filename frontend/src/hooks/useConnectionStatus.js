import { useState, useEffect } from 'react';

export function useConnectionStatus({ apiUrl, pollIntervalMs, onLanguages, onOffline }) {
  const [connectionStatus, setConnectionStatus] = useState('checking');

  useEffect(() => {
    fetch(`${apiUrl}/languages`)
      .then((r) => r.json())
      .then((data) => {
        onLanguages?.(data.languages);
        setConnectionStatus('online');
      })
      .catch(() => {
        onOffline?.();
        setConnectionStatus('offline');
      });
  }, [apiUrl, onLanguages, onOffline]);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const r = await fetch(`${apiUrl}/health`, { cache: 'no-store' });
        if (!r.ok) throw new Error('health check failed');
        if (!cancelled) setConnectionStatus('online');
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
