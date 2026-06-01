/**
 * useHaptic -- returns a stable `haptic(pattern)` callback that calls
 * `navigator.vibrate(pattern)` when the device supports it and does
 * nothing otherwise.
 *
 * Pattern can be a single duration in ms or an array of on/off
 * durations (`navigator.vibrate` semantics). See:
 * https://developer.mozilla.org/en-US/docs/Web/API/Navigator/vibrate
 */

import { useCallback } from 'react';

export default function useHaptic() {
  return useCallback((pattern = 12) => {
    try {
      window.navigator?.vibrate?.(pattern);
    } catch {
      /* ignore -- vibrate is best-effort */
    }
  }, []);
}
