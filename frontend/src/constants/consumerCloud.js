/** Consumer path: same-origin hosted deploy (Railway) needs no extra API config. */
export const CONSUMER_OPEN_AND_GO = true;

export function getConsumerCloudApiUrl() {
  const configured = String(import.meta.env.VITE_CLOUD_API_URL || "").trim().replace(/\/+$/, "");
  if (configured.startsWith("http://") || configured.startsWith("https://")) {
    return configured;
  }
  return "";
}

export function hasConsumerCloudBackend() {
  return Boolean(getConsumerCloudApiUrl());
}
