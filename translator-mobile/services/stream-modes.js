// Pure helpers for interpreting the streaming backend's live-status events.
// Kept dependency-free so they can be unit tested and reused across screens.

const MODE_LABELS = {
  streaming_stt: "Live streaming",
  degraded: "Degraded — backup mode",
  unknown: "Connecting",
};

/**
 * Derive a display label and degraded flag from a backend `mode` event so the
 * mobile UI can show the active live mode and surface weak-network fallbacks.
 */
export function describeLiveMode(payload = {}) {
  const mode = payload.mode || "unknown";
  const recommendFallback = Boolean(payload.recommend_fallback);
  return {
    mode,
    degraded: recommendFallback || mode === "degraded",
    recommendFallback,
    label: MODE_LABELS[mode] || mode,
    hint: payload.reason || "",
  };
}

/**
 * Format a `peer_message` (another speaker's routed translation) for display.
 */
export function formatPeerTurn(payload = {}) {
  const label = payload.speaker_label || payload.speaker || "Speaker";
  const text = (payload.translated_text || "").trim();
  return text ? `${label}: ${text}` : "";
}

/**
 * Collapse a `repair` event's options into a short human-readable summary.
 */
export function summarizeRepair(payload = {}) {
  const options = Array.isArray(payload.options) ? payload.options : [];
  const labels = options.map((option) => option && option.label).filter(Boolean);
  return labels.join(" \u00b7 ");
}
