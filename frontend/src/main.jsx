import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowLeftRight, Check, Clock3, Copy, Download, Languages, Mic, Radio, Repeat2, Share2, Sparkles, Trash2, UserRound, Volume2 } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';
import Assistant from './Assistant';
import ErrorBoundary from './ErrorBoundary';
import LanguageDock from './components/LanguageDock';
import SystemBanners from './components/SystemBanners';
import AppHeader from './components/AppHeader';
import DebugPanel from './components/DebugPanel';
import MicPanel from './components/MicPanel';
import TranslationStack from './components/TranslationStack';
import useCopyToClipboard from './hooks/useCopyToClipboard';
import useHaptic from './hooks/useHaptic';
import useInstallPrompt from './hooks/useInstallPrompt';
import useLatencyHistory from './hooks/useLatencyHistory';
import useDiagnostics from './hooks/useDiagnostics';
import useConversationHistory from './hooks/useConversationHistory';
import useSelfTest from './hooks/useSelfTest';
import useMicPermission from './hooks/useMicPermission';
import useServiceWorkerUpdate from './hooks/useServiceWorkerUpdate';
import {
  // host detection + URL helpers
  isLocalHost,
  isSameOriginBackendHost,
  defaultApiUrl,
  configuredUrl,
  // session/device
  normalizeSessionId,
  readInitialSessionId,
  // constants
  TARGET_LANGUAGE_OPTIONS,
  VOICE_WARMUP_PHRASES,
  HEALTH_POLL_MS,
  STREAM_HEARTBEAT_MS,
  STREAM_HEARTBEAT_MAX_MISSES,
  STREAM_RECONNECT_MS,
  STREAM_RECONNECT_MAX_ATTEMPTS,
  STREAM_RECONNECT_MAX_DELAY_MS,
  MAX_AUDIO_SEND_QUEUE,
  MAX_BUFFERED_AUDIO_CHUNKS,
  LATENCY_HISTORY_KEY,
  LATENCY_HISTORY_LIMIT,
  LATENCY_TARGET_MS,
  VOICE_WARMUP_COOLDOWN_MS,
  VOICE_PREFETCH_TIMEOUT_MS,
  HOLD_TO_TALK_DELAY_MS,
  EXPECTED_BACKEND_RELEASE,
  FRONTEND_BUILD_ID,
  EXPERIMENTAL_IOS_STREAMING,
  // persistence
  readPersistedTargetLanguage,
  readPersistedSourceLanguage,
  // debug
  readDebugFlag,
  makeDebugLog,
  // latency
  blankLatencyStats,
  formatLatencyValue,
  readLatencyHistory,
  summarizeLatencyHistory,
  // speaker labels
  fallbackSpeakerLabel,
  // browser probes
  isManualInstallBrowser,
  isIosOrSafariRecorder,
  // audio
  preferredAudioMimeType,
  createAudioRecorder as createAudioRecorderRaw,
  audioFileExtension,
  logAudioStream as logAudioStreamRaw,
  // speech recognition
  speechRecognitionConstructor,
  speechRecognitionLanguage,
  // auth
  withAuthToken,
  authHeaders,
  responseErrorMessage,
  // mic
  mediaErrorMessage,
  requestAudioStream,
  // misc
  uniqueStrings,
  extractBrainPlan,
  compactRepairLabel,
} from './utils';

// Resolve API URL up-front from env + host.
const LOCAL_BACKEND = isLocalHost(window.location.hostname);
const SAME_ORIGIN_BACKEND = isSameOriginBackendHost(window.location.hostname);
const API_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? defaultApiUrl() : (configuredUrl(import.meta.env.VITE_API_URL) || defaultApiUrl())).replace(/\/+$/, '');
const WS_BASE_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? API_URL : (configuredUrl(import.meta.env.VITE_WS_URL) || API_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:'))).replace(/\/+$/, '');
const WS_AUDIO_URL = LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? `${WS_BASE_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')}/ws/audio` : (configuredUrl(import.meta.env.VITE_WS_AUDIO_URL) || `${WS_BASE_URL}/ws/audio`);
const INITIAL_TOKEN = localStorage.getItem('translator_token') || '';

const INITIAL_SESSION_ID = readInitialSessionId();
const INITIAL_DEVICE_ID = localStorage.getItem('translator_device_id') || crypto.randomUUID();
const INITIAL_SPEAKER_NAME = localStorage.getItem('translator_speaker_name') || '';
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 60);
const STREAM_AUDIO_BITRATE = Number(import.meta.env.VITE_STREAM_AUDIO_BITRATE || 48000);
const CLIENT_VAD_THRESHOLD = Number(import.meta.env.VITE_CLIENT_VAD_THRESHOLD || 0.055);
const FAST_SPEECH_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_SPEECH_TIMEOUT_MS || 10000);
const FAST_TTS_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_TTS_TIMEOUT_MS || 10000);
const MIN_STREAM_CAPTURE_MS = Number(import.meta.env.VITE_MIN_STREAM_CAPTURE_MS || 1800);
const LIVE_SPEECH_TEXT_THROTTLE_MS = Number(import.meta.env.VITE_LIVE_SPEECH_TEXT_THROTTLE_MS || 90);

const DEBUG_LOGS = readDebugFlag();
const debugLog = makeDebugLog(DEBUG_LOGS);
localStorage.setItem('translator_session_id', INITIAL_SESSION_ID);
localStorage.setItem('translator_device_id', INITIAL_DEVICE_ID);
registerServiceWorker();

// Bind recorder + audio-stream logger to local bitrate / debugLog so callers
// keep the original signatures.
function createAudioRecorder(stream) {
  return createAudioRecorderRaw(stream, STREAM_AUDIO_BITRATE);
}
function logAudioStream(stream) {
  logAudioStreamRaw(stream, debugLog);
}

// Target languages live in `utils.js` (TARGET_LANGUAGE_OPTIONS) so they can
// be shared between this file and tests. Same for VOICE_WARMUP_PHRASES,
// readPersistedTargetLanguage, readPersistedSourceLanguage, uniqueStrings,
// extractBrainPlan, and compactRepairLabel.

