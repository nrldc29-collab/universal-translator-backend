import { useState } from "react";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "translator_token";
const WS_URL_KEY = "translator_ws_url";
const SETUP_COMPLETE_KEY = "translator_setup_complete";
const RECENT_URLS_KEY = "recent_urls";
const MAX_RECENT_URLS = 5;

export function useMobileAuth({ defaultUrl = "", onStatus }) {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo");
  const [wsUrl, setWsUrl] = useState(defaultUrl);
  const [recentUrls, setRecentUrls] = useState([]);
  const [showRecentUrls, setShowRecentUrls] = useState(false);
  const [backendReachable, setBackendReachable] = useState(null);
  const [setupComplete, setSetupComplete] = useState(false);
  const [isCheckingBackend, setIsCheckingBackend] = useState(false);

  function normalizeUrl(url) {
    return String(url || "").trim().replace(/\/+$/, "");
  }

  async function loadStoredData() {
    try {
      const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
      if (storedToken) {
        setToken(storedToken);
        onStatus?.("Token restored", "success");
      }
      const envUrl = normalizeUrl(defaultUrl);
      const storedUrl = normalizeUrl(await SecureStore.getItemAsync(WS_URL_KEY));
      let envChanged = false;
      // Prefer the baked-in Expo env URL when it changes (e.g. Start-MobilePhoneMode.ps1 refreshed LAN IP).
      if (envUrl && validateUrl(envUrl)) {
        envChanged = Boolean(storedUrl && storedUrl !== envUrl);
        if (!storedUrl || envChanged) {
          setWsUrl(envUrl);
          await SecureStore.setItemAsync(WS_URL_KEY, envUrl);
          if (envChanged) {
            setBackendReachable(null);
            setSetupComplete(false);
            await SecureStore.deleteItemAsync(SETUP_COMPLETE_KEY);
          }
        } else {
          setWsUrl(storedUrl);
        }
      } else if (storedUrl && validateUrl(storedUrl)) {
        setWsUrl(storedUrl);
      }
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
      if (!envChanged) {
        const storedSetup = await SecureStore.getItemAsync(SETUP_COMPLETE_KEY);
        setSetupComplete(storedSetup === "1");
      }
    } catch (error) {
      console.error("Error loading stored data:", error);
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

  function validateUrl(url) {
    try {
      const trimmed = String(url || "").trim();
      if (!trimmed) return false;
      if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) return false;
      const parsed = new URL(trimmed);
      return Boolean(parsed.hostname);
    } catch {
      return false;
    }
  }

  async function checkBackendHealth(url, { quiet = false } = {}) {
    const target = normalizeUrl(url || wsUrl);
    if (!validateUrl(target)) {
      setBackendReachable(false);
      return false;
    }
    if (/localhost|127\.0\.0\.1/i.test(target)) {
      setBackendReachable(false);
      if (!quiet) {
        onStatus?.("Use your PC's LAN IP (not localhost) — the phone cannot reach this machine.", "error");
      }
      return false;
    }
    try {
      if (!quiet) {
        setIsCheckingBackend(true);
        onStatus?.("Checking server...", "connecting");
      }
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 12000);
      const response = await fetch(`${target}/health`, {
        method: "GET",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      setBackendReachable(response.ok);
      if (!quiet) {
        if (response.ok) {
          onStatus?.("Server reachable", "success");
        } else {
          onStatus?.(`Server responded with HTTP ${response.status}`, "error");
        }
      }
      return response.ok;
    } catch (error) {
      setBackendReachable(false);
      const message = String(error?.message || error || "");
      if (!quiet) {
        if (/abort|timeout/i.test(message)) {
          onStatus?.("Server check timed out. Same Wi‑Fi? Firewall open on ports 8000 and 8081?", "error");
        } else if (/network request failed|failed to fetch|cleartext/i.test(message)) {
          onStatus?.("Cannot reach server. Use your PC's LAN IP and allow HTTP through Windows Firewall.", "error");
        } else {
          onStatus?.("Cannot reach server. Check URL, Wi‑Fi, and firewall.", "error");
        }
      }
      return false;
    } finally {
      if (!quiet) {
        setIsCheckingBackend(false);
      }
    }
  }

  async function login({ onSuccess } = {}) {
    if (!validateUrl(wsUrl)) {
      onStatus?.("Invalid backend URL format", "error");
      return;
    }
    try {
      onStatus?.("Logging in...", "connecting");
      const isHealthy = await checkBackendHealth(wsUrl);
      if (!isHealthy) {
        onStatus?.("Backend is not reachable. Check URL and ensure backend is running.", "error");
        return;
      }
      const target = normalizeUrl(wsUrl);
      const response = await fetch(`${target}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        onStatus?.("Login failed: " + (data.detail || "Unknown error"), "error");
        return;
      }
      const data = await response.json();
      await SecureStore.setItemAsync(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      await saveWsUrl(wsUrl);
      onStatus?.("Logged in as " + username, "success");
      onSuccess?.(data.access_token);
    } catch (error) {
      onStatus?.("Login error: " + error.message, "error");
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
    setupComplete,
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
  };
}
