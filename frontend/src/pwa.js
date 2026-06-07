const SW_VERSION = 'v42-tap-once';
const SW_RELOAD_KEY = `translator_sw_reloaded_${SW_VERSION}`;

function reloadForUpdatedServiceWorker() {
  if (sessionStorage.getItem(SW_RELOAD_KEY) === '1') return;
  sessionStorage.setItem(SW_RELOAD_KEY, '1');
  window.location.reload();
}

/**
 * Service worker disabled while speech-first UX stabilizes.
 * Stale cached CSS was causing the old upward language menu and choppy layout.
 */
export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;

  navigator.serviceWorker.getRegistrations()
    .then((regs) => Promise.all(regs.map((reg) => reg.unregister())))
    .catch(() => {});

  if ('caches' in window) {
    caches.keys()
      .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
      .catch(() => {});
  }
}
