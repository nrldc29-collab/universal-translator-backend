import Constants from "expo-constants";

/** Consumer App Store path: connect to hosted Anai cloud without LAN/PC setup. */
export const CONSUMER_OPEN_AND_GO = true;

function normalizeUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function isHttpUrl(url) {
  const value = normalizeUrl(url);
  return value.startsWith("http://") || value.startsWith("https://");
}

let discoveredConsumerCloudUrl = "";

/** Remember cloud URL from /mobile/info (hosted deploy advertises itself). */
export function rememberDiscoveredConsumerCloudUrl(url) {
  const normalized = normalizeUrl(url);
  if (isHttpUrl(normalized)) {
    discoveredConsumerCloudUrl = normalized;
  }
}

function isHttpsCloudUrl(url) {
  return normalizeUrl(url).startsWith("https://");
}

/** Hosted bridge URL baked into production builds (Railway, etc.). */
export function getConsumerCloudApiUrl() {
  const fromEnv = normalizeUrl(process.env.EXPO_PUBLIC_CLOUD_API_URL || "");
  if (isHttpUrl(fromEnv)) return fromEnv;
  const fromApiEnv = normalizeUrl(process.env.EXPO_PUBLIC_API_URL || "");
  if (isHttpsCloudUrl(fromApiEnv)) return fromApiEnv;
  const fromExtra = normalizeUrl(Constants.expoConfig?.extra?.cloudApiUrl || "");
  if (isHttpUrl(fromExtra)) return fromExtra;
  if (isHttpUrl(discoveredConsumerCloudUrl)) return discoveredConsumerCloudUrl;
  return "";
}

export function hasConsumerCloudBackend() {
  return Boolean(getConsumerCloudApiUrl());
}

export function isConsumerCloudUrl(url) {
  const cloud = getConsumerCloudApiUrl();
  if (!cloud) return false;
  return normalizeUrl(url) === cloud;
}

function readCredential(candidates, fallback = "") {
  for (const raw of candidates) {
    if (raw === undefined || raw === null) continue;
    const trimmed = String(raw).trim();
    if (trimmed) return trimmed;
  }
  return fallback;
}

export function getConsumerDemoCredentials() {
  return {
    username: readCredential(
      [process.env.EXPO_PUBLIC_CLOUD_DEMO_USER, Constants.expoConfig?.extra?.cloudDemoUser],
      "demo",
    ),
    password: readCredential(
      [process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS, Constants.expoConfig?.extra?.cloudDemoPass],
      "",
    ),
  };
}

export function hasConsumerDemoCredentials() {
  const { password } = getConsumerDemoCredentials();
  return Boolean(String(password || "").trim());
}
