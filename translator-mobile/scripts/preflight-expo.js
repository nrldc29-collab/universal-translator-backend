#!/usr/bin/env node
/** Validates .env + production backend before starting Expo Go. */
const fs = require("fs");
const path = require("path");

function loadEnvFile(filePath) {
  const env = {};
  if (!fs.existsSync(filePath)) return env;
  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const idx = trimmed.indexOf("=");
    env[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
  }
  return env;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { ...options, cache: "no-store" });
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  return { ok: response.ok, status: response.status, body };
}

async function main() {
  const envPath = path.join(process.cwd(), ".env");
  const env = loadEnvFile(envPath);
  const apiUrl = (env.EXPO_PUBLIC_CLOUD_API_URL || env.EXPO_PUBLIC_API_URL || "").replace(/\/+$/, "");
  const user = env.EXPO_PUBLIC_CLOUD_DEMO_USER || "demo";
  const pass = env.EXPO_PUBLIC_CLOUD_DEMO_PASS || "";
  const debugLogs = env.EXPO_PUBLIC_DEBUG_LOGS || "0";

  const errors = [];
  if (!apiUrl) errors.push("Missing EXPO_PUBLIC_API_URL or EXPO_PUBLIC_CLOUD_API_URL in .env");
  if (!pass) errors.push("Missing EXPO_PUBLIC_CLOUD_DEMO_PASS in .env (sync from Railway USERS)");
  if (errors.length) {
    console.error("Preflight failed:\n- " + errors.join("\n- "));
    console.error("\nRun from repo root: .\\Start-ExpoCloud.ps1");
    process.exit(1);
  }

  const health = await fetchJson(`${apiUrl}/health`);
  if (!health.ok) {
    console.error(`Preflight failed: ${apiUrl}/health returned HTTP ${health.status}`);
    process.exit(1);
  }

  const login = await fetchJson(`${apiUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: user, password: pass }),
  });
  if (!login.ok) {
    console.error(`Preflight failed: login HTTP ${login.status} - check EXPO_PUBLIC_CLOUD_DEMO_PASS`);
    process.exit(1);
  }

  console.log("Expo preflight OK");
  console.log(`  API: ${apiUrl}`);
  console.log(`  Health ready: ${health.body?.ready !== false}`);
  console.log(`  Login user: ${user}`);
  console.log(`  EXPO_PUBLIC_DEBUG_LOGS: ${debugLogs} (0 = quiet console)`);
  console.log("\nStart Expo: npm run start:clean");
}

main().catch((error) => {
  console.error("Preflight failed:", error?.message || error);
  process.exit(1);
});
