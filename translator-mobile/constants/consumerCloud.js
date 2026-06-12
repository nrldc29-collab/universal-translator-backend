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

/** Hosted bridge URL baked into production builds (Railway, etc.). */
export function getConsumerCloudApiUrl() {
  const fromEnv = normalizeUrl(process.env.EXPO_PUBLIC_CLOUD_API_URL || "");
  if (isHttpUrl(fromEnv)) return fromEnv;
  const fromExtra = normalizeUrl(Constants.expoConfig?.extra?.cloudApiUrl || "");
  if (isHttpUrl(fromExtra)) return fromExtra;
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

export function getConsumerDemoCredentials() {
  return {
    username:
      process.env.EXPO_PUBLIC_CLOUD_DEMO_USER
      || Constants.expoConfig?.extra?.cloudDemoUser
      || "demo",
    password:
      process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS
      || Constants.expoConfig?.extra?.cloudDemoPass
      || "demo",
  };
}
