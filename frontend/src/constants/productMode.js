/** Main web interpreter: mic, languages, transcript, translation only unless debug is on. */
export const FOCUSED_PRODUCT_UI = true;

export function showAdvancedInterpreterChrome(debugMode = false) {
  return !FOCUSED_PRODUCT_UI || Boolean(debugMode);
}
