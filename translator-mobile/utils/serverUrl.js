export function isLocalLanServerUrl(url) {
  try {
    const parsed = new URL(String(url || "").trim());
    const host = parsed.hostname;
    if (host === "localhost" || host === "127.0.0.1") return false;
    return (
      host.startsWith("192.168.") ||
      host.startsWith("10.") ||
      /^172\.(1[6-9]|2\d|3[0-1])\./.test(host)
    );
  } catch {
    return false;
  }
}

const CELLULAR_NETWORK_TYPES = new Set([
  "CELLULAR",
  "MOBILE",
  "2G",
  "3G",
  "4G",
  "5G",
]);

export function isPhoneOnWifi(networkState) {
  const type = String(networkState?.type || "").toUpperCase();
  return type === "WIFI" || type === "ETHERNET";
}

export function isNetworkTypeKnown(networkState) {
  const type = String(networkState?.type || "").toUpperCase();
  return Boolean(type && type !== "UNKNOWN");
}

/** LAN server URLs only work when the phone shares Wi‑Fi with the PC (not cellular). */
export function needsWifiForLanServer(networkState, url) {
  if (!isLocalLanServerUrl(url)) return false;
  if (networkState?.isConnected === false) return false;
  if (isPhoneOnWifi(networkState)) return false;
  const type = String(networkState?.type || "").toUpperCase();
  if (!type || type === "UNKNOWN") return false;
  return CELLULAR_NETWORK_TYPES.has(type);
}
