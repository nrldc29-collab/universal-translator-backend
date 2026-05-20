/**
 * useDiagnostics — fetch `/diagnostics` from the backend and expose the
 * structured response plus a status string (`checking` / `online` /
 * `offline`) that the UI uses to render a health indicator.
 *
 * Returns `{ diagnostics, diagnosticsStatus, loadDiagnostics }`.
 * `loadDiagnostics()` is stable across renders so it can be passed
 * straight into onClick handlers or effect deps.
 *
 * On mount we run one fetch automatically; the parent decides when to
 * refresh after that.
 */

import { useCallback, useEffect, useState } from 'react';

import { responseErrorMessage } from '../utils';

export default function useDiagnostics(apiUrl) {
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState('checking');

  const loadDiagnostics = useCallback(async () => {
    if (!apiUrl) return;
    setDiagnosticsStatus('checking');
    try {
      const response = await fetch(`${apiUrl}/diagnostics`);
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Diagnostics unavailable'));
      }
      const data = await response.json();
      setDiagnostics(data);
      setDiagnosticsStatus(data.ready ? 'online' : 'checking');
    } catch {
      setDiagnosticsStatus('offline');
    }
  }, [apiUrl]);

  useEffect(() => {
    loadDiagnostics();
  }, [loadDiagnostics]);

  return { diagnostics, diagnosticsStatus, loadDiagnostics };
}
