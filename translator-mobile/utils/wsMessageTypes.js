/** Message types emitted by backend/streaming.py on the audio WebSocket. */
export const BACKEND_AUDIO_WS_TYPES = [
  "active_speaker",
  "cancelled",
  "cip",
  "clarify",
  "config_ack",
  "error",
  "final",
  "final_transcription",
  "latency",
  "listening",
  "live_translation",
  "partial_transcription",
  "partial_translation",
  "ready",
  "semantic_context",
  "session_restored",
  "session_sync",
  "speaker_detected",
  "stage",
  "translation",
  "turn",
  "tts_audio_chunk",
  "tts_end",
  "tts_start",
  "tts_style",
  "vad",
  "vad_error",
];

/** Handled in translator-mobile/App.js handleMessage (pong handled in services/ws.js). */
export const HANDLED_MOBILE_WS_TYPES = [
  ...BACKEND_AUDIO_WS_TYPES,
];

export function isHandledMobileWsType(type) {
  if (type === "pong") return true;
  return HANDLED_MOBILE_WS_TYPES.includes(type);
}

export function resolvePipelineStageLabel(stage, message = "") {
  const text = String(message || "").trim();
  switch (stage) {
    case "queued":
      return text || "Audio queued for bridging…";
    case "translation":
      return text || "Understanding…";
    case "stt":
      return text || "Transcribing…";
    case "tts":
      return text || "Preparing bridged voice…";
    case "tts_skipped":
      return text || "Bridge voice skipped";
    case "smoothing":
      return text || "Short burst ignored";
    case "partial_timeout":
    case "live_text_timeout":
      return text || "Still processing — hang on…";
    case "partial_degraded":
      return text || "Catching up…";
    case "turn_held":
      return text || "Waiting for bridged voice";
    case "weak_audio":
      return text || "Move closer to the mic";
    default:
      return text || stage || "";
  }
}
