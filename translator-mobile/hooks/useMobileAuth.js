import { useEffect, useState } from "react";
import * as SecureStore from "expo-secure-store";
import { bridgeServerStatusMessages } from "../constants/productVoice";
import {
  getConsumerCloudApiUrl,
  getConsumerDemoCredentials,
  hasConsumerCloudBackend,
} from "../constants/consumerCloud";
import {
  checkBackendHealthUrl,
  deriveApiUrlFromExpo,
  isOffLanBackendHost,
  resolveServerUrl,
  tunnelFetchHeaders,
} from "../utils/discoverServer";

let activeLoginAbort = null;
let activeDiscoveryGeneration = 0;
let activeHealthCheckGeneration = 0;

export function cancelLogin() {
  activeHealthCheckGeneration += 1;
  if (activeLoginAbort) {
    activeLoginAbort.abort();
    activeLoginAbort = null;
  }
}

export function cancelDiscovery() {
  activeDiscoveryGeneration += 1;
  activeHealthCheckGeneration += 1;
}

const TOKEN_KEY = "translator_token";
const WS_URL_KEY = "translator_ws_url";
const SETUP_COMPLETE_KEY = "translator_setup_complete";
const RECENT_URLS_KEY = "recent_urls";
const MAX_RECENT_URLS = 5;

export function validateServerUrl(url) {
  try {
    const trimmed = String(url || "").trim();
    if (!trimmed) return false;
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) return false;
    const parsed = new URL(trimmed);
    if (!parsed.hostname) return false;
    if (/^(localhost|127\.0\.0\.1)$/i.test(parsed.hostname)) return false;
    return true;
  } catch {
    return false;
  }
}

export function isJwtExpired(token) {
  try {
    const parts = String(token || "").split(".");
    if (parts.length < 2) return false;
    const payloadJson = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(payloadJson);
    const exp = Number(payload.exp);
    if (!Number.isFinite(exp) || exp <= 0) return false;
    return Date.now() >= exp * 1000;
  } catch {
    return false;
  }
}

