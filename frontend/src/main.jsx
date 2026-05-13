import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowLeftRight, Download, Mic, Share2 } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';

function isLocalHost(hostname) {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)
  );
}

function isSameOriginBackendHost(hostname) {
  return (
    hostname.endsWith('.trycloudflare.com') ||
    hostname.endsWith('.up.railway.app') ||
    hostname.endsWith('.onrender.com') ||
    hostname.endsWith('.fly.dev')
  );
}

function defaultApiUrl() {
  if (isLocalHost(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  if (isSameOriginBackendHost(window.location.hostname)) {
    return window.location.origin;
  }
  return 'https://universal-translator-phone-production.up.railway.app';
}

function configuredUrl(value) {
  if (!value || value.includes('your-backend')) {
    return '';
  }
  return value;
}

const LOCAL_BACKEND = isLocalHost(window.location.hostname);
const SAME_ORIGIN_BACKEND = isSameOriginBackendHost(window.location.hostname);
const API_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? defaultApiUrl() : (configuredUrl(import.meta.env.VITE_API_URL) || defaultApiUrl())).replace(/\/+$/, '');
const WS_BASE_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? API_URL : (configuredUrl(import.meta.env.VITE_WS_URL) || API_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:'))).replace(/\/+$/, '');
const WS_AUDIO_URL = LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? `${WS_BASE_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')}/ws/audio` : (configuredUrl(import.meta.env.VITE_WS_AUDIO_URL) || `${WS_BASE_URL}/ws/audio`);
const INITIAL_TOKEN = localStorage.getItem('translator_token') || '';

function normalizeSessionId(value) {
  return String(value || '').trim().replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
}

function readInitialSessionId() {
  const params = new URLSearchParams(window.location.search);
  const linkedSession = normalizeSessionId(params.get('session') || params.get('room'));
  return linkedSession || normalizeSessionId(localStorage.getItem('translator_session_id')) || crypto.randomUUID();
}

const INITIAL_SESSION_ID = readInitialSessionId();
const INITIAL_DEVICE_ID = localStorage.getItem('translator_device_id') || crypto.randomUUID();
const INITIAL_SPEAKER_NAME = localStorage.getItem('translator_speaker_name') || '';
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 80);
const STREAM_AUDIO_BITRATE = Number(import.meta.env.VITE_STREAM_AUDIO_BITRATE || 32000);
const HEALTH_POLL_MS = 3000;
const STREAM_HEARTBEAT_MS = 2500;
const STREAM_HEARTBEAT_MAX_MISSES = 2;
const STREAM_RECONNECT_MS = 1000;
const STREAM_RECONNECT_MAX_ATTEMPTS = 5;
const MAX_AUDIO_SEND_QUEUE = 10;
const MAX_BUFFERED_AUDIO_CHUNKS = 30;
const FAST_SPEECH_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_SPEECH_TIMEOUT_MS || 10000);
const FAST_TTS_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_TTS_TIMEOUT_MS || 10000);
const LATENCY_HISTORY_KEY = 'translator_latency_history';
const LATENCY_HISTORY_LIMIT = 12;
const LATENCY_TARGET_MS = 1000;
const VOICE_WARMUP_COOLDOWN_MS = 5 * 60 * 1000;
const HOLD_TO_TALK_DELAY_MS = 260;
const MIN_STREAM_CAPTURE_MS = Number(import.meta.env.VITE_MIN_STREAM_CAPTURE_MS || 1800);
const EXPECTED_BACKEND_RELEASE = '2026-05-13-tts-cache-v15';
const FRONTEND_BUILD_ID = 'tts-cache-v20';
const EXPERIMENTAL_IOS_STREAMING = true;
localStorage.setItem('translator_session_id', INITIAL_SESSION_ID);
localStorage.setItem('translator_device_id', INITIAL_DEVICE_ID);
registerServiceWorker();

function blankLatencyStats() {
  return { mic_to_backend: '-', backend_response: '-', first_audio: '-', end_to_end: '-' };
}

function formatLatencyValue(value) {
  if (value === null || value === undefined || value === '' || value === '-') return '-';
  if (typeof value === 'number' && Number.isFinite(value)) return `${Math.max(0, Math.round(value))}ms`;
  return String(value);
}

