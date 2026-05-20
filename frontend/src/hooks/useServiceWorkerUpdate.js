/**
 * useServiceWorkerUpdate — poll `${apiUrl}/debug/version` every minute
 * and surface a value when the backend reports a release that differs
 * from `expectedRelease`, so the parent can show an "Update available"
 * banner with a Reload button.
 *
 * Returns `updateAvailable` — either `null` (in sync) or
 * `{ frontend, backend }`.
 */

import { useEffect, useState } from 'react';

const POLL_MS = 60_000;

export default function useServiceWorkerUpdate({ apiUrl, expectedRelease } = {}) {
  const [updateAvailable, setUpdateAvailable] = useState(null);

  useEffect(() => {
    if (!apiUrl || !expectedRelease) return undefined;
    let cancelled = false;

    async function checkRelease() {
      try {
        const response = await fetch(`${apiUrl}/debug/version?cb=${Date.now()}`, {
          cache: 'no-store',
        });
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled) return;
        const live = String((data && data.release) || '');
        if (live && live !== expectedRelease) {
          console.warn('Frontend/backend release mismatch', {
            frontend: expectedRelease,
            backend: live,
          });
          setUpdateAvailable({ frontend: expectedRelease, backend: live });
        } else if (live) {
          setUpdateAvailable(null);
        }
      } catch {
        // ignore network errors — we'll try again on the next tick
      }
    }

    checkRelease();
    const interval = window.setInterval(checkRelease, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiUrl, expectedRelease]);

  return updateAvailable;
}