function App() {
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish', ht: 'Haitian Creole' });
  const [sourceLanguageState, setSourceLanguageState] = useState(readPersistedSourceLanguage);
  const sourceLanguage = sourceLanguageState;
  const setSourceLanguage = (next) => {
    setSourceLanguageState(next);
    try { localStorage.setItem('sourceLanguage', next); } catch {}
  };
  const [targetLanguage, setTargetLanguageState] = useState(readPersistedTargetLanguage);
  const setTargetLanguage = (next) => {
    setTargetLanguageState(next);
    try { localStorage.setItem('targetLanguage', next); } catch {}
  };
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const { micPermission, setMicPermission, requestMicPermission } = useMicPermission({
    onStatus: (message) => setStatus(message),
  });
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [instantListening, setInstantListening] = useState(false);
  const [liveAssistActive, setLiveAssistActive] = useState(false);
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
  const [latencyHistory, setLatencyHistory, latencySummary] = useLatencyHistory();
  const [authToken, setAuthToken] = useState(INITIAL_TOKEN);
  const { selfTest, runSelfTest } = useSelfTest({
    apiUrl: API_URL,
    wsAudioUrl: WS_AUDIO_URL,
    authToken,
    onStatus: (message) => setStatus(message),
  });
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const [sessionId, setSessionId] = useState(INITIAL_SESSION_ID);
  const [sharedSession, setSharedSession] = useState(null);
  const [conversationTurns, setConversationTurns] = useConversationHistory();
  const [analytics, setAnalytics] = useState(null);
  const { diagnostics, diagnosticsStatus, loadDiagnostics } = useDiagnostics(API_URL);
  const [wsDebug, setWsDebug] = useState({ url: WS_AUDIO_URL, close: '-', error: '-' });
  // selfTest + runSelfTest come from useSelfTest below (after authToken is declared).
  // Initial PWA-installed status (true if launched from the home screen).
  const initialPwaInstalled =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator?.standalone === true;
  const updateAvailable = useServiceWorkerUpdate({
    apiUrl: API_URL,
    expectedRelease: EXPECTED_BACKEND_RELEASE,
  });
  const [micLevel, setMicLevel] = useState(0);
  const [copiedKey, copyToClipboard] = useCopyToClipboard();
  const haptic = useHaptic();
  const { installPrompt, pwaInstalled, installApp } = useInstallPrompt({
    onStatus: (message) => setStatus(message),
  });
  // Initialize pwaInstalled from the launch context (home-screen install).
  useEffect(() => {
    if (initialPwaInstalled) {
      // useInstallPrompt only flips pwaInstalled on `appinstalled`; we
      // also want it true when the user opens an already-installed PWA.
      // Use a one-shot synthetic event to surface that.
      window.dispatchEvent(new Event('appinstalled'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [cameraActive, setCameraActive] = useState(false);
  const [ocrText, setOcrText] = useState('');
  const [clarifyVisible, setClarifyVisible] = useState(false);
  const [clarifyMessage, setClarifyMessage] = useState('');
  const [brainUi, setBrainUi] = useState({
    visible: false,
    message: '',
    mode: '',
    strategy: '',
    hints: {},
    repairOptions: [],
    highlightTerms: [],
    riskScore: null,
  });
  const [reconnectToastVisible, setReconnectToastVisible] = useState(false);

  // conversation history persistence is in useConversationHistory above.

  // latencyHistory persistence + summary computation live inside
  // useLatencyHistory; we only need to react to slow trends here.
  useEffect(() => {
    if (!latencySummary.average || latencySummary.average <= LATENCY_TARGET_MS) return;
    if (connectionStatus !== 'online' || processing || playing || streaming) return;
    warmVoiceCache('slow_latency');
  }, [connectionStatus, latencySummary.average, playing, processing, streaming]);

  useEffect(() => {
    if (connectionStatus !== 'online' || processing || playing || streaming) return undefined;
    const timer = window.setTimeout(() => {
      warmVoiceCache('language_ready');
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [connectionStatus, playing, processing, streaming, targetLanguage]);

  // copyToClipboard + copiedKey come from useCopyToClipboard above.

  function languageName(code) {
    if (!code) return '';
    return languages[code] || TARGET_LANGUAGE_OPTIONS.find((option) => option.code === code)?.label || String(code).toUpperCase();
  }

  function applyBrainPayload(payload = {}, origin = 'translation') {
    const { plan, hints, repairOptions } = extractBrainPlan(payload);
    if (!plan && Object.keys(hints).length === 0 && repairOptions.length === 0) return null;

    const repeatedTerms = repairOptions
      .filter((option) => option?.type === 'repeat_terms')
      .flatMap((option) => option.terms || []);
    const highlightTerms = uniqueStrings(repeatedTerms.length ? repeatedTerms : (hints.highlight_terms || []));
    const repairedLanguage = hints.repaired_source_language || plan?.suggested_source_language;
    const languageAutoRepaired = Boolean(hints.language_auto_repaired);
    const suggestSwitch = Boolean(hints.suggest_source_language_switch);
    const skipTts = Boolean(hints.skip_tts || hints.tts_mode === 'skip');
    const activeSpeakerId = hints.active_speaker || plan?.turn_policy?.active_speaker || '';
    const speakerShift = Boolean(hints.speaker_shift || plan?.turn_policy?.speaker_shift);
    const activeSpeakerLabel = activeSpeakerId ? (speakerLabelsRef.current[activeSpeakerId] || fallbackSpeakerLabel(activeSpeakerId)) : '';
    const riskScore = Number.isFinite(Number(plan?.meaning_risk_score)) ? Number(plan.meaning_risk_score) : null;

    brainHintsRef.current = hints;
    brainPlanRef.current = plan;

    let message = '';
    if (languageAutoRepaired && repairedLanguage) {
      message = `Source auto-switched to ${languageName(repairedLanguage)}`;
      if (repairedLanguage !== sourceLanguage) {
        setSourceLanguage(repairedLanguage);
      }
      setClarifyVisible(false);
    } else if (suggestSwitch && repairedLanguage) {
      message = `Source sounds like ${languageName(repairedLanguage)}`;
    } else if (repairOptions.some((option) => option?.type === 'repeat_terms')) {
      message = 'Exact term check needed';
    } else if (repairOptions.some((option) => option?.type === 'confirm_exact')) {
      message = 'Confirm exact words before speaking';
    } else if (plan?.turn_policy?.mode === 'guarded_translate') {
      message = 'Guarded translation active';
    } else if (skipTts) {
      message = 'Voice skipped for confirmation';
    } else if (speakerShift && activeSpeakerLabel) {
      message = `${activeSpeakerLabel} speaking now`;
    }

    if (speakerShift && activeSpeakerLabel) {
      setDetectedSpeaker(activeSpeakerLabel);
      setConversationBrain(`${activeSpeakerLabel}: active speaker shift`);
    }

    if (skipTts) {
      ttsQueueRef.current = [];
      setTtsQueueLength(0);
      setTtsChunksBuffer([]);
      setPlaying(false);
      setTtsPlaying(false);
    }

    const next = {
      visible: Boolean(message || repairOptions.length || highlightTerms.length || hints.ask_before_speaking || suggestSwitch || languageAutoRepaired || speakerShift || skipTts),
      message,
      mode: plan?.turn_policy?.mode || '',
      strategy: plan?.strategy || '',
      hints,
      repairOptions,
      highlightTerms,
      riskScore,
      skipTts,
      speakerShift,
      activeSpeakerLabel,
      origin,
    };
    setBrainUi(next);
    return next;
  }

  function runRepairOption(option = {}) {
    haptic(18);
    if ((option.type === 'switch_source_language' || option.type === 'auto_switch_source_language') && option.language) {
      setSourceLanguage(option.language);
      setBrainUi((current) => ({
        ...current,
        message: `Source set to ${languageName(option.language)}`,
        visible: true,
      }));
      setStatus(`Source set to ${languageName(option.language)}`);
      return;
    }
    if (option.type === 'choose_meaning' && option.word) {
      const choices = Array.isArray(option.options) ? option.options.join(' / ') : 'the intended meaning';
      setClarifyMessage(`For "${option.word}", say: ${choices}`);
      setClarifyVisible(true);
      setStatus('Choose the intended meaning');
      return;
    }
    setClarifyVisible(false);
    setPipelineStage('Ready to repair');
    setStatus(option.label || 'Please repeat');
    if (!streaming && !processing && !playing) {
      try { handleMicClick(); } catch {}
    }
  }

  function shouldSkipBrainTts(payload = null) {
    const hints = payload ? extractBrainPlan(payload).hints : brainHintsRef.current;
    return Boolean(hints?.skip_tts || hints?.tts_mode === 'skip');
  }

  function resetBrainRuntimeUi() {
    brainHintsRef.current = {};
    brainPlanRef.current = null;
    setBrainUi((current) => ({ ...current, visible: false, message: '', repairOptions: [], highlightTerms: [], skipTts: false, speakerShift: false }));
  }

  function clearInterpreterScreen() {
    if (streaming || processing || playing || ttsPlaying) return;
    haptic(14);
    resetBrainRuntimeUi();
    setResult(null);
    setText('');
    setPartialTranscript('');
    setLiveTranslation('');
    setConversationTurns([]);
    setClarifyVisible(false);
    setClarifyMessage('');
    setDetectedSpeaker('-');
    setLatencyStats(blankLatencyStats());
    setAudioReplayAvailable(false);
    setAutoPlayFailed(false);
    setTtsQueueLength(0);
    setTtsChunksBuffer([]);
    setStatus('Ready');
    setPipelineStage('Ready');
  }

  function flipLanguageDirection() {
    if (streaming || processing || playing || ttsPlaying || sourceLanguage === targetLanguage) return;
    const nextSource = targetLanguage;
    const nextTarget = sourceLanguage || 'en';
    haptic(12);
    setSourceLanguage(nextSource);
    setTargetLanguage(nextTarget);
    resetBrainRuntimeUi();
    setStatus(`${languageName(nextSource)} to ${languageName(nextTarget)}`);
    setPipelineStage('Direction switched');
  }
  const mediaRecorderRef = useRef(null);
  const micMeterRef = useRef({});
  const streamRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);
  const duplexRefs = useRef({ A: {}, B: {} });
  const speakerLabelsRef = useRef({});
  const brainHintsRef = useRef({});
  const brainPlanRef = useRef(null);
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
  const speechAssistSocketRef = useRef(null);
  const speechAssistRestartTimerRef = useRef(null);
  const speechAssistStopRequestedRef = useRef(false);
  const speechLastSentTextRef = useRef('');
  const speechLastSentAtRef = useRef(0);
  const voiceWarmupRef = useRef({ inFlight: false, lastAtByLanguage: {} });
  const appStateRef = useRef({});

  useEffect(() => {
    appStateRef.current = { interpreterMode, speakerMode, recording, processing, playing, streaming };
  }, [interpreterMode, speakerMode, recording, processing, playing, streaming]);

  // haptic comes from useHaptic() above.

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

  // backend/frontend release polling lives in useServiceWorkerUpdate above.

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

  // First diagnostics fetch happens inside useDiagnostics on mount.

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

  // mic permission lifecycle is in useMicPermission above.
  // PWA install lifecycle is in useInstallPrompt above.

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
          debugLog('AudioContext warmup oscillator started');
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
        debugLog('Audio unlocked successfully (muted priming)');
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
      const item = { url, buffer, mimeType: 'audio/wav', objectUrl: true };
      revokeTtsItemUrl(lastTtsItemRef.current);
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

  function resolveAudioUrl(audioUrl) {
    const rawUrl = String(audioUrl || '').trim();
    if (!rawUrl) return '';
    try {
      const baseUrl = API_URL || window.location.origin;
      return new URL(rawUrl, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`).toString();
    } catch (error) {
      console.warn('Unable to resolve audio URL:', error);
      return rawUrl;
    }
  }

  function revokeTtsItemUrl(item) {
    if (item?.url && item.objectUrl) {
      URL.revokeObjectURL(item.url);
    }
  }

  function hasPlayableAudioPayload(data) {
    return Boolean(data?.audio_url || data?.audio_base64);
  }

  async function prefetchAudioUrl(audioUrl, reason = 'warmup') {
    const directAudioUrl = resolveAudioUrl(audioUrl);
    if (!directAudioUrl) return false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), VOICE_PREFETCH_TIMEOUT_MS);
    try {
      const response = await fetch(directAudioUrl, {
        cache: 'force-cache',
        signal: controller.signal,
      });
      window.clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      window.clearTimeout(timeoutId);
      if (error?.name !== 'AbortError') {
        console.warn('voice audio prefetch failed:', reason, error);
      }
      return false;
    }
  }

  async function warmVoiceCache(reason = 'idle') {
    const current = voiceWarmupRef.current;
    const now = Date.now();
    const language = targetLanguage || 'es';
    const textToWarm = VOICE_WARMUP_PHRASES[language] || VOICE_WARMUP_PHRASES.es;
    const lastAt = current.lastAtByLanguage?.[language] || 0;
    if (current.inFlight || now - lastAt < VOICE_WARMUP_COOLDOWN_MS) return false;
    current.inFlight = true;
    current.lastAtByLanguage = { ...(current.lastAtByLanguage || {}), [language]: now };
    try {
      const response = await fetch(`${API_URL}/tts`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        cache: 'no-store',
        body: JSON.stringify({
          text: textToWarm,
          language,
          response_format: 'url',
          warmup_reason: reason,
        }),
      });
      if (!response.ok) return false;
      const data = await response.json().catch(() => null);
      if (data?.audio_url) {
        await prefetchAudioUrl(data.audio_url, reason);
      }
      return true;
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

      const stream = await requestAudioStream();
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
    resetBrainRuntimeUi();
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
      const brainUpdate = applyBrainPayload(data, 'text');
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
        setStatus(brainUpdate?.message || 'Text translated');
      }
    } catch (error) {
      setStatus(error.message || 'Text translation failed');
    } finally {
      setProcessing(false);
    }
  }

  async function playEmbeddedTranslationAudio(data, endStatus = 'Voice played') {
    if (!hasPlayableAudioPayload(data)) return false;
    if (shouldSkipBrainTts(data)) {
      setPlaying(false);
      setTtsPlaying(false);
      setPipelineStage('Voice skipped');
      setStatus('Confirmation needed before voice');
      return false;
    }
    await ensureAudioUnlocked().catch((e) => console.warn('embedded audio unlock failed:', e));
    const mimeType = data.mime_type || 'audio/wav';
    const directAudioUrl = resolveAudioUrl(data.audio_url);
    if (directAudioUrl) {
      const item = { url: directAudioUrl, buffer: null, mimeType, objectUrl: false };
      revokeTtsItemUrl(lastTtsItemRef.current);
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
    const binary = atob(data.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    if (buffer.byteLength < 100) return false;
    const url = URL.createObjectURL(new Blob([buffer], { type: mimeType }));
    const item = { url, buffer, mimeType, objectUrl: true };
    revokeTtsItemUrl(lastTtsItemRef.current);
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
        body: JSON.stringify({ text: spokenText, language, response_format: 'url' }),
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
    resetBrainRuntimeUi();
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
          synthesize_audio: true,
          audio_response_format: 'url',
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
      const brainUpdate = applyBrainPayload(data, 'speech');
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
      const firstAudioMs = hasPlayableAudioPayload(data) ? Math.round(performance.now() - capturedAt) : null;
      if (firstAudioMs) updateLatency('first_audio', firstAudioMs);
      recordLatencyTurn({ total: endToEndMs, backend: backendResponseMs, audio: firstAudioMs });
      if (hasPlayableAudioPayload(data)) {
        setPipelineStage('Playing voice');
        setStatus(brainUpdate?.message || 'Playing voice...');
      } else {
        setPipelineStage('Translation ready');
        setStatus(brainUpdate?.message || 'Translation ready');
      }
      const played = await playEmbeddedTranslationAudio(
        data,
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

  // diagnostics + loadDiagnostics come from useDiagnostics(API_URL) above.

  // selfTest + runSelfTest are in useSelfTest above.

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
      title: 'Anai Translator',
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
    setLiveAssistActive(false);
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
    if (isIosOrSafariRecorder()) return EXPERIMENTAL_IOS_STREAMING ? 110 : Math.max(STREAM_PACKET_MS, 400);
    return Math.min(STREAM_PACKET_MS, 80);
  }

  function sendAudioPacket(socket, packet) {
    if (socket.readyState !== WebSocket.OPEN) return false;
    try {
      debugLog('sending audio chunk', packet.meta.bytes, packet.meta.mime_type);
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
    debugLog('AUDIO CHUNK:', event.data);
    if (audioSendQueueRef.current.length >= MAX_AUDIO_SEND_QUEUE && socket.readyState === WebSocket.OPEN) {
      audioSendQueueRef.current.shift();
    }
    const buffer = await event.data.arrayBuffer();
    const audioLevel = Number(micMeterRef.current?.smoothed || 0);
    const packet = {
      meta: {
        type: 'chunk_meta',
        sent_at_ms: Date.now(),
        captured_at_ms: performance.now(),
        bytes: buffer.byteLength,
        mime_type: recorder?.mimeType || event.data.type || preferredAudioMimeType(),
        audio_level: Number(audioLevel.toFixed(4)),
        voice_active: audioLevel >= CLIENT_VAD_THRESHOLD,
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

  function shouldKeepContinuousStream(socket) {
    const options = streamReconnectRef.current.options || {};
    return (
      socketRef.current === socket &&
      options.interpreter === true &&
      options.speakerMode === 'auto' &&
      options.holdToTalk !== true &&
      !holdToTalkActiveRef.current
    );
  }

  function isFatalStreamError(message = '') {
    return /quota|too many active|not authorized|unauthorized|forbidden|exceeds|buffer limit/i.test(String(message || ''));
  }

  function stopContinuousStream(nextStatus = 'Interpreter stopped') {
    const socket = socketRef.current;
    const recorder = streamRecorderRef.current;
    if (!socket && !recorder) return false;
    disableStreamReconnect();
    clearStreamHeartbeat();
    if (streamSafetyTimeoutRef.current) {
      window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = null;
    }
    audioSendQueueRef.current = [];
    streamFinalizePendingRef.current = false;
    holdToTalkReleasePendingRef.current = false;
    releaseWakeLock();
    stopBrowserSpeechFastPath();
    try {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'cancel' }));
      }
    } catch {}
    if (recorder?.state === 'recording') {
      recorder.stop();
    } else {
      recorder?.stream?.getTracks().forEach((track) => track.stop());
    }
    try {
      if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) socket.close();
    } catch {}
    socketRef.current = null;
    streamRecorderRef.current = null;
    setStreaming(false);
    setInstantListening(false);
    setProcessing(false);
    setPlaying(false);
    setTtsPlaying(false);
    setInterpreterMode(false);
    setPipelineStage('Stopped');
    setStatus(nextStatus);
    return true;
  }

  function stopBrowserSpeechFastPath() {
    if (!speechFastPathActiveRef.current) return false;
    speechAssistStopRequestedRef.current = true;
    if (speechAssistRestartTimerRef.current) {
      window.clearTimeout(speechAssistRestartTimerRef.current);
      speechAssistRestartTimerRef.current = null;
    }
    try {
      speechRecognitionRef.current?.abort?.();
    } catch (error) {
      console.warn('speech recognition stop failed:', error);
    }
    speechFastPathActiveRef.current = false;
    speechRecognitionRef.current = null;
    speechAssistSocketRef.current = null;
    speechFinalTextRef.current = '';
    speechInterimTextRef.current = '';
    speechLastSentTextRef.current = '';
    speechLastSentAtRef.current = 0;
    setLiveAssistActive(false);
    if (!socketRef.current) {
      setStreaming(false);
      setInstantListening(false);
      setProcessing(true);
      setPipelineStage('Processing');
      setStatus('Processing speech...');
    }
    return true;
  }

  function sendLiveSpeechText(socket, textValue, isFinal = false) {
    const normalized = String(textValue || '').replace(/\s+/g, ' ').trim();
    if (!normalized || !socket || socket.readyState !== WebSocket.OPEN) return false;
    const now = performance.now();
    if (!isFinal && normalized === speechLastSentTextRef.current) return false;
    if (!isFinal && now - speechLastSentAtRef.current < LIVE_SPEECH_TEXT_THROTTLE_MS) return false;
    speechLastSentTextRef.current = normalized;
    speechLastSentAtRef.current = now;
    try {
      socket.send(JSON.stringify({
        type: 'live_text',
        text: normalized,
        final: Boolean(isFinal),
        session_id: sessionId,
        device_id: INITIAL_DEVICE_ID,
        speaker_name: INITIAL_SPEAKER_NAME,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        speaker_mode: speakerMode,
        speaker: speakerMode === 'auto' ? 'auto' : 'A',
        sent_at_ms: Date.now(),
      }));
      return true;
    } catch (error) {
      console.warn('live speech text send failed:', error);
      return false;
    }
  }

  function startBrowserSpeechFastPath(socket = null) {
    const Recognition = speechRecognitionConstructor();
    const current = appStateRef.current;
    const activeSocket = socket || socketRef.current;
    if (!Recognition || !activeSocket || current.recording || current.processing) return false;

    let recognition;
    try {
      recognition = new Recognition();
    } catch (error) {
      console.warn('speech recognition unavailable:', error);
      return false;
    }

    if (speechFastPathActiveRef.current) return true;
    speechRecognitionRef.current = recognition;
    speechFastPathActiveRef.current = true;
    speechAssistSocketRef.current = activeSocket;
    speechAssistStopRequestedRef.current = false;
    setLiveAssistActive(true);
    speechLastSentTextRef.current = '';
    speechLastSentAtRef.current = 0;
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
    setStatus('Listening live...');
    streamStartedAtRef.current = performance.now();
    requestWakeLock();

    recognition.lang = speechRecognitionLanguage(sourceLanguage);
    recognition.interimResults = true;
    recognition.continuous = true;
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
      if (visibleText) {
        setPartialTranscript(visibleText);
        sendLiveSpeechText(activeSocket, visibleText, Boolean(finalText.trim()));
      }
    };

    recognition.onerror = (event) => {
      const message = event?.error || 'speech recognition error';
      console.warn('speech recognition error:', message);
      if (message === 'not-allowed' || message === 'service-not-allowed') {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        speechAssistSocketRef.current = null;
        setLiveAssistActive(false);
        releaseWakeLock();
        setMicPermission('denied');
        if (!socketRef.current) {
          setStreaming(false);
          setStatus('Microphone permission blocked');
          setPipelineStage('Permission blocked');
        } else {
          setStatus('Audio fallback listening...');
          setPipelineStage('Audio fallback');
        }
        return;
      }
      if (!speechFinalTextRef.current.trim() && !socketRef.current) {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        setLiveAssistActive(false);
        releaseWakeLock();
        setStreaming(false);
        setStatus('Using audio fallback...');
        setPipelineStage('Audio fallback');
        window.setTimeout(() => toggleStreaming({ interpreter: true, speakerMode: 'auto' }), 80);
      }
    };

    recognition.onend = () => {
      if (!speechFastPathActiveRef.current) return;
      if (speechAssistStopRequestedRef.current || socketRef.current !== activeSocket || activeSocket.readyState !== WebSocket.OPEN) {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        speechAssistSocketRef.current = null;
        setLiveAssistActive(false);
        return;
      }
      speechAssistRestartTimerRef.current = window.setTimeout(() => {
        if (!speechFastPathActiveRef.current || speechAssistStopRequestedRef.current) return;
        if (socketRef.current !== activeSocket || activeSocket.readyState !== WebSocket.OPEN) return;
        try {
          recognition.start();
        } catch (error) {
          console.warn('speech recognition restart failed:', error);
        }
      }, 80);
    };

    try {
      recognition.start();
      haptic(14);
      return true;
    } catch (error) {
      console.warn('speech recognition start failed:', error);
      speechFastPathActiveRef.current = false;
      speechRecognitionRef.current = null;
      speechAssistSocketRef.current = null;
      setLiveAssistActive(false);
      setPipelineStage('Audio fallback');
      setStatus('Using audio fallback...');
      if (!socketRef.current) {
        releaseWakeLock();
        setStreaming(false);
      }
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
      toggleStreaming({ interpreter: true, speakerMode: 'auto' });
    }, 450);
  }

  async function handleMicClick() {
    debugLog('MIC BUTTON CLICKED');
    if (ignoreNextMicClickRef.current) {
      ignoreNextMicClickRef.current = false;
      return;
    }
    synchronousAudioUnlock();
    if (socketRef.current) {
      haptic(8);
      setInstantListening(false);
      stopContinuousStream();
      return;
    }
    if (stopBrowserSpeechFastPath()) return;
    if (isIosOrSafariRecorder() && !EXPERIMENTAL_IOS_STREAMING) {
      haptic(recording ? 8 : 14);
      if (recording) stopRecording();
      else startRecording();
      return;
    }
    haptic(14);
    setInstantListening(true);
    toggleStreaming({ interpreter: true, speakerMode: 'auto' });
  }

  async function handleMicPointerDown(event) {
    debugLog('MIC BUTTON CLICKED');
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
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Install Anai Translator</title></head><body style="font-family:system-ui;margin:24px;line-height:1.5;background:#03050a;color:#f8fafc"><h1>Install Anai Translator</h1><p>Open <a style="color:#67e8f9" href="${appUrl}">${appUrl}</a>, then use your browser's Add to Home Screen or Install app option.</p><p><a style="color:#67e8f9" href="${appUrl}">Open app now</a></p></body></html>`;
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'anai-translator-install.html';
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
    debugLog('startRecording: called');
    if (recording || processing) {
      debugLog('startRecording: already recording or processing, skipping');
      return;
    }
    let stream;
    try {
      stream = await requestAudioStream();
      debugLog('MIC STREAM ACTIVE:', stream);
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
      debugLog('MOBILE AUDIO SIZE:', event.data.size);
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
    debugLog('stopRecording: called');
    if (recordingStoppedRef.current) {
      debugLog('stopRecording: already stopped, skipping');
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
    resetBrainRuntimeUi();

    try {
      debugLog('UPLOAD: posting audio to', `${API_URL}/translate/audio`, 'size', blob.size);
      const response = await fetch(`${API_URL}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
      debugLog('UPLOAD: response status', response.status);
      if (!response.ok) {
        const errText = await responseErrorMessage(response, 'Audio translation failed');
        console.error('UPLOAD: response not ok', response.status, errText);
        throw new Error(errText);
      }
      const data = await response.json();
      debugLog('UPLOAD: response data keys', Object.keys(data));
      debugLog('UPLOAD: translated_text', data.translated_text ? 'yes' : 'no');
      debugLog('UPLOAD: audio_base64 length', data.audio_base64?.length || 0);
      const brainUpdate = applyBrainPayload(data, 'audio');
      if (data.clarify) {
        setResult(data);
        setStatus(data.clarify_message || 'Clarification requested');
        setLiveTranslation(data.translated_text || '');
        setClarifyMessage(data.clarify_message || 'Clarification requested');
        setClarifyVisible(true);
        return;
      }
      setResult(data);
      setStatus(brainUpdate?.message || (data.translated_text ? (data.audio_base64 ? 'Playing...' : 'Audio translated') : 'No clear speech recognized'));
      if (shouldSkipBrainTts(data)) {
        setPipelineStage('Voice skipped');
        return;
      }
      if (data.audio_base64) {
        await ensureAudioUnlocked().catch((e) => console.warn('uploadRecording audio unlock failed:', e));
        const binary = atob(data.audio_base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        debugLog('UPLOAD: decoded audio buffer size', buffer.byteLength);
        // Validate WAV header
        if (buffer.byteLength >= 12) {
          const header = new Uint8Array(buffer, 0, 12);
          const riff = String.fromCharCode(...header.slice(0, 4));
          const wave = String.fromCharCode(...header.slice(8, 12));
          debugLog('UPLOAD: WAV header', riff, wave, 'valid:', riff === 'RIFF' && wave === 'WAVE');
        } else {
          console.warn('UPLOAD: audio buffer too small for WAV header');
        }
        const url = URL.createObjectURL(new Blob([buffer], { type: data.mime_type || 'audio/wav' }));
        const item = { url, buffer, mimeType: data.mime_type || 'audio/wav', objectUrl: true };
        revokeTtsItemUrl(lastTtsItemRef.current);
        lastTtsItemRef.current = item;
        setAudioReplayAvailable(true);
        setPlaying(true);
        debugLog('UPLOAD: calling playTtsItem');
        // iOS needs a delay after mic release for the audio session to transition
        // from playAndRecord back to playback; 150ms is often too short.
        const playDelay = isIosOrSafariRecorder() ? 400 : 0;
        window.setTimeout(() => {
          debugLog('UPLOAD: starting playback after', playDelay, 'ms delay');
          playTtsItem(item, { revokeOnFinish: false, manual: true, onEnd: () => {
            debugLog('UPLOAD: playTtsItem finished');
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
      stopContinuousStream();
      return;
    }

    const reconnecting = options.reconnect === true;
    const cleanOptions = { ...options };
    delete cleanOptions.reconnect;
    let stream;
    try {
      stream = await requestAudioStream();
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
    if (!cleanOptions.holdToTalk) {
      startBrowserSpeechFastPath(socket);
    }
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
      resetBrainRuntimeUi();
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
      if (!cleanOptions.holdToTalk && !speechFastPathActiveRef.current) {
        startBrowserSpeechFastPath(socket);
      }
      flushAudioSendQueue(socket);
      startStreamHeartbeat(socket);
      streamRecorderRef.current = recorder;
      debugLog('STEP 9: starting recorder');
      try {
        recorder.start(activePacketMs());
        if (streamSafetyTimeoutRef.current) {
          window.clearTimeout(streamSafetyTimeoutRef.current);
          streamSafetyTimeoutRef.current = null;
        }
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
      debugLog('STEP 10: recorder started, state=', recorder.state);
      if (cleanOptions.holdToTalk && holdToTalkReleasePendingRef.current) {
        holdToTalkReleasePendingRef.current = false;
        finalizeCurrentStream('Processing speech...');
      }
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      debugLog('WS MESSAGE:', event.data);
      if (data.type === 'pong') {
        markStreamPong();
        return;
      }
      if (data.type === 'session_restored' || data.type === 'session_sync') applySharedSession(data.session?.shared || data.session);
      if (data.type === 'speaker_detected') {
        const label = rememberSpeaker(data);
        setPipelineStage(`${label} detected`);
      }
      if (data.type === 'active_speaker') {
        const label = rememberSpeaker(data);
        setDetectedSpeaker(label);
        setConversationBrain(`${label}: ${data.reason || 'speaking'}${data.behavior ? ` - ${data.behavior}` : ''}`);
        if (data.allowed !== false) setPipelineStage(`${label} speaking`);
      }
      if (data.type === 'latency') {
        updateLatency(data.metric, data.ms);
      }
      if (data.type === 'cip') {
        const brainUpdate = applyBrainPayload(data, 'stream');
        if (brainUpdate?.message) {
          setPipelineStage(brainUpdate.message);
          setStatus(brainUpdate.message);
        }
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
        const brainUpdate = applyBrainPayload(data, 'turn');
        const playback = data.playback_owner_label || data.playback_owner;
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${playback ? ` - playback: ${playback}` : ''}`);
        if (brainUpdate?.speakerShift && brainUpdate.message) {
          setPipelineStage(brainUpdate.message);
          setStatus(brainUpdate.message);
        }
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
        if (shouldSkipBrainTts(data)) {
          ttsQueueRef.current = [];
          setTtsQueueLength(0);
          setTtsChunksBuffer([]);
          setPlaying(false);
          setTtsPlaying(false);
          setPipelineStage('Voice skipped');
          setStatus('Confirmation needed before voice');
          return;
        }
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
        if (!data.partial && isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING && !shouldKeepContinuousStream(socket)) {
          // Pause mic capture to route audio to speaker reliably on iOS
          resumeAfterTtsRef.current = true;
          finalizeCurrentStream('Playing voice...', { delay: false });
        }
      }
      if (data.type === 'tts_audio_chunk') {
        if (shouldSkipBrainTts(data)) {
          setPipelineStage('Voice skipped');
          return;
        }
        if (!firstAudioSeenRef.current) {
          firstAudioSeenRef.current = true;
          updateLatency('first_audio', Math.round(performance.now() - streamStartedAtRef.current));
        }
        setPipelineStage(`Streaming voice: ${data.index}/${data.total}`);
        debugLog(`Received TTS chunk ${data.index}/${data.total}, text: "${data.text}", audio size: ${data.audio_base64?.length || 0} chars`);
        ensureAudioUnlocked().catch((e) => console.warn('TTS chunk audio unlock failed:', e));
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'tts_end') {
        if (shouldSkipBrainTts(data)) {
          ttsQueueRef.current = [];
          setTtsQueueLength(0);
          setTtsChunksBuffer([]);
          setPlaying(false);
          setTtsPlaying(false);
          setPipelineStage('Voice skipped');
          setStatus('Confirmation needed before voice');
          return;
        }
        setPipelineStage('Voice stream complete');
        setTtsChunksBuffer((chunks) => {
          if (chunks.length === 0) {
            debugLog('No TTS chunks to play');
            return [];
          }
          debugLog(`Playing ${chunks.length} TTS chunks sequentially to bypass concatenation error`);
          let index = 0;
          const playNextChunk = () => {
            if (index >= chunks.length) {
              debugLog('All chunks played');
              setPlaying(false);
              setTtsPlaying(false);
              if (shouldKeepContinuousStream(socket)) {
                setPipelineStage('Listening');
                setStatus('Listening for the next speaker...');
              } else {
                setPipelineStage('Voice played');
                setStatus('Voice played');
              }
              return;
            }
            const chunk = chunks[index];
            const url = URL.createObjectURL(new Blob([chunk], { type: 'audio/wav' }));
            const item = { url, buffer: chunk, mimeType: 'audio/wav', objectUrl: true };
            revokeTtsItemUrl(lastTtsItemRef.current);
            lastTtsItemRef.current = item;
            setAudioReplayAvailable(true);
            debugLog(`Playing chunk ${index + 1}/${chunks.length}, size: ${chunk.byteLength} bytes`);
            playTtsItem(item, { revokeOnFinish: true, manual: false, onEnd: () => {
              index++;
              playNextChunk();
            }});
          };
          ensureAudioUnlocked().catch((e) => console.warn('TTS end audio unlock failed:', e));
          debugLog('Starting sequential TTS playback');
          playNextChunk();
          return [];
        });
        setTtsQueueLength(0);
        if (!data.partial && resumeAfterTtsRef.current && (isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING) && !shouldKeepContinuousStream(socket)) {
          resumeAfterTtsRef.current = false;
          window.setTimeout(() => {
            if (!socketRef.current) {
              toggleStreaming({ interpreter: true, speakerMode: 'auto' });
            }
          }, 250);
        }
      }
      if (data.type === 'error') {
        debugLog('WS ERROR MESSAGE:', data);
        const message = data.message || 'Stream recovered';
        if (shouldKeepContinuousStream(socket) && !isFatalStreamError(message)) {
          setProcessing(false);
          setPipelineStage('Listening');
          setStatus(`${message} Listening...`);
          streamFinalizePendingRef.current = false;
          holdToTalkReleasePendingRef.current = false;
          return;
        }
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        resetStreamState();
        setPipelineStage('Hold and speak longer');
        setStatus(message || 'Stream failed');
        streamFinalizePendingRef.current = false;
        holdToTalkReleasePendingRef.current = false;
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        socket.close();
        socketRef.current = null;
      }
      if (data.type === 'vad' && data.speech_detected) setStatus('Streaming audio... speech detected');
      if (data.type === 'final') {
        const keepContinuous = shouldKeepContinuousStream(socket);
        if (!keepContinuous) {
          disableStreamReconnect();
          clearStreamHeartbeat();
          audioSendQueueRef.current = [];
        }
        const brainUpdate = applyBrainPayload(data, 'final');
        rememberSpeaker(data);
        setResult(data);
        if (data.session) {
          applySharedSession(data.session);
        } else {
          appendConversationTurn(data);
        }
        setProcessing(false);
        streamFinalizePendingRef.current = false;
        if (keepContinuous) {
          setStreaming(true);
          setInstantListening(false);
          if (!ttsPlayingRef.current && !playing) {
            setPipelineStage(data.clarify ? 'Clarification needed' : 'Listening');
            setStatus(brainUpdate?.message || (data.clarify ? 'Clarification needed. Listening...' : 'Listening for the next speaker...'));
          }
          return;
        }
        setPipelineStage('Complete');
        setStatus(brainUpdate?.message || 'Stream translated');
        if (streamRecorderRef.current?.state === 'recording') {
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
      stopBrowserSpeechFastPath();
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
      stopBrowserSpeechFastPath();
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
      const attempt = streamReconnectRef.current.attempts;
      const exponentialDelay = Math.min(
        STREAM_RECONNECT_MS * Math.pow(2, attempt - 1),
        STREAM_RECONNECT_MAX_DELAY_MS
      );
      setStatus('Reconnecting stream...');
      setPipelineStage(`Reconnecting ${attempt}/${STREAM_RECONNECT_MAX_ATTEMPTS} (${Math.round(exponentialDelay / 1000)}s)`);
      window.setTimeout(() => {
        if (!streamReconnectRef.current.enabled || socketRef.current) return;
        toggleStreaming({ ...(streamReconnectRef.current.options || {}), reconnect: true });
      }, exponentialDelay);
    };
  }

  function enqueueTtsChunk(audioBase64, mimeType) {
    if (shouldSkipBrainTts()) {
      setPipelineStage('Voice skipped');
      return;
    }
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
    debugLog('playTtsItem: starting playback, manual=', manual, 'mimeType=', item.mimeType, 'buffer size=', item.buffer?.byteLength || 0);
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
      if (revokeOnFinish) revokeTtsItemUrl(item);
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
      debugLog('playWithHtmlAudio: using persistent audio element');
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
          debugLog('Audio readyState:', audio.readyState, 'paused:', audio.paused, 'muted:', audio.muted, 'volume:', audio.volume, 'duration:', audio.duration);
          audio.play().then(() => {
            debugLog('HTML audio playing successfully (persistent element)');
            setLastAudioError(null);
          }).catch((error) => {
            console.error('HTML audio play failed on persistent element:', error);
            // Nuclear fallback: try a completely fresh audio element
            debugLog('Trying nuclear fallback with fresh audio element');
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
              debugLog('Fresh audio element playing successfully');
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
          debugLog('Audio already ready (readyState >= 2), playing immediately');
          doPlay();
        } else {
          debugLog('Audio not ready yet (readyState:', audio.readyState, '), waiting for canplay');
          audio.oncanplay = () => {
            debugLog('Audio canplay event fired, readyState:', audio.readyState);
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
        debugLog('HTML audio playing successfully (fallback)');
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
      debugLog('playTtsItem: iOS detected, using HTML audio directly');
      playWithHtmlAudio();
      return;
    }

    if (!item.buffer) {
      debugLog('playTtsItem: direct audio URL, using HTML audio');
      playWithHtmlAudio();
      return;
    }

    debugLog('playTtsItem: trying AudioContext path');
    ensureAudioContext()
      .then((context) => {
        debugLog('playTtsItem: AudioContext state', context?.state);
        if (!context || context.state !== 'running') {
          debugLog('AudioContext not running, using HTML audio fallback');
          playWithHtmlAudio();
          return;
        }
        return context.decodeAudioData(item.buffer.slice(0))
          .then((audioBuffer) => {
            debugLog('playTtsItem: decoded audio buffer, duration', audioBuffer.duration);
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
            debugLog('playTtsItem: AudioBufferSource started');
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
      revokeTtsItemUrl(item);
      item.url = URL.createObjectURL(new Blob([item.buffer], { type: item.mimeType || 'audio/wav' }));
      item.objectUrl = true;
    }
    playTtsItem(item, { revokeOnFinish: false, manual: true });
  }

  function playNextTtsChunk() {
    if (ttsPlayingRef.current || ttsQueueRef.current.length === 0) {
      if (!ttsPlayingRef.current && ttsQueueRef.current.length === 0 && playing) {
        setPlaying(false);
        setTtsQueueLength(0);
        if (socketRef.current && shouldKeepContinuousStream(socketRef.current)) {
          setPipelineStage('Listening');
          setStatus('Listening live...');
        } else {
          setPipelineStage('Ready to listen');
          setStatus('Ready to listen');
        }
      }
      return;
    }

    const item = ttsQueueRef.current.shift();
    setTtsQueueLength(ttsQueueRef.current.length);
    debugLog(`Playing TTS chunk, ${ttsQueueRef.current.length} remaining in queue`);
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
      stream = await requestAudioStream();
      debugLog('MIC STREAM ACTIVE:', stream);
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
      debugLog('MOBILE AUDIO SIZE:', event.data.size);
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
      if (data.type === 'cip') {
        const brainUpdate = applyBrainPayload(data, `duplex-${speaker}`);
        if (brainUpdate?.message) updateDuplexSpeaker(speaker, { stage: brainUpdate.message });
      }
      if (data.type === 'stage') updateDuplexSpeaker(speaker, { stage: data.message });
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        const brainUpdate = applyBrainPayload(data, `duplex-${speaker}`);
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${data.playback_owner ? ` - playback: ${data.playback_owner}` : ''}`);
        if (brainUpdate?.speakerShift && brainUpdate.message) {
          updateDuplexSpeaker(speaker, { stage: brainUpdate.message });
        }
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
        if (shouldSkipBrainTts(data)) {
          updateDuplexSpeaker(speaker, { stage: 'Voice skipped for confirmation' });
          return;
        }
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
        const brainUpdate = applyBrainPayload(data, `duplex-${speaker}`);
        const label = rememberSpeaker(data);
        if (data.session) applySharedSession(data.session);
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          speaker_label: label,
          stage: brainUpdate?.message || 'Complete',
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
  const translatedText = liveTranslation || result?.translated_text || 'Ready to translate';
  const hasSourceText = Boolean(partialTranscript || result?.source_text);
  const hasTranslatedText = Boolean(liveTranslation || result?.translated_text);
  const perceivedListening = streaming || instantListening;
  const micState = playing ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'idle';
  const micLabel = playing ? 'Speaking' : streaming ? 'Listening' : processing ? 'Processing' : 'Tap to Speak';
  const statusText = pipelineStage && pipelineStage !== 'Idle' ? pipelineStage : status;
  const showInstallAction = !pwaInstalled && (installPrompt || isManualInstallBrowser());
  const activeSpeakerLabel = detectedSpeaker && detectedSpeaker !== '-' && detectedSpeaker !== 'Person' ? detectedSpeaker : '';
  const recentConversationTurns = conversationTurns.slice(-4);
  const latencyTotalMs = Number.parseInt(String(latencyStats.end_to_end || ''), 10);
  const { average: latencyAverageMs } = summarizeLatencyHistory(latencyHistory);
  const sourceLanguageLabel = languages[sourceLanguage] || sourceLanguage.toUpperCase();
  const targetLanguageLabel = TARGET_LANGUAGE_OPTIONS.find((option) => option.code === targetLanguage)?.label || languages[targetLanguage] || targetLanguage.toUpperCase();
  const statusTone = connectionStatus !== 'online' ? 'offline' : playing || ttsPlaying ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'ready';
  const timingLabel = Number.isFinite(latencyTotalMs) ? `${latencyTotalMs}ms` : latencyAverageMs ? `${latencyAverageMs}ms avg` : '';
  const speakerSummary = activeSpeakerLabel;
  const micHint = perceivedListening ? 'Listening now' : processing ? 'Translation in motion' : playing ? 'Voice playing' : 'Ready for one tap';
  const visibleRepairOptions = (brainUi.repairOptions || []).slice(0, 3);
  const visibleHighlightTerms = (brainUi.highlightTerms || []).slice(0, 5);
  const brainModeLabel = brainUi.mode ? brainUi.mode.replace(/_/g, ' ') : brainUi.strategy?.replace(/_/g, ' ');
  const liveHudMode = liveAssistActive ? 'Instant' : perceivedListening ? 'Audio' : connectionStatus === 'online' ? 'Ready' : 'Offline';
  const transcriptState = hasSourceText ? (perceivedListening ? 'live' : 'filled') : 'empty';
  const translationState = hasTranslatedText ? ((playing || ttsPlaying) ? 'speaking' : 'filled') : 'empty';
  const liveHudItems = [
    { key: 'listen', label: 'Hear', Icon: Radio, active: perceivedListening, level: micLevel },
    { key: 'ai', label: 'AI', Icon: Sparkles, active: liveAssistActive || brainUi.visible },
    { key: 'translate', label: 'Text', Icon: Languages, active: Boolean(liveTranslation) || /translat/i.test(statusText || '') },
    { key: 'voice', label: 'Voice', Icon: Volume2, active: playing || ttsPlaying || ttsQueueLength > 0 },
  ];
  const hasVisibleConversation = hasSourceText || hasTranslatedText || recentConversationTurns.length > 0 || clarifyVisible || brainUi.visible;
  const quickActions = [
    {
      key: 'flip',
      label: 'Flip',
      Icon: Repeat2,
      onClick: flipLanguageDirection,
      disabled: streaming || processing || playing || ttsPlaying || sourceLanguage === targetLanguage,
    },
    {
      key: 'replay',
      label: 'Replay',
      Icon: Volume2,
      onClick: playTranslationAudio,
      disabled: !audioReplayAvailable || playing || ttsPlaying,
    },
    {
      key: 'clear',
      label: 'Clear',
      Icon: Trash2,
      onClick: clearInterpreterScreen,
      disabled: streaming || processing || playing || ttsPlaying || !hasVisibleConversation,
    },
  ];

  return (
    <main className="app-shell">
      <SystemBanners
        updateAvailable={updateAvailable}
        reconnectToastVisible={reconnectToastVisible}
        onDismissReconnect={() => {
          setReconnectToastVisible(false);
          haptic(30);
        }}
        onReconnectRetry={() => {
          try { handleMicClick(); } catch {}
        }}
      />
      <section className="phone-frame" data-connection={connectionStatus} data-smoke-check="Self Test">
        <AppHeader
          connectionStatus={connectionStatus}
          shareConversationRoom={shareConversationRoom}
          copiedKey={copiedKey}
          showInstallAction={showInstallAction}
          installApp={installApp}
        />

        <MicPanel
          micState={micState}
          micLevel={micLevel}
          perceivedListening={perceivedListening}
          micLabel={micLabel}
          micHint={micHint}
          handleMicClick={handleMicClick}
          handleMicPointerDown={handleMicPointerDown}
          handleMicPointerUp={handleMicPointerUp}
          playing={playing}
          processing={processing}
          streaming={streaming}
          recording={recording}
          liveHudMode={liveHudMode}
          liveHudItems={liveHudItems}
          statusTone={statusTone}
          statusText={statusText}
          speakerSummary={speakerSummary}
          timingLabel={timingLabel}
          audioReplayAvailable={audioReplayAvailable}
          autoPlayFailed={autoPlayFailed}
          playTranslationAudio={playTranslationAudio}
        />

        <LanguageDock
          sourceLanguageLabel={sourceLanguageLabel}
          targetLanguageLabel={targetLanguageLabel}
          targetLanguage={targetLanguage}
          setTargetLanguage={setTargetLanguage}
          recording={recording}
          processing={processing}
          brainUi={brainUi}
          quickActions={quickActions}
        />

        <TranslationStack
          brainUi={brainUi}
          brainModeLabel={brainModeLabel}
          visibleRepairOptions={visibleRepairOptions}
          visibleHighlightTerms={visibleHighlightTerms}
          runRepairOption={runRepairOption}
          hasSourceText={hasSourceText}
          transcriptState={transcriptState}
          sourceLanguageLabel={sourceLanguageLabel}
          sourceText={sourceText}
          hasTranslatedText={hasTranslatedText}
          translationState={translationState}
          targetLanguageLabel={targetLanguageLabel}
          translatedText={translatedText}
          copyToClipboard={copyToClipboard}
          copiedKey={copiedKey}
          cameraActive={cameraActive}
          videoRef={videoRef}
          ocrText={ocrText}
          recentConversationTurns={recentConversationTurns}
          clarifyVisible={clarifyVisible}
          clarifyMessage={clarifyMessage}
          result={result}
          setClarifyVisible={setClarifyVisible}
          setPipelineStage={setPipelineStage}
          setStatus={setStatus}
          haptic={haptic}
          streaming={streaming}
          processing={processing}
          handleMicClick={handleMicClick}
        />

        {false && showDebugPanel && (
          <DebugPanel
            onClose={() => setShowDebugPanel(false)}
            loadDiagnostics={loadDiagnostics}
            connectionStatus={connectionStatus}
            micPermission={micPermission}
            audioContextState={audioContextState}
            mobileAudioUnlocked={mobileAudioUnlocked}
            audioReplayAvailable={audioReplayAvailable}
            ttsQueueLength={ttsQueueLength}
            ttsPlaying={ttsPlaying}
            pipelineStage={pipelineStage}
            status={status}
            diagnosticsStatus={diagnosticsStatus}
            diagnostics={diagnostics}
            result={result}
            lastAudioError={lastAudioError}
          />
        )}

      </section>
      <Assistant
        apiUrl={API_URL}
        authToken={authToken}
        getTranslationContext={() => {
          if (!result) return null;
          return {
            source_language: sourceLanguage,
            target_language: targetLanguage,
            source_text: result.source_text || result.original_text || '',
            translated_text: result.translated_text || '',
          };
        }}
      />
    </main>
  );
}

createRoot(document.getElementById('root')).render(<ErrorBoundary><App /></ErrorBoundary>);