function readLatencyHistory() {
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

function summarizeLatencyHistory(history) {
  if (!history.length) return { average: null, best: null };
  const totals = history.map((item) => item.total).filter((value) => Number.isFinite(value) && value > 0);
  if (!totals.length) return { average: null, best: null };
  return {
    average: Math.round(totals.reduce((sum, value) => sum + value, 0) / totals.length),
    best: Math.min(...totals),
  };
}

function fallbackSpeakerLabel(speaker) {
  const value = String(speaker || '').trim();
  if (!value || value === '-') return 'Person';
  const numericId = value.match(/(\d+)$/)?.[1];
  if (numericId) return `Person ${numericId}`;
  return value.replace(/^speaker[-_\s]*/i, 'Person ').trim() || 'Person';
}

function isManualInstallBrowser() {
  const userAgent = navigator.userAgent || '';
  const isIos = /iphone|ipad|ipod/i.test(userAgent);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg/i.test(userAgent);
  return isIos || isSafari;
}

function isIosOrSafariRecorder() {
  const userAgent = navigator.userAgent || '';
  const platform = navigator.platform || '';
  const isIos =
    /iphone|ipad|ipod/i.test(userAgent) ||
    (platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg|edgios/i.test(userAgent);
  return isIos || isSafari;
}

function preferredAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  const candidates = isIosOrSafariRecorder()
    ? ['audio/mp4', 'audio/aac', 'audio/mp4;codecs=mp4a.40.2', 'audio/webm;codecs=opus', 'audio/webm']
    : ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/ogg;codecs=opus', 'audio/ogg'];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

function createAudioRecorder(stream) {
  if (!window.MediaRecorder) {
    window.alert?.('Recording not supported on this device/browser');
    throw new Error('Recording not supported on this device/browser');
  }
  const options = {};
  const mimeType = preferredAudioMimeType();
  if (mimeType) options.mimeType = mimeType;
  options.audioBitsPerSecond = 96000;
  try {
    return new MediaRecorder(stream, options);
  } catch (err) {
    console.warn('MediaRecorder rejected options, retrying without explicit mimeType', err);
    return new MediaRecorder(stream);
  }
}

function logAudioStream(stream) {
  console.log('AUDIO STREAM:', stream);
  console.log('AUDIO TRACKS:', stream.getAudioTracks());
  stream.getAudioTracks().forEach((track) => {
    console.log('TRACK ENABLED:', track.enabled);
    console.log('TRACK STATE:', track.readyState);
  });
}

function audioFileExtension(mimeType) {
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return '.m4a';
  if (mimeType.includes('ogg')) return '.ogg';
  return '.webm';
}

function speechRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function speechRecognitionLanguage(code) {
  const normalized = String(code || 'en').toLowerCase().split(/[-_]/)[0];
  return {
    en: 'en-US',
    es: 'es-ES',
    ht: 'ht-HT',
    fr: 'fr-FR',
    de: 'de-DE',
    it: 'it-IT',
    pt: 'pt-BR',
  }[normalized] || normalized;
}

function withAuthToken(url, token) {
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

function authHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

async function responseErrorMessage(response, fallback) {
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

function mediaErrorMessage(error) {
  if (error?.name === 'NotAllowedError') return 'Microphone permission blocked';
  if (error?.name === 'NotFoundError') return 'No microphone found';
  if (error?.name === 'NotSupportedError') return 'Audio recording is not supported in this browser';
  return 'Could not start microphone';
}

// Target languages exposed in the picker. Keep tight — every entry needs both
// translation support (NLLB-200 covers all of these) AND some form of TTS,
// either Piper (es) or eSpeak NG fallback (ht).
const TARGET_LANGUAGE_OPTIONS = [
  { code: 'es', label: 'Spanish' },
  { code: 'ht', label: 'Haitian Creole' },
];

function readPersistedTargetLanguage() {
  try {
    const stored = localStorage.getItem('targetLanguage');
    if (stored && TARGET_LANGUAGE_OPTIONS.some((o) => o.code === stored)) return stored;
  } catch {}
  return 'es';
}

function App() {
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish', ht: 'Haitian Creole' });
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguage, setTargetLanguageState] = useState(readPersistedTargetLanguage);
  const setTargetLanguage = (next) => {
    setTargetLanguageState(next);
    try { localStorage.setItem('targetLanguage', next); } catch {}
  };
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const [micPermission, setMicPermission] = useState('checking');
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [instantListening, setInstantListening] = useState(false);
  const [partialTranscript, setPartialTranscript] = useState('');
  const [liveTranslation, setLiveTranslation] = useState('');
  const [pipelineStage, setPipelineStage] = useState('Idle');
  const [duplex, setDuplex] = useState({
    A: { active: false, transcript: '', translation: '', stage: 'Idle' },
    B: { active: false, transcript: '', translation: '', stage: 'Idle' },
  });
  const [conversationBrain, setConversationBrain] = useState('Idle');
  const [semanticContext, setSemanticContext] = useState({ last_intent: 'statement', conversation_mood: 'neutral', topics: [] });
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [accessibilityMode, setAccessibilityMode] = useState('balanced');
  const [speechSpeed, setSpeechSpeed] = useState('normal');
  const [lowBandwidthMode, setLowBandwidthMode] = useState(false);
  const [mobileAudioUnlocked, setMobileAudioUnlocked] = useState(false);
  const [audioReplayAvailable, setAudioReplayAvailable] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [audioContextState, setAudioContextState] = useState('unknown');
  const [lastAudioError, setLastAudioError] = useState(null);
  const [ttsQueueLength, setTtsQueueLength] = useState(0);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsChunksBuffer, setTtsChunksBuffer] = useState([]);
  const [userRequestedPlayback, setUserRequestedPlayback] = useState(false);
  const [autoPlayFailed, setAutoPlayFailed] = useState(false);
  const [interpreterMode, setInterpreterMode] = useState(false);
  const [speakerMode, setSpeakerMode] = useState('auto');
  const [detectedSpeaker, setDetectedSpeaker] = useState('-');
  const [latencyStats, setLatencyStats] = useState(() => blankLatencyStats());
  const [latencyHistory, setLatencyHistory] = useState(() => readLatencyHistory());
  const [authToken, setAuthToken] = useState(INITIAL_TOKEN);
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const [sessionId, setSessionId] = useState(INITIAL_SESSION_ID);
  const [sharedSession, setSharedSession] = useState(null);
  const [conversationTurns, setConversationTurns] = useState(() => {
    try {
      const raw = localStorage.getItem('translator_conversation_turns');
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(-50) : [];
    } catch {
      return [];
    }
  });
  const [analytics, setAnalytics] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState('checking');
  const [wsDebug, setWsDebug] = useState({ url: WS_AUDIO_URL, close: '-', error: '-' });
  const [selfTest, setSelfTest] = useState({
    status: 'idle',
    translation: '-',
    websocket: '-',
    message: 'Not run yet',
  });
  const [installPrompt, setInstallPrompt] = useState(null);
  const [pwaInstalled, setPwaInstalled] = useState(() => window.matchMedia?.('(display-mode: standalone)').matches || window.navigator?.standalone === true);
  const [updateAvailable, setUpdateAvailable] = useState(null);
  const [micLevel, setMicLevel] = useState(0);
  const [copiedKey, setCopiedKey] = useState(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [ocrText, setOcrText] = useState('');
  const [clarifyVisible, setClarifyVisible] = useState(false);
  const [clarifyMessage, setClarifyMessage] = useState('');
  const [reconnectToastVisible, setReconnectToastVisible] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem('translator_conversation_turns', JSON.stringify(conversationTurns.slice(-50)));
    } catch {
      /* ignore quota errors */
    }
  }, [conversationTurns]);

  useEffect(() => {
    try {
      localStorage.setItem(LATENCY_HISTORY_KEY, JSON.stringify(latencyHistory.slice(-LATENCY_HISTORY_LIMIT)));
    } catch {
      /* ignore quota errors */
    }
  }, [latencyHistory]);

  useEffect(() => {
    const { average } = summarizeLatencyHistory(latencyHistory);
    if (!average || average <= LATENCY_TARGET_MS) return;
    if (connectionStatus !== 'online' || processing || playing || streaming) return;
    warmVoiceCache('slow_latency');
  }, [connectionStatus, latencyHistory, playing, processing, streaming]);

  async function copyToClipboard(text, key) {
    if (!text) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1400);
    } catch (err) {
      console.warn('copy failed', err);
    }
  }
  const mediaRecorderRef = useRef(null);
  const micMeterRef = useRef({});
  const streamRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);
  const duplexRefs = useRef({ A: {}, B: {} });
  const speakerLabelsRef = useRef({});
  const recordingStoppedRef = useRef(false);
  const streamFinalizePendingRef = useRef(false);
  const streamFinalizeTimerRef = useRef(null);
  const streamStartedAtRef = useRef(0);
  const streamRecordingStartedAtRef = useRef(0);
  const firstAudioSeenRef = useRef(false);
  const streamHeartbeatRef = useRef({ timer: null, missed: 0 });
  const streamReconnectRef = useRef({ enabled: false, options: null, attempts: 0 });
  const holdToTalkTimerRef = useRef(null);
  const holdToTalkActiveRef = useRef(false);
  const holdToTalkReleasePendingRef = useRef(false);
  const ignoreNextMicClickRef = useRef(false);
  const ttsQueueRef = useRef([]);
  const lastTtsItemRef = useRef(null);
  const ttsPlayingRef = useRef(false);
  const audioSendQueueRef = useRef([]);
  const wakeLockRef = useRef(null);
  const audioContextRef = useRef(null);
  const persistentAudioRef = useRef(null);
  const mobileAudioUnlockedRef = useRef(false);
  const warmupOscRef = useRef(null);
  const warmupGainRef = useRef(null);
  const streamSafetyTimeoutRef = useRef(null);
  const currentTtsFinishRef = useRef(null);
  const canplayTimeoutRef = useRef(null);
  const silenceDetectRafRef = useRef(0);
  const silenceSeenSpeechRef = useRef(false);
  const silenceStartRef = useRef(0);
  const resumeAfterTtsRef = useRef(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const speechRecognitionRef = useRef(null);
  const speechFastPathActiveRef = useRef(false);
  const speechFinalTextRef = useRef('');
  const speechInterimTextRef = useRef('');
  const voiceWarmupRef = useRef({ inFlight: false, lastAt: 0 });
  const appStateRef = useRef({});

  useEffect(() => {
    appStateRef.current = { interpreterMode, speakerMode, recording, processing, playing, streaming };
  }, [interpreterMode, speakerMode, recording, processing, playing, streaming]);

  function haptic(pattern = 12) {
    window.navigator?.vibrate?.(pattern);
  }

  async function ensureAudioContext() {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return null;
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContextCtor();
    }
    const state = audioContextRef.current.state;
    setAudioContextState(state);
    if (state === 'suspended') {
      try {
        await audioContextRef.current.resume?.();
      } catch (e) {
        console.warn('AudioContext resume failed (no user gesture):', e);
      }
    }
    return audioContextRef.current;
  }

  async function requestWakeLock() {
    try {
      wakeLockRef.current = await navigator.wakeLock?.request?.('screen') || null;
    } catch {
      wakeLockRef.current = null;
    }
  }

  async function releaseWakeLock() {
    try {
      await wakeLockRef.current?.release?.();
    } catch {
    } finally {
      wakeLockRef.current = null;
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function checkRelease() {
      try {
        const response = await fetch(`${API_URL}/debug/version?cb=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled) return;
        const live = String(data && data.release || '');
        if (live && live !== EXPECTED_BACKEND_RELEASE) {
          console.warn('Frontend/backend release mismatch', { frontend: EXPECTED_BACKEND_RELEASE, backend: live });
          setUpdateAvailable({ frontend: EXPECTED_BACKEND_RELEASE, backend: live });
        } else if (live) {
          setUpdateAvailable(null);
        }
      } catch {
        // ignore network errors
      }
    }
    checkRelease();
    const interval = window.setInterval(checkRelease, 60000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, []);

  useEffect(() => {
    return () => {
      stopAudioWarmup();
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        try { audioContextRef.current.close(); } catch (e) {}
      }
      if (persistentAudioRef.current) {
        try { document.body.removeChild(persistentAudioRef.current); } catch (e) {}
        persistentAudioRef.current = null;
        mobileAudioUnlockedRef.current = false;
      }
      if (canplayTimeoutRef.current) {
        window.clearTimeout(canplayTimeoutRef.current);
        canplayTimeoutRef.current = null;
      }
      try { speechRecognitionRef.current?.abort?.(); } catch (e) {}
    };
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/languages`)
      .then((response) => response.json())
      .then((data) => {
        setLanguages(data.languages || languages);
        setConnectionStatus('online');
      })
      .catch(() => {
        setStatus('Backend offline');
        setConnectionStatus('offline');
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_URL}/health`, { cache: 'no-store' });
        if (!response.ok) throw new Error('Backend health check failed');
        if (!cancelled) setConnectionStatus('online');
      } catch {
        if (!cancelled) setConnectionStatus('offline');
      }
    };

    checkHealth();
    const timer = window.setInterval(checkHealth, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    loadDiagnostics();
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && (streaming || instantListening) && !wakeLockRef.current) {
        requestWakeLock();
      }
      if (document.visibilityState === 'hidden' && socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [streaming, instantListening]);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission('unavailable');
      return;
    }

    setMicPermission('available');
    navigator.permissions?.query?.({ name: 'microphone' })
      .then((permission) => {
        setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        permission.onchange = () => {
          setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        };
      })
      .catch(() => setMicPermission('available'));
  }, []);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    const handleInstalled = () => {
      setPwaInstalled(true);
      setInstallPrompt(null);
      setStatus('App installed');
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  async function installApp() {
    if (!installPrompt) {
      window.location.href = '/install.html';
      return;
    }
    installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    setInstallPrompt(null);
    setStatus(choice.outcome === 'accepted' ? 'Installing app' : 'Install dismissed');
  }

  async function requestMicPermission() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission('available');
      setStatus('Microphone ready');
    } catch {
      setMicPermission('denied');
      setStatus('Microphone permission blocked');
    }
  }

  function createPersistentAudio() {
    if (persistentAudioRef.current) return persistentAudioRef.current;
    const audio = document.createElement('audio');
    audio.setAttribute('playsinline', '');
    audio.setAttribute('webkit-playsinline', '');
    audio.setAttribute('preload', 'auto');
    audio.setAttribute('disableRemotePlayback', '');
    audio.setAttribute('x-webkit-airplay', 'deny');
    audio.crossOrigin = 'anonymous';
    audio.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;';
    document.body.appendChild(audio);
    persistentAudioRef.current = audio;
    return audio;
  }

  /*
    iOS Safari requires audio.play() to be called SYNCHRONOUSLY inside a user
    gesture handler. An async handler that awaits something before calling
    play() will fail because the gesture context expires.
    This function must be called DIRECTLY from onPointerDown / onClick with
    NO await before it.
  */
  function synchronousAudioUnlock() {
    /*
      iOS Safari requires audio.play() to be called SYNCHRONOUSLY inside a user
      gesture handler. An async handler that awaits something before calling
      play() will fail because the gesture context expires.
      We also create the AudioContext here so it's born inside the gesture.
    */
    if (mobileAudioUnlockedRef.current) {
      // Already unlocked — don't change audio.src or interrupt playback
      return;
    }

    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (AudioContextCtor && !audioContextRef.current) {
      audioContextRef.current = new AudioContextCtor();
    }
    const context = audioContextRef.current;
    if (context) {
      if (context.state === 'suspended') {
        context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
      }
      // Start a silent oscillator to keep the AudioContext warm on iOS.
      // iOS Safari auto-suspends the context after a few seconds of inactivity.
      // A 40 Hz sine at gain 0.0001 is inaudible but keeps the context running.
      if (!warmupOscRef.current) {
        try {
          const osc = context.createOscillator();
          osc.frequency.value = 40;
          const gain = context.createGain();
          gain.gain.value = 0.0001;
          osc.connect(gain);
          gain.connect(context.destination);
          osc.start();
          warmupOscRef.current = osc;
          warmupGainRef.current = gain;
          console.log('AudioContext warmup oscillator started');
        } catch (e) {
          console.warn('Failed to start warmup oscillator:', e);
        }
      }
    }

    const audio = createPersistentAudio();
    // Build a valid silent WAV programmatically so iOS Safari accepts it
    const sampleRate = 22050;
    const seconds = 0.05;
    const numSamples = Math.floor(sampleRate * seconds);
    const dataSize = numSamples * 2; // mono 16-bit
    const fileSize = 36 + dataSize;
    const wavBuf = new ArrayBuffer(8 + fileSize);
    const view = new DataView(wavBuf);
    const writeStr = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
    writeStr(0, 'RIFF');
    view.setUint32(4, fileSize, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);   // PCM
    view.setUint16(22, 1, true);   // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);  // 16-bit
    writeStr(36, 'data');
    view.setUint32(40, dataSize, true);
    // ArrayBuffer is already zero-filled (silence)
    const silentUrl = URL.createObjectURL(new Blob([wavBuf], { type: 'audio/wav' }));
    audio.src = silentUrl;
    // Prime the element with muted playback during the user gesture.
    // iOS Safari requires this to grant autoplay permission for the element.
    // After priming, we can play unmuted audio from the same element.
    audio.muted = true;
    audio.volume = 1;
    let unlockPromise;
    try {
      unlockPromise = audio.play();
    } catch (e) {
      console.warn('Audio unlock play threw:', e);
      try { URL.revokeObjectURL(silentUrl); } catch (e) {}
      return;
    }
    if (unlockPromise && unlockPromise.then) {
      unlockPromise.then(() => {
        console.log('Audio unlocked successfully (muted priming)');
        mobileAudioUnlockedRef.current = true;
        setMobileAudioUnlocked(true);
      }).catch((e) => {
        console.warn('Audio unlock play failed:', e);
        // Do NOT mark as unlocked — allow retry on next user gesture
      }).finally(() => {
        try { URL.revokeObjectURL(silentUrl); } catch (e) {}
      });
    } else {
      // Old browsers without promise-based play()
      mobileAudioUnlockedRef.current = true;
      setMobileAudioUnlocked(true);
      try { URL.revokeObjectURL(silentUrl); } catch (e) {}
    }
  }

  async function unlockMobileAudio() {
    // CRITICAL: synchronousAudioUnlock must be called SYNCHRONOUSLY before any
    // await to preserve the iOS user gesture context. An await before play()
    // causes the gesture to expire and autoplay permission to be denied.
    synchronousAudioUnlock();
    const context = await ensureAudioContext();
    if (context && context.state === 'suspended') {
      await context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
    }
  }

  async function ensureAudioUnlocked() {
    if (!mobileAudioUnlockedRef.current) {
      await unlockMobileAudio();
    } else {
      const context = await ensureAudioContext();
      if (context && context.state === 'suspended') {
        await context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
      }
    }
  }

  function stopAudioWarmup() {
    if (warmupOscRef.current) {
      try { warmupOscRef.current.stop(); } catch (e) {}
      warmupOscRef.current = null;
    }
    if (warmupGainRef.current) {
      try { warmupGainRef.current.disconnect(); } catch (e) {}
      warmupGainRef.current = null;
    }
  }

  async function playSpeakerTestSound() {
    try {
      await ensureAudioUnlocked();
      const context = await ensureAudioContext();
      if (!context) {
        setStatus('Speaker test unavailable in this browser');
        setLastAudioError({ type: 'no_audio_context', message: 'AudioContext not available' });
        return;
      }
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.28);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(context.currentTime);
      oscillator.stop(context.currentTime + 0.3);
      setPipelineStage('Speaker test played');
      setStatus('Speaker test played');
      setLastAudioError(null);
    } catch (error) {
      setPipelineStage(`Speaker blocked: ${error?.name || 'tap again'}`);
      setStatus('Speaker blocked. Check mute switch and volume.');
      setLastAudioError({ type: 'speaker_test', name: error?.name, message: error?.message });
    }
  }

  async function playServerVoiceTest() {
    try {
      await ensureAudioUnlocked();
      setPipelineStage('Loading test voice');
      setStatus('Loading test voice...');
      const response = await fetch(`${API_URL}/debug/tts-sample.wav?ts=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Voice test unavailable'));
      const buffer = await response.arrayBuffer();
      const url = URL.createObjectURL(new Blob([buffer], { type: response.headers.get('content-type') || 'audio/wav' }));
      const item = { url, buffer, mimeType: 'audio/wav' };
      if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
      lastTtsItemRef.current = item;
      setAudioReplayAvailable(true);
      playTtsItem(item, { revokeOnFinish: false, manual: true });
      setLastAudioError(null);
    } catch (error) {
      setPipelineStage('Voice test failed');
      setStatus(error.message || 'Voice test failed');
      setLastAudioError({ type: 'voice_test', name: error?.name, message: error?.message });
    }
  }

  async function warmVoiceCache(reason = 'idle') {
    const current = voiceWarmupRef.current;
    const now = Date.now();
    if (current.inFlight || now - current.lastAt < VOICE_WARMUP_COOLDOWN_MS) return false;
    current.inFlight = true;
    current.lastAt = now;
    try {
      const response = await fetch(`${API_URL}/debug/tts-sample.wav?warm=${encodeURIComponent(reason)}&ts=${now}`, { cache: 'no-store' });
      return response.ok;
    } catch (error) {
      console.warn('voice warmup failed:', error);
      return false;
    } finally {
      current.inFlight = false;
    }
  }

  async function testMicrophoneAndPlayback() {
    try {
      await ensureAudioUnlocked();
      setPipelineStage('Testing microphone');
      setStatus('Tap to record, then playback...');

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = createAudioRecorder(stream);
      const chunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        const url = URL.createObjectURL(blob);
        const audio = document.createElement('audio');
        audio.setAttribute('playsinline', '');
        audio.setAttribute('webkit-playsinline', '');
        audio.preload = 'auto';
        audio.playsInline = true;
        audio.muted = false;
        audio.volume = 1;
        audio.crossOrigin = 'anonymous';
        audio.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;';
        document.body.appendChild(audio);
        audio.src = url;
        const cleanup = () => {
          try { document.body.removeChild(audio); } catch (e) {}
          URL.revokeObjectURL(url);
        };
        audio.onended = () => {
          cleanup();
          setLastAudioError(null);
        };
        audio.onerror = () => {
          cleanup();
          setPipelineStage('Mic playback failed');
          setStatus('Mic playback failed');
          setLastAudioError({ type: 'mic_playback', message: 'Audio element error' });
        };
        audio.play().then(() => {
          setPipelineStage('Mic test played');
          setStatus('Mic test: recording played back');
        }).catch((error) => {
          cleanup();
          setPipelineStage('Mic playback blocked');
          setStatus('Mic playback blocked: ' + (error?.name || 'unknown'));
          setLastAudioError({ type: 'mic_playback_blocked', name: error?.name, message: error?.message });
        });
      };

      mediaRecorder.start();
      setPipelineStage('Recording...');
      setStatus('Recording 1 second...');

      setTimeout(() => {
        mediaRecorder.stop();
      }, 1000);
    } catch (error) {
      setPipelineStage('Mic test failed');
      setStatus(error.message || 'Microphone unavailable');
      setLastAudioError({ type: 'mic_test', name: error?.name, message: error?.message });
    }
  }

  async function translateText() {
    if (processing || !text.trim()) return;
    setProcessing(true);
    setStatus('Translating text...');
    try {
      const response = await fetch(`${API_URL}/translate/text`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
          synthesize_audio: false,
          session_id: sessionId,
          device_id: INITIAL_DEVICE_ID,
          speaker_name: INITIAL_SPEAKER_NAME,
          speaker_mode: speakerMode,
        }),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Text translation failed'));
      const data = await response.json();
      setResult(data);
      setLiveTranslation(data.translated_text || '');
      rememberSpeaker(data);
      if (data.session) applySharedSession(data.session);
      else appendConversationTurn(data);
      if (data.clarify) {
        setStatus(data.clarify_message || 'Clarification requested');
        setLiveTranslation(data.translated_text || '');
        setClarifyMessage(data.clarify_message || 'Clarification requested');
        setClarifyVisible(true);
      } else {
        setStatus('Text translated');
      }
    } catch (error) {
      setStatus(error.message || 'Text translation failed');
    } finally {
      setProcessing(false);
    }
  }

  async function playEmbeddedTranslationAudio(data, endStatus = 'Voice played') {
    if (!data?.audio_base64) return false;
    await ensureAudioUnlocked().catch((e) => console.warn('embedded audio unlock failed:', e));
    const binary = atob(data.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    if (buffer.byteLength < 100) return false;
    const mimeType = data.mime_type || 'audio/wav';
    const url = URL.createObjectURL(new Blob([buffer], { type: mimeType }));
    const item = { url, buffer, mimeType };
    if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
    lastTtsItemRef.current = item;
    setAudioReplayAvailable(true);
    setPlaying(true);
    const playDelay = isIosOrSafariRecorder() ? 300 : 0;
    window.setTimeout(() => {
      playTtsItem(item, {
        revokeOnFinish: false,
        manual: true,
        onEnd: () => {
          setPlaying(false);
          resumeInterpreterAfterPlayback(endStatus);
        },
      });
    }, playDelay);
    return true;
  }

  async function fetchTranslationVoice(textToSpeak, language, activeAuthToken) {
    const spokenText = String(textToSpeak || '').trim();
    if (!spokenText) return null;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), FAST_TTS_TIMEOUT_MS);
    try {
      const response = await fetch(`${API_URL}/tts`, {
        method: 'POST',
        headers: authHeaders(activeAuthToken, { 'Content-Type': 'application/json' }),
        signal: controller.signal,
        body: JSON.stringify({ text: spokenText, language }),
      });
      window.clearTimeout(timeoutId);
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Voice unavailable'));
      return await response.json();
    } catch (error) {
      window.clearTimeout(timeoutId);
      if (error?.name === 'AbortError') {
        setStatus('Voice is slow. Translation is ready.');
        setPipelineStage('Voice timed out');
      } else {
        setStatus(error.message || 'Voice unavailable');
        setPipelineStage('Voice unavailable');
      }
      return null;
    }
  }

  async function submitRecognizedSpeech(recognizedText) {
    const spokenText = String(recognizedText || '').trim();
    speechFastPathActiveRef.current = false;
    speechRecognitionRef.current = null;
    setStreaming(false);
    setInstantListening(false);
    if (!spokenText) {
      setProcessing(false);
      setPipelineStage('Ready');
      setStatus('No speech heard');
      return;
    }

    setPartialTranscript(spokenText);
    setProcessing(true);
    setPipelineStage('Translating');
    setStatus('Translating speech...');
    const capturedAt = streamStartedAtRef.current || performance.now();
    const requestStartedAt = performance.now();
    updateLatency('mic_to_backend', Math.round(requestStartedAt - capturedAt));
    updateLatency('backend_response', '-');
    updateLatency('first_audio', '-');
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), FAST_SPEECH_TIMEOUT_MS);
    try {
      const activeAuthToken = await ensureAuthToken();
      const response = await fetch(`${API_URL}/translate/text`, {
        method: 'POST',
        headers: authHeaders(activeAuthToken, { 'Content-Type': 'application/json' }),
        signal: controller.signal,
        body: JSON.stringify({
          text: spokenText,
          source_language: sourceLanguage,
          target_language: targetLanguage,
          synthesize_audio: false,
          session_id: sessionId,
          device_id: INITIAL_DEVICE_ID,
          speaker_name: INITIAL_SPEAKER_NAME,
          speaker_mode: speakerMode,
        }),
      });
      window.clearTimeout(timeoutId);
      const backendResponseMs = Math.round(performance.now() - requestStartedAt);
      updateLatency('backend_response', backendResponseMs);
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Speech translation failed'));
      const data = await response.json();
      const endToEndMs = Math.round(performance.now() - capturedAt);
      updateLatency('end_to_end', endToEndMs);
      setResult(data);
      setLiveTranslation(data.translated_text || '');
      rememberSpeaker(data);
      if (data.session) applySharedSession(data.session);
      else appendConversationTurn(data);
      if (data.clarify) {
        setClarifyMessage(data.clarify_message || 'Clarification requested');
        setClarifyVisible(true);
        setPipelineStage('Clarification needed');
        setStatus(data.clarify_message || 'Clarification requested');
        recordLatencyTurn({ total: endToEndMs, backend: backendResponseMs, audio: null });
        return;
      }
      setPipelineStage('Translation ready');
      setStatus('Translation ready. Loading voice...');
      const voiceData = await fetchTranslationVoice(data.translated_text, targetLanguage, activeAuthToken);
      const firstAudioMs = voiceData?.audio_base64 ? Math.round(performance.now() - capturedAt) : null;
      if (firstAudioMs) updateLatency('first_audio', firstAudioMs);
      recordLatencyTurn({ total: endToEndMs, backend: backendResponseMs, audio: firstAudioMs });
      if (voiceData?.audio_base64) {
        setPipelineStage('Playing voice');
        setStatus('Playing voice...');
      }
      const played = await playEmbeddedTranslationAudio(
        voiceData ? { ...data, ...voiceData, translated_text: data.translated_text } : data,
        'Ready',
      );
      if (!played) resumeInterpreterAfterPlayback('Ready');
    } catch (error) {
      window.clearTimeout(timeoutId);
      const timedOut = error?.name === 'AbortError';
      if (timedOut) {
        setLatencyStats((current) => ({
          ...current,
          backend_response: `${FAST_SPEECH_TIMEOUT_MS}ms+`,
          end_to_end: `${FAST_SPEECH_TIMEOUT_MS}ms+`,
        }));
        setPipelineStage('Translation timed out');
        setStatus('Network slow. Ready to try again.');
        resumeInterpreterAfterPlayback('Ready to listen');
      } else {
        setPipelineStage('Speech translation failed');
        setStatus(error.message || 'Speech translation failed');
      }
    } finally {
      setProcessing(false);
    }
  }

  async function startCamera() {
    try {
      if (streamRef.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      streamRef.current = stream;
      const el = videoRef.current || document.createElement('video');
      el.setAttribute('playsinline', '');
      el.muted = true;
      el.srcObject = stream;
      await el.play();
      videoRef.current = el;
      setCameraActive(true);
      setStatus('Camera ready');
    } catch (e) {
      setStatus('Camera permission denied');
    }
  }

  async function stopCamera() {
    try { streamRef.current?.getTracks()?.forEach((t) => t.stop()); } catch {}
    streamRef.current = null;
    setCameraActive(false);
  }

  async function captureAndTranslateFrame() {
    if (!videoRef.current) { setStatus('Open camera first'); return; }
    try {
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 360;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
      const form = new FormData();
      form.append('image', blob, 'frame.png');
      form.append('source_language', 'auto');
      form.append('target_language', targetLanguage);
      form.append('synthesize_audio', 'false');
      setStatus('OCR translating...');
      const resp = await fetch(`${API_URL}/translate/image`, { method: 'POST', headers: authHeaders(authToken), body: form });
      if (!resp.ok) throw new Error(await responseErrorMessage(resp, 'OCR failed'));
      const data = await resp.json();
      setOcrText(data.ocr_text || '');
      setResult({ source_text: data.ocr_text || '', translated_text: data.translated_text || '' });
      setLiveTranslation(data.translated_text || '');
      setStatus('Image translated');
    } catch (e) {
      setStatus(e.message || 'OCR failed');
    }
  }

  async function login() {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      setStatus('Login failed');
      return;
    }
    const data = await response.json();
    localStorage.setItem('translator_token', data.access_token);
    setAuthToken(data.access_token);
    setStatus(`Logged in as ${username}`);
  }

  async function ensureAuthToken() {
    if (authToken) return authToken;
    return '';
  }

  async function loadAnalytics() {
    if (!authToken) {
      setStatus('Log in to view analytics');
      return;
    }
    const response = await fetch(`${API_URL}/analytics`, { headers: authHeaders(authToken) });
    if (!response.ok) {
      setStatus('Analytics unavailable');
      return;
    }
    setAnalytics(await response.json());
    setStatus('Analytics refreshed');
  }

  async function loadDiagnostics() {
    setDiagnosticsStatus('checking');
    try {
      const response = await fetch(`${API_URL}/diagnostics`);
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Diagnostics unavailable'));
      const data = await response.json();
      setDiagnostics(data);
      setDiagnosticsStatus(data.ready ? 'online' : 'checking');
    } catch {
      setDiagnosticsStatus('offline');
    }
  }

  function testAudioSocket() {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, authToken));
      const timeout = window.setTimeout(() => {
        socket.close();
        reject(new Error('Audio socket timed out'));
      }, 6000);

      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'ping' }));
      };
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type !== 'pong') return;
        window.clearTimeout(timeout);
        socket.close();
        resolve('pong');
      };
      socket.onerror = () => {
        window.clearTimeout(timeout);
        reject(new Error('Audio socket failed'));
      };
    });
  }

  async function runSelfTest() {
    setSelfTest({ status: 'running', translation: 'checking', websocket: 'checking', message: 'Running checks...' });
    setStatus('Running self test...');

    const next = {
      status: 'online',
      translation: '-',
      websocket: '-',
      message: 'Self-test passed',
    };
    const failures = [];

    try {
      const response = await fetch(`${API_URL}/translate/text`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text: 'hello world', source_language: 'en', target_language: 'es', synthesize_audio: false }),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Translation test failed'));
      const data = await response.json();
      if (!data.translated_text?.trim()) throw new Error('Translation returned empty text');
      next.translation = data.translated_text;
    } catch (error) {
      next.translation = 'failed';
      failures.push(error.message || 'Translation test failed');
    }

    try {
      next.websocket = await testAudioSocket();
    } catch (error) {
      next.websocket = 'failed';
      failures.push(error.message || 'Audio socket test failed');
    }

    if (failures.length) {
      next.status = 'offline';
      next.message = failures.join(' / ');
      setStatus('Self-test failed');
    } else {
      setStatus('Self-test passed');
    }

    setSelfTest(next);
  }

  function logout() {
    localStorage.removeItem('translator_token');
    setAuthToken('');
    setStatus('Logged out');
  }

  function updateSessionId(value) {
    const normalized = normalizeSessionId(value) || crypto.randomUUID();
    setSessionId(normalized);
    localStorage.setItem('translator_session_id', normalized);
  }

  async function shareConversationRoom() {
    const shareUrl = new URL(window.location.origin);
    shareUrl.searchParams.set('session', sessionId);
    const url = shareUrl.toString();
    const payload = {
      title: 'Universal Translator',
      text: 'Join my live translator room.',
      url,
    };
    try {
      if (navigator.share) {
        await navigator.share(payload);
        setStatus('Room link shared');
      } else {
        await copyToClipboard(url, 'room');
        setStatus('Room link copied');
      }
    } catch (error) {
      if (error?.name !== 'AbortError') {
        await copyToClipboard(url, 'room');
        setStatus('Room link copied');
      }
    }
  }

  function rememberSpeaker(data = {}) {
    const speakerId = data.speaker || '';
    const label = data.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    if (label && label !== 'Person') setDetectedSpeaker(label);
    return label;
  }

  function normalizeConversationTurn(turn, index = 0) {
    const speakerId = turn.speaker || '';
    const label = turn.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    return {
      id: `${turn.created_at || Date.now()}-${speakerId || index}-${index}`,
      speaker: speakerId,
      speaker_label: label,
      source_text: turn.source_text || '',
      translated_text: turn.translated_text || '',
      created_at: turn.created_at || Date.now() / 1000,
    };
  }

  function appendConversationTurn(turn) {
    const normalized = normalizeConversationTurn(turn);
    setConversationTurns((current) => {
      const nextKey = `${normalized.speaker}-${normalized.created_at}-${normalized.source_text}`;
      const withoutDuplicate = current.filter((item) => `${item.speaker}-${item.created_at}-${item.source_text}` !== nextKey);
      return [...withoutDuplicate, normalized].slice(-6);
    });
  }

  function updateLatency(metric, ms) {
    setLatencyStats((current) => ({ ...current, [metric]: formatLatencyValue(ms) }));
  }

  function recordLatencyTurn(entry) {
    if (!Number.isFinite(entry.total) || entry.total <= 0) return;
    setLatencyHistory((current) => [
      ...current,
      {
        total: Math.round(entry.total),
        backend: Number.isFinite(entry.backend) ? Math.round(entry.backend) : null,
        audio: Number.isFinite(entry.audio) ? Math.round(entry.audio) : null,
        created_at: Date.now(),
      },
    ].slice(-LATENCY_HISTORY_LIMIT));
  }

  function resetStreamState() {
    if (streamSafetyTimeoutRef.current) {
      window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = null;
    }
    if (streamFinalizeTimerRef.current) {
      window.clearTimeout(streamFinalizeTimerRef.current);
      streamFinalizeTimerRef.current = null;
    }
    setRecording(false);
    setStreaming(false);
    setInstantListening(false);
    setProcessing(false);
    setPlaying(false);
    setInterpreterMode(false);
    ttsPlayingRef.current = false;
    streamFinalizePendingRef.current = false;
    streamRecordingStartedAtRef.current = 0;
    holdToTalkReleasePendingRef.current = false;
    audioSendQueueRef.current = [];
    ttsQueueRef.current = [];
    setTtsQueueLength(0);
    setTtsChunksBuffer([]);
    if (currentTtsFinishRef.current) {
      const fn = currentTtsFinishRef.current;
      currentTtsFinishRef.current = null;
      fn();
    }
    if (canplayTimeoutRef.current) {
      window.clearTimeout(canplayTimeoutRef.current);
      canplayTimeoutRef.current = null;
    }
  }

  function activePacketMs() {
    if (lowBandwidthMode) return 500;
    if (isIosOrSafariRecorder()) return EXPERIMENTAL_IOS_STREAMING ? 140 : Math.max(STREAM_PACKET_MS, 400);
    return Math.min(STREAM_PACKET_MS, 100);
  }

  function sendAudioPacket(socket, packet) {
    if (socket.readyState !== WebSocket.OPEN) return false;
    try {
      console.log('sending audio chunk', packet.meta.bytes, packet.meta.mime_type);
      socket.send(JSON.stringify(packet.meta));
      socket.send(packet.buffer);
      return true;
    } catch (e) {
      console.error('WebSocket send failed:', e);
      return false;
    }
  }

  function queueAudioPacket(packet) {
    const queue = audioSendQueueRef.current;
    if (queue.length >= MAX_BUFFERED_AUDIO_CHUNKS) queue.shift();
    queue.push(packet);
  }

  function flushAudioSendQueue(socket) {
    const queue = audioSendQueueRef.current;
    while (queue.length > 0 && socket.readyState === WebSocket.OPEN) {
      const packet = queue[0];
      if (!sendAudioPacket(socket, packet)) break;
      queue.shift();
    }
  }

  async function sendRecorderChunk(socket, event, recorder) {
    if (event.data.size <= 0) return;
    console.log('AUDIO CHUNK:', event.data);
    if (audioSendQueueRef.current.length >= MAX_AUDIO_SEND_QUEUE && socket.readyState === WebSocket.OPEN) {
      audioSendQueueRef.current.shift();
    }
    const buffer = await event.data.arrayBuffer();
    const packet = {
      meta: {
        type: 'chunk_meta',
        sent_at_ms: Date.now(),
        captured_at_ms: performance.now(),
        bytes: buffer.byteLength,
        mime_type: recorder?.mimeType || event.data.type || preferredAudioMimeType(),
      },
      buffer,
    };
    if (!sendAudioPacket(socket, packet)) queueAudioPacket(packet);
  }

  function stopTracks(stream) {
    stopMicMeter();
    stream?.getTracks().forEach((track) => track.stop());
  }

  function clearStreamHeartbeat() {
    if (streamHeartbeatRef.current?.timer) {
      window.clearInterval(streamHeartbeatRef.current.timer);
    }
    streamHeartbeatRef.current = { timer: null, missed: 0 };
  }

  function markStreamPong() {
    streamHeartbeatRef.current.missed = 0;
    setConnectionStatus('online');
  }

  function startStreamHeartbeat(socket) {
    clearStreamHeartbeat();
    streamHeartbeatRef.current = { timer: null, missed: 0 };
    const timer = window.setInterval(() => {
      if (socketRef.current !== socket) {
        clearStreamHeartbeat();
        return;
      }
      if (socket.readyState !== WebSocket.OPEN) return;
      streamHeartbeatRef.current.missed += 1;
      if (streamHeartbeatRef.current.missed > STREAM_HEARTBEAT_MAX_MISSES) {
        setPipelineStage('Connection heartbeat missed');
        setStatus('Reconnecting stream...');
        socket.close();
        return;
      }
      socket.send(JSON.stringify({ type: 'ping' }));
    }, STREAM_HEARTBEAT_MS);
    streamHeartbeatRef.current.timer = timer;
  }

  function disableStreamReconnect() {
    streamReconnectRef.current = { ...streamReconnectRef.current, enabled: false };
  }

  function finalizeCurrentStream(nextStatus = 'Processing stream...', options = {}) {
    if (!socketRef.current) return false;
    if (socketRef.current.readyState !== WebSocket.OPEN && !streamRecorderRef.current) return false;
    const recorder = streamRecorderRef.current;
    if (options.delay !== false && recorder?.state === 'recording' && streamRecordingStartedAtRef.current) {
      const remainingMs = MIN_STREAM_CAPTURE_MS - (performance.now() - streamRecordingStartedAtRef.current);
      if (remainingMs > 0) {
        if (!streamFinalizeTimerRef.current) {
          setPipelineStage('Keep speaking');
          setStatus('Keep speaking for a moment...');
          streamFinalizeTimerRef.current = window.setTimeout(() => {
            streamFinalizeTimerRef.current = null;
            finalizeCurrentStream(nextStatus, { delay: false });
          }, remainingMs);
        }
        return true;
      }
    }
    if (streamFinalizeTimerRef.current) {
      window.clearTimeout(streamFinalizeTimerRef.current);
      streamFinalizeTimerRef.current = null;
    }
    disableStreamReconnect();
    clearStreamHeartbeat();
    streamFinalizePendingRef.current = true;
    if (recorder?.state === 'recording') {
      recorder.requestData?.();
      recorder.stop();
    } else if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'finalize' }));
    }
    setStreaming(false);
    setInstantListening(false);
    setProcessing(true);
    releaseWakeLock();
    setPipelineStage('Processing');
    setStatus(nextStatus);
    setUserRequestedPlayback(true);
    return true;
  }

  function stopBrowserSpeechFastPath() {
    if (!speechFastPathActiveRef.current) return false;
    try {
      speechRecognitionRef.current?.stop?.();
    } catch (error) {
      console.warn('speech recognition stop failed:', error);
    }
    setStreaming(false);
    setInstantListening(false);
    setProcessing(true);
    setPipelineStage('Processing');
    setStatus('Processing speech...');
    return true;
  }

  function startBrowserSpeechFastPath() {
    const Recognition = speechRecognitionConstructor();
    const current = appStateRef.current;
    if (!Recognition || socketRef.current || current.recording || current.processing || current.playing) return false;

    let recognition;
    try {
      recognition = new Recognition();
    } catch (error) {
      console.warn('speech recognition unavailable:', error);
      return false;
    }

    speechRecognitionRef.current = recognition;
    speechFastPathActiveRef.current = true;
    speechFinalTextRef.current = '';
    speechInterimTextRef.current = '';
    setMicPermission('available');
    setInterpreterMode(true);
    setDetectedSpeaker('Phone speaker');
    setLatencyStats(blankLatencyStats());
    setResult(null);
    setPartialTranscript('');
    setLiveTranslation('');
    setStreaming(true);
    setInstantListening(false);
    setProcessing(false);
    setPipelineStage('Listening');
    setStatus('Listening...');
    streamStartedAtRef.current = performance.now();
    requestWakeLock();

    recognition.lang = speechRecognitionLanguage(sourceLanguage);
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let interim = '';
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = event.results[i]?.[0]?.transcript || '';
        if (event.results[i].isFinal) finalText += `${transcript} `;
        else interim += `${transcript} `;
      }
      if (finalText.trim()) {
        speechFinalTextRef.current = `${speechFinalTextRef.current} ${finalText}`.trim();
      }
      speechInterimTextRef.current = interim.trim();
      const visibleText = `${speechFinalTextRef.current} ${interim}`.trim();
      if (visibleText) setPartialTranscript(visibleText);
    };

    recognition.onerror = (event) => {
      const message = event?.error || 'speech recognition error';
      console.warn('speech recognition error:', message);
      if (message === 'not-allowed' || message === 'service-not-allowed') {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        releaseWakeLock();
        setMicPermission('denied');
        setStreaming(false);
        setStatus('Microphone permission blocked');
        setPipelineStage('Permission blocked');
        return;
      }
      if (!speechFinalTextRef.current.trim()) {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        releaseWakeLock();
        setStreaming(false);
        setStatus('Using audio fallback...');
        setPipelineStage('Audio fallback');
        window.setTimeout(() => toggleStreaming({ interpreter: true, speakerMode: 'auto' }), 80);
      }
    };

    recognition.onend = () => {
      if (!speechFastPathActiveRef.current) return;
      const finalText = (speechFinalTextRef.current || speechInterimTextRef.current || '').trim();
      releaseWakeLock();
      submitRecognizedSpeech(finalText);
    };

    try {
      recognition.start();
      haptic(14);
      return true;
    } catch (error) {
      console.warn('speech recognition start failed:', error);
      speechFastPathActiveRef.current = false;
      speechRecognitionRef.current = null;
      releaseWakeLock();
      setStreaming(false);
      setPipelineStage('Audio fallback');
      setStatus('Using audio fallback...');
      return false;
    }
  }

  function resumeInterpreterAfterPlayback(endStatus = 'Ready') {
    const current = appStateRef.current;
    if (!current.interpreterMode || current.speakerMode !== 'auto' || holdToTalkActiveRef.current) {
      setStatus(endStatus);
      setPipelineStage('Ready');
      return;
    }

    setStatus('Ready to listen');
    setPipelineStage('Ready to listen');
    window.setTimeout(() => {
      const latest = appStateRef.current;
      if (!latest.interpreterMode || latest.speakerMode !== 'auto') return;
      if (socketRef.current || speechFastPathActiveRef.current || latest.recording || latest.processing || latest.playing) return;
      if (startBrowserSpeechFastPath()) return;
      toggleStreaming({ interpreter: true, speakerMode: 'auto' });
    }, 450);
  }

  async function handleMicClick() {
    console.log('MIC BUTTON CLICKED');
    if (ignoreNextMicClickRef.current) {
      ignoreNextMicClickRef.current = false;
      return;
    }
    synchronousAudioUnlock();
    if (stopBrowserSpeechFastPath()) return;
    if (!socketRef.current && startBrowserSpeechFastPath()) return;
    if (isIosOrSafariRecorder() && !EXPERIMENTAL_IOS_STREAMING) {
      haptic(recording ? 8 : 14);
      if (recording) stopRecording();
      else startRecording();
      return;
    }
    haptic(socketRef.current ? 8 : 14);
    setInstantListening(!socketRef.current);
    toggleStreaming({ interpreter: true, speakerMode: 'auto' });
  }

  async function handleMicPointerDown(event) {
    console.log('MIC BUTTON CLICKED');
    synchronousAudioUnlock();
    if (isIosOrSafariRecorder() && !EXPERIMENTAL_IOS_STREAMING) return;
    if (socketRef.current || processing || playing) return;
    haptic(8);
    setInstantListening(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    holdToTalkTimerRef.current = window.setTimeout(() => {
      holdToTalkActiveRef.current = true;
      holdToTalkReleasePendingRef.current = false;
      ignoreNextMicClickRef.current = true;
      toggleStreaming({ interpreter: true, speakerMode: 'auto', holdToTalk: true });
    }, HOLD_TO_TALK_DELAY_MS);
  }

  function handleMicPointerUp() {
    if (holdToTalkTimerRef.current) {
      window.clearTimeout(holdToTalkTimerRef.current);
      holdToTalkTimerRef.current = null;
    }
    if (!holdToTalkActiveRef.current) {
      setInstantListening(false);
      return;
    }
    haptic([8, 24, 8]);
    holdToTalkActiveRef.current = false;
    ignoreNextMicClickRef.current = true;
    if (!finalizeCurrentStream('Processing speech...')) {
      holdToTalkReleasePendingRef.current = true;
    }
  }

  function downloadPwaInstaller() {
    const appUrl = window.location.origin;
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Install Universal Translator</title></head><body style="font-family:system-ui;margin:24px;line-height:1.5"><h1>Install Universal Translator</h1><p>Open <a href="${appUrl}">${appUrl}</a>, then use your browser's Add to Home Screen or Install app option.</p><p><a href="${appUrl}">Open app now</a></p></body></html>`;
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'universal-translator-install.html';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus('Installer file downloaded');
  }

  function applySharedSession(session) {
    if (!session) return;
    setSharedSession(session);
    Object.values(session.speakers || {}).forEach((profile) => {
      if (profile?.speaker) {
        speakerLabelsRef.current = {
          ...speakerLabelsRef.current,
          [profile.speaker]: profile.speaker_label || fallbackSpeakerLabel(profile.speaker),
        };
      }
    });
    if (session.history?.length) {
      setConversationTurns(session.history.map((turn, index) => normalizeConversationTurn(turn, index)).slice(-6));
    }
    const latest = session.history?.[session.history.length - 1];
    if (latest) {
      const latestLabel = latest.speaker_label || speakerLabelsRef.current[latest.speaker] || fallbackSpeakerLabel(latest.speaker);
      setResult({
        source_text: latest.source_text,
        translated_text: latest.translated_text,
        audio_output_path: null,
      });
      setDetectedSpeaker(latestLabel);
      updateDuplexSpeaker(latest.speaker || 'A', {
        transcript: latest.source_text,
        translation: latest.translated_text,
        speaker_label: latestLabel,
        stage: 'Synced from shared session',
      });
    }
  }

  function startMicMeter(stream) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx || !stream) return;
      const ctx = micMeterRef.current.ctx || new Ctx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      // Smaller FFT + low smoothing = real-time response.
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.15;
      source.connect(analyser);
      // Use time-domain (waveform) data — reacts instantly, unlike FFT bins
      // which need a few frames to settle and feel laggy.
      const data = new Uint8Array(analyser.fftSize);
      micMeterRef.current = { ctx, analyser, source, data, raf: 0, stopped: false, smoothed: 0 };
      const tick = () => {
        if (micMeterRef.current.stopped) return;
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        let sumSq = 0;
        for (let i = 0; i < data.length; i += 1) {
          const v = (data[i] - 128) / 128; // -1..1
          const a = Math.abs(v);
          if (a > peak) peak = a;
          sumSq += v * v;
        }
        const rms = Math.sqrt(sumSq / data.length);
        // Blend RMS (loudness) with peak (transients) so taps & consonants pop.
        const raw = Math.min(1, rms * 2.4 + peak * 0.6);
        // Asymmetric smoothing: snap up fast, decay slowly. Feels live.
        const prev = micMeterRef.current.smoothed || 0;
        const smoothed = raw > prev ? raw : prev * 0.78 + raw * 0.22;
        micMeterRef.current.smoothed = smoothed;
        setMicLevel(smoothed);
        micMeterRef.current.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch (err) {
      console.warn('mic meter failed to start', err);
    }
  }

  function stopMicMeter() {
    const m = micMeterRef.current;
    if (!m) return;
    m.stopped = true;
    if (m.raf) cancelAnimationFrame(m.raf);
    try { m.source && m.source.disconnect(); } catch (e) { console.warn('Mic meter source disconnect error:', e); }
    try { m.analyser && m.analyser.disconnect(); } catch (e) { console.warn('Mic meter analyser disconnect error:', e); }
    try { m.ctx && m.ctx.state !== 'closed' && m.ctx.close(); } catch (e) { console.warn('Mic meter context close error:', e); }
    micMeterRef.current = {};
    setMicLevel(0);
  }

  function stopSilenceDetector() {
    if (silenceDetectRafRef.current) {
      cancelAnimationFrame(silenceDetectRafRef.current);
      silenceDetectRafRef.current = 0;
    }
    silenceSeenSpeechRef.current = false;
    silenceStartRef.current = 0;
  }

  function startSilenceDetector() {
    stopSilenceDetector();
    const tick = () => {
      if (recordingStoppedRef.current || mediaRecorderRef.current?.state !== 'recording') {
        stopSilenceDetector();
        return;
      }
      const level = micMeterRef.current?.smoothed || 0;
      if (!silenceSeenSpeechRef.current && level > 0.12) {
        silenceSeenSpeechRef.current = true;
        silenceStartRef.current = 0;
      } else if (silenceSeenSpeechRef.current && level < 0.045) {
        if (!silenceStartRef.current) {
          silenceStartRef.current = performance.now();
        } else if (performance.now() - silenceStartRef.current > 260) {
          stopSilenceDetector();
          try { stopRecording(); } catch (e) {}
          return;
        }
      } else if (level >= 0.045) {
        silenceStartRef.current = 0;
      }
      silenceDetectRafRef.current = requestAnimationFrame(tick);
    };
    silenceDetectRafRef.current = requestAnimationFrame(tick);
  }

  async function startRecording() {
    console.log('startRecording: called');
    if (recording || processing) {
      console.log('startRecording: already recording or processing, skipping');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('MIC STREAM ACTIVE:', stream);
      logAudioStream(stream);
    } catch (error) {
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    setMicPermission('available');
    chunksRef.current = [];
    recordingStoppedRef.current = false;
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      setStatus(error.message || 'Recording not supported');
      return;
    }
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      console.log('MOBILE AUDIO SIZE:', event.data.size);
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      stopMicMeter();
      uploadRecording().catch((err) => {
        console.error('uploadRecording error:', err);
        setProcessing(false);
        setStatus('Upload failed');
      });
    };
    startMicMeter(stream);
    try {
      if (isIosOrSafariRecorder()) {
        recorder.start();
      } else {
        recorder.start(250);
      }
    } catch (startErr) {
      console.error('Recorder start failed in startRecording:', startErr);
      stopTracks(stream);
      mediaRecorderRef.current = null;
      setStatus('Recording not supported on this device');
      setPipelineStage('Recording unsupported');
      return;
    }
    setRecording(true);
    setStatus('Listening...');
    startSilenceDetector();
  }

  function stopRecording() {
    console.log('stopRecording: called');
    if (recordingStoppedRef.current) {
      console.log('stopRecording: already stopped, skipping');
      return;
    }
    stopSilenceDetector();
    recordingStoppedRef.current = true;
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
    setRecording(false);
    setProcessing(true);
    setStatus('Processing...');
  }

  async function uploadRecording() {
    const recordingMimeType = mediaRecorderRef.current?.mimeType || preferredAudioMimeType() || 'audio/webm';
    const blob = new Blob(chunksRef.current, { type: recordingMimeType });
    if (blob.size === 0) {
      setProcessing(false);
      setStatus('No audio captured');
      return;
    }
    const formData = new FormData();
    formData.append('audio', blob, `recording${audioFileExtension(recordingMimeType)}`);
    formData.append('source_language', sourceLanguage);
    formData.append('target_language', targetLanguage);
    formData.append('synthesize_audio', 'true');

    try {
      console.log('UPLOAD: posting audio to', `${API_URL}/translate/audio`, 'size', blob.size);
      const response = await fetch(`${API_URL}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
      console.log('UPLOAD: response status', response.status);
      if (!response.ok) {
        const errText = await responseErrorMessage(response, 'Audio translation failed');
        console.error('UPLOAD: response not ok', response.status, errText);
        throw new Error(errText);
      }
      const data = await response.json();
      console.log('UPLOAD: response data keys', Object.keys(data));
      console.log('UPLOAD: translated_text', data.translated_text ? 'yes' : 'no');
      console.log('UPLOAD: audio_base64 length', data.audio_base64?.length || 0);
      if (data.clarify) {
        setResult(data);
        setStatus(data.clarify_message || 'Clarification requested');
        setLiveTranslation(data.translated_text || '');
        setClarifyMessage(data.clarify_message || 'Clarification requested');
        setClarifyVisible(true);
        return;
      }
      setResult(data);
      setStatus(data.translated_text ? (data.audio_base64 ? 'Playing...' : 'Audio translated') : 'No clear speech recognized');
      if (data.audio_base64) {
        await ensureAudioUnlocked().catch((e) => console.warn('uploadRecording audio unlock failed:', e));
        const binary = atob(data.audio_base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        console.log('UPLOAD: decoded audio buffer size', buffer.byteLength);
        // Validate WAV header
        if (buffer.byteLength >= 12) {
          const header = new Uint8Array(buffer, 0, 12);
          const riff = String.fromCharCode(...header.slice(0, 4));
          const wave = String.fromCharCode(...header.slice(8, 12));
          console.log('UPLOAD: WAV header', riff, wave, 'valid:', riff === 'RIFF' && wave === 'WAVE');
        } else {
          console.warn('UPLOAD: audio buffer too small for WAV header');
        }
        const url = URL.createObjectURL(new Blob([buffer], { type: data.mime_type || 'audio/wav' }));
        const item = { url, buffer, mimeType: data.mime_type || 'audio/wav' };
        if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
        lastTtsItemRef.current = item;
        setAudioReplayAvailable(true);
        setPlaying(true);
        console.log('UPLOAD: calling playTtsItem');
        // iOS needs a delay after mic release for the audio session to transition
        // from playAndRecord back to playback; 150ms is often too short.
        const playDelay = isIosOrSafariRecorder() ? 400 : 0;
        window.setTimeout(() => {
          console.log('UPLOAD: starting playback after', playDelay, 'ms delay');
          playTtsItem(item, { revokeOnFinish: false, manual: true, onEnd: () => {
            console.log('UPLOAD: playTtsItem finished');
            setPlaying(false);
            setStatus('Audio translated');
          }});
        }, playDelay);
      }
    } catch (error) {
      console.error('UPLOAD: catch error', error);
      setStatus(error.message || 'Audio translation failed');
    } finally {
      setProcessing(false);
    }
  }

  async function toggleStreaming(options = {}) {
    if (socketRef.current) {
      finalizeCurrentStream();
      return;
    }

    const reconnecting = options.reconnect === true;
    const cleanOptions = { ...options };
    delete cleanOptions.reconnect;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      logAudioStream(stream);
    } catch (error) {
      disableStreamReconnect();
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    const selectedSpeakerMode = cleanOptions.speakerMode || speakerMode;
    setMicPermission('available');
    await unlockMobileAudio();
    requestWakeLock();
    setInterpreterMode(Boolean(cleanOptions.interpreter || selectedSpeakerMode === 'auto'));
    setDetectedSpeaker('-');
    setLatencyStats(blankLatencyStats());
    firstAudioSeenRef.current = false;
    streamStartedAtRef.current = performance.now();
    streamReconnectRef.current = {
      enabled: true,
      options: {
        ...cleanOptions,
        interpreter: Boolean(cleanOptions.interpreter || selectedSpeakerMode === 'auto'),
        speakerMode: selectedSpeakerMode,
      },
      attempts: reconnecting ? streamReconnectRef.current.attempts : 0,
    };
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      disableStreamReconnect();
      resetStreamState();
      setStatus(error.message || 'Recording not supported');
      setPipelineStage('Recording unsupported');
      return;
    }
    const activeAuthToken = await ensureAuthToken();
    const socketUrl = withAuthToken(WS_AUDIO_URL, activeAuthToken);
    setWsDebug({ url: WS_AUDIO_URL, close: 'connecting', error: '-' });
    const socket = new WebSocket(socketUrl);
    socketRef.current = socket;
    socket.binaryType = 'arraybuffer';
    recorder.ondataavailable = (event) => {
      sendRecorderChunk(socket, event, recorder).catch((err) => {
        console.error('sendRecorderChunk error:', err);
      });
    };
    recorder.onstop = () => {
      if (streamFinalizePendingRef.current && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'finalize' }));
      }
      stopTracks(stream);
    };
    socket.onopen = () => {
      if (streamSafetyTimeoutRef.current) window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = window.setTimeout(() => {
        resetStreamState();
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) socket.close();
        if (socketRef.current === socket) socketRef.current = null;
        setStatus('Ready to try again');
        setPipelineStage('Safety reset');
      }, 15000);
      streamFinalizePendingRef.current = false;
      setConnectionStatus('online');
      setStreaming(true);
      setInstantListening(false);
      setResult(null);
      setPartialTranscript('');
      setLiveTranslation('');
      setPipelineStage('Listening');
      setStatus(selectedSpeakerMode === 'auto' ? 'Interpreter mode listening...' : 'Streaming audio...');
      socket.send(JSON.stringify({
        type: 'start',
        session_id: sessionId,
        device_id: INITIAL_DEVICE_ID,
        speaker_name: INITIAL_SPEAKER_NAME,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        speaker_mode: selectedSpeakerMode,
        speaker: selectedSpeakerMode === 'auto' ? 'auto' : 'A',
        mime_type: recorder.mimeType || preferredAudioMimeType(),
      }));
      flushAudioSendQueue(socket);
      startStreamHeartbeat(socket);
      streamRecorderRef.current = recorder;
      console.log('STEP 9: starting recorder');
      try {
        recorder.start(activePacketMs());
      } catch (startErr) {
        console.error('Recorder start failed:', startErr);
        stopTracks(stream);
        socket.close();
        socketRef.current = null;
        setStatus('Recording not supported on this device');
        setPipelineStage('Recording unsupported');
        return;
      }
      startMicMeter(stream);
      streamRecordingStartedAtRef.current = performance.now();
      console.log('STEP 10: recorder started, state=', recorder.state);
      if (cleanOptions.holdToTalk && holdToTalkReleasePendingRef.current) {
        holdToTalkReleasePendingRef.current = false;
        finalizeCurrentStream('Processing speech...');
      }
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WS MESSAGE:', event.data);
      if (data.type === 'pong') {
        markStreamPong();
        return;
      }
      if (data.type === 'session_restored' || data.type === 'session_sync') applySharedSession(data.session?.shared || data.session);
      if (data.type === 'speaker_detected') {
        const label = rememberSpeaker(data);
        setPipelineStage(`${label} detected`);
      }
      if (data.type === 'latency') {
        updateLatency(data.metric, data.ms);
      }
      if (data.type === 'clarify') {
        setPipelineStage('Clarification needed');
        setStatus(data.message || 'Clarification requested');
        setClarifyMessage(data.message || 'Clarification requested');
        setClarifyVisible(true);
      }
      if (data.type === 'stage') {
        setPipelineStage(data.message);
        setStatus(data.message);
      }
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        const playback = data.playback_owner_label || data.playback_owner;
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${playback ? ` - playback: ${playback}` : ''}`);
      }
      if (data.type === 'partial_transcription') {
        rememberSpeaker(data);
        setPartialTranscript(data.text);
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        setLiveTranslation(data.text);
        setPipelineStage('Live translation');
      }
      if (data.type === 'final_transcription') {
        rememberSpeaker(data);
        setPartialTranscript(data.text);
        setPipelineStage('Transcription ready');
      }
      if (data.type === 'live_translation') {
        rememberSpeaker(data);
        setLiveTranslation(data.text);
        setPipelineStage('Translation ready');
      }
      if (data.type === 'tts_start') {
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
        if (isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING) {
          // Pause mic capture to route audio to speaker reliably on iOS
          resumeAfterTtsRef.current = true;
          finalizeCurrentStream('Playing voice...', { delay: false });
        }
      }
      if (data.type === 'tts_audio_chunk') {
        if (!firstAudioSeenRef.current) {
          firstAudioSeenRef.current = true;
          updateLatency('first_audio', Math.round(performance.now() - streamStartedAtRef.current));
        }
        setPipelineStage(`Streaming voice: ${data.index}/${data.total}`);
        console.log(`Received TTS chunk ${data.index}/${data.total}, text: "${data.text}", audio size: ${data.audio_base64?.length || 0} chars`);
        ensureAudioUnlocked().catch((e) => console.warn('TTS chunk audio unlock failed:', e));
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'tts_end') {
        setPipelineStage('Voice stream complete');
        setTtsChunksBuffer((chunks) => {
          if (chunks.length === 0) {
            console.log('No TTS chunks to play');
            return [];
          }
          console.log(`Playing ${chunks.length} TTS chunks sequentially to bypass concatenation error`);
          let index = 0;
          const playNextChunk = () => {
            if (index >= chunks.length) {
              console.log('All chunks played');
              setPlaying(false);
              setTtsPlaying(false);
              setPipelineStage('Voice played');
              setStatus('Voice played');
              return;
            }
            const chunk = chunks[index];
            const url = URL.createObjectURL(new Blob([chunk], { type: 'audio/wav' }));
            const item = { url, buffer: chunk, mimeType: 'audio/wav' };
            if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
            lastTtsItemRef.current = item;
            setAudioReplayAvailable(true);
            console.log(`Playing chunk ${index + 1}/${chunks.length}, size: ${chunk.byteLength} bytes`);
            playTtsItem(item, { revokeOnFinish: true, manual: false, onEnd: () => {
              index++;
              playNextChunk();
            }});
          };
          ensureAudioUnlocked().catch((e) => console.warn('TTS end audio unlock failed:', e));
          console.log('Starting sequential TTS playback');
          playNextChunk();
          return [];
        });
        setTtsQueueLength(0);
        if (resumeAfterTtsRef.current && (isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING)) {
          resumeAfterTtsRef.current = false;
          window.setTimeout(() => {
            if (!socketRef.current) {
              toggleStreaming({ interpreter: true, speakerMode: 'auto' });
            }
          }, 250);
        }
      }
      if (data.type === 'error') {
        console.log('WS ERROR MESSAGE:', data);
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        resetStreamState();
        setPipelineStage('Hold and speak longer');
        setStatus(data.message || 'Stream failed');
        streamFinalizePendingRef.current = false;
        holdToTalkReleasePendingRef.current = false;
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        socket.close();
        socketRef.current = null;
      }
      if (data.type === 'vad' && data.speech_detected) setStatus('Streaming audio... speech detected');
      if (data.type === 'final') {
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        rememberSpeaker(data);
        setResult(data);
        if (data.session) {
          applySharedSession(data.session);
        } else {
          appendConversationTurn(data);
        }
        setProcessing(false);
        setPipelineStage('Complete');
        setStatus('Stream translated');
        if (streamRecorderRef.current?.state === 'recording') {
          streamFinalizePendingRef.current = false;
          streamRecorderRef.current.stop();
        }
        socket.close();
        socketRef.current = null;
      }
    };
    socket.onerror = (event) => {
      setWsDebug((current) => ({ ...current, error: 'socket error' }));
      setStatus('Stream connection error');
      setPipelineStage('Connection error');
      releaseWakeLock();
      resetStreamState();
      if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
      else stopTracks(stream);
    };
    socket.onclose = (event) => {
      setWsDebug((current) => ({
        ...current,
        close: `${event.code || 'no-code'} ${event.reason || 'no-reason'} clean:${event.wasClean ? 1 : 0}`,
      }));
      clearStreamHeartbeat();
      releaseWakeLock();
      resetStreamState();
      streamFinalizePendingRef.current = false;
      holdToTalkReleasePendingRef.current = false;
      if (streamRecorderRef.current === recorder) {
        if (streamRecorderRef.current.state === 'recording') {
          streamRecorderRef.current.stop();
        } else {
          stopTracks(stream);
        }
        streamRecorderRef.current = null;
      } else {
        stopTracks(stream);
      }
      if (socketRef.current === socket) socketRef.current = null;
      if (!streamReconnectRef.current.enabled) return;

      if (streamReconnectRef.current.attempts >= STREAM_RECONNECT_MAX_ATTEMPTS) {
        disableStreamReconnect();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        setStatus('Connection lost. Tap to restart.');
        setPipelineStage('Connection lost');
        setConnectionStatus('offline');
        return;
      }

      streamReconnectRef.current.attempts += 1;
      setStatus('Reconnecting stream...');
      setPipelineStage(`Reconnecting ${streamReconnectRef.current.attempts}/${STREAM_RECONNECT_MAX_ATTEMPTS}`);
      window.setTimeout(() => {
        if (!streamReconnectRef.current.enabled || socketRef.current) return;
        toggleStreaming({ ...(streamReconnectRef.current.options || {}), reconnect: true });
      }, STREAM_RECONNECT_MS);
    };
  }

  function enqueueTtsChunk(audioBase64, mimeType) {
    if (lowBandwidthMode) {
      setPipelineStage('Low-bandwidth mode: text translation only');
      return;
    }
    ensureAudioContext().catch((e) => console.warn('enqueueTtsChunk AudioContext failed:', e));
    const binary = atob(audioBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const bufferCopy = buffer.slice(0);
    setTtsChunksBuffer((prev) => [...prev, bufferCopy]);
    setTtsQueueLength((prev) => prev + 1);
  }

  function playTtsItem(item, { revokeOnFinish = true, manual = false, onEnd } = {}) {
    if (!item) return;
    if (currentTtsFinishRef.current) {
      const prevFinish = currentTtsFinishRef.current;
      currentTtsFinishRef.current = null;
      prevFinish();
    }
    console.log('playTtsItem: starting playback, manual=', manual, 'mimeType=', item.mimeType, 'buffer size=', item.buffer?.byteLength || 0);
    ttsPlayingRef.current = true;
    setTtsPlaying(true);
    setPlaying(true);
    setPipelineStage(manual ? 'Playing translation voice' : 'Playing voice');
    setStatus(manual ? 'Playing translation voice...' : 'Playing voice...');
    haptic(6);
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      currentTtsFinishRef.current = null;
      if (revokeOnFinish) URL.revokeObjectURL(item.url);
      ttsPlayingRef.current = false;
      setTtsPlaying(false);
      if (onEnd) onEnd();
      if (manual) {
        setPlaying(false);
        setPipelineStage('Voice played');
        if (!onEnd) setStatus('Voice played');
        return;
      }
      playNextTtsChunk();
    };
    currentTtsFinishRef.current = finish;
    const playWithHtmlAudio = () => {
      console.log('playWithHtmlAudio: using persistent audio element');
      if (!item?.url) {
        console.error('playWithHtmlAudio: no item.url available');
        finish();
        return;
      }
      const audio = persistentAudioRef.current;
      if (audio) {
        // Clean slate: clear old handlers, pause, reset time
        audio.onended = null;
        audio.onerror = null;
        audio.oncanplay = null;
        audio.oncanplaythrough = null;
        audio.onloadedmetadata = null;
        if (canplayTimeoutRef.current) {
          window.clearTimeout(canplayTimeoutRef.current);
          canplayTimeoutRef.current = null;
        }
        audio.src = '';
        audio.pause();
        audio.currentTime = 0;
        audio.src = item.url;
        audio.preload = 'auto';
        try { audio.load(); } catch (e) {}
        audio.muted = false;
        audio.volume = 1;
        audio.onended = finish;
        audio.onerror = (error) => {
          console.error('HTML audio error:', error);
          console.error('Audio error code:', audio?.error?.code, 'message:', audio?.error?.message);
          setLastAudioError({ type: 'tts_playback', message: `HTML audio error: ${error}` });
          finish();
        };

        let doPlayCalled = false;
        const doPlay = () => {
          if (doPlayCalled) return;
          doPlayCalled = true;
          console.log('Audio readyState:', audio.readyState, 'paused:', audio.paused, 'muted:', audio.muted, 'volume:', audio.volume, 'duration:', audio.duration);
          audio.play().then(() => {
            console.log('HTML audio playing successfully (persistent element)');
            setLastAudioError(null);
          }).catch((error) => {
            console.error('HTML audio play failed on persistent element:', error);
            // Nuclear fallback: try a completely fresh audio element
            console.log('Trying nuclear fallback with fresh audio element');
            const fresh = new Audio(item.url);
            fresh.setAttribute('playsinline', '');
            fresh.setAttribute('webkit-playsinline', '');
            fresh.preload = 'auto';
            fresh.playsInline = true;
            fresh.muted = false;
            fresh.volume = 1;
            fresh.crossOrigin = 'anonymous';
            fresh.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;';
            document.body.appendChild(fresh);
            fresh.onended = () => {
              finish();
              try { document.body.removeChild(fresh); } catch (e) {}
            };
            fresh.onerror = (err2) => {
              try { document.body.removeChild(fresh); } catch (e) {}
              finish();
              console.error('Fresh audio element also failed:', err2);
              ttsPlayingRef.current = false;
              setPlaying(false);
              setAudioReplayAvailable(true);
              setPipelineStage(`Audio playback blocked: ${error?.name || 'tap play voice'}`);
              setStatus('Tap Play Voice to hear translation');
              setLastAudioError({ type: 'tts_playback_blocked', name: error?.name, message: error?.message });
            };
            fresh.play().then(() => {
              console.log('Fresh audio element playing successfully');
              setLastAudioError(null);
            }).catch((err2) => {
              console.error('Fresh audio element play failed:', err2);
              try { document.body.removeChild(fresh); } catch (e) {}
              finish();
              ttsPlayingRef.current = false;
              setPlaying(false);
              setAudioReplayAvailable(true);
              setPipelineStage(`Audio playback blocked: ${err2?.name || 'tap play voice'}`);
              setStatus('Tap Play Voice to hear translation');
              setLastAudioError({ type: 'tts_playback_blocked', name: err2?.name, message: err2?.message });
            });
          });
        };

        // On iOS, wait for canplay to ensure the audio session is ready
        if (audio.readyState >= 2) {
          console.log('Audio already ready (readyState >= 2), playing immediately');
          doPlay();
        } else {
          console.log('Audio not ready yet (readyState:', audio.readyState, '), waiting for canplay');
          audio.oncanplay = () => {
            console.log('Audio canplay event fired, readyState:', audio.readyState);
            audio.oncanplay = null;
            if (canplayTimeoutRef.current) {
              window.clearTimeout(canplayTimeoutRef.current);
              canplayTimeoutRef.current = null;
            }
            doPlay();
          };
          // Timeout fallback in case canplay never fires
          canplayTimeoutRef.current = window.setTimeout(() => {
            if (audio.readyState < 2) {
              console.warn('Audio canplay timeout, readyState:', audio.readyState, 'error:', audio.error?.code);
              audio.oncanplay = null;
              // Try playing anyway as a last resort
              doPlay();
            }
          }, 500);
        }
        return;
      }

      // Fallback for browsers that don't need the persistent element trick
      const fallbackAudio = new Audio(item.url);
      fallbackAudio.setAttribute('playsinline', '');
      fallbackAudio.setAttribute('webkit-playsinline', '');
      fallbackAudio.preload = 'auto';
      fallbackAudio.playsInline = true;
      fallbackAudio.muted = false;
      fallbackAudio.volume = 1;
      fallbackAudio.crossOrigin = 'anonymous';
      fallbackAudio.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;';
      document.body.appendChild(fallbackAudio);
      fallbackAudio.onended = () => {
        finish();
        try { document.body.removeChild(fallbackAudio); } catch (e) {}
      };
      fallbackAudio.onerror = (error) => {
        try { document.body.removeChild(fallbackAudio); } catch (e) {}
        console.error('HTML audio error:', error);
        setLastAudioError({ type: 'tts_playback', message: `HTML audio error: ${error}` });
        finish();
      };
      fallbackAudio.play().then(() => {
        console.log('HTML audio playing successfully (fallback)');
        setLastAudioError(null);
      }).catch((error) => {
        console.error('HTML audio play failed:', error);
        try { document.body.removeChild(fallbackAudio); } catch (e) {}
        finish();
        ttsPlayingRef.current = false;
        setPlaying(false);
        setAudioReplayAvailable(true);
        setPipelineStage(`Audio playback blocked: ${error?.name || 'tap play voice'}`);
        setStatus('Tap Play Voice to hear translation');
        setLastAudioError({ type: 'tts_playback_blocked', name: error?.name, message: error?.message });
      });
    };
    // iOS Safari: skip AudioContext and use persistent HTML audio directly.
    // After microphone use, iOS audio session transitions can break AudioContext.
    if (isIosOrSafariRecorder()) {
      console.log('playTtsItem: iOS detected, using HTML audio directly');
      playWithHtmlAudio();
      return;
    }

    console.log('playTtsItem: trying AudioContext path');
    ensureAudioContext()
      .then((context) => {
        console.log('playTtsItem: AudioContext state', context?.state);
        if (!context || context.state !== 'running') {
          console.log('AudioContext not running, using HTML audio fallback');
          playWithHtmlAudio();
          return;
        }
        return context.decodeAudioData(item.buffer.slice(0))
          .then((audioBuffer) => {
            console.log('playTtsItem: decoded audio buffer, duration', audioBuffer.duration);
            const source = context.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(context.destination);
            source.onended = () => {
              window.clearTimeout(sourceSafetyTimeout);
              setLastAudioError(null);
              finish();
            };
            source.start(0);
            const sourceSafetyTimeout = window.setTimeout(() => {
              console.warn('AudioBufferSource safety timeout fired, forcing finish');
              finish();
            }, Math.ceil(audioBuffer.duration * 1000) + 1000);
            console.log('playTtsItem: AudioBufferSource started');
          })
          .catch((error) => {
            console.error('AudioContext decode failed, using HTML audio fallback:', error);
            setLastAudioError({ type: 'tts_decode', name: error?.name, message: error?.message });
            playWithHtmlAudio();
          });
      })
      .catch((error) => {
        console.error('AudioContext error, using HTML audio fallback:', error);
        setLastAudioError({ type: 'tts_context', name: error?.name, message: error?.message });
        playWithHtmlAudio();
      });
  }

  async function playTranslationAudio() {
    await ensureAudioUnlocked();
    const item = lastTtsItemRef.current;
    if (!item) return;
    if (item.buffer) {
      if (item.url) URL.revokeObjectURL(item.url);
      item.url = URL.createObjectURL(new Blob([item.buffer], { type: item.mimeType || 'audio/wav' }));
    }
    playTtsItem(item, { revokeOnFinish: false, manual: true });
  }

  function playNextTtsChunk() {
    if (ttsPlayingRef.current || ttsQueueRef.current.length === 0) {
      if (!ttsPlayingRef.current && ttsQueueRef.current.length === 0 && playing) {
        setPlaying(false);
        setTtsQueueLength(0);
        setPipelineStage('Ready to listen');
        setStatus('Ready to listen');
      }
      return;
    }

    const item = ttsQueueRef.current.shift();
    setTtsQueueLength(ttsQueueRef.current.length);
    console.log(`Playing TTS chunk, ${ttsQueueRef.current.length} remaining in queue`);
    playTtsItem(item, { revokeOnFinish: false });
  }

  function updateDuplexSpeaker(speaker, patch) {
    setDuplex((current) => ({
      ...current,
      [speaker]: { ...current[speaker], ...patch },
    }));
  }

  async function toggleDuplexSpeaker(speaker) {
    const refs = duplexRefs.current[speaker];
    if (refs.socket) {
      refs.manualClose = true;
      refs.shouldReconnect = false;
      refs.finalizePending = true;
      if (refs.recorder?.state === 'recording') {
        refs.recorder.requestData?.();
        refs.recorder.stop();
      } else if (refs.socket.readyState === WebSocket.OPEN) {
        refs.socket.send(JSON.stringify({ type: 'finalize' }));
      }
      updateDuplexSpeaker(speaker, { active: false, stage: 'Processing...' });
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('MIC STREAM ACTIVE:', stream);
      logAudioStream(stream);
    } catch (error) {
      setMicPermission('denied');
      updateDuplexSpeaker(speaker, { active: false, stage: mediaErrorMessage(error) });
      return;
    }
    setMicPermission('available');
    const activeAuthToken = await ensureAuthToken();
    const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, activeAuthToken));
    const source = speaker === 'A' ? sourceLanguage : targetLanguage;
    const target = speaker === 'A' ? targetLanguage : sourceLanguage;
    refs.manualClose = false;
    refs.shouldReconnect = true;
    refs.finalizePending = false;
    refs.socket = socket;
    socket.binaryType = 'arraybuffer';
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      updateDuplexSpeaker(speaker, { active: false, stage: error.message || 'Recording not supported' });
      return;
    }
    refs.recorder = recorder;
    recorder.ondataavailable = (event) => {
      console.log('MOBILE AUDIO SIZE:', event.data.size);
      sendRecorderChunk(socket, event, recorder).catch((err) => {
        console.error('Duplex sendRecorderChunk error:', err);
      });
    };
    recorder.onstop = () => {
      if (refs.finalizePending && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'finalize' }));
      }
      stopTracks(stream);
    };

    socket.onopen = () => {
      updateDuplexSpeaker(speaker, { active: true, transcript: '', translation: '', stage: 'Listening' });
      socket.send(JSON.stringify({
        type: 'start',
        session_id: sessionId,
        device_id: `${INITIAL_DEVICE_ID}-${speaker}`,
        speaker,
        speaker_label: `Speaker ${speaker}`,
        speaker_mode: 'manual',
        source_language: source,
        target_language: target,
        mime_type: recorder.mimeType || preferredAudioMimeType(),
      }));
      recorder.start(activePacketMs());
      startMicMeter(stream);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'session_restored') {
        applySharedSession(data.session?.shared);
        updateDuplexSpeaker(speaker, { stage: `Rebound session (${data.session.reconnects} reconnects)` });
      }
      if (data.type === 'session_sync') applySharedSession(data.session);
      if (data.type === 'speaker_detected') {
        const label = rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { speaker_label: label, stage: `${label} connected` });
      }
      if (data.type === 'stage') updateDuplexSpeaker(speaker, { stage: data.message });
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${data.playback_owner ? ` - playback: ${data.playback_owner}` : ''}`);
        if (!data.allowed && data.behavior === 'hold') {
          refs.recorder?.stop();
          refs.recorder?.stream.getTracks().forEach((track) => track.stop());
          socket.close();
          refs.socket = null;
          updateDuplexSpeaker(speaker, { active: false, stage: data.reason });
        }
      }
      if (data.type === 'final_transcription') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { transcript: data.text, stage: 'Transcription ready' });
      }
      if (data.type === 'semantic_context') {
        setSemanticContext({
          last_intent: data.last_intent,
          conversation_mood: data.conversation_mood,
          topics: data.topics || [],
        });
        updateDuplexSpeaker(speaker, { stage: `Intent: ${data.last_intent}, mood: ${data.conversation_mood}` });
      }
      if (data.type === 'live_translation') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Translation ready' });
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Live translation' });
      }
      if (data.type === 'tts_audio_chunk') {
        ensureAudioUnlocked().catch((e) => console.warn('Duplex TTS chunk audio unlock failed:', e));
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'error') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        updateDuplexSpeaker(speaker, { active: false, stage: data.message || 'Stream failed' });
        refs.finalizePending = false;
        if (refs.recorder?.state === 'recording') refs.recorder.stop();
        else stopTracks(stream);
        socket.close();
        refs.socket = null;
      }
      if (data.type === 'final') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        const label = rememberSpeaker(data);
        if (data.session) applySharedSession(data.session);
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          speaker_label: label,
          stage: 'Complete',
        });
        if (refs.recorder?.state === 'recording') {
          refs.finalizePending = false;
          refs.recorder.stop();
        }
        socket.close();
        refs.socket = null;
      }
    };

    socket.onerror = () => {
      updateDuplexSpeaker(speaker, { active: false, stage: 'Connection error' });
      setConversationBrain('WebSocket connection error');
      resetStreamState();
      setReconnectToastVisible(true);
    };
    socket.onclose = () => {
      updateDuplexSpeaker(speaker, { active: false });
      refs.finalizePending = false;
      stopTracks(stream);
      refs.socket = null;
      resetStreamState();
      if (refs.shouldReconnect && !refs.manualClose) {
        updateDuplexSpeaker(speaker, { stage: 'Reconnecting...' });
        window.setTimeout(() => toggleDuplexSpeaker(speaker), 1500);
      } else {
        setReconnectToastVisible(true);
      }
    };
  }


  const sourceText = partialTranscript || result?.source_text || 'Ready to listen';
  const translatedText = liveTranslation || result?.translated_text || 'Translation appears here';
  const hasSourceText = Boolean(partialTranscript || result?.source_text);
  const hasTranslatedText = Boolean(liveTranslation || result?.translated_text);
  const perceivedListening = streaming || instantListening;
  const micState = playing ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'idle';
  const micLabel = playing ? 'Speaking' : streaming ? 'Listening' : processing ? 'Processing' : 'Tap to Speak';
  const statusText = pipelineStage && pipelineStage !== 'Idle' ? pipelineStage : status;
  const showInstallAction = !pwaInstalled && (installPrompt || isManualInstallBrowser());
  const activeSpeakerLabel = detectedSpeaker && detectedSpeaker !== '-' && detectedSpeaker !== 'Person' ? detectedSpeaker : '';
  const recentConversationTurns = conversationTurns.slice(-4);
  const latencyItems = [
    { label: 'Text', value: latencyStats.end_to_end },
    { label: 'Backend', value: latencyStats.backend_response },
    { label: 'Audio', value: latencyStats.first_audio },
  ].filter((item) => item.value && item.value !== '-');
  const latencyTotalMs = Number.parseInt(String(latencyStats.end_to_end || ''), 10);
  const latencyTone = Number.isFinite(latencyTotalMs) && latencyTotalMs <= LATENCY_TARGET_MS ? 'fast' : Number.isFinite(latencyTotalMs) ? 'slow' : 'pending';
  const { average: latencyAverageMs, best: latencyBestMs } = summarizeLatencyHistory(latencyHistory);
  const latencyTrendItems = [
    { label: 'Avg', value: latencyAverageMs ? `${latencyAverageMs}ms` : '-' },
    { label: 'Best', value: latencyBestMs ? `${latencyBestMs}ms` : '-' },
  ].filter((item) => item.value !== '-');
  const latencyTrendTone = latencyAverageMs && latencyAverageMs <= LATENCY_TARGET_MS ? 'fast' : latencyAverageMs ? 'slow' : 'pending';

  return (
    <main className="app-shell">
      {updateAvailable && (
        <div role="alert" style={{ background: '#1d4ed8', color: '#ffffff', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', fontSize: '14px', fontWeight: 600, position: 'sticky', top: 0, zIndex: 50 }}>
          <span>Update available. Backend: <code style={{ background: 'rgba(255,255,255,.18)', padding: '2px 6px', borderRadius: 4 }}>{updateAvailable.backend}</code> | App: <code style={{ background: 'rgba(255,255,255,.18)', padding: '2px 6px', borderRadius: 4 }}>{updateAvailable.frontend}</code></span>
          <button type="button" onClick={async () => {
            try {
              const regs = await (navigator.serviceWorker && navigator.serviceWorker.getRegistrations && navigator.serviceWorker.getRegistrations());
              if (regs) { regs.forEach((r) => r.waiting && r.waiting.postMessage({ type: 'SKIP_WAITING' })); }
              const cacheNames = await caches.keys();
              await Promise.all(cacheNames.map((name) => caches.delete(name)));
            } catch (err) { console.warn('cache clear failed', err); }
            window.location.reload();
          }} style={{ background: '#ffffff', color: '#1d4ed8', border: 'none', padding: '6px 14px', borderRadius: 999, fontWeight: 700, cursor: 'pointer' }}>Reload</button>
        </div>
      )}
      {reconnectToastVisible && (
        <div role="alert" style={{ background: '#dc2626', color: '#ffffff', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', fontSize: '14px', fontWeight: 600, position: 'sticky', top: updateAvailable ? 48 : 0, zIndex: 49 }}>
          <span>Connection lost. Retry?</span>
          <button type="button" onClick={() => {
            setReconnectToastVisible(false);
            haptic(30);
            try { handleMicClick(); } catch {}
          }} style={{ background: '#ffffff', color: '#dc2626', border: 'none', padding: '6px 14px', borderRadius: 999, fontWeight: 700, cursor: 'pointer' }}>Retry</button>
        </div>
      )}
      <section className="phone-frame" data-connection={connectionStatus} data-smoke-check="Self Test">
        <header className="clean-header">
          <button className="room-share-action" type="button" onClick={shareConversationRoom} aria-label="Share speaker room" title="Share speaker room">
            <Share2 size={14} strokeWidth={2.4} aria-hidden="true" />
            <span className="sr-only">{copiedKey === 'room' ? 'Room link copied' : 'Share speaker room'}</span>
          </button>
          {showInstallAction && (
            <button className="install-action" type="button" onClick={installApp} aria-label="Install App" title="Install App">
              <Download size={14} strokeWidth={2.4} aria-hidden="true" />
              <span>Install App</span>
            </button>
          )}
          <h1 className="app-title">
            <span className="brand-mark">Anai</span>
            <sub>nrldc</sub>
          </h1>
          <div className="connection-indicator" data-status={connectionStatus}>
            <span className="connection-dot" />
            <span className="connection-label">{connectionStatus}</span>
          </div>
        </header>

        <section className="mic-panel">
          <button
            className={`mic-orb ${micState} ${perceivedListening ? 'listening-pulse' : ''}`}
            onClick={handleMicClick}
            onPointerDown={handleMicPointerDown}
            onPointerUp={handleMicPointerUp}
            onPointerCancel={handleMicPointerUp}
            onContextMenu={(event) => event.preventDefault()}
            disabled={playing || (processing && !streaming)}
            aria-label={micLabel}
            aria-live="polite"
          >
            <span className="orb-ring" />
            <span className="orb-spin" />
            <Mic className="mic-icon" size={62} strokeWidth={2.3} aria-hidden="true" />
            <span className="sr-only">{micLabel}</span>
            <span className="rec-led">
              <svg width="28" height="28" viewBox="0 0 28 28">
                <circle cx="14" cy="14" r="12" fill="#ef4444" filter="drop-shadow(0 0 6px rgba(239,68,68,.7))" />
                <circle cx="14" cy="14" r="5" fill="#ffffff" opacity="0.9" />
              </svg>
            </span>
          </button>
          <p className="mic-label">{micLabel}</p>
          {(streaming || recording) && (
            <div aria-hidden="true" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 4, height: 28, marginTop: 8 }}>
              {[0, 1, 2, 3, 4, 5, 6].map((i) => {
                const threshold = (i + 1) / 8;
                const active = micLevel >= threshold * 0.6;
                const heightPx = Math.max(6, Math.min(28, 6 + micLevel * 28 * (i === 3 ? 1 : 0.65 + Math.abs(3 - i) * 0.08)));
                return (
                  <span key={i} style={{
                    width: 5,
                    height: heightPx,
                    borderRadius: 3,
                    background: active ? 'linear-gradient(180deg,#34d399,#10b981)' : 'rgba(148,163,184,.35)',
                    transition: 'height 80ms ease, background 120ms ease',
                  }} />
                );
              })}
            </div>
          )}
          <p className="status-line">{statusText}</p>
          {activeSpeakerLabel && <p className="speaker-line">{activeSpeakerLabel}</p>}
          {latencyItems.length > 0 && (
            <div className="latency-strip" data-speed={latencyTone} aria-label="Translation timing">
              {latencyItems.map((item) => (
                <span className="latency-chip" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </span>
              ))}
            </div>
          )}
          {latencyTrendItems.length > 0 && (
            <div className="latency-strip latency-trend" data-speed={latencyTrendTone} aria-label="Recent timing trend">
              {latencyTrendItems.map((item) => (
                <span className="latency-chip" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </span>
              ))}
            </div>
          )}
          {audioReplayAvailable && autoPlayFailed && (
            <button className="play-voice-button compact-voice-action" type="button" onClick={playTranslationAudio} disabled={playing}>
              Play Voice
            </button>
          )}
          {processing && !streaming && !playing && <p className="thinking">Translating...</p>}
        </section>

        <section style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, margin: '8px 0 12px', flexWrap: 'wrap' }} aria-label="Target language">
          <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600, letterSpacing: '.04em', textTransform: 'uppercase' }}>
            Translate to
          </span>
          <div role="radiogroup" aria-label="Target language" style={{ display: 'inline-flex', borderRadius: 999, padding: 3, background: 'rgba(15,23,42,.55)', border: '1px solid rgba(148,163,184,.3)' }}>
            {TARGET_LANGUAGE_OPTIONS.map((opt) => {
              const active = targetLanguage === opt.code;
              return (
                <button
                  key={opt.code}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setTargetLanguage(opt.code)}
                  disabled={recording || processing}
                  style={{
                    minHeight: 32,
                    padding: '6px 14px',
                    borderRadius: 999,
                    border: 'none',
                    cursor: (recording || processing) ? 'not-allowed' : 'pointer',
                    fontSize: 13,
                    fontWeight: 600,
                    color: active ? '#0b1220' : '#cbd5e1',
                    background: active ? 'linear-gradient(180deg,#a5f3fc,#67e8f9)' : 'transparent',
                    transition: 'background .15s ease, color .15s ease',
                  }}
                >
                  {opt.label}
                  {opt.code === 'ht' && (
                    <span style={{ marginLeft: 4, fontSize: 10, opacity: .7 }} title="Audio uses eSpeak NG fallback (sounds robotic)">*</span>
                  )}
                </button>
              );
            })}
          </div>
        </section>

        <section className="translation-stack">
          <article className="transcript-card" style={{ position: 'relative', paddingBottom: hasSourceText ? 52 : undefined }}>
            <p className="transcript-text fade-in" key={sourceText}>{sourceText}</p>
            {hasSourceText && (
              <button
                type="button"
                onClick={() => copyToClipboard(sourceText, 'src')}
                aria-label="Copy transcript"
                style={{ position: 'absolute', bottom: 10, right: 10, minHeight: 36, padding: '8px 16px', borderRadius: 999, border: '1px solid rgba(148,163,184,.45)', background: copiedKey === 'src' ? '#10b981' : 'rgba(15,23,42,.65)', color: '#e5ecff', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'background .15s ease' }}
              >
                {copiedKey === 'src' ? 'Copied' : 'Copy'}
              </button>
            )}
          </article>
          <article className="translation-card" style={{ position: 'relative', paddingBottom: hasTranslatedText ? 52 : undefined }}>
            <p className="translation-text fade-in" key={translatedText}>{translatedText}</p>
            {cameraActive && (
              <div style={{ position: 'relative', marginTop: 10, display: 'grid', placeItems: 'center' }}>
                <video ref={videoRef} style={{ maxWidth: '100%', borderRadius: 12, border: '1px solid rgba(255,255,255,.15)' }} muted playsInline />
                {ocrText && <p className="transcript-text" style={{ marginTop: 8, opacity: .9 }}>OCR: {ocrText}</p>}
              </div>
            )}
            {hasTranslatedText && (
              <button
                type="button"
                onClick={() => copyToClipboard(translatedText, 'tr')}
                aria-label="Copy translation"
                style={{ position: 'absolute', bottom: 10, right: 10, minHeight: 36, padding: '8px 16px', borderRadius: 999, border: '1px solid rgba(148,163,184,.45)', background: copiedKey === 'tr' ? '#10b981' : 'rgba(15,23,42,.65)', color: '#e5ecff', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'background .15s ease' }}
              >
                {copiedKey === 'tr' ? 'Copied' : 'Copy'}
              </button>
            )}
          </article>
          {recentConversationTurns.length > 0 && (
            <section className="conversation-timeline" aria-label="Recent conversation">
              {recentConversationTurns.map((turn) => (
                <article className="conversation-turn" key={turn.id}>
                  <strong>{turn.speaker_label}</strong>
                  <span>{turn.source_text}</span>
                  <em>{turn.translated_text}</em>
                </article>
              ))}
            </section>
          )}
          {(clarifyVisible || result?.clarify || (result?.cip_decision?.type === 'clarification')) && (
            <div className="clarify-pill" role="status" aria-live="polite" style={{ marginTop: 10, padding: '10px 12px', border: '1px solid #facc15', background: '#fff3cd', color: '#92400e', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{clarifyMessage || result?.clarify_message || 'Clarification requested'}</span>
              <button type="button" onClick={() => {
                setClarifyVisible(false);
                haptic(20);
                setPipelineStage('Refine requested');
                setStatus('Please rephrase your request');
                if (!streaming && !processing) {
                  // Prompt new input via mic if idle
                  try { handleMicClick(); } catch {}
                }
              }} style={{ minHeight: 32, padding: '6px 12px', borderRadius: 999, border: '1px solid rgba(148,163,184,.45)', background: '#f59e0b', color: '#1f2937', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>Refine phrase</button>
            </div>
          )}
        </section>

        {false && showDebugPanel && (
          <section className="debug-panel">
            <div className="debug-header">
              <h3>Debug Panel</h3>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button type="button" onClick={loadDiagnostics}>Refresh</button>
                <button type="button" onClick={() => setShowDebugPanel(false)}>×</button>
              </div>
            </div>
            <div className="debug-grid">
              <div className="debug-item">
                <span className="debug-label">Connection:</span>
                <span className="debug-value">{connectionStatus}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Mic Permission:</span>
                <span className="debug-value">{micPermission}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Audio Context:</span>
                <span className="debug-value">{audioContextState}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Audio Unlocked:</span>
                <span className="debug-value">{mobileAudioUnlocked ? 'Yes' : 'No'}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Audio Replay:</span>
                <span className="debug-value">{audioReplayAvailable ? 'Yes' : 'No'}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">TTS Queue:</span>
                <span className="debug-value">{ttsQueueLength}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">TTS Playing:</span>
                <span className="debug-value">{ttsPlaying ? 'Yes' : 'No'}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Pipeline Stage:</span>
                <span className="debug-value">{pipelineStage}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Status:</span>
                <span className="debug-value">{status}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">Backend Diagnostics:</span>
                <span className="debug-value">{diagnosticsStatus}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">CIP Mode:</span>
                <span className="debug-value">{diagnostics?.cip?.mode || '-'}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">CIP Reachable:</span>
                <span className="debug-value" style={{ color: diagnostics?.cip?.reachable ? '#86efac' : '#fca5a5' }}>
                  {diagnostics?.cip ? (diagnostics.cip.reachable ? 'Yes' : 'No') : '-'}
                </span>
              </div>
              <div className="debug-item">
                <span className="debug-label">CIP Latency:</span>
                <span className="debug-value">{diagnostics?.cip?.latency_ms ?? '-'}{diagnostics?.cip?.latency_ms != null ? ' ms' : ''}</span>
              </div>
              <div className="debug-item">
                <span className="debug-label">CIP OpenAI:</span>
                <span className="debug-value" style={{ color: diagnostics?.cip?.openai?.translator?.configured ? '#86efac' : '#fca5a5' }}>
                  {diagnostics?.cip?.openai?.translator ? (diagnostics.cip.openai.translator.configured ? 'Configured' : 'Not configured') : '-'}
                </span>
              </div>
              <div className="debug-item">
                <span className="debug-label">CIP Translator:</span>
                <span className="debug-value">{diagnostics?.cip?.openai?.translator?.last || diagnostics?.cip?.openai?.error || '-'}</span>
              </div>
              <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                <span className="debug-label">CIP URL:</span>
                <span className="debug-value" style={{ color: diagnostics?.cip?.process_url ? '#93c5fd' : undefined }}>
                  {diagnostics?.cip?.process_url || '-'}
                </span>
              </div>
              {diagnostics?.cip?.error && (
                <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                  <span className="debug-label">CIP Error:</span>
                  <span className="debug-value" style={{ color: '#fca5a5' }}>{diagnostics.cip.error}</span>
                </div>
              )}
              {result?.translated_by && (
                <div className="debug-item">
                  <span className="debug-label">Translated by:</span>
                  <span className="debug-value">{result.translated_by}</span>
                </div>
              )}
              {result?.cip_decision && (
                <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                  <span className="debug-label">CIP Decision:</span>
                  <span className="debug-value" style={{ color: '#93c5fd' }}>
                    {JSON.stringify(result.cip_decision)}
                  </span>
                </div>
              )}
              {lastAudioError && (
                <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                  <span className="debug-label">Last Error:</span>
                  <span className="debug-value" style={{ color: '#fca5a5' }}>
                    {lastAudioError.type}: {lastAudioError.name || ''} {lastAudioError.message || ''}
                  </span>
                </div>
              )}
              <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                <span className="debug-label">Build:</span>
                <span className="debug-value" style={{ color: '#86efac' }}>ios-audio-fix-v3</span>
              </div>
              <div className="debug-item" style={{ gridColumn: '1 / -1' }}>
                <span className="debug-label">iOS path:</span>
                <span className="debug-value">
                  {isIosOrSafariRecorder() ? (EXPERIMENTAL_IOS_STREAMING ? 'WebSocket streaming (experimental)' : 'HTTP record-and-upload (no chunked WS)') : 'WebSocket streaming'}
                </span>
              </div>
            </div>
          </section>
        )}

      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
