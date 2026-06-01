/**
 * useInstallPrompt -- wraps the PWA `beforeinstallprompt` + `appinstalled`
 * events.
 *
 * Returns `{ installPrompt, pwaInstalled, installApp }`:
 *  - `installPrompt` -- the deferred event, or null until the browser fires
 *    `beforeinstallprompt`.
 *  - `pwaInstalled` -- true once the OS reports `appinstalled`.
 *  - `installApp()` -- call to show the native install dialog. If no
 *    deferred prompt is available (e.g. iOS Safari), navigates to
 *    `/install.html` with manual install steps.
 *
 * `onStatus` is an optional callback the hook fires with human-readable
 * status strings (e.g. "App installed", "Installing app", "Install
 * dismissed") so the parent can surface them in its status panel.
 */

import { useCallback, useEffect, useState } from 'react';

export default function useInstallPrompt({ onStatus } = {}) {
  const [installPrompt, setInstallPrompt] = useState(null);
  const [pwaInstalled, setPwaInstalled] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    const handleInstalled = () => {
      setPwaInstalled(true);
      setInstallPrompt(null);
      onStatus?.('App installed');
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, [onStatus]);

  const installApp = useCallback(async () => {
    if (!installPrompt) {
      window.location.href = '/install.html';
      return;
    }
    installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    setInstallPrompt(null);
    onStatus?.(choice.outcome === 'accepted' ? 'Installing app' : 'Install dismissed');
  }, [installPrompt, onStatus]);

  return { installPrompt, pwaInstalled, installApp };
}
