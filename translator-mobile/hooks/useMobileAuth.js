import { useState } from "react";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "translator_token";
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

  async function loadStoredData() {
    try {
      const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
      if (storedToken) {
        setToken(storedToken);
        onStatus?.("Token restored", "success");
      }
      const storedUrls = await SecureStore.getItemAsync(RECENT_URLS_KEY);
      if (storedUrls) setRecentUrls(JSON.parse(storedUrls));
    } catch (error) {
      console.error("Error loading stored data:", error);
    }
  }

  async function saveRecentUrl(url) {
    try {
      const updated = [url, ...recentUrls.filter((u) => u !== url)].slice(0, MAX_RECENT_URLS);
      setRecentUrls(updated);
      await SecureStore.setItemAsync(RECENT_URLS_KEY, JSON.stringify(updated));
    } catch (error) {
      console.error("Error saving recent URL:", error);
    }
  }

  function validateUrl(url) {
    try {
      if (!url || url.trim() === "") return false;
      return url.startsWith("http://") || url.startsWith("https://");
    } catch {
      return false;
    }
  }

  async function checkBackendHealth(url) {
    try {
      onStatus?.("Checking backend...", "connecting");
      const response = await fetch(`${url}/health`, {
        method: "GET",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
      });
      setBackendReachable(response.ok);
      return response.ok;
    } catch {
      setBackendReachable(false);
      return false;
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
      const response = await fetch(`${wsUrl}/auth/login`, {
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
      await saveRecentUrl(wsUrl);
      onStatus?.("Logged in as " + username, "success");
      onSuccess?.();
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
    await SecureStore.deleteItemAsync(RECENT_URLS_KEY);
    setToken("");
    setRecentUrls([]);
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
    recentUrls,
    setRecentUrls,
    showRecentUrls,
    setShowRecentUrls,
    backendReachable,
    loadStoredData,
    saveRecentUrl,
    validateUrl,
    checkBackendHealth,
    login,
    logout,
    clearAllData,
  };
}
