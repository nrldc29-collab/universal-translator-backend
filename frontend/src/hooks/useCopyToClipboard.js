/**
 * useCopyToClipboard -- copy text to the clipboard and track which "key"
 * was most recently copied so callers can flash a "Copied!" indicator.
 *
 * Returns `[copiedKey, copyToClipboard]`. `copiedKey` flips back to null
 * after `revertAfterMs` (default 1.4s). Falls back to a hidden <textarea>
 * + execCommand('copy') if `navigator.clipboard` is unavailable.
 */

import { useCallback, useRef, useState } from 'react';

export default function useCopyToClipboard(revertAfterMs = 1400) {
  const [copiedKey, setCopiedKey] = useState(null);
  const timerRef = useRef(null);

  const copyToClipboard = useCallback(
    async (text, key) => {
      if (!text) return;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
        setCopiedKey(key);
        if (timerRef.current) window.clearTimeout(timerRef.current);
        timerRef.current = window.setTimeout(() => {
          setCopiedKey((current) => (current === key ? null : current));
          timerRef.current = null;
        }, revertAfterMs);
      } catch (err) {
        console.warn('copy failed', err);
      }
    },
    [revertAfterMs],
  );

  return [copiedKey, copyToClipboard];
}
