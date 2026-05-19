/**
 * Shared utilities for the Anai Translator web client.
 *
 * Extracted from `main.jsx` so that file can focus on the App component.
 * Everything here is pure (no React) — constants, browser feature probes,
 * latency/audio helpers, repair-label formatting, and small URL helpers.
 *
 * Side effects: `registerServiceWorker()` is *not* called here; callers
 * must invoke it. localStorage reads are wrapped in try/catch so the
 * module is safe to import in SSR-ish environments.
 */

// ---------- Host classification + default URLs ----------

export function isLocalHost(hostname) {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)
  );
}

export function isSameOriginBackendHost(hostname) {
  return (
    hostname.endsWith('.trycloudflare.com') ||
    hostname.endsWith('.up.railway.app') ||
    hostname.endsWith('.onrender.com') ||
    hostname.endsWith('.fly.dev')
  );
}

export function defaultApiUrl() {
  if (isLocalHost(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  if (isSameOriginBackendHost(window.location.hostname)) {
    return window.location.origin;
  }
  return '';
}

/** Treat `your-backend.example.com`-style placeholders as unset. */
export function configuredUrl(value) {
  if (!value || value.includes('your-backend')) return '';
  return value;
}

// ---------- Session/device identifiers ----------

export function normalizeSessionId(value) {
  return String(value || '').trim().replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
}

export function readInitialSessionId() {
  const params = new URLSearchParams(window.location.search);
  const linkedSession = normalizeSessionId(params.get('session') || params.get('room'));
  return (
    linkedSession ||
    normalizeSessionId(localStorage.getItem('translator_session_id')) ||
    crypto.randomUUID()
  );
}

// ---------- Constants ----------

export const TARGET_LANGUAGE_OPTIONS = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Spanish' },
  { code: 'ht', label: 'Haitian Creole' },
];

export const VOICE_WARMUP_PHRASES = {
  es: 'Hola, ¿cómo estás?',
  ht: 'Bonjou, kijan ou ye?',
};

export const HEALTH_POLL_MS = 3000;
export const STREAM_HEARTBEAT_MS = 2500;
export const STREAM_HEARTBEAT_MAX_MISSES = 2;
export const STREAM_RECONNECT_MS = 1000;
export const STREAM_RECONNECT_MAX_ATTEMPTS = 5;
export const STREAM_RECONNECT_MAX_DELAY_MS = 30000;
export const MAX_AUDIO_SEND_QUEUE = 10;
export const MAX_BUFFERED_AUDIO_CHUNKS = 30;
export const LATENCY_HISTORY_KEY = 'translator_latency_history';
export const LATENCY_HISTORY_LIMIT = 12;
export const LATENCY_TARGET_MS = 1000;
export const VOICE_WARMUP_COOLDOWN_MS = 5 * 60 * 1000;
export const VOICE_PREFETCH_TIMEOUT_MS = 4000;
export const HOLD_TO_TALK_DELAY_MS = 260;
export const EXPECTED_BACKEND_RELEASE = '2026-05-13-active-speaker-v19';
export const FRONTEND_BUILD_ID = 'continuous-interpreter-v29-browser-live-text';
export const EXPERIMENTAL_IOS_STREAMING = true;

// ---------- Persistence ----------

export function readPersistedTargetLanguage() {
  try {
    const stored = localStorage.getItem('targetLanguage');
    if (stored && TARGET_LANGUAGE_OPTIONS.some((o) => o.code === stored)) return stored;
  } catch {}
  return 'es';
}

export function readPersistedSourceLanguage() {
  try {
    const stored = localStorage.getItem('sourceLanguage');
    if (stored && TARGET_LANGUAGE_OPTIONS.some((o) => o.code === stored)) return stored;
  } catch {}
  return 'en';
}

// ---------- Debug logging ----------

export function readDebugFlag() {
  try {
    return import.meta.env.DEV || localStorage.getItem('translator_debug') === '1';
  } catch {
    return import.meta.env.DEV;
  }
}

export function makeDebugLog(enabled) {
  return (...args) => {
    if (enabled) console.debug(...args);
  };
}

// ---------- Latency stats ----------

export function blankLatencyStats() {
  return { mic_to_backend: '-', backend_response: '-', first_audio: '-', end_to_end: '-' };
}

export function formatLatencyValue(value) {
  if (value === null || value === undefined || value === '' || value === '-') return '-';
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `${Math.max(0, Math.round(value))}ms`;
  }
  return String(value);
}