export function useMobileAuth({ defaultUrl = "", onStatus }) {
  const [token, setToken] = useState("");
  const demoCreds = getConsumerDemoCredentials();
  const [username, setUsername] = useState(demoCreds.username);
  const [password, setPassword] = useState(demoCreds.password);
  const [wsUrl, setWsUrl] = useState(defaultUrl);
  const [recentUrls, setRecentUrls] = useState([]);
  const [showRecentUrls, setShowRecentUrls] = useState(false);
  const [backendReachable, setBackendReachable] = useState(null);
  const [setupComplete, setSetupComplete] = useState(false);
  const [discoveryComplete, setDiscoveryComplete] = useState(false);
  const [isCheckingBackend, setIsCheckingBackend] = useState(false);
  const validateUrl = validateServerUrl;

  useEffect(() => () => {
    cancelLogin();
    cancelDiscovery();
  }, []);

  function normalizeUrl(url) {
    return String(url || "").trim().replace(/\/+$/, "");
  }

  async function loadStoredData() {
    const discoveryGen = activeDiscoveryGeneration;
    const discoveryStale = () => discoveryGen !== activeDiscoveryGeneration;
    try {
      const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
      const storedUrlEarly = normalizeUrl(await SecureStore.getItemAsync(WS_URL_KEY));
      const bootstrapUrl = normalizeUrl(defaultUrl);
      const cloudUrl = getConsumerCloudApiUrl();
      const trustedBootstrap = validateUrl(bootstrapUrl);
      let envUrl = trustedBootstrap ? bootstrapUrl : "";
      if (!validateUrl(envUrl) && !storedUrlEarly && cloudUrl) {
        envUrl = cloudUrl;
      }
      if (!validateUrl(envUrl)) {
        envUrl = normalizeUrl(deriveApiUrlFromExpo());
      } else {
        const preferred = normalizeUrl(deriveApiUrlFromExpo(envUrl));
        if (preferred && validateUrl(preferred)) {
          envUrl = preferred;
        }
      }
      let skipHeavyDiscovery = false;
      if (trustedBootstrap) {
        envUrl = bootstrapUrl;
        try {
          const quickReady = await checkBackendHealthUrl(bootstrapUrl, {
            timeoutMs: 5000,
            requireReady: true,
          });
          setBackendReachable(quickReady ? true : null);
          skipHeavyDiscovery = quickReady;
        } catch {
          setBackendReachable(null);
        }
      }
      if (!skipHeavyDiscovery && envUrl && validateUrl(envUrl)) {
        try {
          let resolved = await resolveServerUrl(envUrl, {
            preferCloud: hasConsumerCloudBackend(),
            shouldAbort: discoveryStale,
          });
          if (discoveryStale()) return;
          if (!resolved?.healthy) {
            const tunnelResolved = await resolveServerUrl(envUrl, {
              preferOffLan: true,
              preferCloud: hasConsumerCloudBackend(),
              shouldAbort: discoveryStale,
            });
            if (discoveryStale()) return;
            if (tunnelResolved?.healthy) {
              resolved = tunnelResolved;
            }
          }
          const tunnelBaked = normalizeUrl(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "");
          if (!resolved?.healthy && tunnelBaked && validateUrl(tunnelBaked)) {
            const tunnelHealthy = await checkBackendHealthUrl(tunnelBaked, {
              timeoutMs: 6000,
              requireReady: true,
            });
            if (discoveryStale()) return;
            if (tunnelHealthy) {
              resolved = { apiUrl: tunnelBaked, healthy: true, mobileInfo: null, hostname: "" };
            }
          }
          if (resolved?.healthy && resolved?.apiUrl && validateUrl(resolved.apiUrl)) {
            envUrl = normalizeUrl(resolved.apiUrl);
          }
          if (discoveryStale()) return;
          if (resolved?.healthy) {
            setBackendReachable(true);
          } else if (resolved?.apiUrl) {
            setBackendReachable(false);
          }
        } catch (error) {
          if (discoveryStale()) return;
          console.error("Server discovery failed:", error);
          setBackendReachable(await checkBackendHealthUrl(envUrl));
        }
      }
      if (discoveryStale()) return;
      const storedUrl = storedUrlEarly;
      let envChanged = false;
      // Prefer the baked-in Expo env URL when it changes (e.g. Start-MobilePhoneMode.ps1 refreshed LAN IP).
      if (envUrl && validateUrl(envUrl)) {
        envChanged = Boolean(storedUrl && storedUrl !== envUrl);
        setWsUrl(envUrl);
        if (!storedUrl || envChanged) {
          await SecureStore.setItemAsync(WS_URL_KEY, envUrl);
          if (envChanged) {
            setBackendReachable(null);
            await SecureStore.deleteItemAsync(TOKEN_KEY);
          }
        }
      } else if (storedUrl && validateUrl(storedUrl)) {
        setWsUrl(storedUrl);
      }
      if (discoveryStale()) return;
      if (storedToken && !envChanged) {
        if (isJwtExpired(storedToken)) {
          setToken("");
          await SecureStore.deleteItemAsync(TOKEN_KEY);
          if (!discoveryStale()) onStatus?.("Session expired — sign in again", "warning");
        } else {
          setToken(storedToken);
          if (!discoveryStale()) onStatus?.("Token restored", "success");
        }
      } else {
        setToken("");
      }
      if (discoveryStale()) return;
      const storedUrls = await SecureStore.getItemAsync(RECENT_URLS_KEY);
      if (storedUrls) {
        try {
          const parsed = JSON.parse(storedUrls);
          setRecentUrls(Array.isArray(parsed) ? parsed : []);
        } catch {
          setRecentUrls([]);
          await SecureStore.deleteItemAsync(RECENT_URLS_KEY);
        }
      }
      const storedSetup = await SecureStore.getItemAsync(SETUP_COMPLETE_KEY);
      const activeUrl = normalizeUrl(
        envUrl && validateUrl(envUrl) ? envUrl : storedUrl && validateUrl(storedUrl) ? storedUrl : "",
      );
      if (storedSetup === "1" || (activeUrl && validateUrl(activeUrl))) {
        setSetupComplete(true);
        if (storedSetup !== "1") {
          await SecureStore.setItemAsync(SETUP_COMPLETE_KEY, "1");
        }
      } else {
        setSetupComplete(false);
      }
    } catch (error) {
      console.error("Error loading stored data:", error);
    } finally {
      if (!discoveryStale()) {
        setDiscoveryComplete(true);
      }
    }
  }

  function editWsUrl(url) {
    setWsUrl(url);
    setBackendReachable(null);
  }

  async function saveWsUrl(url) {
    const trimmed = String(url || "").trim().replace(/\/+$/, "");
    setWsUrl(trimmed);
    if (trimmed) {
      await SecureStore.setItemAsync(WS_URL_KEY, trimmed);
      await saveRecentUrl(trimmed);
    }
  }

  async function markSetupComplete() {
    setSetupComplete(true);
    await SecureStore.setItemAsync(SETUP_COMPLETE_KEY, "1");
  }

  async function saveRecentUrl(url) {
    try {
      const stored = await SecureStore.getItemAsync(RECENT_URLS_KEY);
      const current = stored ? JSON.parse(stored) : [];
      const updated = [url, ...current.filter((u) => u !== url)].slice(0, MAX_RECENT_URLS);
      setRecentUrls(updated);
      await SecureStore.setItemAsync(RECENT_URLS_KEY, JSON.stringify(updated));
    } catch (error) {
      console.error("Error saving recent URL:", error);
    }
  }

  async function checkBackendHealth(url, { quiet = false, shouldAbort } = {}) {
    const checkGen = ++activeHealthCheckGeneration;
    const isStale = () =>
      checkGen !== activeHealthCheckGeneration
      || (typeof shouldAbort === "function" && shouldAbort());
    const target = normalizeUrl(url || wsUrl);
    if (!validateUrl(target)) {
      if (!isStale()) setBackendReachable(false);
      return false;
    }
    if (/localhost|127\.0\.0\.1/i.test(target)) {
      if (!isStale()) setBackendReachable(false);
      if (!quiet) {
        onStatus?.("Use your PC's LAN IP (not localhost) — the phone cannot reach this machine.", "error");
      }
      return false;
    }
    let controller = null;
    try {
      if (!quiet) {
        setIsCheckingBackend(true);
        onStatus?.("Checking server...", "connecting");
      }
      controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 12000);
      let response;
      try {
        response = await fetch(`${target}/health`, {
          method: "GET",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            ...tunnelFetchHeaders(target),
          },
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeoutId);
      }
      if (controller.signal.aborted || isStale()) return false;
      let ready = true;
      if (response.ok) {
        try {
          const payload = await response.json();
          ready = payload?.ready !== false;
        } catch {
          ready = true;
        }
      }
      if (isStale()) return false;
      // Reachable = HTTP response (warming still counts as reachable on LAN).
      setBackendReachable(response.ok);
      if (!quiet) {
        const srv = bridgeServerStatusMessages();
        if (response.ok && ready) {
          onStatus?.(srv.reachable, "success");
        } else if (response.ok && !ready) {
          onStatus?.(srv.warming, "connecting");
        } else {
          onStatus?.(`Bridge server responded with HTTP ${response.status}`, "error");
        }
      }
      return response.ok && ready;
    } catch (error) {
      if (controller?.signal?.aborted || error?.name === "AbortError" || isStale()) {
        return false;
      }
      setBackendReachable(false);
      const message = String(error?.message || error || "");
      if (!quiet) {
        const srv = bridgeServerStatusMessages();
        if (/abort|timeout/i.test(message)) {
          onStatus?.(srv.timeout, "error");
        } else if (/network request failed|failed to fetch|cleartext/i.test(message)) {
          onStatus?.(srv.cannotReachLan, "error");
        } else {
          onStatus?.(srv.cannotReach, "error");
        }
      }
      return false;
    } finally {
      if (!quiet && checkGen === activeHealthCheckGeneration) {
        setIsCheckingBackend(false);
      }
    }
  }

  async function login({
    onSuccess,
    skipHealthCheck = false,
    apiUrl,
    username: usernameOverride,
    password: passwordOverride,
  } = {}) {
    const loginUser = usernameOverride ?? username;
    const loginPass = passwordOverride ?? password;
    const target = normalizeUrl(apiUrl || wsUrl);
    if (!validateUrl(target)) {
      onStatus?.("Invalid backend URL format", "error");
      return false;
    }
    cancelLogin();
    let loginController = null;
    try {
      onStatus?.("Logging in...", "connecting");
      if (!skipHealthCheck) {
        const isHealthy = await checkBackendHealth(target);
        if (!isHealthy) {
          onStatus?.("Backend is not reachable. Check URL and ensure backend is running.", "error");
          return false;
        }
      }
      loginController = new AbortController();
      activeLoginAbort = loginController;
      const { signal } = loginController;
      if (signal.aborted) return false;
      let loginHost = "";
      try {
        loginHost = new URL(target).hostname;
      } catch {
        loginHost = "";
      }
      const loginTimeoutMs = isOffLanBackendHost(loginHost) ? 25000 : 15000;
      const loginTimeoutId = setTimeout(() => loginController.abort(), loginTimeoutMs);
      let response;
      try {
        response = await fetch(`${target}/auth/login`, {
          method: "POST",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            ...tunnelFetchHeaders(target),
          },
          body: JSON.stringify({ username: loginUser, password: loginPass }),
          signal,
        });
      } finally {
        clearTimeout(loginTimeoutId);
      }
      if (signal.aborted) return false;
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        onStatus?.("Login failed: " + (data.detail || "Unknown error"), "error");
        return false;
      }
      const data = await response.json();
      if (signal.aborted) return false;
      if (isJwtExpired(data.access_token)) {
        onStatus?.("Login returned an expired session — try again", "error");
        return false;
      }
      if (signal.aborted) return false;
      await SecureStore.setItemAsync(TOKEN_KEY, data.access_token);
      if (signal.aborted) return false;
      setToken(data.access_token);
      await saveWsUrl(target);
      if (signal.aborted) return false;
      onStatus?.("Logged in as " + loginUser, "success");
      onSuccess?.(data.access_token);
      return true;
    } catch (error) {
      if (loginController?.signal?.aborted || error?.name === "AbortError") {
        return false;
      }
      const message = String(error?.message || error || "Unknown error");
      if (/network request failed|failed to fetch|timeout|aborted/i.test(message)) {
        onStatus?.("Cannot reach server — check Wi‑Fi and that the PC backend is running.", "error");
      } else {
        onStatus?.("Login error: " + message, "error");
      }
      return false;
    } finally {
      if (loginController && activeLoginAbort === loginController) {
        activeLoginAbort = null;
      }
    }
  }

  async function logout({ onDisconnect } = {}) {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken("");
    onStatus?.("Logged out", "idle");
    onDisconnect?.();
  }

  async function clearAllData() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    await SecureStore.deleteItemAsync(WS_URL_KEY);
    await SecureStore.deleteItemAsync(SETUP_COMPLETE_KEY);
    await SecureStore.deleteItemAsync(RECENT_URLS_KEY);
    setToken("");
    setRecentUrls([]);
    setSetupComplete(false);
    setBackendReachable(null);
    setWsUrl(defaultUrl || "");
  }

  function markBackendReachable(value = true) {
    setBackendReachable(Boolean(value));
  }

  return {
    token,
    setToken,
    username,
    setUsername,
    password,
    setPassword,
    wsUrl,
    setWsUrl,
    editWsUrl,
    recentUrls,
    setRecentUrls,
    showRecentUrls,
    setShowRecentUrls,
    backendReachable,
    markBackendReachable,
    setupComplete,
    discoveryComplete,
    isCheckingBackend,
    loadStoredData,
    saveRecentUrl,
    saveWsUrl,
    markSetupComplete,
    validateUrl,
    checkBackendHealth,
    login,
    logout,
    clearAllData,
    cancelLogin,
    cancelDiscovery,
  };
}
