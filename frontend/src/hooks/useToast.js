import { useState, useCallback, useRef } from 'react';

let _id = 0;

/**
 * Lightweight toast queue.
 * Returns { toasts, toast } where toast(msg, type, duration) adds a toast.
 */
export function useToast() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, leaving: true } : t));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 220);
  }, []);

  const toast = useCallback((message, type = 'info', duration = 2600) => {
    const id = ++_id;
    setToasts(prev => [...prev.slice(-3), { id, message, type, leaving: false }]);
    timers.current[id] = setTimeout(() => dismiss(id), duration);
    return id;
  }, [dismiss]);

  return { toasts, toast, dismiss };
}
