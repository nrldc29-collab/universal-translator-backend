/**
 * SystemBanners -- update-available and reconnect-toast banners shown at
 * the top of the app shell.
 */

import React from 'react';
import {
  AlertTriangle,
  Download,
  Mic,
  RefreshCw,
  Smartphone,
  WifiOff,
  X,
} from 'lucide-react';

async function reloadForUpdate() {
  try {
    const regs = await (
      navigator.serviceWorker &&
      navigator.serviceWorker.getRegistrations &&
      navigator.serviceWorker.getRegistrations()
    );
    if (regs) {
      regs.forEach((r) => r.waiting && r.waiting.postMessage({ type: 'SKIP_WAITING' }));
    }
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map((name) => caches.delete(name)));
  } catch (err) {
    console.warn('cache clear failed', err);
  }
  window.location.reload();
}

function BannerBody({ icon: Icon, iconClass, children }) {
  return (
    <div className="banner-body">
      {Icon ? <Icon size={16} strokeWidth={2.2} className={`banner-icon ${iconClass || ''}`} aria-hidden="true" /> : null}
      <span>{children}</span>
    </div>
  );
}

export default function SystemBanners({
  updateAvailable,
  reconnectToastVisible,
  onReconnectRetry,
  onDismissReconnect,
  connectionStatus,
  offlineBannerDismissed,
  onDismissOffline,
  onOfflineRetry,
  micPermission,
  micBannerDismissed,
  onDismissMicBanner,
  onRequestMic,
  showInstallNudge,
  installNudgeDismissed,
  onDismissInstallNudge,
  onInstallApp,
  onOpenSettings,
  showIosMicHint,
  iosMicHintDismissed,
  onDismissIosMicHint,
}) {
  const showOfflineBanner =
    connectionStatus === 'offline' &&
    !reconnectToastVisible &&
    !offlineBannerDismissed;

  const showMicBanner =
    micPermission === 'denied' &&
    !micBannerDismissed;

  return (
    <>
      {showMicBanner && (
        <div className="system-banner warning" role="alert">
          <BannerBody icon={Mic} iconClass="warning">
            Microphone access is blocked. Allow the mic to open the conversation bridge.
          </BannerBody>
          <div className="banner-actions">
            <button
              type="button"
              className="banner-dismiss"
              aria-label="Dismiss"
              onClick={onDismissMicBanner}
            >
              <X size={14} strokeWidth={2.5} />
            </button>
            <button type="button" className="banner-action" onClick={onRequestMic}>
              Allow mic
            </button>
          </div>
        </div>
      )}
      {showOfflineBanner && (
        <div className="system-banner warning" role="alert">
          <BannerBody icon={WifiOff} iconClass="warning">
            Can&apos;t reach the bridge server.
          </BannerBody>
          <div className="banner-actions">
            <button
              type="button"
              className="banner-dismiss"
              aria-label="Dismiss"
              onClick={onDismissOffline}
            >
              <X size={14} strokeWidth={2.5} />
            </button>
            {onOpenSettings && (
              <button type="button" className="banner-action" onClick={onOpenSettings}>
                Settings
              </button>
            )}
            <button type="button" className="banner-action" onClick={onOfflineRetry}>
              Retry
            </button>
          </div>
        </div>
      )}
      {showInstallNudge && !installNudgeDismissed && (
        <div className="system-banner install" role="status">
          <BannerBody icon={Download} iconClass="install">
            Install Anai for faster bridge access and offline-ready shortcuts.
          </BannerBody>
          <div className="banner-actions">
            <button
              type="button"
              className="banner-dismiss"
              aria-label="Dismiss"
              onClick={onDismissInstallNudge}
            >
              <X size={14} strokeWidth={2.5} />
            </button>
            <button type="button" className="banner-action" onClick={onInstallApp}>
              Install
            </button>
          </div>
        </div>
      )}
      {showIosMicHint && !iosMicHintDismissed && (
        <div className="system-banner info" role="status">
          <BannerBody icon={Smartphone} iconClass="info">
            On iPhone and iPad: tap the mic once to start, tap again to stop.
          </BannerBody>
          <div className="banner-actions">
            <button type="button" className="banner-dismiss" aria-label="Dismiss" onClick={onDismissIosMicHint}>
              <X size={14} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      )}
      {updateAvailable && (
        <div className="system-banner" role="alert">
          <BannerBody icon={RefreshCw} iconClass="update">
            A new version is available.
          </BannerBody>
          <button type="button" className="banner-action" onClick={reloadForUpdate}>
            Reload
          </button>
        </div>
      )}
      {reconnectToastVisible && (
        <div className="system-banner danger" role="alert">
          <BannerBody icon={AlertTriangle} iconClass="danger">
            Connection lost — tap to relink the bridge.
          </BannerBody>
          <div className="banner-actions">
            <button
              type="button"
              className="banner-dismiss"
              aria-label="Dismiss"
              onClick={onDismissReconnect}
            >
              <X size={14} strokeWidth={2.5} />
            </button>
            <button
              type="button"
              className="banner-action"
              onClick={() => {
                onDismissReconnect?.();
                onReconnectRetry?.();
              }}
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </>
  );
}
