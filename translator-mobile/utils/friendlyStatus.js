/**
 * User-friendly status labels for the mobile interpreter UI.
 */

import { friendlyPanelStates } from "../constants/productVoice";

const PANEL = friendlyPanelStates();

export function getFriendlyPanelState({
  isPlayingTts = false,
  isStreaming = false,
  isInterpreterActive = false,
  isConnected = false,
  isConnecting = false,
  needsWifi = false,
  status = "",
}) {
  if (isPlayingTts) return PANEL.bridging;
  if (isStreaming) return PANEL.listening;
  if (isInterpreterActive && isConnected) return PANEL.bridgeReady;
  if (needsWifi && !isConnected) return PANEL.needsWifi;
  if (isInterpreterActive || isConnecting) return PANEL.linking;
  if (isConnected) return PANEL.bridgeReady;
  if (/network restored|handshaking|reconnect|connecting/i.test(String(status || ""))) return PANEL.linking;
  return PANEL.offline;
}

export function getFriendlyStatusLine(status = "", { isConnected = false, isConnecting = false, needsWifi = false } = {}) {
  const raw = String(status || "").trim();
  if (!raw) {
    if (needsWifi && !isConnected) return "Join same Wi‑Fi as your PC";
    if (isConnecting) return "Linking bridge…";
    if (!isConnected) return "Link your bridge below";
    return PANEL.bridgeReady;
  }

  const lower = raw.toLowerCase();
  if (!isConnected && needsWifi) return "Join same Wi‑Fi as your PC";
  if (!isConnected && /network restored/i.test(lower)) {
    return needsWifi ? "Join same Wi‑Fi as your PC" : isConnecting ? "Linking bridge…" : "Link your bridge below";
  }
  if (!isConnected && /token restored/i.test(lower)) return "Linking bridge…";
  if (/^connected/.test(lower)) return "Bridge linked";
  if (/^paused|bridge paused/.test(lower)) return "Bridge paused";
  if (/listen|speech detected|opening microphone|microphone/.test(lower)) return PANEL.listening;
  if (/translat|processing|understanding/.test(lower)) return "Understanding…";
  if (/speak|voice delivered|playing|tts|bridging/.test(lower)) return PANEL.bridging;
  if (/reconnect|handshake|connecting|opening|linking/.test(lower)) return "Linking bridge…";
  if (/network lost/i.test(lower)) return raw;
  if (/disconnected/i.test(lower)) return isConnected ? raw : "Link your bridge below";
  if (/two-way|together|one-way|for you/.test(lower)) return raw;
  if (/fail|error|denied|unavailable/.test(lower)) return raw;

  return raw.length > 52 ? `${raw.slice(0, 49)}…` : raw;
}
