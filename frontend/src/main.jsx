import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowLeftRight, Check, Clock3, Copy, Download, Heart, Keyboard, Languages, Mic, Radio, Repeat2, Share2, Trash2, UserRound, Volume2 } from 'lucide-react';
import './styles.css';
import './beauty-polish.css';
import './speech-first.css';
import { registerServiceWorker } from './pwa';
import Assistant from './Assistant';
// ConversationMode removed — unified single-view handles both solo and multi-speaker.
import ErrorBoundary from './ErrorBoundary';
import LanguageDock from './components/LanguageDock';
import SystemBanners from './components/SystemBanners';
import AppHeader from './components/AppHeader';
import DebugPanel from './components/DebugPanel';
import AILangConfigPanel from './components/AILangConfigPanel';
import SettingsPanel from './components/SettingsPanel';
import MicPanel from './components/MicPanel';
import TranslationStack from './components/TranslationStack';
import OnboardingTour from './components/OnboardingTour';
import UserFriendlyError, { mapTechnicalError } from './components/UserFriendlyError';
import LoadingSpinner, { InlineSpinner } from './components/LoadingSpinner';
import HelpTooltip from './components/HelpTooltip';
import KeyboardHelp from './components/KeyboardHelp';
import VolumeControl from './components/VolumeControl';
import ConnectionQualityIndicator from './components/ConnectionQualityIndicator';
import EnhancedMicButton from './components/EnhancedMicButton';
import ErrorRetryHandler from './components/ErrorRetryHandler';
import LanguageFlag from './components/LanguageFlag';
import ThinkingIndicator from './components/ThinkingIndicator';
import TypingText from './components/TypingText';
import WaveformVisualizer from './components/WaveformVisualizer';
import useCopyToClipboard from './hooks/useCopyToClipboard';
import useHaptic from './hooks/useHaptic';
import { useToast } from './hooks/useToast';
import ToastRegion from './components/ToastRegion';
import useInstallPrompt from './hooks/useInstallPrompt';
import useDiagnostics from './hooks/useDiagnostics';
import useConversationHistory, { CONVERSATION_DISPLAY_LIMIT } from './hooks/useConversationHistory';
import useSelfTest from './hooks/useSelfTest';
import useMicPermission from './hooks/useMicPermission';
import useServiceWorkerUpdate from './hooks/useServiceWorkerUpdate';
import useInterpreterState from './hooks/useInterpreterState';
import useWakeLock from './hooks/useWakeLock';
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts';
import useMicMeter from './hooks/useMicMeter';
import useCamera from './hooks/useCamera';
import { useAuth } from './hooks/useAuth';
import { useLanguagePair } from './hooks/useLanguagePair';
import { useConnectionStatus } from './hooks/useConnectionStatus';
import { useStreamSession } from './hooks/useStreamSession';
import { useVoiceWarmup } from './hooks/useVoiceWarmup';
import { useAnalytics } from './hooks/useAnalytics';
import { useSpeakerMemory } from './hooks/useSpeakerMemory';
import { useTtsQueue } from './hooks/useTtsQueue';
import { useBrainState } from './hooks/useBrainState';
import { useDuplexState } from './hooks/useDuplexState';
import { usePersistentAudio } from './hooks/usePersistentAudio';
import { useSettings } from './hooks/useSettings';
import { usePipelineState } from './hooks/usePipelineState';
import { useLatencyStats } from './hooks/useLatencyStats';
import { useTranslationState } from './hooks/useTranslationState';
import { useAudioSendQueue } from './hooks/useAudioSendQueue';
import { useStreamHeartbeat } from './hooks/useStreamHeartbeat';
import { useWsDebug } from './hooks/useWsDebug';
import { useSpeechFastPath } from './hooks/useSpeechFastPath';
import { useStreamRefs } from './hooks/useStreamRefs';
import { useHoldToTalk } from './hooks/useHoldToTalk';
import { useAutoConversation } from './hooks/useAutoConversation';
import useReliabilityMonitor from './hooks/useReliabilityMonitor';
import { getFriendlyStatusLabel, getFriendlyStatusDetail } from './utils/friendlyStatus';
import { humanCertStep, shouldBlockTtsForCert, certificationBanner, asCertBool } from './utils/humanCertification';
import { showAdvancedInterpreterChrome } from './constants/productMode';
import { targetPlaceholder, micLabels, micHints, pipelineStages, pipelineStageLabels, dockQuickActionLabels, clarifyMessages, bridgeErrors, formatBrainModeLabel, bridgeStatusMessages, normalizePipelineStage } from './utils/productVoice';
import {
  // host detection + URL helpers
  isLocalHost,
  isSameOriginBackendHost,
  defaultApiUrl,
  configuredUrl,
  // constants
  TARGET_LANGUAGE_OPTIONS,
  VOICE_WARMUP_PHRASES,
  HEALTH_POLL_MS,
  STREAM_RECONNECT_MS,
  STREAM_RECONNECT_MAX_ATTEMPTS,
  STREAM_RECONNECT_MAX_DELAY_MS,
  MAX_AUDIO_SEND_QUEUE,
  LATENCY_TARGET_MS,
  VOICE_WARMUP_COOLDOWN_MS,
  VOICE_PREFETCH_TIMEOUT_MS,
  HOLD_TO_TALK_DELAY_MS,
  EXPECTED_BACKEND_RELEASE,
  FRONTEND_BUILD_ID,
  EXPERIMENTAL_IOS_STREAMING,
  // debug
  readDebugFlag,
  makeDebugLog,
  isFatalStreamError,
  activePacketMs as activePacketMsUtil,
  // latency
  blankLatencyStats,
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
  languageName as languageNameUtil,
  shareRoomUrl,
  base64ToArrayBuffer,
  buildTranslatePayload,
} from './utils';

// Resolve API URL up-front from env + host.
const LOCAL_BACKEND = isLocalHost(window.location.hostname);
const SAME_ORIGIN_BACKEND = isSameOriginBackendHost(window.location.hostname);
const API_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? defaultApiUrl() : (configuredUrl(import.meta.env.VITE_API_URL) || defaultApiUrl())).replace(/\/+$/, '');
const WS_BASE_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? API_URL : (configuredUrl(import.meta.env.VITE_WS_URL) || API_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:'))).replace(/\/+$/, '');
const WS_AUDIO_URL = LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? `${WS_BASE_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')}/ws/audio` : (configuredUrl(import.meta.env.VITE_WS_AUDIO_URL) || `${WS_BASE_URL}/ws/audio`);
const BRIDGE_STATUS = bridgeStatusMessages();
const PIPELINE = pipelineStageLabels();
const DOCK = dockQuickActionLabels();

const INITIAL_DEVICE_ID = localStorage.getItem('translator_device_id') || crypto.randomUUID();

// Backend streams Microsoft Edge neural TTS for these languages (lifelike voice).
const BACKEND_NEURAL_VOICE_LANGS = new Set(['en', 'es', 'ht', 'fr', 'de', 'it', 'pt', 'nl', 'ru', 'zh', 'ja', 'ko', 'ar', 'hi']);
const PIPER_SUPPORTED_LANGS = BACKEND_NEURAL_VOICE_LANGS;
const BACKEND_TTS_WAIT_MS = Number(import.meta.env.VITE_BACKEND_TTS_WAIT_MS || 12000);

function shouldUseBrowserTts(settings, targetLang) {
  return settings?.ttsVoice === 'browser';
}

function prefersBackendNeuralVoice(settings, targetLang) {
  if (settings?.ttsVoice === 'browser') return false;
  if (settings?.ttsVoice === 'backend' || settings?.ttsVoice === 'google' || settings?.ttsVoice === 'auto') {
    return BACKEND_NEURAL_VOICE_LANGS.has(targetLang);
  }
  return BACKEND_NEURAL_VOICE_LANGS.has(targetLang);
}

function neuralPlaybackRate(speedSetting) {
  // Neural Edge TTS renders at natural speed — only apply the user's speed preference.
  const user = Number(speedSetting ?? 1.0);
  return Math.min(Math.max(user, 0.88), 1.12);
}
const BROWSER_TTS_LANG_MAP = {
  en: 'en-US', es: 'es-MX', fr: 'fr-FR', de: 'de-DE', it: 'it-IT',
  pt: 'pt-BR', ru: 'ru-RU', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR',
  ar: 'ar-SA', hi: 'hi-IN', ht: 'fr-HT', nl: 'nl-NL',
};
let browserTtsLastText = '';
let browserTtsLastFullText = '';
let browserTtsLastSourceText = '';
let browserTtsLastUtteranceId = null;
let browserTtsResetTimer = null;

function liveBrowserTtsDelta(nextText, sourceText = '', utteranceId = null) {
  const next = String(nextText || '').trim();
  const previous = String(browserTtsLastFullText || '').trim();
  const source = String(sourceText || '').trim();
  const previousSource = String(browserTtsLastSourceText || '').trim();
  const normalizedUtteranceId = utteranceId === undefined || utteranceId === null ? null : String(utteranceId);
  const utteranceChanged = normalizedUtteranceId !== null
    && browserTtsLastUtteranceId !== null
    && normalizedUtteranceId !== browserTtsLastUtteranceId;
  const sourceChanged = Boolean(source && previousSource && source !== previousSource && !source.toLowerCase().startsWith(previousSource.toLowerCase()));
  browserTtsLastFullText = next;
  if (source) browserTtsLastSourceText = source;
  if (normalizedUtteranceId !== null) browserTtsLastUtteranceId = normalizedUtteranceId;
  if (!next || next === previous) return '';
  if (utteranceChanged || sourceChanged) return next;
  if (previous && next.toLowerCase().startsWith(previous.toLowerCase())) {
    return next.slice(previous.length).trim().replace(/^[,.;:!?-]+\s*/, '');
  }
  return next;
}

function browserTtsSpeak(text, langCode, speed = 1.0, options = {}) {
  if (!window.speechSynthesis || !text) return false;
  browserTtsLastText = text;
  const lang = BROWSER_TTS_LANG_MAP[langCode] || langCode || 'en-US';
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = lang;
  utt.rate = Math.min(Math.max(speed * 0.92, 0.5), 1.35);
  utt.volume = 0.84;
  utt.pitch = 0.92;
  const voices = window.speechSynthesis.getVoices();
  const languagePrefix = lang.slice(0, 2);
  const premiumVoice = voices.find((v) => (
    v.lang.startsWith(languagePrefix)
    && /natural|neural|online|premium|aria|denise|nanami|xiaoxiao|google/i.test(`${v.name} ${v.voiceURI}`)
  ));
  const match = premiumVoice
    || voices.find((v) => v.lang.startsWith(languagePrefix) && !v.localService)
    || voices.find((v) => v.lang.startsWith(languagePrefix));
  if (match) utt.voice = match;
  const finish = () => {
    try { options.onEnd?.(); } catch {}
  };
  utt.onend = finish;
  utt.onerror = finish;
  try { options.onStart?.(); } catch {}
  try { window.speechSynthesis.resume?.(); } catch {}
  try {
    window.speechSynthesis.speak(utt);
  } catch (error) {
    finish();
    return false;
  }
  if (browserTtsResetTimer) window.clearTimeout(browserTtsResetTimer);
  browserTtsResetTimer = window.setTimeout(() => {
    if (document.visibilityState !== 'visible') return;
    browserTtsLastText = '';
    browserTtsLastFullText = '';
    browserTtsLastSourceText = '';
    browserTtsLastUtteranceId = null;
  }, 5000);
  return true;
}

const INITIAL_SPEAKER_NAME = localStorage.getItem('translator_speaker_name') || '';
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 60);
const STREAM_AUDIO_BITRATE = Number(import.meta.env.VITE_STREAM_AUDIO_BITRATE || 48000);
const CLIENT_VAD_THRESHOLD = Number(import.meta.env.VITE_CLIENT_VAD_THRESHOLD || 0.055);
const FAST_SPEECH_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_SPEECH_TIMEOUT_MS || 10000);
const FAST_TTS_TIMEOUT_MS = Number(import.meta.env.VITE_FAST_TTS_TIMEOUT_MS || 10000);
const MIN_STREAM_CAPTURE_MS = Number(import.meta.env.VITE_MIN_STREAM_CAPTURE_MS || 1800);
const LIVE_SPEECH_TEXT_THROTTLE_MS = Number(import.meta.env.VITE_LIVE_SPEECH_TEXT_THROTTLE_MS || 90);
const LIVE_TTS_MAX_QUEUE = Number(import.meta.env.VITE_LIVE_TTS_MAX_QUEUE || 4);

