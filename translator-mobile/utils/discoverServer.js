import Constants from "expo-constants";
import { getConsumerCloudApiUrl } from "../constants/consumerCloud";

const METRO_PORTS = ["8082", "8081", "19000"];

function normalizeUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function parseHostname(raw) {
  const value = String(raw || "").trim();
  if (!value) return "";
  const withoutScheme = value.replace(/^exp:\/\//, "").replace(/^https?:\/\//, "");
  const hostPort = withoutScheme.split("/")[0] || "";
  const hostname = hostPort.split(":")[0] || "";
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1") return "";
  return hostname;
}

function isUsableBackendUrl(url) {
  const normalized = normalizeUrl(url);
  if (!normalized) return false;
  return !/localhost|127\.0\.0\.1/i.test(normalized);
}

export function isOffLanBackendHost(hostname) {
  const host = String(hostname || "").trim();
  if (!host) return false;
  return !/^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.|localhost|127\.)/i.test(host);
}

export function isOffLanBackendUrl(url) {
  try {
    return isOffLanBackendHost(new URL(normalizeUrl(url)).hostname);
  } catch {
    return false;
  }
}

/** Headers required by some tunnel providers (loca.lt interstitial, ngrok browser warning). */
export function tunnelFetchHeaders(url) {
  const headers = { Accept: "application/json" };
  try {
    const host = new URL(normalizeUrl(url)).hostname;
    if (/\.loca\.lt$/i.test(host)) {
      headers["Bypass-Tunnel-Reminder"] = "true";
    }
    if (/ngrok-free\.app|ngrok\.io|ngrok\.app/i.test(host)) {
      headers["ngrok-skip-browser-warning"] = "true";
    }
  } catch {
    // Ignore malformed URLs.
  }
  return headers;
}

export function deriveBackendPortFromEnv(fallback = "8000") {
  const candidates = [
    process.env.EXPO_PUBLIC_API_URL,
    process.env.EXPO_PUBLIC_TUNNEL_API_URL,
  ];
  for (const raw of candidates) {
    try {
      const port = new URL(normalizeUrl(raw)).port;
      if (port) return port;
    } catch {
      // Try next candidate.
    }
  }
  return String(fallback || "8000");
}

export function deriveLanBackendUrl(hostname) {
  const host = String(hostname || "").trim();
  if (!host || isOffLanBackendHost(host)) return "";
  const port = deriveBackendPortFromEnv();
  return `http://${host}:${port}`;
}

/** LAN hostname from the active Expo Go / Metro session (works when env URL is stale). */
export function deriveLanHostFromExpo() {
  const candidates = [
    Constants.expoGoConfig?.debuggerHost,
    Constants.expoConfig?.hostUri,
    Constants.linkingUri,
    Constants.manifest2?.extra?.expoClient?.hostUri,
  ];
  for (const raw of candidates) {
    const hostname = parseHostname(raw);
    if (hostname) return hostname;
  }
  return "";
}

/** Backend API URL: prefer live Expo session LAN host over a stale baked-in env IP. */
export function deriveApiUrlFromExpo(fallback = "") {
  const envUrl = normalizeUrl(process.env.EXPO_PUBLIC_API_URL || fallback || "");
  if (envUrl && isUsableBackendUrl(envUrl) && isOffLanBackendUrl(envUrl)) {
    return envUrl;
  }
  const hostname = deriveLanHostFromExpo();
  const sessionUrl = deriveLanBackendUrl(hostname);
  if (sessionUrl && isUsableBackendUrl(sessionUrl)) {
    if (!envUrl || !isUsableBackendUrl(envUrl)) {
      return sessionUrl;
    }
    try {
      const envHost = new URL(envUrl).hostname;
      if (hostname && envHost !== hostname) {
        return sessionUrl;
      }
    } catch {
      return sessionUrl;
    }
  }
  if (envUrl && isUsableBackendUrl(envUrl)) {
    return envUrl;
  }
  return sessionUrl || envUrl;
}

export function deriveMetroProbeUrls(hostname = deriveLanHostFromExpo(), preferredPort = "") {
  if (!hostname) return [];
  const ports = [];
  const preferred = String(preferredPort || "").trim();
  if (preferred) ports.push(preferred);
  for (const port of METRO_PORTS) {
    if (!ports.includes(port)) ports.push(port);
  }
  return ports.map((port) => `http://${hostname}:${port}`);
}