export function readLatencyHistory() {
  try {
    const raw = localStorage.getItem(LATENCY_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => ({
        total: Number(item.total),
        backend: Number(item.backend),
        audio: Number(item.audio),
        created_at: Number(item.created_at) || Date.now(),
      }))
      .filter((item) => Number.isFinite(item.total) && item.total > 0)
      .slice(-LATENCY_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function summarizeLatencyHistory(history) {
  if (!history.length) return { average: null, best: null };
  const totals = history.map((item) => item.total).filter((value) => Number.isFinite(value) && value > 0);
  if (!totals.length) return { average: null, best: null };
  return {
    average: Math.round(totals.reduce((sum, value) => sum + value, 0) / totals.length),
    best: Math.min(...totals),
  };
}

// ---------- Speaker labels ----------

export function fallbackSpeakerLabel(speaker) {
  const value = String(speaker || '').trim();
  if (!value || value === '-') return 'Person';
  const numericId = value.match(/(\d+)$/)?.[1];
  if (numericId) return `Person ${numericId}`;
  return value.replace(/^speaker[-_\s]*/i, 'Person ').trim() || 'Person';
}

// ---------- Browser feature probes ----------

export function isManualInstallBrowser() {
  const userAgent = navigator.userAgent || '';
  const isIos = /iphone|ipad|ipod/i.test(userAgent);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg/i.test(userAgent);
  return isIos || isSafari;
}

export function isIosOrSafariRecorder() {
  const userAgent = navigator.userAgent || '';
  const platform = navigator.platform || '';
  const isIos =
    /iphone|ipad|ipod/i.test(userAgent) ||
    (platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg|edgios/i.test(userAgent);
  return isIos || isSafari;
}

// ---------- Audio recording ----------

export function preferredAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  const candidates = isIosOrSafariRecorder()
    ? ['audio/mp4', 'audio/aac', 'audio/mp4;codecs=mp4a.40.2', 'audio/webm;codecs=opus', 'audio/webm']
    : ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/ogg;codecs=opus', 'audio/ogg'];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

export function createAudioRecorder(stream, audioBitsPerSecond) {
  if (!window.MediaRecorder) {
    window.alert?.('Recording not supported on this device/browser');
    throw new Error('Recording not supported on this device/browser');
  }
  const options = {};
  const mimeType = preferredAudioMimeType();
  if (mimeType) options.mimeType = mimeType;
  if (audioBitsPerSecond) options.audioBitsPerSecond = audioBitsPerSecond;
  try {
    return new MediaRecorder(stream, options);
  } catch (err) {
    console.warn('MediaRecorder rejected options, retrying without explicit mimeType', err);
    return new MediaRecorder(stream);
  }
}

export function audioFileExtension(mimeType) {
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return '.m4a';
  if (mimeType.includes('ogg')) return '.ogg';
  return '.webm';
}

// ---------- Speech recognition ----------

export function speechRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function speechRecognitionLanguage(code) {
  const normalized = String(code || 'en').toLowerCase().split(/[-_]/)[0];
  return (
    {
      en: 'en-US',
      es: 'es-ES',
      ht: 'ht-HT',
      fr: 'fr-FR',
      de: 'de-DE',
      it: 'it-IT',
      pt: 'pt-BR',
    }[normalized] || normalized
  );
}

// ---------- Auth helpers ----------

export function withAuthToken(url, token) {
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

export function authHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

export async function responseErrorMessage(response, fallback) {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const body = await response.json();
      return body.detail || body.message || fallback;
    }
    const text = await response.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

// ---------- Media / mic errors ----------

export function mediaErrorMessage(error) {
  if (error?.name === 'NotAllowedError') return 'Microphone permission blocked';
  if (error?.name === 'NotFoundError') return 'No microphone found';
  if (error?.name === 'NotSupportedError') return 'Audio recording is not supported in this browser';
  return 'Could not start microphone';
}

export async function requestAudioStream() {
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (error) {
    console.warn('Enhanced audio constraints failed, retrying basic audio', error);
    return navigator.mediaDevices.getUserMedia({ audio: true });
  }
}

// ---------- Misc text helpers ----------

export function uniqueStrings(values = []) {
  const seen = new Set();
  return values
    .map((value) => String(value || '').trim())
    .filter((value) => {
      if (!value || seen.has(value.toLowerCase())) return false;
      seen.add(value.toLowerCase());
      return true;
    });
}

export function extractBrainPlan(payload = {}) {
  const plan = payload.cip_response_plan || payload.response_plan || null;
  const hints = payload.cip_client_hints || payload.client_hints || plan?.client_hints || {};
  const repairOptions = payload.cip_repair_options || plan?.repair_options || [];
  return {
    plan: plan && typeof plan === 'object' ? plan : null,
    hints: hints && typeof hints === 'object' ? hints : {},
    repairOptions: Array.isArray(repairOptions) ? repairOptions : [],
  };
}

export function compactRepairLabel(option = {}) {
  if (option.type === 'auto_switch_source_language') {
    return `Using ${String(option.language || '').toUpperCase()}`;
  }
  if (option.type === 'switch_source_language') {
    return `Switch to ${String(option.language || '').toUpperCase()}`;
  }
  if (option.type === 'repeat_terms') return 'Repeat exact terms';
  if (option.type === 'confirm_exact') return 'Confirm exact words';
  if (option.type === 'choose_meaning') return `Meaning of ${option.word}`;
  if (option.type === 'repeat_slowly') return 'Repeat slowly';
  if (option.type === 'preserve_code_switch') return 'Keep mixed language';
  return option.label || 'Repair';
}

export function logAudioStream(stream, debugLog) {
  debugLog('AUDIO STREAM:', stream);
  debugLog('AUDIO TRACKS:', stream.getAudioTracks());
  stream.getAudioTracks().forEach((track) => {
    debugLog('TRACK ENABLED:', track.enabled);
    debugLog('TRACK STATE:', track.readyState);
  });
}
