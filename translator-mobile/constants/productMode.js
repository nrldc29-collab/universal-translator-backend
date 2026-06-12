/** When true, main screen shows only title, languages, mic, transcript, and translation (README design rule). */
export const FOCUSED_PRODUCT_UI = true;

/** Advanced panels (duplex rail, flow steps, history) — settings / debug only when focused. */
export function showAdvancedInterpreterChrome(showDebugDetails = false) {
  return !FOCUSED_PRODUCT_UI || Boolean(showDebugDetails);
}