export function deriveExpoUrlFromInfo(hostname, info) {
  const fromInfo = String(info?.expo_url || "").trim();
  if (fromInfo) return fromInfo;
  const host = hostname || deriveLanHostFromExpo();
  if (!host) return "";
  const port = Number(info?.expo_port) || 8082;
  return `exp://${host}:${port}`;
}

async function fetchMobileConnectInfoOnce(apiBase, timeoutMs = 10000) {
  const base = normalizeUrl(apiBase);
  if (!base || !isUsableBackendUrl(base)) return null;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}/mobile/info`, {
      method: "GET",
      cache: "no-store",
      headers: tunnelFetchHeaders(base),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const data = await response.json();
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchMobileConnectInfo(apiBase, options = {}) {
  const base = normalizeUrl(apiBase);
  const shouldAbort = options.shouldAbort;
  if (typeof shouldAbort === "function" && shouldAbort()) return null;
  const first = await fetchMobileConnectInfoOnce(base);
  if (typeof shouldAbort === "function" && shouldAbort()) return null;
  if (first) return first;
  const tunnel = normalizeUrl(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "");
  if (tunnel && tunnel !== base && isUsableBackendUrl(tunnel)) {
    if (typeof shouldAbort === "function" && shouldAbort()) return null;
    const tunnelInfo = await fetchMobileConnectInfoOnce(tunnel);
    if (typeof shouldAbort === "function" && shouldAbort()) return null;
    if (tunnelInfo) return tunnelInfo;
  }
  const continued = await sleepWithAbort(800, shouldAbort);
  if (!continued) return null;
  const retry = await fetchMobileConnectInfoOnce(base, 8000);
  if (typeof shouldAbort === "function" && shouldAbort()) return null;
  if (retry) return retry;
  if (tunnel && tunnel !== base && isUsableBackendUrl(tunnel)) {
    if (typeof shouldAbort === "function" && shouldAbort()) return null;
    const retryTunnel = await fetchMobileConnectInfoOnce(tunnel, 8000);
    if (typeof shouldAbort === "function" && shouldAbort()) return null;
    return retryTunnel;
  }
  return null;
}

export async function probeMetroBundleSignature(hostname = deriveLanHostFromExpo(), preferredPort = "", options = {}) {
  const shouldAbort = options.shouldAbort;
  const minBytes = Math.max(2_000_000, Number(options.minBytes) || 2_000_000);
  const maxAttempts = Math.max(1, Number(options.maxAttempts) || 3);
  const delayMs = Math.max(0, Number(options.delayMs) || 1500);
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (typeof shouldAbort === "function" && shouldAbort()) return false;
    for (const base of deriveMetroProbeUrls(hostname, preferredPort)) {
      if (typeof shouldAbort === "function" && shouldAbort()) return false;
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const response = await fetch(`${base}/.anai/bundle-ready`, {
          method: "GET",
          cache: "no-store",
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) continue;
        const text = String(await response.text() || "").trim();
        const match = text.match(/^1:(\d+)/);
        if (match && Number(match[1]) >= minBytes) return true;
      } catch {
        // Try next Metro port.
      }
    }
    if (attempt < maxAttempts - 1) {
      const continued = await sleepWithAbort(delayMs, shouldAbort);
      if (!continued) return false;
    }
  }
  return false;
}

export async function probeMetroBundleReady(hostname = deriveLanHostFromExpo(), preferredPort = "", options = {}) {
  const shouldAbort = options.shouldAbort;
  const maxAttempts = Math.max(1, Number(options.maxAttempts) || 12);
  const delayMs = Math.max(0, Number(options.delayMs) || 2500);
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (typeof shouldAbort === "function" && shouldAbort()) return false;
    for (const base of deriveMetroProbeUrls(hostname, preferredPort)) {
      if (typeof shouldAbort === "function" && shouldAbort()) return false;
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const response = await fetch(`${base}/.anai/bundle-ready`, {
          method: "GET",
          cache: "no-store",
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) continue;
        const text = String(await response.text() || "").trim();
        const ready = text === "1" || /^1:\d+(?::\d+)?$/.test(text);
        const byteMatch = text.match(/^1:(\d+)/);
        const bytes = byteMatch ? Number(byteMatch[1]) : 0;
        if (typeof options.onProgress === "function") {
          options.onProgress({ ready, bytes, attempt });
        }
        if (ready) return true;
      } catch {
        // Try next Metro port.
      }
    }
    if (typeof options.onProgress === "function") {
      options.onProgress({ ready: false, bytes: 0, attempt });
    }
    if (attempt < maxAttempts - 1) {
      const continued = await sleepWithAbort(delayMs, shouldAbort);
      if (!continued) return false;
    }
  }
  return false;
}

export async function probeMetroBuildId(hostname = deriveLanHostFromExpo(), preferredPort = "", options = {}) {
  const shouldAbort = options.shouldAbort;
  for (const base of deriveMetroProbeUrls(hostname, preferredPort)) {
    if (typeof shouldAbort === "function" && shouldAbort()) return null;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const response = await fetch(`${base}/.anai/build-id`, {
        method: "GET",
        cache: "no-store",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (!response.ok) continue;
      const buildId = String(await response.text() || "").trim();
      if (buildId) return { buildId, metroBase: base };
    } catch {
      // Try next Metro port.
    }
  }
  return null;
}

export async function checkBackendHealthUrl(apiBase, options = {}) {
  const shouldAbort = options.shouldAbort;
  if (typeof shouldAbort === "function" && shouldAbort()) return false;
  const base = normalizeUrl(apiBase);
  if (!base || !isUsableBackendUrl(base)) return false;
  const timeoutMs = Number(options.timeoutMs)
    || (isOffLanBackendUrl(base) ? 6000 : 10000);
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const response = await fetch(`${base}/health`, {
      method: "GET",
      cache: "no-store",
      headers: tunnelFetchHeaders(base),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (controller.signal.aborted) return false;
    if (!response.ok) return false;
    if (options.requireReady) {
      try {
        const payload = await response.json();
        if (typeof shouldAbort === "function" && shouldAbort()) return false;
        return payload?.ready !== false;
      } catch {
        return true;
      }
    }
    return true;
  } catch {
    return false;
  }
}

async function sleepWithAbort(ms, shouldAbort) {
  const stepMs = 250;
  let elapsed = 0;
  while (elapsed < ms) {
    if (typeof shouldAbort === "function" && shouldAbort()) {
      return false;
    }
    const chunkMs = Math.min(stepMs, ms - elapsed);
    await new Promise((resolve) => setTimeout(resolve, chunkMs));
    elapsed += chunkMs;
  }
  return true;
}

/** Poll /health until ready:true (or timeout). Avoids predictable WS close 1013 during warmup. */
export async function waitForBackendReady(apiBase, options = {}) {
  const base = normalizeUrl(apiBase);
  if (!base || !isUsableBackendUrl(base)) return false;
  const maxAttempts = Number(options.maxAttempts) || 15;
  const delayMs = Number(options.delayMs) || 1500;
  const shouldAbort = options.shouldAbort;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (typeof shouldAbort === "function" && shouldAbort()) {
      return false;
    }
    const ready = await checkBackendHealthUrl(base, {
      timeoutMs: options.timeoutMs || 8000,
      requireReady: true,
      shouldAbort,
    });
    if (ready) return true;
    if (attempt < maxAttempts - 1) {
      const continued = await sleepWithAbort(delayMs, shouldAbort);
      if (!continued) return false;
    }
  }
  return false;
}

async function collectBackendCandidates(fallback = "", options = {}) {
  const shouldAbort = options.shouldAbort;
  const hostname = deriveLanHostFromExpo();
  const candidates = [];
  const seen = new Set();

  const addCandidate = (url) => {
    const normalized = normalizeUrl(url);
    if (!isUsableBackendUrl(normalized) || seen.has(normalized)) return;
    seen.add(normalized);
    candidates.push(normalized);
  };

  const cloudUrl = getConsumerCloudApiUrl();
  if (cloudUrl) addCandidate(cloudUrl);

  if (hostname) {
    const lanUrl = deriveLanBackendUrl(hostname);
    if (lanUrl) addCandidate(lanUrl);
  }
  addCandidate(deriveApiUrlFromExpo(fallback));
  const bakedUrl = normalizeUrl(process.env.EXPO_PUBLIC_API_URL || fallback || "");
  if (bakedUrl) addCandidate(bakedUrl);
  const tunnelBaked = normalizeUrl(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "");
  if (tunnelBaked) addCandidate(tunnelBaked);

  const probeBases = [];
  const probeSeen = new Set();
  const addProbeBase = (url) => {
    const normalized = normalizeUrl(url);
    if (!isUsableBackendUrl(normalized) || probeSeen.has(normalized)) return;
    probeSeen.add(normalized);
    probeBases.push(normalized);
  };
  if (tunnelBaked) addProbeBase(tunnelBaked);
  for (const url of candidates) {
    addProbeBase(url);
    if (probeBases.length >= 6) break;
  }
  if (typeof shouldAbort === "function" && shouldAbort()) {
    return { candidates, hostname };
  }
  const infoResults = await Promise.allSettled(
    probeBases.map((base) => fetchMobileConnectInfo(base, { shouldAbort })),
  );
  for (const result of infoResults) {
    if (result.status !== "fulfilled" || !result.value) continue;
    const info = result.value;
    if (info?.backend_url) addCandidate(info.backend_url);
    const infoTunnel = normalizeUrl(info?.tunnel_backend_url || "");
    if (infoTunnel) addCandidate(infoTunnel);
  }

  const healthyTunnelChecks = await Promise.all(
    candidates
      .filter((url) => isOffLanBackendUrl(url))
      .map(async (url) => ({
        url,
        healthy: await checkBackendHealthUrl(url, { timeoutMs: 5000, requireReady: true }),
      })),
  );
  for (const { url, healthy } of healthyTunnelChecks) {
    if (!healthy) {
      const index = candidates.indexOf(url);
      if (index >= 0) candidates.splice(index, 1);
    }
  }

  return { candidates, hostname };
}

/** Resolve the best backend URL for this phone session. */
export async function resolveServerUrl(fallback = "", options = {}) {
  const preferOffLan = Boolean(options.preferOffLan);
  const shouldAbort = options.shouldAbort;
  if (typeof shouldAbort === "function" && shouldAbort()) {
    const hintUrl = deriveApiUrlFromExpo(fallback);
    return {
      apiUrl: hintUrl,
      healthy: false,
      mobileInfo: null,
      hostname: deriveLanHostFromExpo(),
    };
  }
  const { candidates, hostname } = await collectBackendCandidates(fallback, { shouldAbort });

  const preferCloud = Boolean(options.preferCloud);
  const cloudFirst = getConsumerCloudApiUrl();
  let orderedCandidates = preferOffLan
    ? [
      ...candidates.filter((url) => isOffLanBackendUrl(url)),
      ...candidates.filter((url) => !isOffLanBackendUrl(url)),
    ]
    : [...candidates];
  if (preferCloud && cloudFirst) {
    orderedCandidates = [
      cloudFirst,
      ...orderedCandidates.filter((url) => normalizeUrl(url) !== cloudFirst),
    ];
  }

  let healthResults;
  if (preferOffLan) {
    healthResults = [];
    for (const apiUrl of orderedCandidates) {
      if (typeof shouldAbort === "function" && shouldAbort()) break;
      const healthy = await checkBackendHealthUrl(
        apiUrl,
        isOffLanBackendUrl(apiUrl)
          ? { timeoutMs: 5000, requireReady: true }
          : { timeoutMs: 4000, requireReady: true },
      );
      healthResults.push({ apiUrl, healthy });
      if (healthy && isOffLanBackendUrl(apiUrl)) break;
    }
  } else {
    healthResults = [];
    for (const apiUrl of orderedCandidates) {
      if (typeof shouldAbort === "function" && shouldAbort()) break;
      const healthy = await checkBackendHealthUrl(apiUrl, { requireReady: true });
      healthResults.push({ apiUrl, healthy });
    }
  }

  for (const { apiUrl, healthy } of healthResults) {
    if (!healthy) continue;
    if (typeof shouldAbort === "function" && shouldAbort()) break;
    const mobileInfo = await fetchMobileConnectInfo(apiUrl, { shouldAbort });
    if (typeof shouldAbort === "function" && shouldAbort()) break;
    return {
      apiUrl,
      healthy: true,
      mobileInfo,
      hostname,
    };
  }

  const hintUrl = candidates[0] || deriveApiUrlFromExpo(fallback);
  if (typeof shouldAbort === "function" && shouldAbort()) {
    return {
      apiUrl: hintUrl,
      healthy: false,
      mobileInfo: null,
      hostname,
    };
  }
  const mobileInfo = hintUrl ? await fetchMobileConnectInfo(hintUrl, { shouldAbort }) : null;
  return {
    apiUrl: hintUrl,
    healthy: false,
    mobileInfo,
    hostname,
  };
}
