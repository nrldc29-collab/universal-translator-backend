/**
 * User-friendly status labels for the mobile interpreter UI.
 */

export function getFriendlyPanelState({
  isPlayingTts = false,
  isStreaming = false,
  isInterpreterActive = false,
  isConnected = false,
  isConnecting = false,
}) {
  if (isPlayingTts) return "Speaking";
  if (isStreaming) return "Listening";
  if (isInterpreterActive && isConnected) return "Ready";
  if (isInterpreterActive || isConnecting) return "Connecting";
  if (isConnected) return "Standby";
  return "Offline";
}

export function getFriendlyStatusLine(status = "") {
  const raw = String(status || "").trim();
  if (!raw) return "Ready";

  const lower = raw.toLowerCase();
  if (/^connected/.test(lower)) return "Connected";
  if (/^paused/.test(lower)) return "Paused";
  if (/listen|speech detected|opening microphone|microphone/.test(lower)) return "Listening";
  if (/translat|processing/.test(lower)) return "Translating…";
  if (/speak|voice delivered|playing|tts/.test(lower)) return "Speaking";
  if (/reconnect|handshake|connecting|opening/.test(lower)) return "Connecting…";
  if (/network (lost|restored)/.test(lower)) return raw;
  if (/two-way|one-way/.test(lower)) return raw;
  if (/fail|error|denied|unavailable/.test(lower)) return raw;

  return raw.length > 52 ? `${raw.slice(0, 49)}…` : raw;
}
