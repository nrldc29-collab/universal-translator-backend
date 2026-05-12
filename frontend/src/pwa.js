const SW_VERSION = 'v14-speaker-room';
const SW_RELOAD_KEY = `translator_sw_reloaded_${SW_VERSION}`;

function reloadForUpdatedServiceWorker() {
  if (sessionStorage.getItem(SW_RELOAD_KEY) === '1') return;
  sessionStorage.setItem(SW_RELOAD_KEY, '1');
  window.location.reload();
}

function activateWaitingWorker(registration) {
  if (registration.waiting) {
    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
  }
}

export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    reloadForUpdatedServiceWorker();
  });

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        registration.update().catch(() => {});
        activateWaitingWorker(registration);
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing;
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) {
              activateWaitingWorker(registration);
            }
          });
        });
      })
      .catch(() => {});
  });
}
