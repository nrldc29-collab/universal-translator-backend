import { useRef } from 'react';

export default function useWakeLock() {
  const wakeLockRef = useRef(null);

  async function requestWakeLock() {
    try {
      wakeLockRef.current = await navigator.wakeLock?.request?.('screen') || null;
    } catch {
      wakeLockRef.current = null;
    }
  }

  async function releaseWakeLock() {
    try {
      await wakeLockRef.current?.release?.();
    } catch {
    } finally {
      wakeLockRef.current = null;
    }
  }

  return { requestWakeLock, releaseWakeLock };
}