const DEBUG_LOGS = readDebugFlag();
const debugLog = makeDebugLog(DEBUG_LOGS);
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
  const { languages, setLanguages, sourceLanguage, setSourceLanguage, targetLanguage, setTargetLanguage } = useLanguagePair();
  const { text, setText, result, setResult, status, setStatus } = useTranslationState();
  // Settings is loaded first (sync from localStorage) so liveApiUrl is available for all hooks below.
  const { settings, updateSetting, NOISY_ENVIRONMENTS } = useSettings();
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const liveApiUrl = (settings.backendUrl || '').trim().replace(/\/+$/, '') || API_URL;
  const liveWsUrl = liveApiUrl.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
  const handleLanguagesLoaded = React.useCallback((langs) => {
    if (langs) setLanguages((prev) => ({ ...prev, ...langs }));
  }, [setLanguages]);
  const handleConnectionOffline = React.useCallback(() => {
    setStatus(BRIDGE_STATUS.serverOffline);
  }, [setStatus]);
  const { connectionStatus, setConnectionStatus } = useConnectionStatus({
    apiUrl: liveApiUrl,
    pollIntervalMs: HEALTH_POLL_MS,
    onLanguages: handleLanguagesLoaded,
    onOffline: handleConnectionOffline,
  });
  const { diagnostics, diagnosticsStatus, loadDiagnostics } = useDiagnostics(liveApiUrl);
  const { micPermission, setMicPermission, requestMicPermission } = useMicPermission({
    onStatus: (message) => setStatus(message),
  });
  const { sessionId, setSessionId, updateSessionId, sharedSession, setSharedSession, speakerMode, setSpeakerMode } = useStreamSession();
  // Pipeline-stage flags: one reducer, individual shim setters keep
  // existing call sites unchanged. See hooks/useInterpreterState.js.
  const {
    recording,
    streaming,
    processing,
    playing,
    interpreterMode,
    instantListening,
    liveAssistActive,
    setRecording,
    setStreaming,
    setProcessing,
    setPlaying,
    setInterpreterMode,
    setInstantListening,
    setLiveAssistActive,
  } = useInterpreterState();
  const {
    partialTranscript, setPartialTranscript,
    liveTranslation, setLiveTranslation,
    pipelineStage, setPipelineStage,
    audioReplayAvailable, setAudioReplayAvailable,
    lastAudioError, setLastAudioError,
  } = usePipelineState();
  const { duplex, setDuplex, duplexRefs, updateDuplexSpeaker } = useDuplexState();
  const {
    clarifyVisible, setClarifyVisible,
    clarifyMessage, setClarifyMessage,
    brainUi, setBrainUi,
    conversationBrain, setConversationBrain,
    semanticContext, setSemanticContext,
    brainHintsRef, brainPlanRef,
    shouldSkipBrainTts, resetBrainRuntimeUi,
    applyConfidenceSignals,
    confidenceWarningVisible,
    setConfidenceWarningVisible,
    confidenceWarningMessage,
    humanCertificationStep,
    setHumanCertificationStep,
  } = useBrainState();
  const {
    recordSuccess: recordReliabilitySuccess,
    recordFailure: recordReliabilityFailure,
  } = useReliabilityMonitor();
  const reliabilityRef = useRef({
    recordSuccess: recordReliabilitySuccess,
    recordFailure: recordReliabilityFailure,
  });
  useEffect(() => {
    reliabilityRef.current = {
      recordSuccess: recordReliabilitySuccess,
      recordFailure: recordReliabilityFailure,
    };
  });
  const {
    mediaRecorderRef, streamRecorderRef, chunksRef, socketRef,
    recordingStoppedRef, streamFinalizePendingRef, streamFinalizeTimerRef,
    streamStartedAtRef, streamRecordingStartedAtRef, firstAudioSeenRef,
    streamReconnectRef, streamReconnectTimerRef, streamSafetyTimeoutRef, resumeAfterTtsRef,
  } = useStreamRefs();
  // Auth must be declared before any hook that references authToken.
  const { authToken, setAuthToken, username, setUsername, password, setPassword, login, logout, ensureAuthToken } = useAuth({ apiUrl: liveApiUrl, onStatus: setStatus });
  const { voiceWarmupRef, resolveAudioUrl, prefetchAudioUrl, warmVoiceCache } = useVoiceWarmup({
    apiUrl: liveApiUrl,
    authToken,
    targetLanguage,
    warmupPhrases: VOICE_WARMUP_PHRASES,
    cooldownMs: VOICE_WARMUP_COOLDOWN_MS,
    prefetchTimeoutMs: VOICE_PREFETCH_TIMEOUT_MS,
  });
  const { streamHeartbeatRef, clearStreamHeartbeat, markStreamPong, startStreamHeartbeat } = useStreamHeartbeat({ socketRef, setPipelineStage, setStatus });
  const { holdToTalkTimerRef, holdToTalkActiveRef, holdToTalkReleasePendingRef, ignoreNextMicClickRef } = useHoldToTalk();
  const { audioSendQueueRef, sendAudioPacket, queueAudioPacket, flushAudioSendQueue, drainQueue: drainAudioSendQueue } = useAudioSendQueue({ debugLog });
  const { wakeLockRef, requestWakeLock, releaseWakeLock } = useWakeLock();
  const {
    speechRecognitionRef, speechFastPathActiveRef,
    speechFinalTextRef, speechInterimTextRef,
    speechAssistSocketRef, speechAssistRestartTimerRef, speechAssistStopRequestedRef,
    speechLastSentTextRef, speechLastSentAtRef, speechUtteranceSeqRef,
  } = useSpeechFastPath();
  const autoConversation = useAutoConversation({
    wsAudioUrl: `${liveWsUrl}/ws/audio`,
    authToken,
    sourceLanguage,
    targetLanguage,
    sessionId,
    deviceId: INITIAL_DEVICE_ID,
    withAuthToken,
    backendReady: connectionStatus === 'online' || connectionStatus === 'warming',
    onStatus: setStatus,
    onNeedAudioStream: () => {
      if (socketRef.current) return;
      toggleStreaming({ interpreter: true, speakerMode: 'auto' });
    },
  });
  const autoTurnSyncRef = useRef(0);
  const lowBandwidthMode = !!settings.lowBandwidthMode;
  const advancedChrome = showAdvancedInterpreterChrome(settings.debugMode);
  const [showDebugPanel, setShowDebugPanel] = useState(() => !!settings.debugMode);
  const [showAILangConfig, setShowAILangConfig] = useState(false);
  const [reconnectToastVisible, setReconnectToastVisible] = useState(false);

  // Error state for user-friendly error display
  const [currentError, setCurrentError] = useState(null);
  const [iosMicHintDismissed, setIosMicHintDismissed] = useState(() => {
    try { return sessionStorage.getItem('anai_ios_mic_hint_dismissed') === '1'; } catch { return false; }
  });
  const showUserError = React.useCallback((errorCode) => {
    try {
      if (localStorage.getItem(`anai_error_dismissed_${errorCode}`)) return;
    } catch {}
    setCurrentError(errorCode);
  }, []);
  const handleDismissError = () => setCurrentError(null);
  const handleRetryError = () => {
    const code = currentError;
    setCurrentError(null);
    if (code === 'network_offline' || code === 'websocket_disconnected' || code === 'network_timeout') {
      retryBackendConnection();
      return;
    }
    if (code === 'mic_permission_denied' || code === 'mic_not_found' || code === 'mic_blocked') {
      requestMicPermission().catch(() => {});
      return;
    }
    try { handleMicClick(); } catch {}
  };

  // Keyboard shortcuts
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [textInputMode, setTextInputMode] = useState(false);
  const [offlineBannerDismissed, setOfflineBannerDismissed] = useState(false);
  const [micBannerDismissed, setMicBannerDismissed] = useState(false);
  const [installNudgeDismissed, setInstallNudgeDismissed] = useState(() => {
    try { return sessionStorage.getItem('anai_install_nudge_dismissed') === '1'; } catch { return false; }
  });
  const [showFriendlyStatus, setShowFriendlyStatus] = useState(() => {
    try { return localStorage.getItem('anai_friendly_status') !== 'false'; } catch { return true; }
  });
  const [interpreterSocketOpen, setInterpreterSocketOpen] = useState(false);
  const [liveSpeechSession, setLiveSpeechSession] = useState(false);
  const liveSpeechSessionRef = useRef(false);
  const autoListenBootRef = useRef(false);
  const partialTranscriptRafRef = useRef(null);
  const liveTranslationRafRef = useRef(null);
  const statusRafRef = useRef(null);
  const pendingStatusRef = useRef(null);

  useEffect(() => {
    liveSpeechSessionRef.current = liveSpeechSession;
  }, [liveSpeechSession]);

  function scheduleStatusUpdate(stage, nextStatus) {
    pendingStatusRef.current = { stage, status: nextStatus };
    if (statusRafRef.current) return;
    statusRafRef.current = window.requestAnimationFrame(() => {
      statusRafRef.current = null;
      const pending = pendingStatusRef.current;
      pendingStatusRef.current = null;
      if (!pending) return;
      if (pending.stage) setPipelineStage(pending.stage);
      if (pending.status) setStatus(pending.status);
    });
  }

  function schedulePartialTranscript(text) {
    if (partialTranscriptRafRef.current) window.cancelAnimationFrame(partialTranscriptRafRef.current);
    partialTranscriptRafRef.current = window.requestAnimationFrame(() => {
      partialTranscriptRafRef.current = null;
      setPartialTranscript(text);
    });
  }

  function scheduleLiveTranslation(text) {
    if (liveTranslationRafRef.current) window.cancelAnimationFrame(liveTranslationRafRef.current);
    liveTranslationRafRef.current = window.requestAnimationFrame(() => {
      liveTranslationRafRef.current = null;
      setLiveTranslation(text);
    });
  }

  useEffect(() => {
    if (micPermission === 'available') setMicBannerDismissed(false);
  }, [micPermission]);

  useEffect(() => {
    if (connectionStatus === 'online') setOfflineBannerDismissed(false);
  }, [connectionStatus]);

  // Returning users: resume continuous listening without tapping again each visit.
  useEffect(() => {
    if (connectionStatus !== 'online' || micPermission !== 'available') return;
    if (autoListenBootRef.current || liveSpeechSessionRef.current || socketRef.current) return;
    let enabled = false;
    try { enabled = sessionStorage.getItem('anai_auto_listen_enabled') === '1'; } catch {}
    if (!enabled) return;
    autoListenBootRef.current = true;
    const timer = window.setTimeout(() => {
      if (!navigator.onLine || document.visibilityState !== 'visible') {
        autoListenBootRef.current = false;
        return;
      }
      handleMicClick().catch(() => { autoListenBootRef.current = false; });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [connectionStatus, micPermission]);

  useEffect(() => {
    const openKeyboardHelp = () => setShowKeyboardHelp(true);
    window.addEventListener('anai-open-keyboard-help', openKeyboardHelp);
    return () => window.removeEventListener('anai-open-keyboard-help', openKeyboardHelp);
  }, []);

  async function retryBackendConnection() {
    setConnectionStatus('checking');
    try {
      const response = await fetch(`${liveApiUrl}/health`, { cache: 'no-store' });
      if (!response.ok) throw new Error('health check failed');
      const data = await response.json();
      setConnectionStatus(data.ready === false ? 'warming' : 'online');
      if (data.ready !== false) {
        await loadDiagnostics();
        reliabilityRef.current.recordSuccess('translation');
      }
    } catch {
      setConnectionStatus('offline');
      reliabilityRef.current.recordFailure('translation');
    }
  }
  // Volume state synced from settings; keyboard shortcut toggles mute
  const [volume, setVolume] = useState(() => settings.volume ?? 0.8);
  // Keep local volume in sync when settings.volume changes externally
  useEffect(() => { setVolume(settings.volume ?? 0.8); }, [settings.volume]);
  useKeyboardShortcuts({
    onToggleMic: handleMicClick,
    onToggleMute: () => {
      const next = volume === 0 ? (settings.volume || 0.8) : 0;
      setVolume(next);
      if (settings.soundEffects !== false) haptic(20);
    },
    onClearConversation: clearInterpreterScreen,
    onSetLanguage: setTargetLanguage,
    onShowHelp: () => setShowKeyboardHelp(true),
    onCloseModals: () => {
      setShowKeyboardHelp(false);
      setCurrentError(null);
    },
    disabled: recording || processing,
  });

  const handleVolumeChange = (newVolume) => {
    setVolume(newVolume);
    updateSetting('volume', newVolume);
    const audioElements = document.querySelectorAll('audio');
    audioElements.forEach(audio => { audio.volume = newVolume; });
    if (masterGainRef.current) {
      masterGainRef.current.gain.setTargetAtTime(newVolume * 0.92, masterGainRef.current.context.currentTime, 0.05);
    }
  };
  const {
    mobileAudioUnlocked, setMobileAudioUnlocked,
    audioContextState, setAudioContextState,
    audioContextRef, persistentAudioRef, mobileAudioUnlockedRef, warmupOscRef, warmupGainRef,
    createPersistentAudio, ensureAudioContext, stopAudioWarmup, destroyPersistentAudio,
    synchronousAudioUnlock, unlockMobileAudio, ensureAudioUnlocked,
  } = usePersistentAudio({ debugLog });
  const {
    ttsQueueLength, setTtsQueueLength,
    ttsPlaying, setTtsPlaying,
    ttsChunksBuffer, setTtsChunksBuffer,
    userRequestedPlayback, setUserRequestedPlayback,
    autoPlayFailed, setAutoPlayFailed,
    ttsQueueRef, lastTtsItemRef, ttsPlayingRef, currentTtsFinishRef, canplayTimeoutRef,
    revokeTtsItemUrl, hasPlayableAudioPayload, clearTtsQueue,
  } = useTtsQueue();
  // interpreterMode is part of useInterpreterState (declared above).
  const { detectedSpeaker, setDetectedSpeaker, speakerLabelsRef, rememberSpeaker, normalizeConversationTurn, loadSpeakerProfiles } = useSpeakerMemory();
  const { latencyStats, setLatencyStats, latencyHistory, setLatencyHistory, latencySummary, updateLatency, recordLatencyTurn } = useLatencyStats();
  // useAuth is declared earlier (before useAutoConversation) — do not duplicate.
  const { selfTest, runSelfTest } = useSelfTest({
    apiUrl: liveApiUrl,
    wsAudioUrl: `${liveWsUrl}/ws/audio`,
    authToken,
    onStatus: (message) => setStatus(message),
  });
  const [appMode, setAppMode] = React.useState('solo'); // 'solo' | 'conversation'
  const [conversationTurns, setConversationTurns, appendConversationTurn] = useConversationHistory(50, { normalizeConversationTurn });
  useEffect(() => {
    const turns = autoConversation.turns;
    if (turns.length <= autoTurnSyncRef.current) return;
    const fresh = turns.slice(autoTurnSyncRef.current);
    autoTurnSyncRef.current = turns.length;
    fresh.forEach((turn) => {
      appendConversationTurn({
        speaker: turn.conversationSpeaker || turn.speaker || 'A',
        speaker_label: turn.speaker_label,
        source_text: turn.source_text || '',
        translated_text: turn.translated_text || '',
        source_language: turn.srcLang,
        target_language: turn.tgtLang,
        created_at: (turn.timestamp || Date.now()) / 1000,
      });
    });
  }, [autoConversation.turns, appendConversationTurn]);
  const { analytics, setAnalytics, loadAnalytics } = useAnalytics({ apiUrl: liveApiUrl, authToken, onStatus: setStatus });
  const { wsDebug, setWsDebug } = useWsDebug(`${liveWsUrl}/ws/audio`);
  // selfTest + runSelfTest come from useSelfTest below (after authToken is declared).
  // Initial PWA-installed status (true if launched from the home screen).
  const initialPwaInstalled =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator?.standalone === true;
  const updateAvailable = useServiceWorkerUpdate({
    apiUrl: liveApiUrl,
    expectedRelease: EXPECTED_BACKEND_RELEASE,
  });
  const { micLevel, micMeterRef, startMicMeter, stopMicMeter, stopTracks, startSilenceDetector, stopSilenceDetector } = useMicMeter();
  const { toasts, toast, dismiss } = useToast();
  const [copiedKey, _copyToClipboard] = useCopyToClipboard();
  const copyToClipboard = (text, key) => {
    _copyToClipboard(text, key);
    const copyLabels = {
      src: 'Transcript copied',
      tr: 'Bridged text copied',
      conversation: 'Conversation copied',
      room: 'Room link copied',
    };
    toast(copyLabels[key] || 'Copied to clipboard', 'success', 2000);
  };
  const hapticRaw = useHaptic();
  const haptic = React.useCallback((ms) => {
    if (settings.soundEffects !== false) hapticRaw(ms);
  }, [hapticRaw, settings.soundEffects]);
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
  const { cameraActive, ocrText, videoRef, startCamera, stopCamera, captureAndTranslateFrame } = useCamera({
    apiUrl: liveApiUrl,
    authToken,
    targetLanguage,
    setStatus,
    onResult: (data) => {
      setResult(data);
      setLiveTranslation(data.translated_text || '');
    },
  });

  // conversation history persistence is in useConversationHistory above.

  // latencyHistory persistence + summary computation live inside
  // useLatencyHistory; we only need to react to slow trends here.
  useEffect(() => {
    if (!latencySummary.average || latencySummary.average <= LATENCY_TARGET_MS) return;
    if (connectionStatus !== 'online' || processing || playing || streaming) return;
    if (!navigator.onLine || document.visibilityState !== 'visible') return;
    warmVoiceCache('slow_latency').then((ok) => {
      if (ok) reliabilityRef.current.recordSuccess('tts');
      else reliabilityRef.current.recordFailure('tts');
    }).catch(() => reliabilityRef.current.recordFailure('tts'));
  }, [connectionStatus, latencySummary.average, playing, processing, streaming, warmVoiceCache]);

  useEffect(() => {
    if (connectionStatus !== 'online' || processing || playing || streaming) return undefined;
    const timer = window.setTimeout(() => {
      if (!navigator.onLine || document.visibilityState !== 'visible') return;
      warmVoiceCache('language_ready').then((ok) => {
        if (ok) reliabilityRef.current.recordSuccess('tts');
      }).catch(() => reliabilityRef.current.recordFailure('tts'));
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [connectionStatus, playing, processing, streaming, targetLanguage, warmVoiceCache]);

  // copyToClipboard + copiedKey come from useCopyToClipboard above.

  // shareRoomUrl call sites stay terse below.

  function applyBrainPayload(payload = {}, origin = 'translation') {
    applyConfidenceSignals(payload);
    if (payload.source_text) lastGuardedSourceRef.current = payload.source_text;
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
      message = pipelineStages().guarded;
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
      setStatus(BRIDGE_STATUS.chooseMeaning);
      return;
    }
    setClarifyVisible(false);
    setPipelineStage(PIPELINE.readyToRepair);
    setStatus(option.label || 'Please repeat');
    if (!streaming && !processing && !playing) {
      try { handleMicClick(); } catch {}
    }
  }


  function clearInterpreterScreen() {
    if (autoConversation.active) {
      haptic(14);
      autoConversation.clearTurns();
      autoTurnSyncRef.current = 0;
      setConversationTurns([]);
      setPartialTranscript('');
      setLiveTranslation('');
      setResult(null);
      return;
    }
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
    setStatus(BRIDGE_STATUS.ready);
    setPipelineStage(PIPELINE.ready);
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
    setPipelineStage(PIPELINE.directionSwitched);
  }
  const appStateRef = useRef({});
  const liveVoiceFallbackTimerRef = useRef(null);
  const backendVoiceChunkSeenAtRef = useRef(0);
  const micPausedForVoiceRef = useRef(false);
  const micTracksPausedForVoiceRef = useRef([]);
  const liveTtsPlaybackRef = useRef(false);
  const languagePairRef = useRef({ sourceLanguage, targetLanguage });
  const streamChunkCounterRef = useRef(0);
  const lastGuardedSourceRef = useRef('');
  const browserVoiceReleaseTimerRef = useRef(null);
  const pendingBrowserVoiceTextRef = useRef(null);
  const languageName = (code) => languageNameUtil(code, languages);

  function resolveStreamBarrierMode() {
    if (settings.barrierMode === false) return false;
    const pair = new Set([sourceLanguage, targetLanguage]);
    return pair.has('ht') || settings.barrierMode === true;
  }

  function resolveStreamEnvironment() {
    return settings.audioEnvironment || 'auto';
  }

  function shouldPreferHoldToTalk() {
    const env = resolveStreamEnvironment();
    if (settings.holdToTalkInNoise !== false && NOISY_ENVIRONMENTS.includes(env)) {
      return true;
    }
    return false;
  }

  function streamConfigPayload(extra = {}) {
    return {
      type: 'config',
      session_id: sessionId,
      device_id: INITIAL_DEVICE_ID,
      speaker_name: INITIAL_SPEAKER_NAME,
      source_language: sourceLanguage,
      target_language: targetLanguage,
      speaker_mode: speakerMode,
      speaker: speakerMode === 'auto' ? 'auto' : 'A',
      barrier_mode: resolveStreamBarrierMode(),
      environment: resolveStreamEnvironment(),
      ...extra,
    };
  }

  function sendGlossaryCorrection({ sourceText, translatedText, context = 'general' } = {}) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    const { sourceLanguage: activeSource, targetLanguage: activeTarget } = languagePairRef.current;
    try {
      socket.send(JSON.stringify({
        type: 'glossary_correction',
        session_id: sessionId,
        source_text: sourceText,
        corrected_text: translatedText,
        source_language: activeSource,
        target_language: activeTarget,
        context,
      }));
      setHumanCertificationStep('none');
      toast('Saved native-verified phrasing for this session.', 'success', 2500);
    } catch (error) {
      console.warn('glossary correction send failed:', error);
    }
  }

  useEffect(() => {
    if (diagnosticsStatus === 'online') {
      reliabilityRef.current.recordSuccess('translation');
    }
  }, [diagnosticsStatus]);

  useEffect(() => {
    appStateRef.current = { interpreterMode, speakerMode, recording, processing, playing, streaming };
  }, [interpreterMode, speakerMode, recording, processing, playing, streaming]);

  useEffect(() => {
    const previous = languagePairRef.current;
    languagePairRef.current = { sourceLanguage, targetLanguage };
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    try {
      socket.send(JSON.stringify(streamConfigPayload()));
    } catch (error) {
      console.warn('stream language config send failed:', error);
    }
    setPipelineStage(`${languageName(sourceLanguage)} to ${languageName(targetLanguage)}`);
    if (previous.sourceLanguage !== sourceLanguage && speechFastPathActiveRef.current) {
      try { speechRecognitionRef.current?.abort?.(); } catch (error) {
        console.warn('speech recognition language restart failed:', error);
      }
      speechFastPathActiveRef.current = false;
      speechRecognitionRef.current = null;
      speechAssistSocketRef.current = null;
      if (speechAssistRestartTimerRef.current) {
        window.clearTimeout(speechAssistRestartTimerRef.current);
        speechAssistRestartTimerRef.current = null;
      }
      window.setTimeout(() => {
        if (!navigator.onLine || document.visibilityState !== 'visible') return;
        if (socketRef.current === socket && socket.readyState === WebSocket.OPEN) {
          startBrowserSpeechFastPath(socket);
        }
      }, 80);
    }
  }, [sourceLanguage, targetLanguage, speakerMode, sessionId]);

  // haptic comes from useHaptic() above.


  // backend/frontend release polling lives in useServiceWorkerUpdate above.

  useEffect(() => {
    return () => {
      destroyPersistentAudio();
      if (canplayTimeoutRef.current) {
        window.clearTimeout(canplayTimeoutRef.current);
        canplayTimeoutRef.current = null;
      }
      try { speechRecognitionRef.current?.abort?.(); } catch (e) {}
      if (liveVoiceFallbackTimerRef.current) {
        window.clearTimeout(liveVoiceFallbackTimerRef.current);
        liveVoiceFallbackTimerRef.current = null;
      }
      if (browserVoiceReleaseTimerRef.current) {
        window.clearTimeout(browserVoiceReleaseTimerRef.current);
        browserVoiceReleaseTimerRef.current = null;
      }
      micTracksPausedForVoiceRef.current.forEach((track) => {
        try {
          if (track.readyState === 'live') track.enabled = true;
        } catch {}
      });
      micTracksPausedForVoiceRef.current = [];
    };
  }, []);

  // Connection status polling and language loading are handled by useConnectionStatus above.
  // First diagnostics fetch happens inside useDiagnostics on mount.
  useEffect(() => {
    if (diagnosticsStatus !== 'online' || !diagnostics?.tts_neural) return;
    if (diagnostics.tts_neural.neural_ready === false && settings.ttsVoice !== 'browser') {
      toast('Neural voice offline — speech may sound robotic. Run Restart-Translator.ps1', 'error', 9000);
    }
  }, [diagnostics, diagnosticsStatus, settings.ttsVoice, toast]);

  function shouldPauseMicForVoicePlayback() {
    const ua = navigator.userAgent || '';
    return /iphone|ipad|ipod|android|mobile/i.test(ua) || isIosOrSafariRecorder();
  }

  function pauseMicForVoicePlayback() {
    if (!shouldPauseMicForVoicePlayback()) return false;
    const recorder = streamRecorderRef.current;
    if (!recorder) return false;
    const liveTracks = Array.from(recorder.stream?.getAudioTracks?.() || []).filter((track) => track.readyState === 'live');
    const enabledTracks = liveTracks.filter((track) => track.enabled);
    let pausedRecorder = false;
    try {
      if (recorder.state === 'recording' && typeof recorder.pause === 'function') {
        recorder.requestData?.();
        recorder.pause();
        pausedRecorder = true;
      }
      if (enabledTracks.length && micTracksPausedForVoiceRef.current.length === 0) {
        enabledTracks.forEach((track) => {
          track.enabled = false;
        });
        micTracksPausedForVoiceRef.current = enabledTracks;
      }
      micPausedForVoiceRef.current = pausedRecorder || micTracksPausedForVoiceRef.current.length > 0;
      return micPausedForVoiceRef.current;
    } catch (error) {
      console.warn('Unable to pause mic for voice playback:', error);
      return false;
    }
  }

  function resumeMicAfterVoicePlayback() {
    const recorder = streamRecorderRef.current;
    const restorePausedTracks = () => {
      micTracksPausedForVoiceRef.current.forEach((track) => {
        try {
          if (track.readyState === 'live') track.enabled = true;
        } catch {}
      });
      micTracksPausedForVoiceRef.current = [];
    };
    if (!micPausedForVoiceRef.current) {
      restorePausedTracks();
      return;
    }
    if (!recorder || recorder.state !== 'paused' || typeof recorder.resume !== 'function') {
      restorePausedTracks();
      micPausedForVoiceRef.current = false;
      return;
    }
    window.setTimeout(() => {
      try {
        if (streamRecorderRef.current === recorder && recorder.state === 'paused') {
          restorePausedTracks();
          recorder.resume();
        }
      } catch (error) {
        console.warn('Unable to resume mic after voice playback:', error);
      } finally {
        restorePausedTracks();
        micPausedForVoiceRef.current = false;
        if (socketRef.current?.readyState === WebSocket.OPEN && shouldKeepContinuousStream(socketRef.current)) {
          setStreaming(true);
          setInstantListening(true);
        }
      }
    }, 80);
  }

  function finishBrowserTranslatedSpeech() {
    if (browserVoiceReleaseTimerRef.current) {
      window.clearTimeout(browserVoiceReleaseTimerRef.current);
      browserVoiceReleaseTimerRef.current = null;
    }
    ttsPlayingRef.current = false;
    setTtsPlaying(false);
    setPlaying(false);
    resumeMicAfterVoicePlayback();
    const pending = pendingBrowserVoiceTextRef.current;
    pendingBrowserVoiceTextRef.current = null;
    if (pending && socketRef.current?.readyState === WebSocket.OPEN) {
      window.setTimeout(() => {
        if (document.visibilityState !== 'visible' || !navigator.onLine) return;
        speakTranslatedTextWithBrowser(pending.text, pending.sourceText, pending.utteranceId, pending.languageOverride);
      }, 80);
    } else if (socketRef.current?.readyState === WebSocket.OPEN) {
      if (shouldKeepContinuousStream(socketRef.current)) {
        setStreaming(true);
        setInstantListening(true);
      }
      setPipelineStage(PIPELINE.listening);
      setStatus(BRIDGE_STATUS.listeningNextSpeaker);
    }
  }

  function speakTranslatedTextWithBrowser(fullTranslatedText, sourceText = '', utteranceId = null, languageOverride = null) {
    const voiceLanguage = languageOverride || languagePairRef.current.targetLanguage;
    if (!shouldUseBrowserTts(settings, voiceLanguage)) return false;
    const text = String(fullTranslatedText || '').trim();
    if (!text || lowBandwidthMode) return false;
    if (ttsPlayingRef.current) {
      pendingBrowserVoiceTextRef.current = { text, sourceText, utteranceId, languageOverride };
      return false;
    }
    const spokenDelta = liveBrowserTtsDelta(text, sourceText, utteranceId);
    if (!spokenDelta || spokenDelta.split(/\s+/).length < 1) return false;
    const estimatedMs = Math.min(12000, Math.max(1800, spokenDelta.split(/\s+/).length * 520));
    const started = browserTtsSpeak(spokenDelta, voiceLanguage, settings.ttsSpeed ?? 1.0, {
      onStart: () => {
        pauseMicForVoicePlayback();
        ttsPlayingRef.current = true;
        setTtsPlaying(true);
        setPlaying(true);
        setPipelineStage(pipelineStages().bridging);
        setStatus(pipelineStages().bridgingStatus);
        if (browserVoiceReleaseTimerRef.current) window.clearTimeout(browserVoiceReleaseTimerRef.current);
        browserVoiceReleaseTimerRef.current = window.setTimeout(() => {
          if (document.visibilityState !== 'visible' || !navigator.onLine) return;
          finishBrowserTranslatedSpeech();
        }, estimatedMs);
      },
      onEnd: finishBrowserTranslatedSpeech,
    });
    if (!started) {
      resumeMicAfterVoicePlayback();
    }
    return started;
  }

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && (streaming || instantListening) && !wakeLockRef.current) {
        requestWakeLock();
      }
      if (document.visibilityState === 'hidden') {
        clearStreamHeartbeat();
        if (streamReconnectTimerRef.current) {
          window.clearTimeout(streamReconnectTimerRef.current);
          streamReconnectTimerRef.current = null;
        }
        if (streamSafetyTimeoutRef.current) {
          window.clearTimeout(streamSafetyTimeoutRef.current);
          streamSafetyTimeoutRef.current = null;
        }
        if (liveVoiceFallbackTimerRef.current) {
          window.clearTimeout(liveVoiceFallbackTimerRef.current);
          liveVoiceFallbackTimerRef.current = null;
        }
        if (browserVoiceReleaseTimerRef.current) {
          window.clearTimeout(browserVoiceReleaseTimerRef.current);
          browserVoiceReleaseTimerRef.current = null;
        }
        if (speechAssistRestartTimerRef.current) {
          window.clearTimeout(speechAssistRestartTimerRef.current);
          speechAssistRestartTimerRef.current = null;
        }
        stopBrowserSpeechFastPath();
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          try {
            socketRef.current.send(JSON.stringify({ type: 'ping' }));
          } catch {
            // Socket may have closed between the check and send.
          }
        }
      }
      if (document.visibilityState === 'visible') {
        const liveSocket = socketRef.current;
        if (liveSocket?.readyState === WebSocket.OPEN) {
          startStreamHeartbeat(liveSocket);
        }
      }
      if (
        document.visibilityState === 'visible'
        && streamReconnectRef.current.enabled
        && liveSpeechSessionRef.current
        && !socketRef.current
      ) {
        if (streamReconnectTimerRef.current) window.clearTimeout(streamReconnectTimerRef.current);
        streamReconnectTimerRef.current = window.setTimeout(() => {
          streamReconnectTimerRef.current = null;
          if (!navigator.onLine || document.visibilityState !== 'visible') return;
          if (!streamReconnectRef.current.enabled || socketRef.current) return;
          toggleStreaming({
            ...(streamReconnectRef.current.options || {}),
            interpreter: true,
            speakerMode: 'auto',
            reconnect: true,
          });
        }, 350);
      }
    };
    const handleOnlineResume = () => {
      if (!navigator.onLine) return;
      const liveSocket = socketRef.current;
      if (liveSocket?.readyState === WebSocket.OPEN) {
        startStreamHeartbeat(liveSocket);
      }
      if (
        streamReconnectRef.current.enabled
        && liveSpeechSessionRef.current
        && !socketRef.current
      ) {
        if (streamReconnectTimerRef.current) window.clearTimeout(streamReconnectTimerRef.current);
        streamReconnectTimerRef.current = window.setTimeout(() => {
          streamReconnectTimerRef.current = null;
          if (!navigator.onLine || document.visibilityState !== 'visible') return;
          if (!streamReconnectRef.current.enabled || socketRef.current) return;
          toggleStreaming({
            ...(streamReconnectRef.current.options || {}),
            interpreter: true,
            speakerMode: 'auto',
            reconnect: true,
          });
        }, 400);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    const handleOfflinePause = () => {
      clearStreamHeartbeat();
      if (streamReconnectTimerRef.current) {
        window.clearTimeout(streamReconnectTimerRef.current);
        streamReconnectTimerRef.current = null;
      }
      if (streamSafetyTimeoutRef.current) {
        window.clearTimeout(streamSafetyTimeoutRef.current);
        streamSafetyTimeoutRef.current = null;
      }
      if (liveVoiceFallbackTimerRef.current) {
        window.clearTimeout(liveVoiceFallbackTimerRef.current);
        liveVoiceFallbackTimerRef.current = null;
      }
      if (browserVoiceReleaseTimerRef.current) {
        window.clearTimeout(browserVoiceReleaseTimerRef.current);
        browserVoiceReleaseTimerRef.current = null;
      }
    };
    const handlePageShow = () => {
      if (!navigator.onLine || document.visibilityState !== 'visible') return;
      const liveSocket = socketRef.current;
      if (liveSocket?.readyState === WebSocket.OPEN) {
        startStreamHeartbeat(liveSocket);
      }
      if (
        streamReconnectRef.current.enabled
        && liveSpeechSessionRef.current
        && !socketRef.current
      ) {
        if (streamReconnectTimerRef.current) window.clearTimeout(streamReconnectTimerRef.current);
        streamReconnectTimerRef.current = window.setTimeout(() => {
          streamReconnectTimerRef.current = null;
          if (!navigator.onLine || document.visibilityState !== 'visible') return;
          if (!streamReconnectRef.current.enabled || socketRef.current) return;
          toggleStreaming({
            ...(streamReconnectRef.current.options || {}),
            interpreter: true,
            speakerMode: 'auto',
            reconnect: true,
          });
        }, 350);
      }
    };
    window.addEventListener('online', handleOnlineResume);
    window.addEventListener('offline', handleOfflinePause);
    window.addEventListener('pageshow', handlePageShow);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('online', handleOnlineResume);
      window.removeEventListener('offline', handleOfflinePause);
      window.removeEventListener('pageshow', handlePageShow);
      if (streamReconnectTimerRef.current) {
        window.clearTimeout(streamReconnectTimerRef.current);
        streamReconnectTimerRef.current = null;
      }
    };
  }, [streaming, instantListening]);

  // mic permission lifecycle is in useMicPermission above.
  // PWA install lifecycle is in useInstallPrompt above.



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
      setPipelineStage(PIPELINE.speakerTestPlayed);
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
      const response = await fetch(`${liveApiUrl}/debug/tts-sample.wav?ts=${Date.now()}`, { cache: 'no-store' });
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



  async function testMicrophoneAndPlayback() {
    try {
      await ensureAudioUnlocked();
      setPipelineStage('Testing microphone');
      setStatus('Tap to record, then playback...');

      const stream = await requestAudioStream(settings.micDeviceId !== 'default' ? settings.micDeviceId : undefined);
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

  async function translateText(textOverride) {
    const textToSend = textOverride ?? text;
    if (processing || !textToSend.trim()) return;
    if (textOverride) setText(textOverride);
    setProcessing(true);
    setStatus(BRIDGE_STATUS.understandingText);
    resetBrainRuntimeUi();
    try {
      const response = await fetch(`${liveApiUrl}/translate/text`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify(buildTranslatePayload({
          text: textToSend,
          sourceLanguage, targetLanguage, sessionId,
          deviceId: INITIAL_DEVICE_ID, speakerName: INITIAL_SPEAKER_NAME, speakerMode,
          translationMode: settings.translationMode, translationProvider: settings.translationProvider,
          googleTtsApiKey: settings.googleTtsApiKey || undefined,
        })),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, bridgeErrors().text));
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
        setTextInputMode(false);
      } else {
        setStatus(brainUpdate?.message || 'Text bridged');
        setTextInputMode(false);
        toast('Bridge ready', 'success', 2200);
        reliabilityRef.current.recordSuccess('translation');
        if (data.translated_text && shouldUseBrowserTts(settings, languagePairRef.current.targetLanguage)) {
          speakTranslatedTextWithBrowser(data.translated_text, textToSend, `text-${Date.now()}`);
        }
      }
    } catch (error) {
      reliabilityRef.current.recordFailure('translation');
      setStatus(error.message || bridgeErrors().text);
      toast(error.message || bridgeErrors().text, 'error', 3200);
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
      setStatus(BRIDGE_STATUS.confirmBeforeVoice);
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
    const buffer = base64ToArrayBuffer(data.audio_base64);
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
      const response = await fetch(`${liveApiUrl}/tts`, {
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
        setStatus('Voice is slow. Bridge is ready.');
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
      setPipelineStage(PIPELINE.ready);
      setStatus(BRIDGE_STATUS.noSpeech);
      return;
    }

    setPartialTranscript(spokenText);
    setProcessing(true);
    setPipelineStage('Understanding');
    setStatus(BRIDGE_STATUS.understandingSpeech);
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
      const response = await fetch(`${liveApiUrl}/translate/text`, {
        method: 'POST',
        headers: authHeaders(activeAuthToken, { 'Content-Type': 'application/json' }),
        signal: controller.signal,
        body: JSON.stringify(buildTranslatePayload({
          text: spokenText,
          sourceLanguage, targetLanguage, sessionId,
          deviceId: INITIAL_DEVICE_ID, speakerName: INITIAL_SPEAKER_NAME, speakerMode,
          translationMode: settings.translationMode, translationProvider: settings.translationProvider,
          googleTtsApiKey: settings.googleTtsApiKey || undefined,
          synthesizeAudio: true, audioResponseFormat: 'url',
        })),
      });
      window.clearTimeout(timeoutId);
      const backendResponseMs = Math.round(performance.now() - requestStartedAt);
      updateLatency('backend_response', backendResponseMs);
      if (!response.ok) throw new Error(await responseErrorMessage(response, bridgeErrors().speech));
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
        setPipelineStage('Bridge ready');
        setStatus(brainUpdate?.message || 'Bridge ready');
      }
      const played = await playEmbeddedTranslationAudio(
        data,
        'Ready',
      );
      if (!played) {
        const targetLang = languagePairRef.current.targetLanguage;
        if (shouldUseBrowserTts(settings, targetLang)) {
          const browserPlayed = speakTranslatedTextWithBrowser(data.translated_text || '');
          if (!browserPlayed) resumeInterpreterAfterPlayback('Ready');
        } else {
          resumeInterpreterAfterPlayback('Ready');
          if (data.translated_text && prefersBackendNeuralVoice(settings, targetLang)) {
            setStatus('Neural voice unavailable — check Settings or restart the app');
          }
        }
      }
    } catch (error) {
      window.clearTimeout(timeoutId);
      const timedOut = error?.name === 'AbortError';
      if (timedOut) {
        setLatencyStats((current) => ({
          ...current,
          backend_response: `${FAST_SPEECH_TIMEOUT_MS}ms+`,
          end_to_end: `${FAST_SPEECH_TIMEOUT_MS}ms+`,
        }));
        setPipelineStage('Bridge timed out');
        setStatus(BRIDGE_STATUS.networkSlowReady);
        resumeInterpreterAfterPlayback(BRIDGE_STATUS.bridgeReadySpeak);
      } else {
        setPipelineStage(bridgeErrors().speech);
        setStatus(error.message || bridgeErrors().speech);
      }
    } finally {
      setProcessing(false);
    }
  }




  // diagnostics + loadDiagnostics come from useDiagnostics(liveApiUrl) above.

  // selfTest + runSelfTest are in useSelfTest above.



  async function shareConversationRoom() {
    const mechanism = await shareRoomUrl({ sessionId, copyToClipboard });
    setStatus(mechanism === 'share' ? 'Room link shared' : 'Room link copied');
    toast(mechanism === 'share' ? 'Room link shared' : 'Room link copied', 'success', 2400);
  }




  function resetStreamState({ preserveInterpreter = false } = {}) {
    if (streamReconnectTimerRef.current) {
      window.clearTimeout(streamReconnectTimerRef.current);
      streamReconnectTimerRef.current = null;
    }
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
    if (!preserveInterpreter) {
      setInterpreterMode(false);
      setInterpreterSocketOpen(false);
    }
    setLiveAssistActive(false);
    ttsPlayingRef.current = false;
    liveTtsPlaybackRef.current = false;
    pendingBrowserVoiceTextRef.current = null;
    browserTtsLastText = '';
    browserTtsLastFullText = '';
    browserTtsLastSourceText = '';
    browserTtsLastUtteranceId = null;
    if (liveVoiceFallbackTimerRef.current) {
      window.clearTimeout(liveVoiceFallbackTimerRef.current);
      liveVoiceFallbackTimerRef.current = null;
    }
    if (browserVoiceReleaseTimerRef.current) {
      window.clearTimeout(browserVoiceReleaseTimerRef.current);
      browserVoiceReleaseTimerRef.current = null;
    }
    resumeMicAfterVoicePlayback();
    streamFinalizePendingRef.current = false;
    streamRecordingStartedAtRef.current = 0;
    holdToTalkReleasePendingRef.current = false;
    drainAudioSendQueue();
    clearTtsQueue();
  }

  function activePacketMs() {
    return activePacketMsUtil({ lowBandwidthMode, streamPacketMs: STREAM_PACKET_MS, experimentalIosStreaming: EXPERIMENTAL_IOS_STREAMING });
  }

  function restoreLiveListeningAfterVoice() {
    if (!liveSpeechSessionRef.current) return;
    setPlaying(false);
    if (!resumeInterpreterListeningUI(BRIDGE_STATUS.listeningSpeak)) {
      setStreaming(true);
      setInstantListening(true);
      setPipelineStage(PIPELINE.listening);
      setStatus(BRIDGE_STATUS.listeningSpeak);
    }
  }

  function resumeInterpreterListeningUI(message = BRIDGE_STATUS.listeningSpeak) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    if (!shouldKeepContinuousStream(socket) && !(appStateRef.current.interpreterMode && appStateRef.current.speakerMode === 'auto')) {
      return false;
    }
    setStreaming(true);
    setInstantListening(true);
    setPlaying(false);
    setProcessing(false);
    setPipelineStage(PIPELINE.listening);
    setStatus(message);
    return true;
  }


  async function sendRecorderChunk(socket, event, recorder) {
    if (event.data.size <= 0) return;
    if (ttsPlayingRef.current && !liveTtsPlaybackRef.current) return;
    debugLog('AUDIO CHUNK:', event.data);
    if (audioSendQueueRef.current.length >= MAX_AUDIO_SEND_QUEUE && socket.readyState === WebSocket.OPEN) {
      audioSendQueueRef.current.shift();
    }
    const buffer = await event.data.arrayBuffer();
    const audioLevel = Number(micMeterRef.current?.smoothed || 0);
    streamChunkCounterRef.current += 1;
    const packet = {
      meta: {
        type: 'chunk_meta',
        sent_at_ms: Date.now(),
        captured_at_ms: performance.now(),
        bytes: buffer.byteLength,
        mime_type: event.data.type || recorder?.mimeType || preferredAudioMimeType(),
        audio_level: Number(audioLevel.toFixed(4)),
        voice_active: audioLevel >= CLIENT_VAD_THRESHOLD,
        heartbeat: streamChunkCounterRef.current % 5 === 0,
      },
      buffer,
    };
    if (!sendAudioPacket(socket, packet)) queueAudioPacket(packet);
  }


  function disableStreamReconnect() {
    if (streamReconnectTimerRef.current) {
      window.clearTimeout(streamReconnectTimerRef.current);
      streamReconnectTimerRef.current = null;
    }
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
          setStatus(BRIDGE_STATUS.keepSpeaking);
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
    if (liveSpeechSessionRef.current) return socketRef.current === socket;
    const options = streamReconnectRef.current.options || {};
    const current = appStateRef.current;
    return (
      socketRef.current === socket &&
      (options.interpreter === true || current.interpreterMode) &&
      (options.speakerMode === 'auto' || current.speakerMode === 'auto') &&
      options.holdToTalk !== true &&
      !holdToTalkActiveRef.current
    );
  }


  function stopContinuousStream(nextStatus = BRIDGE_STATUS.bridgePaused) {
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
    liveTtsPlaybackRef.current = false;
    setInterpreterMode(false);
    setInterpreterSocketOpen(false);
    setLiveSpeechSession(false);
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
    speechUtteranceSeqRef.current = 0;
    setLiveAssistActive(false);
    if (!socketRef.current) {
      setStreaming(false);
      setInstantListening(false);
      setProcessing(true);
      setPipelineStage('Processing');
      setStatus(BRIDGE_STATUS.processingSpeech);
    }
    return true;
  }

  function sendLiveSpeechText(socket, textValue, isFinal = false, utteranceId = speechUtteranceSeqRef.current) {
    const normalized = String(textValue || '').replace(/\s+/g, ' ').trim();
    if (!normalized || !socket || socket.readyState !== WebSocket.OPEN) return false;
    const now = performance.now();
    const sendKey = `${utteranceId}:${normalized}`;
    if (!isFinal && sendKey === speechLastSentTextRef.current) return false;
    if (!isFinal && now - speechLastSentAtRef.current < LIVE_SPEECH_TEXT_THROTTLE_MS) return false;
    speechLastSentTextRef.current = sendKey;
    speechLastSentAtRef.current = now;
    const { sourceLanguage: activeSourceLanguage, targetLanguage: activeTargetLanguage } = languagePairRef.current;
    try {
      socket.send(JSON.stringify({
        type: 'live_text',
        text: normalized,
        final: Boolean(isFinal),
        utterance_id: utteranceId,
        session_id: sessionId,
        device_id: INITIAL_DEVICE_ID,
        speaker_name: INITIAL_SPEAKER_NAME,
        source_language: activeSourceLanguage,
        target_language: activeTargetLanguage,
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
    speechUtteranceSeqRef.current = 0;
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
    setInstantListening(true);
    setProcessing(false);
    setPipelineStage(PIPELINE.listening);
    setStatus(BRIDGE_STATUS.listeningLive);
    streamStartedAtRef.current = performance.now();
    requestWakeLock();

    recognition.lang = speechRecognitionLanguage(languagePairRef.current.sourceLanguage);
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
      const currentUtteranceText = (finalText.trim() || interim.trim());
      if (visibleText) {
        setPartialTranscript(visibleText);
        const utteranceId = speechUtteranceSeqRef.current;
        if (currentUtteranceText) {
          sendLiveSpeechText(activeSocket, currentUtteranceText, Boolean(finalText.trim()), utteranceId);
          if (finalText.trim()) {
            speechUtteranceSeqRef.current = utteranceId + 1;
            speechLastSentTextRef.current = '';
            speechLastSentAtRef.current = 0;
          }
        }
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
          setStatus(BRIDGE_STATUS.audioFallbackListening);
          setPipelineStage('Audio fallback');
        }
        return;
      }
      if (socketRef.current) {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        speechAssistSocketRef.current = null;
        setLiveAssistActive(false);
        speechInterimTextRef.current = '';
        speechLastSentTextRef.current = '';
        speechLastSentAtRef.current = 0;
        setStatus(BRIDGE_STATUS.audioFallback);
        setPipelineStage('Audio fallback');
        return;
      }
      if (!speechFinalTextRef.current.trim() && !socketRef.current) {
        speechFastPathActiveRef.current = false;
        speechRecognitionRef.current = null;
        setLiveAssistActive(false);
        releaseWakeLock();
        setStreaming(false);
        setStatus(BRIDGE_STATUS.usingAudioFallback);
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
        if (!navigator.onLine || document.visibilityState !== 'visible') return;
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
      setStatus(BRIDGE_STATUS.usingAudioFallback);
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
      setPipelineStage(PIPELINE.ready);
      return;
    }

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      resumeMicAfterVoicePlayback();
      setStreaming(true);
      setInstantListening(true);
      setPipelineStage(PIPELINE.listening);
      setStatus(BRIDGE_STATUS.listeningSpeak);
      return;
    }

    setStatus(BRIDGE_STATUS.bridgeReadySpeak);
    setPipelineStage('Ready to listen');
    ensureAuthToken()
      .then(() => toggleStreaming({ interpreter: true, speakerMode: 'auto' }))
      .catch(() => {});
  }

  function handleStopListening() {
    if (!socketRef.current && !liveSpeechSessionRef.current) return;
    haptic(8);
    stopContinuousStream();
  }

  async function handleMicClick() {
    debugLog('MIC BUTTON CLICKED');
    if (ignoreNextMicClickRef.current) {
      ignoreNextMicClickRef.current = false;
      return;
    }
    synchronousAudioUnlock();
    if (autoConversation.active) {
      haptic(8);
      if (socketRef.current) stopContinuousStream();
      stopBrowserSpeechFastPath();
      autoConversation.stop();
      autoTurnSyncRef.current = 0;
      setInstantListening(false);
      setStreaming(false);
      setInterpreterMode(false);
      setProcessing(false);
      setPlaying(false);
      setPipelineStage('Stopped');
      setStatus(BRIDGE_STATUS.bridgePaused);
      setLiveSpeechSession(false);
      return;
    }
    if (socketRef.current && liveSpeechSessionRef.current) {
      haptic(6);
      scheduleStatusUpdate('Listening', 'Still listening — just speak');
      restoreLiveListeningAfterVoice();
      return;
    }
    if (socketRef.current) {
      haptic(8);
      setInstantListening(false);
      stopContinuousStream();
      return;
    }
    if (liveSpeechSessionRef.current) {
      if (document.visibilityState !== 'visible' || !navigator.onLine) {
        setStatus('Come back to this tab to use the microphone');
        return;
      }
      haptic(14);
      setInstantListening(true);
      setInterpreterMode(true);
      setSpeakerMode('auto');
      try {
        await ensureAuthToken();
        await requestMicPermission();
        toggleStreaming({ interpreter: true, speakerMode: 'auto' });
      } catch (error) {
        setStatus(error?.message || 'Could not resume live speech recognition');
        setLiveSpeechSession(false);
      }
      return;
    }
    stopBrowserSpeechFastPath();
    if (connectionStatus !== 'online' && connectionStatus !== 'warming') {
      setStatus(BRIDGE_STATUS.linkFirst);
      setPipelineStage('Offline');
      return;
    }
    if (document.visibilityState !== 'visible' || !navigator.onLine) {
      setStatus('Come back to this tab to use the microphone');
      setPipelineStage('Offline');
      return;
    }
    haptic(14);
    setLiveSpeechSession(true);
    setInstantListening(true);
    setInterpreterMode(true);
    setSpeakerMode('auto');
    try {
      await ensureAuthToken();
      await requestMicPermission();
      requestWakeLock();
      if (autoConversation.active) autoConversation.stop();
      toggleStreaming({ interpreter: true, speakerMode: 'auto' });
    } catch (error) {
      setStatus(error?.message || 'Could not start live speech recognition');
      setPipelineStage('Mic unavailable');
      setInstantListening(false);
      setInterpreterMode(false);
      setLiveSpeechSession(false);
    }
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
    }, shouldPreferHoldToTalk() ? 0 : HOLD_TO_TALK_DELAY_MS);
  }

  function handleMicPointerUp() {
    if (holdToTalkTimerRef.current) {
      window.clearTimeout(holdToTalkTimerRef.current);
      holdToTalkTimerRef.current = null;
    }
    if (!holdToTalkActiveRef.current) {
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
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Install Anai</title></head><body style="font-family:system-ui;margin:24px;line-height:1.5;background:#03050a;color:#f8fafc"><h1>Install Anai</h1><p>Open <a style="color:#67e8f9" href="${appUrl}">${appUrl}</a>, then use your browser's Add to Home Screen or Install app option.</p><p><a style="color:#67e8f9" href="${appUrl}">Open app now</a></p></body></html>`;
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
    loadSpeakerProfiles(session.speakers);
    if (session.history?.length) {
      setConversationTurns(session.history.map((turn, index) => normalizeConversationTurn(turn, index)).slice(-CONVERSATION_DISPLAY_LIMIT));
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
      showUserError(mapTechnicalError(error));
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
    setStatus(BRIDGE_STATUS.listeningEllipsis);
    startSilenceDetector({ shouldStop: () => recordingStoppedRef.current || mediaRecorderRef.current?.state !== 'recording', onSilence: stopRecording });
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
    setStatus(BRIDGE_STATUS.understandingEllipsis);
  }

  async function uploadRecording() {
    const recordingMimeType = chunksRef.current.find((chunk) => chunk?.type)?.type
      || mediaRecorderRef.current?.mimeType
      || preferredAudioMimeType()
      || 'audio/webm';
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
      debugLog('UPLOAD: posting audio to', `${liveApiUrl}/translate/audio`, 'size', blob.size);
      const response = await fetch(`${liveApiUrl}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
      debugLog('UPLOAD: response status', response.status);
      if (!response.ok) {
        const errText = await responseErrorMessage(response, bridgeErrors().audio);
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
      setStatus(brainUpdate?.message || (data.translated_text ? (data.audio_base64 ? 'Playing...' : 'Audio bridged') : 'No clear speech recognized'));
      if (shouldSkipBrainTts(data)) {
        setPipelineStage('Voice skipped');
        return;
      }
      if (data.audio_base64) {
        await ensureAudioUnlocked().catch((e) => console.warn('uploadRecording audio unlock failed:', e));
        const buffer = base64ToArrayBuffer(data.audio_base64);
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
            setStatus('Audio bridged');
          }});
        }, playDelay);
      } else if (data.translated_text) {
        const targetLang = data.target_language || languagePairRef.current.targetLanguage;
        if (shouldUseBrowserTts(settings, targetLang)) {
          const browserPlayed = speakTranslatedTextWithBrowser(data.translated_text, data.source_text || '', `upload-${Date.now()}`);
          if (!browserPlayed) setStatus('Audio bridged');
        } else {
          setStatus('Bridge ready (neural voice unavailable)');
        }
      }
      reliabilityRef.current.recordSuccess('stt');
      reliabilityRef.current.recordSuccess('audio');
    } catch (error) {
      reliabilityRef.current.recordFailure('stt');
      reliabilityRef.current.recordFailure('audio');
      console.error('UPLOAD: catch error', error);
      setStatus(error.message || bridgeErrors().audio);
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
      stream = await requestAudioStream(settings.micDeviceId !== 'default' ? settings.micDeviceId : undefined);
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
    const wsEndpoint = `${liveWsUrl}/ws/audio`;
    const socketUrl = withAuthToken(wsEndpoint, activeAuthToken);
    setWsDebug({ url: wsEndpoint, close: 'connecting', error: '-' });
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
      const intentionalStop = !liveSpeechSessionRef.current || streamFinalizePendingRef.current;
      if (intentionalStop) {
        stopTracks(stream);
      }
    };
    socket.onopen = () => {
      if (streamSafetyTimeoutRef.current) window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = window.setTimeout(() => {
        if (!navigator.onLine || document.visibilityState !== 'visible') return;
        const preserveInterpreter = streamReconnectRef.current.enabled && Boolean(streamReconnectRef.current.options?.interpreter);
        resetStreamState({ preserveInterpreter });
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) socket.close();
        if (socketRef.current === socket) socketRef.current = null;
        setStatus(BRIDGE_STATUS.readyTryAgain);
        setPipelineStage('Safety reset');
      }, 15000);
      streamFinalizePendingRef.current = false;
      setConnectionStatus('online');
      setInterpreterSocketOpen(true);
      setLiveSpeechSession(true);
      try { sessionStorage.setItem('anai_auto_listen_enabled', '1'); } catch {}
      setStreaming(true);
      setInstantListening(Boolean(cleanOptions.interpreter || selectedSpeakerMode === 'auto'));
      setResult(null);
      setPartialTranscript('');
      setLiveTranslation('');
      browserTtsLastText = '';
      browserTtsLastFullText = '';
      browserTtsLastSourceText = '';
      browserTtsLastUtteranceId = null;
      if (liveVoiceFallbackTimerRef.current) {
        window.clearTimeout(liveVoiceFallbackTimerRef.current);
        liveVoiceFallbackTimerRef.current = null;
      }
      resetBrainRuntimeUi();
      setPipelineStage(PIPELINE.listening);
      setStatus(selectedSpeakerMode === 'auto' ? 'Interpreter mode listening...' : 'Streaming audio...');
      const { sourceLanguage: activeSourceLanguage, targetLanguage: activeTargetLanguage } = languagePairRef.current;
      socket.send(JSON.stringify({
        type: 'start',
        session_id: sessionId,
        device_id: INITIAL_DEVICE_ID,
        speaker_name: INITIAL_SPEAKER_NAME,
        source_language: activeSourceLanguage,
        target_language: activeTargetLanguage,
        speaker_mode: selectedSpeakerMode,
        speaker: selectedSpeakerMode === 'auto' ? 'auto' : 'A',
        mime_type: recorder.mimeType || preferredAudioMimeType(),
        barrier_mode: resolveStreamBarrierMode(),
        environment: resolveStreamEnvironment(),
      }));
      if (!cleanOptions.holdToTalk && !speechFastPathActiveRef.current) {
        startBrowserSpeechFastPath(socket);
      }
      if (reconnecting) {
        drainAudioSendQueue();
      }
      flushAudioSendQueue(socket);
      startStreamHeartbeat(socket);
      reliabilityRef.current.recordSuccess('websocket');
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
        reliabilityRef.current.recordSuccess('websocket');
        return;
      }
      if (data.type === 'listening') {
        markStreamPong();
      }
      if (data.type === 'ready') {
        reliabilityRef.current.recordSuccess('websocket');
      }
      if (data.type === 'session_restored' || data.type === 'session_sync') {
        applySharedSession(data.session?.shared || data.session);
        const turns = data.session?.turns
          || data.session?.history
          || data.session?.shared?.history;
        if (Array.isArray(turns) && turns.length) {
          const lastTurn = turns[turns.length - 1];
          if (lastTurn?.source_text || lastTurn?.translated_text) {
            if (lastTurn.source_text) setPartialTranscript(lastTurn.source_text);
            if (lastTurn.translated_text) setLiveTranslation(lastTurn.translated_text);
          }
        }
      }
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
        if (data.stage === 'partial_low_confidence' || data.stage === 'final_low_confidence') {
          setPipelineStage(data.stage === 'partial_low_confidence' ? 'Listening for clearer speech' : 'Moderate confidence');
          setConfidenceWarningMessage(
            data.message || (data.stage === 'partial_low_confidence'
              ? 'Listening for clearer speech…'
              : 'Moderate confidence — double-check important details.'),
          );
          setConfidenceWarningVisible(true);
          setStatus(data.message || 'Keep speaking…');
        } else if (
          data.stage === 'cip_clarification'
          || data.stage === 'translation_safety'
          || asCertBool(data.needs_confirmation)
          || shouldBlockTtsForCert(humanCertStep(data))
        ) {
          setPipelineStage('Clarification needed');
          setStatus(data.message || 'Clarification requested');
          setClarifyMessage(data.message || 'Clarification requested');
          setClarifyVisible(true);
        } else {
          setConfidenceWarningMessage(data.message || 'Check meaning');
          setConfidenceWarningVisible(true);
        }
      }
      if (data.type === 'stage') {
        setPipelineStage(data.message);
        if (data.stage === 'tts_skipped') {
          const skipReason = String(data.message || '');
          const benignSkip = /already streamed|browser voice handles|live voice/i.test(skipReason);
          if (benignSkip && brainHintsRef.current) {
            brainHintsRef.current = { ...brainHintsRef.current, skip_tts: false, tts_mode: undefined };
          }
          if (benignSkip && shouldKeepContinuousStream(socket)) {
            resumeMicAfterVoicePlayback();
          }
        }
        if (data.stage === 'partial_degraded' || data.stage === 'turn_held' || data.stage === 'weak_audio') {
          setStatus(data.message || data.stage);
        } else {
          setStatus(data.message);
        }
      }
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        const brainUpdate = applyBrainPayload(data, 'turn');
        const playback = data.playback_owner_label || data.playback_owner;
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${playback ? ` - playback: ${playback}` : ''}`);
        if (data.behavior === 'hold' || data.behavior === 'playback' || data.allowed === false) {
          pauseMicForVoicePlayback();
          setStatus(data.reason || 'Waiting for other speaker');
        } else if (data.behavior === 'interruption' || data.behavior === 'turn_shift' || data.behavior === 'overlap') {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
          if (liveVoiceFallbackTimerRef.current) {
            window.clearTimeout(liveVoiceFallbackTimerRef.current);
            liveVoiceFallbackTimerRef.current = null;
          }
          try { window.speechSynthesis?.cancel?.(); } catch {}
          resumeMicAfterVoicePlayback();
          if (data.behavior === 'turn_shift') {
            setStatus(BRIDGE_STATUS.speakerSwitched);
          } else if (data.behavior === 'interruption') {
            setStatus(BRIDGE_STATUS.speakerInterrupted);
          } else if (data.behavior === 'overlap') {
            setStatus(BRIDGE_STATUS.bothSpeakers);
          }
        } else if (shouldKeepContinuousStream(socket)) {
          resumeMicAfterVoicePlayback();
        }
        if (brainUpdate?.speakerShift && brainUpdate.message) {
          setPipelineStage(brainUpdate.message);
          setStatus(brainUpdate.message);
        }
      }
      if (data.type === 'partial_transcription') {
        rememberSpeaker(data);
        const text = String(data.text || '').trim();
        if (text && !/^(waiting for speech|preparing audio)/i.test(text)) {
          schedulePartialTranscript(text);
        }
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        scheduleLiveTranslation(data.text);
        setPipelineStage(pipelineStages().liveBridge);
        applyConfidenceSignals(data);
        const partialThreshold = typeof data.confidence_threshold === 'number' ? data.confidence_threshold : 0.72;
        const partialCertStep = humanCertStep(data);
        if (shouldBlockTtsForCert(partialCertStep)) {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
          try { window.speechSynthesis?.cancel?.(); } catch {}
          setClarifyMessage(data.certification_message || data.confidence_message || clarifyMessages().honorNative);
          setClarifyVisible(true);
        } else if (data.low_confidence || (typeof data.confidence === 'number' && data.confidence < partialThreshold)) {
          setConfidenceWarningMessage(data.confidence_message || 'Listening for clearer speech…');
          setConfidenceWarningVisible(true);
        } else if (partialCertStep === 'advisory') {
          setConfidenceWarningMessage(certificationBanner(data, partialCertStep));
          setConfidenceWarningVisible(true);
        }
      }
      if (data.type === 'final_transcription') {
        rememberSpeaker(data);
        setPartialTranscript(data.text);
        setPipelineStage('Transcription ready');
      }
      if (data.type === 'live_translation') {
        rememberSpeaker(data);
        setLiveTranslation(data.text);
        setPipelineStage('Bridge ready');
        const continuousVoiceEnabled = !lowBandwidthMode;
        const activeTargetLanguage = data.target_language || data.targetLanguage || languagePairRef.current.targetLanguage;
        const useBackendNeural = prefersBackendNeuralVoice(settings, activeTargetLanguage);
        const useImmediateBrowserTts = shouldUseBrowserTts(settings, activeTargetLanguage);
        const liveThreshold = typeof data.confidence_threshold === 'number' ? data.confidence_threshold : 0.72;
        const certBlocksVoice = shouldBlockTtsForCert(humanCertStep(data));
        if (continuousVoiceEnabled && data.text && !certBlocksVoice && !shouldSkipBrainTts(data)) {
          const speakWithBrowserFallback = () => {
            speakTranslatedTextWithBrowser(
              data.text,
              data.source_text || data.sourceText || '',
              data.utterance_id ?? data.utteranceId ?? null,
              activeTargetLanguage,
            );
          };
          if (liveVoiceFallbackTimerRef.current) {
            window.clearTimeout(liveVoiceFallbackTimerRef.current);
            liveVoiceFallbackTimerRef.current = null;
          }
          if (useImmediateBrowserTts) {
            speakWithBrowserFallback();
          } else if (useBackendNeural) {
            setPipelineStage('Preparing neural voice...');
            // Wait for backend Edge TTS — never swap to robotic browser voice mid-flight.
          } else if (shouldUseBrowserTts(settings, activeTargetLanguage)) {
            const scheduledAt = performance.now();
            liveVoiceFallbackTimerRef.current = window.setTimeout(() => {
              liveVoiceFallbackTimerRef.current = null;
              if (document.visibilityState !== 'visible' || !navigator.onLine) return;
              if (backendVoiceChunkSeenAtRef.current > scheduledAt) return;
              speakWithBrowserFallback();
            }, BACKEND_TTS_WAIT_MS);
          } else {
            setPipelineStage('Waiting for neural voice...');
          }
        }
      }
      if (data.type === 'tts_start') {
        if (data.partial) {
          setPlaying(true);
          setPipelineStage('Partial voice...');
          return;
        }
        if (shouldSkipBrainTts(data)) {
          ttsQueueRef.current = [];
          setTtsQueueLength(0);
          setTtsChunksBuffer([]);
          setPlaying(false);
          setTtsPlaying(false);
          setPipelineStage('Voice skipped');
          setStatus(BRIDGE_STATUS.confirmBeforeVoice);
          return;
        }
        audioSendQueueRef.current = [];
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
        if (!data.partial && isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING && !shouldKeepContinuousStream(socket)) {
          resumeAfterTtsRef.current = true;
          finalizeCurrentStream('Playing voice...', { delay: false });
        } else if (shouldKeepContinuousStream(socket)) {
          pauseMicForVoicePlayback();
        }
      }
      if (data.type === 'tts_audio_chunk') {
        backendVoiceChunkSeenAtRef.current = performance.now();
        if (liveVoiceFallbackTimerRef.current) {
          window.clearTimeout(liveVoiceFallbackTimerRef.current);
          liveVoiceFallbackTimerRef.current = null;
        }
        if (data.partial) {
          ensureAudioUnlocked().catch((e) => console.warn('partial TTS unlock failed:', e));
          enqueueTtsChunk(data.audio_base64, data.mime_type, {
            live: true,
            pauseMic: false,
            storeReplay: false,
            text: data.text || data.live_translation_text || data.liveTranslationText,
            sourceText: data.source_text || data.sourceText,
            targetLanguage: data.target_language || data.targetLanguage,
          });
          return;
        }
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
        enqueueTtsChunk(data.audio_base64, data.mime_type, {
          text: data.text || data.live_translation_text || data.liveTranslationText,
          sourceText: data.source_text || data.sourceText,
          targetLanguage: data.target_language || data.targetLanguage,
        });
      }
      if (data.type === 'tts_end') {
        if (data.partial) {
          // Partial TTS finished -- keep playing state until final TTS arrives
          return;
        }
        if (shouldSkipBrainTts(data)) {
          ttsQueueRef.current = [];
          setTtsQueueLength(0);
          setTtsChunksBuffer([]);
          setPlaying(false);
          setTtsPlaying(false);
          setPipelineStage('Voice skipped');
          setStatus(BRIDGE_STATUS.confirmBeforeVoice);
          return;
        }
        setPipelineStage('Voice stream complete');
        // If the queue is already playing or has items, let it finish naturally.
        // Only replay from ttsChunksBuffer if nothing is currently playing and
        // the queue is empty (i.e. playback never started or already finished).
        if (ttsPlayingRef.current || ttsQueueRef.current.length > 0) {
          debugLog('TTS queue already playing, letting it finish naturally');
          setTtsChunksBuffer([]);
        } else {
          setTtsChunksBuffer((chunks) => {
            if (chunks.length === 0) {
              debugLog('No TTS chunks to play');
              // Nothing played — update UI to reflect completion
              setPlaying(false);
              setTtsPlaying(false);
              if (!resumeInterpreterListeningUI('Listening for the next speaker...')) {
                setPipelineStage('Voice played');
                setStatus(BRIDGE_STATUS.voicePlayed);
              }
              return [];
            }
            debugLog(`Playing ${chunks.length} TTS chunks sequentially (queue was idle)`);
            pauseMicForVoicePlayback();
            let index = 0;
            const playNextChunk = () => {
              if (index >= chunks.length) {
                debugLog('All chunks played');
                setPlaying(false);
                setTtsPlaying(false);
                resumeMicAfterVoicePlayback();
                if (!resumeInterpreterListeningUI('Listening for the next speaker...')) {
                  setPipelineStage('Voice played');
                  setStatus(BRIDGE_STATUS.voicePlayed);
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
        }
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
          setPipelineStage(PIPELINE.listening);
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
        setLiveSpeechSession(false);
        setPipelineStage('Hold and speak longer');
        setStatus(message || 'Stream failed');
        streamFinalizePendingRef.current = false;
        holdToTalkReleasePendingRef.current = false;
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        socket.close();
        socketRef.current = null;
      }
      if (data.type === 'vad' && data.speech_detected) setStatus(BRIDGE_STATUS.speechDetected);
      if (data.type === 'final') {
        const keepContinuous = liveSpeechSessionRef.current
          || shouldKeepContinuousStream(socket)
          || (appStateRef.current.interpreterMode && appStateRef.current.speakerMode === 'auto');
        if (!keepContinuous) {
          disableStreamReconnect();
          clearStreamHeartbeat();
          audioSendQueueRef.current = [];
        }
        const brainUpdate = applyBrainPayload(data, 'final');
        rememberSpeaker(data);
        applyConfidenceSignals(data);
        if (data.source_text) lastGuardedSourceRef.current = data.source_text;
        setResult(data);
        if (data.translated_text) setLiveTranslation(data.translated_text);
        if (shouldSkipBrainTts(data)) {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
          if (liveVoiceFallbackTimerRef.current) {
            window.clearTimeout(liveVoiceFallbackTimerRef.current);
            liveVoiceFallbackTimerRef.current = null;
          }
          try { window.speechSynthesis?.cancel?.(); } catch {}
        } else if (brainHintsRef.current?.skip_tts || brainHintsRef.current?.tts_mode === 'skip') {
          brainHintsRef.current = { ...brainHintsRef.current, skip_tts: false, tts_mode: undefined };
        }
        if (data.low_confidence || data.needs_native_certification || humanCertStep(data) !== 'none') {
          applyConfidenceSignals(data);
          if (data.confidence_message || data.certification_message) {
            setConfidenceWarningMessage(
              data.certification_message || data.confidence_message || clarifyMessages().checkMeaning,
            );
            setConfidenceWarningVisible(true);
          }
        }
        if (shouldBlockTtsForCert(humanCertStep(data)) || data.stage === 'translation_safety') {
          setClarifyMessage(
            data.clarify_message || data.certification_message || data.confidence_message || clarifyMessages().checkMeaning,
          );
          setClarifyVisible(true);
        } else if (asCertBool(data.needs_confirmation) || data.stage === 'cip_clarification') {
          setClarifyMessage(data.clarify_message || data.confidence_message || clarifyMessages().checkMeaning);
          setClarifyVisible(true);
        }
        if (data.session) {
          applySharedSession(data.session);
        } else {
          appendConversationTurn(data);
        }
        setProcessing(false);
        streamFinalizePendingRef.current = false;
        if (keepContinuous) {
          setStreaming(true);
          setInstantListening(true);
          if (!ttsPlayingRef.current && !appStateRef.current.playing) {
            scheduleStatusUpdate(
              asCertBool(data.needs_confirmation) ? 'Clarification needed' : 'Listening',
              brainUpdate?.message || (asCertBool(data.needs_confirmation) ? 'Clarification needed. Keep speaking...' : 'Listening — speak anytime'),
            );
          }
          const activeRecorder = streamRecorderRef.current;
          if (activeRecorder?.state === 'paused' && typeof activeRecorder.resume === 'function') {
            try { activeRecorder.resume(); } catch {}
          } else if (activeRecorder?.state === 'inactive' && activeRecorder.stream) {
            try {
              const replacement = createAudioRecorder(activeRecorder.stream);
              replacement.ondataavailable = (event) => {
                sendRecorderChunk(socket, event, replacement).catch((err) => {
                  console.error('sendRecorderChunk error:', err);
                });
              };
              replacement.onstop = recorder.onstop;
              replacement.start(activePacketMs());
              streamRecorderRef.current = replacement;
              startMicMeter(activeRecorder.stream);
            } catch (restartErr) {
              console.warn('Live recorder restart failed:', restartErr);
            }
          }
          return;
        }
        setPipelineStage('Complete');
        setStatus(brainUpdate?.message || 'Stream bridged');
        setLiveSpeechSession(false);
        if (streamRecorderRef.current?.state === 'recording') {
          streamRecorderRef.current.stop();
        }
        setInterpreterSocketOpen(false);
        socket.close();
        socketRef.current = null;
      }
    };
    socket.onerror = (event) => {
      reliabilityRef.current.recordFailure('websocket', event);
      setWsDebug((current) => ({ ...current, error: 'socket error' }));
      setStatus(BRIDGE_STATUS.streamError);
      setPipelineStage('Connection error');
      releaseWakeLock();
      stopBrowserSpeechFastPath();
      const preserveInterpreter = streamReconnectRef.current.enabled && Boolean(streamReconnectRef.current.options?.interpreter);
      resetStreamState({ preserveInterpreter });
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
      const preserveInterpreter = streamReconnectRef.current.enabled && Boolean(streamReconnectRef.current.options?.interpreter);
      resetStreamState({ preserveInterpreter });
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
      if (!streamReconnectRef.current.enabled) {
        setInterpreterSocketOpen(false);
        return;
      }

      if (streamReconnectRef.current.attempts >= STREAM_RECONNECT_MAX_ATTEMPTS) {
        reliabilityRef.current.recordFailure('websocket');
        disableStreamReconnect();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        setLiveSpeechSession(false);
        setStatus(BRIDGE_STATUS.bridgeDroppedRestart);
        setPipelineStage('Connection lost');
        setConnectionStatus('offline');
        return;
      }

      streamReconnectRef.current.attempts += 1;
      const attempt = streamReconnectRef.current.attempts;
      const fastReconnect = liveSpeechSessionRef.current;
      const exponentialDelay = fastReconnect
        ? 120
        : Math.min(STREAM_RECONNECT_MS * Math.pow(2, attempt - 1), STREAM_RECONNECT_MAX_DELAY_MS);
      scheduleStatusUpdate(
        fastReconnect ? 'Listening' : `Reconnecting ${attempt}/${STREAM_RECONNECT_MAX_ATTEMPTS}`,
        fastReconnect ? 'Reconnecting — keep speaking...' : 'Reconnecting stream...',
      );
      if (streamReconnectTimerRef.current) window.clearTimeout(streamReconnectTimerRef.current);
      streamReconnectTimerRef.current = window.setTimeout(() => {
        streamReconnectTimerRef.current = null;
        if (!navigator.onLine || document.visibilityState !== 'visible') return;
        if (!streamReconnectRef.current.enabled || socketRef.current) return;
        toggleStreaming({
          ...(streamReconnectRef.current.options || {}),
          interpreter: true,
          speakerMode: 'auto',
          reconnect: true,
        });
      }, exponentialDelay);
    };
  }

  function enqueueTtsChunk(audioBase64, mimeType, options = {}) {
    if (shouldSkipBrainTts()) {
      setPipelineStage('Voice skipped');
      return;
    }
    if (lowBandwidthMode) {
      setPipelineStage(pipelineStages().lowBandwidth);
      return;
    }
    ensureAudioContext().catch((e) => console.warn('enqueueTtsChunk AudioContext failed:', e));
    const buffer = base64ToArrayBuffer(audioBase64);
    const bufferCopy = buffer.slice(0);
    const url = URL.createObjectURL(new Blob([bufferCopy], { type: mimeType || 'audio/wav' }));
    const item = {
      url,
      buffer: bufferCopy,
      mimeType: mimeType || 'audio/wav',
      objectUrl: true,
      liveVoice: Boolean(options.live),
      text: String(options.text || '').trim(),
      sourceText: String(options.sourceText || '').trim(),
      targetLanguage: options.targetLanguage || languagePairRef.current.targetLanguage,
      browserFallbackTried: false,
      neuralBackend: options.neuralBackend !== false,
    };
    if (options.live && Number.isFinite(LIVE_TTS_MAX_QUEUE)) {
      while (ttsQueueRef.current.length >= Math.max(1, LIVE_TTS_MAX_QUEUE)) {
        const dropped = ttsQueueRef.current.shift();
        revokeTtsItemUrl(dropped);
      }
    }
    if (options.pauseMic !== false) pauseMicForVoicePlayback();
    ttsQueueRef.current.push(item);
    setTtsQueueLength(ttsQueueRef.current.length);
    if (options.storeReplay !== false) {
      setTtsChunksBuffer((prev) => [...prev, bufferCopy]);
    }
    // Trigger playback immediately if not already playing
    playNextTtsChunk();
  }

  function playTtsItem(item, { revokeOnFinish = true, manual = false, onEnd } = {}) {
    if (!item) return;
    if (currentTtsFinishRef.current) {
      const prevFinish = currentTtsFinishRef.current;
      currentTtsFinishRef.current = null;
      prevFinish();
    }
    debugLog('playTtsItem: starting playback, manual=', manual, 'mimeType=', item.mimeType, 'buffer size=', item.buffer?.byteLength || 0);
    const liveVoice = Boolean(item.liveVoice);
    liveTtsPlaybackRef.current = liveVoice;
    ttsPlayingRef.current = true;
    setTtsPlaying(true);
    setPlaying(true);
    setPipelineStage(manual ? pipelineStages().playVoiceManual : liveVoice ? pipelineStages().bridgingLive : 'Playing voice');
    setStatus(manual ? `${pipelineStages().playVoiceManual}…` : liveVoice ? `${pipelineStages().bridgingStatus}` : 'Playing voice...');
    haptic(6);
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      currentTtsFinishRef.current = null;
      if (revokeOnFinish) revokeTtsItemUrl(item);
      if (liveVoice) liveTtsPlaybackRef.current = false;
      ttsPlayingRef.current = false;
      setTtsPlaying(false);
      if (onEnd) onEnd();
      if (manual) {
        setPlaying(false);
        setPipelineStage('Voice played');
        if (!onEnd) setStatus(BRIDGE_STATUS.voicePlayed);
        resumeMicAfterVoicePlayback();
        return;
      }
      if (onEnd) return;
      if (ttsQueueRef.current.length > 0) {
        playNextTtsChunk();
        return;
      }
      resumeMicAfterVoicePlayback();
      playNextTtsChunk();
      restoreLiveListeningAfterVoice();
    };
    const finishBrowserFallback = () => {
      if (finished) return;
      finished = true;
      currentTtsFinishRef.current = null;
      if (revokeOnFinish) revokeTtsItemUrl(item);
      liveTtsPlaybackRef.current = false;
      ttsPlayingRef.current = false;
      setTtsPlaying(false);
      if (onEnd) onEnd();
      if (manual) {
        setPlaying(false);
        setPipelineStage('Voice played');
        if (!onEnd) setStatus(BRIDGE_STATUS.voicePlayed);
        resumeMicAfterVoicePlayback();
        return;
      }
      if (onEnd) return;
      if (ttsQueueRef.current.length > 0) {
        playNextTtsChunk();
        return;
      }
      resumeMicAfterVoicePlayback();
      restoreLiveListeningAfterVoice();
    };
    const tryBrowserSpeechFallback = (error) => {
      const fallbackText = String(item.text || '').trim();
      if (!fallbackText || item.browserFallbackTried) return false;
      if (!shouldUseBrowserTts(settings, item.targetLanguage || languagePairRef.current.targetLanguage)) {
        return false;
      }
      if (!window.speechSynthesis) return false;
      item.browserFallbackTried = true;
      const fallbackLanguage = item.targetLanguage || languagePairRef.current.targetLanguage;
      console.warn('TTS audio playback failed; trying browser speech fallback:', error);
      setLastAudioError({ type: 'tts_browser_fallback', name: error?.name, message: error?.message });
      const started = browserTtsSpeak(fallbackText, fallbackLanguage, settings.ttsSpeed ?? 1.0, {
        onStart: () => {
          currentTtsFinishRef.current = finishBrowserFallback;
          liveTtsPlaybackRef.current = liveVoice;
          ttsPlayingRef.current = true;
          setTtsPlaying(true);
          setPlaying(true);
          if (!liveVoice) pauseMicForVoicePlayback();
          setPipelineStage(pipelineStages().bridgingLive);
          setStatus(`${pipelineStages().bridgingStatus}`);
        },
        onEnd: finishBrowserFallback,
      });
      if (!started) {
        item.browserFallbackTried = false;
        return false;
      }
      return true;
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
        if (item.neuralBackend !== false) {
          audio.playbackRate = neuralPlaybackRate(settings.ttsSpeed);
        }
        audio.onended = finish;
        audio.onerror = (error) => {
          console.error('HTML audio error:', error);
          console.error('Audio error code:', audio?.error?.code, 'message:', audio?.error?.message);
          if (tryBrowserSpeechFallback(error)) return;
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
            reliabilityRef.current.recordSuccess('tts');
          }).catch((error) => {
            reliabilityRef.current.recordFailure('tts');
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
              if (tryBrowserSpeechFallback(err2)) return;
              finish();
              console.error('Fresh audio element also failed:', err2);
              ttsPlayingRef.current = false;
              setPlaying(false);
              setAudioReplayAvailable(true);
              setPipelineStage(`Audio playback blocked: ${error?.name || 'tap play voice'}`);
              setStatus(clarifyMessages().tapPlayVoice);
              setLastAudioError({ type: 'tts_playback_blocked', name: error?.name, message: error?.message });
            };
            fresh.play().then(() => {
              debugLog('Fresh audio element playing successfully');
              setLastAudioError(null);
            }).catch((err2) => {
              console.error('Fresh audio element play failed:', err2);
              try { document.body.removeChild(fresh); } catch (e) {}
              if (tryBrowserSpeechFallback(err2)) return;
              finish();
              ttsPlayingRef.current = false;
              setPlaying(false);
              setAudioReplayAvailable(true);
              setPipelineStage(`Audio playback blocked: ${err2?.name || 'tap play voice'}`);
              setStatus(clarifyMessages().tapPlayVoice);
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
        if (tryBrowserSpeechFallback(error)) return;
        setLastAudioError({ type: 'tts_playback', message: `HTML audio error: ${error}` });
        finish();
      };
      fallbackAudio.play().then(() => {
        debugLog('HTML audio playing successfully (fallback)');
        setLastAudioError(null);
      }).catch((error) => {
        console.error('HTML audio play failed:', error);
        try { document.body.removeChild(fallbackAudio); } catch (e) {}
        if (tryBrowserSpeechFallback(error)) return;
        finish();
        ttsPlayingRef.current = false;
        setPlaying(false);
        setAudioReplayAvailable(true);
        setPipelineStage(`Audio playback blocked: ${error?.name || 'tap play voice'}`);
        setStatus(clarifyMessages().tapPlayVoice);
        setLastAudioError({ type: 'tts_playback_blocked', name: error?.name, message: error?.message });
      });
    };
    if (!item.buffer) {
      debugLog('playTtsItem: direct audio URL, using HTML audio');
      playWithHtmlAudio();
      return;
    }

    debugLog('playTtsItem: trying AudioContext path with crossfade', isIosOrSafariRecorder() ? '(mobile Safari)' : '');
    ensureAudioContext()
      .then((context) => {
        debugLog('playTtsItem: AudioContext state', context?.state);
        if (!context || context.state !== 'running') {
          debugLog('AudioContext not running, using HTML audio fallback');
          playWithHtmlAudio();
          return;
        }
        
        // Create gain node routed through master gain for volume control
        const { gainNode } = getOrCreateAudioNodes(context);
        
        return context.decodeAudioData(item.buffer.slice(0))
          .then(async (rawAudioBuffer) => {
            // Trim trailing silence and match volume for seamless transitions
            const targetRMS = lastChunkRMSRef.current;
            const matchVolume = item.neuralBackend === false && targetRMS;
            const { buffer: audioBuffer, trimmedDuration, rms } = await createTrimmedBuffer(
              context,
              rawAudioBuffer,
              matchVolume ? targetRMS : null,
            );
            lastChunkRMSRef.current = rms; // Store for next chunk matching
            const duration = trimmedDuration;
            
            debugLog('playTtsItem: decoded buffer, original:', rawAudioBuffer.duration.toFixed(3), 'trimmed:', duration.toFixed(3));
            
            const source = context.createBufferSource();
            source.buffer = audioBuffer;
            const neuralItem = item.neuralBackend !== false;
            source.playbackRate.value = neuralItem
              ? neuralPlaybackRate(settings.ttsSpeed)
              : Math.min(Math.max((settings.ttsSpeed ?? 0.94) * 0.98, 0.72), 1.15);
            source.connect(gainNode);
            
            // Track duration for adaptive timing
            recentDurationsRef.current.push(duration);
            if (recentDurationsRef.current.length > 5) {
              recentDurationsRef.current.shift();
            }
            
            const now = context.currentTime;
            const hasMoreChunks = ttsQueueRef.current.length > 0 || nextAudioBufferRef.current;
            if (neuralItem) {
              // Neural Edge audio is already lifelike — start at full volume, no slow ramp-in.
              gainNode.gain.cancelScheduledValues(now);
              gainNode.gain.setValueAtTime(1, now);
              if (hasMoreChunks) {
                applySCurveFade(gainNode, now, duration, false, true);
              }
            } else {
              applySCurveFade(gainNode, now, duration, true, hasMoreChunks);
            }
            
            if (hasMoreChunks) {
              debugLog('playTtsItem: scheduled S-curve fade out, duration:', duration.toFixed(3));
            }
            
            source.onended = () => {
              window.clearTimeout(sourceSafetyTimeout);
              setLastAudioError(null);
              // Reset gain for next playback
              gainNode.gain.cancelScheduledValues(context.currentTime);
              gainNode.gain.setValueAtTime(0, context.currentTime);
              finish();
            };
            
            source.start(now);
            
            // Warm the decoder for upcoming chunks; playback remains queue-driven
            // so mobile mic/audio session state changes only after the phrase ends.
            preloadLookaheadChunks();
            
            const sourceSafetyTimeout = window.setTimeout(() => {
              console.warn('AudioBufferSource safety timeout fired, forcing finish');
              finish();
            }, Math.ceil(duration * 1000) + 1000);
            
            debugLog('playTtsItem: started with silence-trimmed crossfade');
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

  // Audio scheduling for gapless playback - ADVANCED SMOOTHNESS
  const nextAudioBufferRef = useRef(null);
  const nextNextAudioBufferRef = useRef(null); // Lookahead: 2 chunks ahead
  const gainNodeRef = useRef(null);
  const masterGainRef = useRef(null); // Limiter to prevent clipping
  const crossfadeDuration = 0.22; // longer crossfade — smoother between neural TTS chunks
  const overlapDuration = 0.05; // 50ms overlap between chunks
  const jitterBufferMs = 50; // Small jitter buffer for network stability
  const recentDurationsRef = useRef([]); // Track durations for adaptive timing
  const silenceThresholdDb = -60; // Silence detection threshold in dB
  const minSilenceMs = 30; // Minimum silence to trim in ms

  function getOrCreateAudioNodes(context) {
    if (!masterGainRef.current || masterGainRef.current.context !== context) {
      // Create master limiter with compressor for smooth dynamics
      masterGainRef.current = context.createGain();
      const volumeLevel = Number.isFinite(Number(volume)) ? Number(volume) : 0.8;
      masterGainRef.current.gain.value = Math.max(0, Math.min(1, volumeLevel)) * 0.92; // More headroom for crossfades
      
      // Add compressor for consistent volume
      const compressor = context.createDynamicsCompressor();
      compressor.threshold.value = -3; // Start compression at -3dB
      compressor.knee.value = 4; // Smooth knee
      compressor.ratio.value = 3; // Moderate compression
      compressor.attack.value = 0.003; // Fast attack
      compressor.release.value = 0.1; // Smooth release
      
      masterGainRef.current.connect(compressor);
      compressor.connect(context.destination);
    }
    if (!gainNodeRef.current || gainNodeRef.current.context !== context) {
      gainNodeRef.current = context.createGain();
      gainNodeRef.current.connect(masterGainRef.current);
    }
    return { masterGain: masterGainRef.current, gainNode: gainNodeRef.current };
  }

  // S-curve fade for more natural transitions (ease-in-out)
  function applySCurveFade(gainNode, startTime, duration, fadeIn, fadeOut) {
    const fadeDuration = Math.min(crossfadeDuration, duration * 0.3);
    
    if (fadeIn) {
      // S-curve fade in: starts slow, speeds up, slows down
      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(0.3, startTime + fadeDuration * 0.3);
      gainNode.gain.linearRampToValueAtTime(1, startTime + fadeDuration);
    }
    
    if (fadeOut) {
      // S-curve fade out
      const fadeStart = startTime + duration - fadeDuration;
      gainNode.gain.setValueAtTime(1, fadeStart);
      gainNode.gain.linearRampToValueAtTime(0.3, fadeStart + fadeDuration * 0.7);
      gainNode.gain.linearRampToValueAtTime(0, startTime + duration);
    }
  }

  // Analyze audio buffer to find trailing silence
  function findTrailingSilence(audioBuffer, thresholdDb = silenceThresholdDb) {
    const threshold = Math.pow(10, thresholdDb / 20);
    const sampleRate = audioBuffer.sampleRate;
    const channelData = audioBuffer.getChannelData(0); // Use first channel
    const minSamples = Math.floor((minSilenceMs / 1000) * sampleRate);
    
    // Find last non-silent sample
    let lastNonSilentIndex = channelData.length - 1;
    for (let i = channelData.length - 1; i >= 0; i--) {
      if (Math.abs(channelData[i]) > threshold) {
        lastNonSilentIndex = i;
        break;
      }
    }
    
    // Ensure minimum samples remain
    const endIndex = Math.max(lastNonSilentIndex + 1, minSamples);
    const silenceSamples = channelData.length - endIndex;
    const silenceDuration = silenceSamples / sampleRate;
    
    return { silenceDuration, endIndex, hasTrailingSilence: silenceSamples > minSamples };
  }

  // Calculate RMS (Root Mean Square) volume of audio buffer
  function calculateRMS(audioBuffer, startSample = 0, endSample = null) {
    const channelData = audioBuffer.getChannelData(0);
    const end = endSample || channelData.length;
    let sum = 0;
    let count = 0;
    
    for (let i = startSample; i < end; i++) {
      sum += channelData[i] * channelData[i];
      count++;
    }
    
    return Math.sqrt(sum / count);
  }

  // Find nearest zero crossing to avoid clicks
  function findNearestZeroCrossing(audioBuffer, targetSample, searchRadius = 50) {
    const channelData = audioBuffer.getChannelData(0);
    const sampleRate = audioBuffer.sampleRate;
    const maxSearch = Math.min(searchRadius, Math.floor(0.005 * sampleRate)); // Max 5ms search
    
    let bestIndex = targetSample;
    let minAmplitude = Math.abs(channelData[targetSample]);
    
    // Search forward and backward
    for (let offset = 1; offset <= maxSearch; offset++) {
      // Check forward
      if (targetSample + offset < channelData.length) {
        const ampForward = Math.abs(channelData[targetSample + offset]);
        if (ampForward < minAmplitude) {
          minAmplitude = ampForward;
          bestIndex = targetSample + offset;
        }
      }
      // Check backward
      if (targetSample - offset >= 0) {
        const ampBackward = Math.abs(channelData[targetSample - offset]);
        if (ampBackward < minAmplitude) {
          minAmplitude = ampBackward;
          bestIndex = targetSample - offset;
        }
      }
    }
    
    return bestIndex;
  }

  // Create trimmed audio buffer without trailing silence, aligned to zero crossing
  async function createTrimmedBuffer(context, originalBuffer, targetRMS = null) {
    const { silenceDuration, endIndex, hasTrailingSilence } = findTrailingSilence(originalBuffer);
    
    // Find optimal end point at zero crossing to prevent clicks
    const optimalEndIndex = findNearestZeroCrossing(originalBuffer, endIndex);
    
    // Calculate RMS for volume matching
    const bufferRMS = calculateRMS(originalBuffer, 0, optimalEndIndex);
    const volumeScale = targetRMS ? (targetRMS / bufferRMS) : 1.0;
    const clampedScale = Math.min(Math.max(volumeScale, 0.7), 1.3); // Limit to reasonable range
    
    if (!hasTrailingSilence && clampedScale === 1.0) {
      // No changes needed
      return { buffer: originalBuffer, trimmedDuration: originalBuffer.duration, rms: bufferRMS };
    }
    
    // Create new buffer without trailing silence, aligned to zero crossing
    const trimmedBuffer = context.createBuffer(
      originalBuffer.numberOfChannels,
      optimalEndIndex,
      originalBuffer.sampleRate
    );
    
    // Copy data with volume adjustment
    for (let channel = 0; channel < originalBuffer.numberOfChannels; channel++) {
      const originalData = originalBuffer.getChannelData(channel);
      const trimmedData = trimmedBuffer.getChannelData(channel);
      for (let i = 0; i < optimalEndIndex; i++) {
        trimmedData[i] = originalData[i] * clampedScale;
      }
    }
    
    debugLog('Optimized buffer: trimmed', silenceDuration.toFixed(3), 's, RMS scale:', clampedScale.toFixed(3), 'zero-cross:', optimalEndIndex);
    
    return { buffer: trimmedBuffer, trimmedDuration: trimmedBuffer.duration, rms: bufferRMS * clampedScale };
  }

  // Last chunk RMS for volume matching between phrases
  const lastChunkRMSRef = useRef(null);

  // Calculate adaptive timing based on recent chunk durations
  function getAdaptiveOverlapDuration() {
    const recent = recentDurationsRef.current;
    if (recent.length < 3) return overlapDuration;
    
    // Average recent durations
    const avgDuration = recent.reduce((a, b) => a + b, 0) / recent.length;
    // Adjust overlap: longer chunks need slightly more overlap
    const adaptive = Math.min(0.08, Math.max(0.02, avgDuration * 0.05));
    return adaptive;
  }

  function preloadLookaheadChunks() {
    ensureAudioContext().then((ctx) => {
      if (!ctx) return;
      
      // Preload first next chunk
      if (ttsQueueRef.current.length > 0 && !nextAudioBufferRef.current) {
        const nextItem = ttsQueueRef.current[0];
        if (nextItem?.buffer) {
          ctx.decodeAudioData(nextItem.buffer.slice(0)).then((buffer) => {
            nextAudioBufferRef.current = buffer;
            debugLog('Preloaded chunk+1, duration:', buffer.duration);
          }).catch(() => { nextAudioBufferRef.current = null; });
        }
      }
      
      // Preload second next chunk (lookahead)
      if (ttsQueueRef.current.length > 1 && !nextNextAudioBufferRef.current) {
        const nextNextItem = ttsQueueRef.current[1];
        if (nextNextItem?.buffer) {
          ctx.decodeAudioData(nextNextItem.buffer.slice(0)).then((buffer) => {
            nextNextAudioBufferRef.current = buffer;
            debugLog('Preloaded chunk+2, duration:', buffer.duration);
          }).catch(() => { nextNextAudioBufferRef.current = null; });
        }
      }
    });
  }

  function shiftLookaheadBuffers() {
    // Shift: next becomes current (consumed), nextNext becomes next
    nextAudioBufferRef.current = nextNextAudioBufferRef.current;
    nextNextAudioBufferRef.current = null;
    // Preload new nextNext
    preloadLookaheadChunks();
  }

  function schedulePreciseNextChunk(context, currentEndTime) {
    if (ttsQueueRef.current.length === 0 || !nextAudioBufferRef.current) return;
    
    const nextStartTime = currentEndTime - overlapDuration;
    const delayMs = Math.max(0, (nextStartTime - context.currentTime) * 1000);
    
    debugLog('Precise schedule: next chunk at', nextStartTime.toFixed(3), '(in', delayMs.toFixed(1), 'ms)');
    
    // Use setTimeout for the precise timing, then start with AudioContext
    window.setTimeout(() => {
      if (ttsPlayingRef.current && ttsQueueRef.current.length > 0) {
        playNextTtsChunkPrecise(context);
      }
    }, delayMs);
  }

  function playNextTtsChunkPrecise(context) {
    if (ttsQueueRef.current.length === 0 || !nextAudioBufferRef.current) return;
    
    const item = ttsQueueRef.current.shift();
    setTtsQueueLength(ttsQueueRef.current.length);
    
    const { gainNode } = getOrCreateAudioNodes(context);
    const audioBuffer = nextAudioBufferRef.current;
    const duration = audioBuffer.duration;
    
    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(gainNode);
    
    const now = context.currentTime;
    
    // Smooth fade in
    gainNode.gain.cancelScheduledValues(now);
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(1, now + crossfadeDuration);
    
    // Schedule fade out before end if we have more chunks
    if (ttsQueueRef.current.length > 0) {
      const fadeOutStart = Math.max(crossfadeDuration, duration - crossfadeDuration);
      gainNode.gain.setValueAtTime(1, now + fadeOutStart);
      gainNode.gain.linearRampToValueAtTime(0, now + duration);
    } else {
      // Last chunk: fade out at end
      gainNode.gain.setValueAtTime(1, now + duration - crossfadeDuration);
      gainNode.gain.linearRampToValueAtTime(0, now + duration);
    }
    
    source.onended = () => {
      if (ttsQueueRef.current.length === 0) {
        ttsPlayingRef.current = false;
        setTtsPlaying(false);
        setPlaying(false);
        gainNode.gain.setValueAtTime(0, context.currentTime);
        resumeMicAfterVoicePlayback();
        if (!resumeInterpreterListeningUI('Listening live...')) {
          setPipelineStage('Ready to listen');
          setStatus(BRIDGE_STATUS.bridgeReadySpeak);
        }
      }
    };
    
    source.start(now);
    
    // Schedule next chunk and shift lookahead
    shiftLookaheadChunks();
    if (ttsQueueRef.current.length > 0) {
      schedulePreciseNextChunk(context, now + duration);
      preloadLookaheadChunks();
    }
    
    debugLog('Precise playback started, duration:', duration, ', queue:', ttsQueueRef.current.length);
  }

  function playNextTtsChunk(scheduled = false) {
    if (ttsQueueRef.current.length === 0) {
      if (!ttsPlayingRef.current && appStateRef.current.playing) {
        setPlaying(false);
        setTtsQueueLength(0);
        if (!resumeInterpreterListeningUI('Listening live...')) {
          setPipelineStage('Ready to listen');
          setStatus(BRIDGE_STATUS.bridgeReadySpeak);
        }
      }
      return;
    }
    if (ttsPlayingRef.current && !scheduled) {
      debugLog(`TTS already playing; ${ttsQueueRef.current.length} chunk(s) waiting`);
      return;
    }

    const item = ttsQueueRef.current.shift();
    setTtsQueueLength(ttsQueueRef.current.length);
    debugLog(`Playing TTS chunk, ${ttsQueueRef.current.length} remaining in queue`);
    playTtsItem(item, { revokeOnFinish: false });
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

    // Mutual exclusion: stop the other speaker before starting this one
    const otherSpeaker = speaker === 'A' ? 'B' : 'A';
    const otherRefs = duplexRefs.current[otherSpeaker];
    if (otherRefs.socket) {
      otherRefs.manualClose = true;
      otherRefs.shouldReconnect = false;
      otherRefs.finalizePending = true;
      if (otherRefs.recorder?.state === 'recording') {
        otherRefs.recorder.requestData?.();
        otherRefs.recorder.stop();
      } else if (otherRefs.socket.readyState === WebSocket.OPEN) {
        otherRefs.socket.send(JSON.stringify({ type: 'finalize' }));
      }
      updateDuplexSpeaker(otherSpeaker, { active: false, stage: 'Paused' });
    }
    // Also stop any playing TTS so the mic is clean
    window.speechSynthesis?.cancel();

    let stream;
    try {
      stream = await requestAudioStream(settings.micDeviceId !== 'default' ? settings.micDeviceId : undefined);
      debugLog('MIC STREAM ACTIVE:', stream);
      logAudioStream(stream);
    } catch (error) {
      setMicPermission('denied');
      updateDuplexSpeaker(speaker, { active: false, stage: mediaErrorMessage(error) });
      showUserError(mapTechnicalError(error));
      return;
    }
    setMicPermission('available');
    const activeAuthToken = await ensureAuthToken();
    const socket = new WebSocket(withAuthToken(`${liveWsUrl}/ws/audio`, activeAuthToken));
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
      refs.reconnectAttempts = 0;
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
        barrier_mode: resolveStreamBarrierMode(),
        environment: resolveStreamEnvironment(),
      }));
      recorder.start(activePacketMs());
      startMicMeter(stream);
      reliabilityRef.current.recordSuccess('websocket');
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'session_restored') {
        applySharedSession(data.session?.shared || data.session);
        const history = data.session?.turns || data.session?.history || data.session?.shared?.history;
        if (Array.isArray(history) && history.length) {
          const lastTurn = history[history.length - 1];
          updateDuplexSpeaker(speaker, {
            transcript: lastTurn.source_text || '',
            translation: lastTurn.translated_text || '',
            stage: `Rebound session (${data.session.reconnects || 0} reconnects)`,
          });
        } else {
          updateDuplexSpeaker(speaker, { stage: `Rebound session (${data.session.reconnects || 0} reconnects)` });
        }
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
        if (!data.allowed && (data.behavior === 'hold' || data.behavior === 'playback')) {
          pauseMicForVoicePlayback();
          updateDuplexSpeaker(speaker, { stage: data.reason || 'Waiting for playback' });
        } else if (data.behavior === 'interruption' || data.behavior === 'turn_shift' || data.behavior === 'overlap') {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
          try { window.speechSynthesis?.cancel?.(); } catch {}
          resumeMicAfterVoicePlayback();
          ['A', 'B'].forEach((spk) => {
            const otherR = duplexRefs.current[spk];
            if (otherR?._pausedForTts && otherR.recorder?.state === 'paused') {
              otherR.recorder.resume?.();
              otherR._pausedForTts = false;
            }
          });
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
        updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Bridge ready' });
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        applyConfidenceSignals(data);
        const duplexPartialThreshold = typeof data.confidence_threshold === 'number' ? data.confidence_threshold : 0.72;
        if (shouldSkipBrainTts(data)) {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
        } else if (data.low_confidence || (typeof data.confidence === 'number' && data.confidence < duplexPartialThreshold)) {
          setConfidenceWarningMessage(data.confidence_message || 'Listening for clearer speech…');
          setConfidenceWarningVisible(true);
        }
        updateDuplexSpeaker(speaker, { translation: data.text, stage: pipelineStages().liveBridge });
      }
      if (data.type === 'tts_audio_chunk') {
        if (shouldSkipBrainTts(data)) {
          updateDuplexSpeaker(speaker, { stage: 'Voice skipped for confirmation' });
          return;
        }
        // Pause the OTHER speaker's mic while TTS plays to prevent echo
        const otherSpk = speaker === 'A' ? 'B' : 'A';
        const otherR = duplexRefs.current[otherSpk];
        if (otherR.recorder?.state === 'recording') {
          otherR.recorder.pause?.();
          otherR._pausedForTts = true;
        }
        ensureAudioUnlocked().catch((e) => console.warn('Duplex TTS chunk audio unlock failed:', e));
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'tts_end' && !data.partial) {
        // Resume the other speaker's mic after TTS finishes
        const otherSpk = speaker === 'A' ? 'B' : 'A';
        const otherR = duplexRefs.current[otherSpk];
        if (otherR._pausedForTts && otherR.recorder?.state === 'paused') {
          otherR.recorder.resume?.();
          otherR._pausedForTts = false;
        }
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
        applyConfidenceSignals(data);
        if (shouldSkipBrainTts(data)) {
          clearTtsQueue();
          setPlaying(false);
          setTtsPlaying(false);
          try { window.speechSynthesis?.cancel?.(); } catch {}
        }
        if (data.low_confidence || data.needs_native_certification || humanCertStep(data) !== 'none') {
          applyConfidenceSignals(data);
          if (data.confidence_message || data.certification_message) {
            setConfidenceWarningMessage(
              data.certification_message || data.confidence_message || clarifyMessages().checkMeaning,
            );
            setConfidenceWarningVisible(true);
          }
        }
        if (shouldBlockTtsForCert(humanCertStep(data)) || data.stage === 'translation_safety') {
          setClarifyMessage(
            data.clarify_message || data.certification_message || data.confidence_message || clarifyMessages().checkMeaning,
          );
          setClarifyVisible(true);
        } else if (asCertBool(data.needs_confirmation) || data.stage === 'cip_clarification') {
          setClarifyMessage(data.clarify_message || data.confidence_message || clarifyMessages().checkMeaning);
          setClarifyVisible(true);
        } else if (data.native_speaker_listen_recommended && data.certification_message) {
          setConfidenceWarningVisible(true);
          setConfidenceWarningMessage(data.certification_message);
        }
        if (data.session) applySharedSession(data.session);
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          speaker_label: label,
          stage: data.clarify || data.low_confidence || data.needs_native_certification
            ? (data.certification_message || data.confidence_message || 'Clarification needed')
            : (brainUpdate?.message || 'Complete'),
        });
        // Append to shared conversation history so turns persist
        if (data.source_text || data.translated_text) {
          appendConversationTurn({
            ...data,
            speaker_label: label || `Person ${speaker}`,
            conversationSpeaker: speaker,
          });
        }
        if (refs.recorder?.state === 'recording') {
          refs.finalizePending = false;
          refs.recorder.stop();
        }
        socket.close();
        refs.socket = null;
      }
    };

    socket.onerror = () => {
      reliabilityRef.current.recordFailure('websocket');
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
        refs.reconnectAttempts = (refs.reconnectAttempts || 0) + 1;
        if (refs.reconnectAttempts >= STREAM_RECONNECT_MAX_ATTEMPTS) {
          updateDuplexSpeaker(speaker, { active: false, stage: 'Reconnect failed — tap to retry' });
          setReconnectToastVisible(true);
          return;
        }
        const delay = Math.min(
          STREAM_RECONNECT_MS * Math.pow(2, refs.reconnectAttempts - 1),
          STREAM_RECONNECT_MAX_DELAY_MS,
        );
        updateDuplexSpeaker(speaker, {
          stage: `Reconnecting (${refs.reconnectAttempts}/${STREAM_RECONNECT_MAX_ATTEMPTS})...`,
        });
        window.setTimeout(() => {
          if (refs.shouldReconnect && !refs.manualClose) toggleDuplexSpeaker(speaker);
        }, delay);
      } else {
        setReconnectToastVisible(true);
      }
    };
  }


  const hasSourceText = Boolean(partialTranscript || result?.source_text);
  const hasTranslatedText = Boolean(liveTranslation || result?.translated_text);
  const sourceText = partialTranscript || result?.source_text || (hasSourceText ? '' : 'Your words will appear here');
  const translatedText = liveTranslation || result?.translated_text || (hasTranslatedText ? '' : targetPlaceholder());
  const interpreterSessionLive = interpreterMode && speakerMode === 'auto' && interpreterSocketOpen;
  const perceivedListening = liveSpeechSession || interpreterSessionLive || streaming || instantListening;
  const displayMicLevel = micLevel;
  const micReady = connectionStatus === 'online' && micPermission !== 'denied' && micPermission !== 'unavailable';
  const micState = playing ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'idle';
  const micLabel = micLabels({
    connectionStatus,
    micReady,
    playing,
    perceivedListening,
    processing,
  });
  const rawStatusText = normalizePipelineStage(pipelineStage && pipelineStage !== 'Idle' ? pipelineStage : status);
  const showInstallAction = !pwaInstalled && (installPrompt || isManualInstallBrowser());
  const activeSpeakerLabel = detectedSpeaker && detectedSpeaker !== '-' && detectedSpeaker !== 'Person' ? detectedSpeaker : '';
  const recentConversationTurns = settings.showConversationHistory !== false ? conversationTurns.slice(-4) : [];
  const latencyTotalMs = Number.parseInt(String(latencyStats.end_to_end || ''), 10);
  const { average: latencyAverageMs } = summarizeLatencyHistory(latencyHistory);
  const sourceLanguageLabel = languages[sourceLanguage] || sourceLanguage.toUpperCase();
  const targetLanguageLabel = TARGET_LANGUAGE_OPTIONS.find((option) => option.code === targetLanguage)?.label || languages[targetLanguage] || targetLanguage.toUpperCase();
  const statusTone = connectionStatus !== 'online' ? 'offline' : playing || ttsPlaying ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'ready';
  const timingLabel = Number.isFinite(latencyTotalMs) ? `${latencyTotalMs}ms` : latencyAverageMs ? `${latencyAverageMs}ms avg` : '';
  const statusText = showFriendlyStatus
    ? getFriendlyStatusLabel({
      statusText: rawStatusText,
      connectionStatus,
      streaming: perceivedListening,
      processing,
      playing,
      ttsPlaying,
    })
    : rawStatusText;
  const statusDetail = showFriendlyStatus
    ? getFriendlyStatusDetail({
      connectionStatus,
      streaming: perceivedListening,
      processing,
      playing,
      ttsPlaying,
      sourceLanguageLabel,
      targetLanguageLabel,
      turnCount: conversationTurns.length,
      timingLabel,
    })
    : '';
  const speakerSummary = showFriendlyStatus ? '' : activeSpeakerLabel;
  const displayTimingLabel = showFriendlyStatus ? '' : timingLabel;
  const micHint = micHints({
    perceivedListening,
    processing,
    playing,
    connectionStatus,
  });
  const visibleRepairOptions = (brainUi.repairOptions || []).slice(0, 3);
  const visibleHighlightTerms = (brainUi.highlightTerms || []).slice(0, 5);
  const brainModeLabel = formatBrainModeLabel(brainUi.mode, brainUi.strategy);
  const liveHudMode = liveAssistActive ? 'Instant' : perceivedListening ? 'Audio' : connectionStatus === 'online' ? 'Ready' : 'Offline';
  const transcriptState = hasSourceText ? (perceivedListening ? 'live' : 'filled') : 'empty';
  const translationState = hasTranslatedText ? ((playing || ttsPlaying) ? 'speaking' : 'filled') : 'empty';
  const liveHudItems = [
    { key: 'listen', label: 'Hear', Icon: Radio, active: perceivedListening, level: displayMicLevel },
    { key: 'understand', label: 'Understand', Icon: Heart, active: liveAssistActive || brainUi.visible || processing },
    { key: 'bridge', label: 'Bridge', Icon: Languages, active: Boolean(liveTranslation) || /translat|understand|bridg/i.test(rawStatusText || '') },
    { key: 'speak', label: 'Out loud', Icon: Volume2, active: playing || ttsPlaying || ttsQueueLength > 0 },
  ];
  const hasVisibleConversation = perceivedListening || hasSourceText || hasTranslatedText || recentConversationTurns.length > 0 || clarifyVisible || brainUi.visible;
  const isTextTranslating = processing && textInputMode;
  const showConnectionQuality =
    connectionStatus !== 'online' ||
    (streamReconnectRef.current?.attempts > 0 && connectionStatus === 'online');
  const showInstallNudge = showInstallAction && hasTranslatedText && !installNudgeDismissed;
  const showIosMicHint = isIosOrSafariRecorder() && !EXPERIMENTAL_IOS_STREAMING && connectionStatus === 'online';
  const quickActions = perceivedListening ? [] : [
    {
      key: 'type',
      label: DOCK.typeToBridge,
      Icon: Keyboard,
      onClick: () => setTextInputMode(true),
      disabled: streaming || processing || playing || connectionStatus !== 'online',
      active: textInputMode,
    },
    {
      key: 'flip',
      label: DOCK.flip,
      Icon: Repeat2,
      onClick: flipLanguageDirection,
      disabled: streaming || processing || playing || ttsPlaying || sourceLanguage === targetLanguage,
    },
    {
      key: 'replay',
      label: DOCK.replay,
      Icon: Volume2,
      onClick: playTranslationAudio,
      disabled: !audioReplayAvailable || playing || ttsPlaying,
      active: playing || ttsPlaying,
    },
    {
      key: 'clear',
      label: DOCK.clear,
      Icon: Trash2,
      onClick: clearInterpreterScreen,
      disabled: streaming || processing || playing || ttsPlaying || !hasVisibleConversation,
      danger: true,
    },
  ];

  return (
    <main className="app-shell">
      <a href="#main-content" className="skip-to-content">Skip to main content</a>
      <SystemBanners
        updateAvailable={updateAvailable}
        reconnectToastVisible={reconnectToastVisible}
        connectionStatus={connectionStatus}
        offlineBannerDismissed={offlineBannerDismissed}
        onDismissOffline={() => setOfflineBannerDismissed(true)}
        onOfflineRetry={retryBackendConnection}
        onDismissReconnect={() => {
          setReconnectToastVisible(false);
          haptic(30);
        }}
        onReconnectRetry={() => {
          try { handleMicClick(); } catch {}
        }}
        micPermission={micPermission}
        micBannerDismissed={micBannerDismissed}
        onDismissMicBanner={() => setMicBannerDismissed(true)}
        onRequestMic={() => {
          setMicBannerDismissed(true);
          requestMicPermission().catch(() => {});
        }}
        showInstallNudge={showInstallNudge}
        installNudgeDismissed={installNudgeDismissed}
        onDismissInstallNudge={() => {
          setInstallNudgeDismissed(true);
          try { sessionStorage.setItem('anai_install_nudge_dismissed', '1'); } catch {}
        }}
        onInstallApp={installApp}
        onOpenSettings={() => setSettingsOpen(true)}
        showIosMicHint={showIosMicHint}
        iosMicHintDismissed={iosMicHintDismissed}
        onDismissIosMicHint={() => {
          setIosMicHintDismissed(true);
          try { sessionStorage.setItem('anai_ios_mic_hint_dismissed', '1'); } catch {}
        }}
      />
      <section
        className={`phone-frame${hasVisibleConversation ? ' has-conversation' : ''}${perceivedListening ? ' is-listening' : ''}`}
        data-connection={connectionStatus}
        data-smoke-check="Self Test"
        id="main-content"
      >
        <div className="phone-top-bar">
          <AppHeader
            connectionStatus={connectionStatus}
            shareConversationRoom={shareConversationRoom}
            copiedKey={copiedKey}
            showInstallAction={showInstallAction}
            installApp={installApp}
            volume={volume}
            onVolumeChange={handleVolumeChange}
            onOpenSettings={() => setSettingsOpen(true)}
            updateAvailable={updateAvailable}
            apiUrl={liveApiUrl}
            diagnostics={diagnostics}
          />
          {advancedChrome && showConnectionQuality && (
            <ConnectionQualityIndicator
              connectionStatus={connectionStatus}
              latencyMs={latencySummary.average}
              reconnectAttempt={streamReconnectRef.current || 0}
              maxReconnectAttempts={STREAM_RECONNECT_MAX_ATTEMPTS}
              isReconnecting={streaming && connectionStatus !== 'online'}
            />
          )}
          {currentError && (
            <UserFriendlyError
              errorCode={currentError}
              onDismiss={handleDismissError}
              onRetry={handleRetryError}
            />
          )}
          <LanguageDock
            sourceLanguageLabel={sourceLanguageLabel}
            targetLanguageLabel={targetLanguageLabel}
            sourceLanguage={sourceLanguage}
            targetLanguage={targetLanguage}
            setSourceLanguage={setSourceLanguage}
            setTargetLanguage={setTargetLanguage}
            recording={recording}
            processing={processing}
            streaming={perceivedListening}
            brainUi={brainUi}
            quickActions={quickActions}
          />
        </div>
        <div className="speech-workspace">
        <MicPanel
          micState={micState}
          micLevel={displayMicLevel}
          perceivedListening={perceivedListening}
          micReady={micReady}
          micLabel={micLabel}
          micHint={micHint}
          handleMicClick={handleMicClick}
          onStopListening={handleStopListening}
          handleMicPointerDown={null}
          handleMicPointerUp={null}
          playing={playing}
          processing={processing}
          streaming={perceivedListening}
          recording={recording}
          liveHudMode={liveHudMode}
          liveHudItems={liveHudItems}
          statusTone={statusTone}
          statusText={statusText}
          statusDetail={statusDetail}
          showFriendlyStatus={showFriendlyStatus}
          onStatusToggle={() => {
            setShowFriendlyStatus((prev) => {
              const next = !prev;
              try { localStorage.setItem('anai_friendly_status', next ? 'true' : 'false'); } catch {}
              return next;
            });
            haptic(20);
          }}
          speakerSummary={speakerSummary}
          timingLabel={displayTimingLabel}
          audioReplayAvailable={audioReplayAvailable}
          autoPlayFailed={autoPlayFailed}
          playTranslationAudio={playTranslationAudio}
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
          sourceLanguageCode={sourceLanguage}
          sourceText={sourceText}
          hasTranslatedText={hasTranslatedText}
          translationState={translationState}
          targetLanguageLabel={targetLanguageLabel}
          targetLanguageCode={targetLanguage}
          translatedText={translatedText}
          copyToClipboard={copyToClipboard}
          copiedKey={copiedKey}
          cameraActive={cameraActive}
          videoRef={videoRef}
          ocrText={ocrText}
          recentConversationTurns={recentConversationTurns}
          onClearConversation={clearInterpreterScreen}
          clarifyVisible={clarifyVisible}
          clarifyMessage={clarifyMessage}
          confidenceWarningVisible={confidenceWarningVisible}
          confidenceWarningMessage={confidenceWarningMessage}
          setConfidenceWarningVisible={setConfidenceWarningVisible}
          humanCertificationStep={humanCertificationStep}
          onConfirmTranslation={sendGlossaryCorrection}
          guardedSourceText={lastGuardedSourceRef.current}
          result={result}
          setClarifyVisible={setClarifyVisible}
          setPipelineStage={setPipelineStage}
          setStatus={setStatus}
          haptic={haptic}
          streaming={perceivedListening}
          processing={processing}
          handleMicClick={handleMicClick}
          enableTypingAnimation={!perceivedListening}
          isTranslationActive={processing && !perceivedListening}
          onTextTranslate={(inputText) => translateText(inputText)}
          textInputMode={textInputMode}
          onTextInputModeChange={setTextInputMode}
          connectionStatus={connectionStatus}
          isTextTranslating={isTextTranslating}
          textTranslateReady={connectionStatus === 'online' && !processing}
          onNotify={(message, type) => toast(message, type, 2000)}
          onOpenSettings={() => setSettingsOpen(true)}
          onOfflineRetry={retryBackendConnection}
        />
        </div>
        <SettingsPanel
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          settings={settings}
          updateSetting={(key, val) => {
            updateSetting(key, val);
            if (key === 'debugMode') setShowDebugPanel(val);
          }}
          onClearHistory={() => { clearInterpreterScreen(); }}
          onClearSession={() => {
            clearInterpreterScreen();
            localStorage.removeItem('translator_device_id');
            localStorage.removeItem('translator_speaker_name');
            try { sessionStorage.clear(); } catch {}
          }}
          diagnostics={diagnostics}
          apiUrl={liveApiUrl}
          selfTest={selfTest}
          runSelfTest={runSelfTest}
        />
        {settings.debugMode && showDebugPanel && (
          <DebugPanel
            onClose={() => setShowDebugPanel(false)}
            onOpenAILangConfig={() => setShowAILangConfig(true)}
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
        {showAILangConfig && (
          <AILangConfigPanel
            apiUrl={liveApiUrl}
            onClose={() => setShowAILangConfig(false)}
          />
        )}

      <ToastRegion toasts={toasts} dismiss={dismiss} />
      </section>
      {advancedChrome ? <OnboardingTour /> : null}
      <KeyboardHelp isOpen={showKeyboardHelp} onClose={() => setShowKeyboardHelp(false)} />
      {advancedChrome ? (
      <Assistant
        apiUrl={liveApiUrl}
        authToken={authToken}
        getTranslationContext={() => {
          if (!result) return null;
          return {
            source_language: sourceLanguage,
            target_language: targetLanguage,
            source_text: result.source_text || result.original_text || '',
            translated_text:result.translated_text || '',
          };
        }}
      />
      ) : null}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<ErrorBoundary><App /></ErrorBoundary>);
