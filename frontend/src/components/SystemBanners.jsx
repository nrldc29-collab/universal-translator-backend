/**
 * SystemBanners — update-available and reconnect-toast banners shown at
 * the top of the app shell. Pulled out of `main.jsx` so the App component
 * doesn't carry the inline event handlers.
 */

import React from 'react';

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

export default function SystemBanners({
  updateAvailable,
  reconnectToastVisible,
  onReconnectRetry,
  onDismissReconnect,
}) {
  return (
    <>
      {updateAvailable && (
        <div className="system-banner" role="alert">
          <span>
            Update available <code>{updateAvailable.backend}</code>
          </span>
          <button type="button" onClick={reloadForUpdate}>
            Reload
          </button>
        </div>
      )}
      {reconnectToastVisible && (
        <div className="system-banner danger" role="alert">
          <span>Connection lost. Retry?</span>
          <button
            type="button"
            onClick={() => {
              onDismissReconnect?.();
              onReconnectRetry?.();
            }}
          >
            Retry
          </button>
        </div>
      )}
    </>
  );
}
