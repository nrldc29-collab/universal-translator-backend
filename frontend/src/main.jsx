import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowLeftRight, Check, Clock3, Copy, Download, Languages, Mic, Radio, Repeat2, Share2, Sparkles, Trash2, UserRound, Volume2 } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';
import Assistant from './Assistant';
import ConversationMode from './components/ConversationMode';
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
import ConversationActions from './components/ConversationActions';
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

const INITIAL_DEVICE_ID = localStorage.getItem('translator_device_id') || crypto.randomUUID();

// Browser TTS -- used as fallback when backend has no voice for the target language.
// Works offline, free, covers all languages via system voices.
const PIPER_SUPPORTED_LANGS = new Set(['en', 'es']); // languages with local Piper voices
const BROWSER_TTS_LANG_MAP = {
  en: 'en-US', es: 'es-MX', fr: 'fr-FR', de: 'de-DE', it: 'it-IT',
  pt: 'pt-BR', ru: 'ru-RU', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR',
  ar: 'ar-SA', hi: 'hi-IN', ht: 'fr-HT', nl: 'nl-NL',
};
let browserTtsLastText = '';
function browserTtsSpeak(text, langCode, speed = 1.0) {
  if (!window.speechSynthesis || !text || text === browserTtsLastText) return;
  browserTtsLastText = text;
  const lang = BROWSER_TTS_LANG_MAP[langCode] || langCode || 'en-US';
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = lang;
  utt.rate = Math.min(Math.max(speed, 0.5), 2.0);
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find((v) => v.lang.startsWith(lang.slice(0, 2)) && !v.localService)
    || voices.find((v) => v.lang.startsWith(lang.slice(0, 2)));
  if (match) utt.voice = match;
  window.speechSynthesis.speak(utt);
  setTimeout(() => { browserTtsLastText = ''; }, 3000);
}

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
  const { settings, updateSetting } = useSettings();
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const liveApiUrl = (settings.backendUrl || '').trim().replace(/\/+$/, '') || API_URL;
  const liveWsUrl = liveApiUrl.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
  const { connectionStatus, setConnectionStatus } = useConnectionStatus({
    apiUrl: liveApiUrl,
    pollIntervalMs: HEALTH_POLL_MS,
    onLanguages: (langs) => langs && setLanguages((prev) => ({ ...prev, ...langs })),
    onOffline: () => setStatus('Backend offline'),
  });
  const { micPermission, setMicPermission, requestMicPermission } = useMicPermission({
    onStatus: (message) => setStatus(message),
  });
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
    confidenceWarningVisible, setConfidenceWarningVisible,
    confidenceWarningMessage, setConfidenceWarningMessage,
    brainUi, setBrainUi,
    conversationBrain, setConversationBrain,
    semanticContext, setSemanticContext,
    brainHintsRef, brainPlanRef,
    shouldSkipBrainTts, resetBrainRuntimeUi,
  } = useBrainState();
  const reliabilityMonitor = useReliabilityMonitor();
  const autoConversation = useAutoConversation({
    wsAudioUrl: `${liveWsUrl}/ws/audio`,
    authToken,
    sourceLanguage,
    targetLanguage,
    withAuthToken,
  });
  const lowBandwidthMode = !!settings.lowBandwidthMode;
  const [showDebugPanel, setShowDebugPanel] = useState(() => !!settings.debugMode);
  const [showAILangConfig, setShowAILangConfig] = useState(false);
  const [reconnectToastVisible, setReconnectToastVisible] = useState(false);

  // Error state for user-friendly error display
  const [currentError, setCurrentError] = useState(null);
  const handleDismissError = () => setCurrentError(null);
  const handleRetryError = () => {
    setCurrentError(null);
    // Retry logic depends on error type - mic click for mic errors, etc.
    try { handleMicClick(); } catch {}
  };

  // Keyboard shortcuts
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
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
  const { authToken, setAuthToken, username, setUsername, password, setPassword, login, logout, ensureAuthToken } = useAuth({ apiUrl: liveApiUrl, onStatus: setStatus });
  const { selfTest, runSelfTest } = useSelfTest({
    apiUrl: liveApiUrl,
    wsAudioUrl: `${liveWsUrl}/ws/audio`,
    authToken,
    onStatus: (message) => setStatus(message),
  });
  const { sessionId, setSessionId, updateSessionId, sharedSession, setSharedSession, speakerMode, setSpeakerMode } = useStreamSession();
  const [appMode, setAppMode] = React.useState('solo'); // 'solo' | 'conversation'
  const [conversationTurns, setConversationTurns, appendConversationTurn] = useConversationHistory(50, { normalizeConversationTurn });
  const { analytics, setAnalytics, loadAnalytics } = useAnalytics({ apiUrl: liveApiUrl, authToken, onStatus: setStatus });
  const { diagnostics, diagnosticsStatus, loadDiagnostics } = useDiagnostics(liveApiUrl);
  const { wsDebug, setWsDebug } = useWsDebug(WS_AUDIO_URL);
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
    toast('Copied to clipboard', 'success', 2000);
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

  // Bind languageName/shareRoomUrl to the current state so call sites stay terse.
  const languageName = (code) => languageNameUtil(code, languages);

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
  const {
    mediaRecorderRef, streamRecorderRef, chunksRef, socketRef,
    recordingStoppedRef, streamFinalizePendingRef, streamFinalizeTimerRef,
    streamStartedAtRef, streamRecordingStartedAtRef, firstAudioSeenRef,
    streamReconnectRef, streamSafetyTimeoutRef, resumeAfterTtsRef,
  } = useStreamRefs();
  const { streamHeartbeatRef, clearStreamHeartbeat, markStreamPong, startStreamHeartbeat } = useStreamHeartbeat({ socketRef, setConnectionStatus, setPipelineStage, setStatus });
  const { holdToTalkTimerRef, holdToTalkActiveRef, holdToTalkReleasePendingRef, ignoreNextMicClickRef } = useHoldToTalk();
  const { audioSendQueueRef, sendAudioPacket, queueAudioPacket, flushAudioSendQueue, drainQueue: drainAudioSendQueue } = useAudioSendQueue({ debugLog });
  const { requestWakeLock, releaseWakeLock } = useWakeLock();
  const {
    speechRecognitionRef, speechFastPathActiveRef,
    speechFinalTextRef, speechInterimTextRef,
    speechAssistSocketRef, speechAssistRestartTimerRef, speechAssistStopRequestedRef,
    speechLastSentTextRef, speechLastSentAtRef,
  } = useSpeechFastPath();
  const { voiceWarmupRef, resolveAudioUrl, prefetchAudioUrl, warmVoiceCache } = useVoiceWarmup({
    apiUrl: liveApiUrl,
    authToken,
    targetLanguage,
    warmupPhrases: VOICE_WARMUP_PHRASES,
    cooldownMs: VOICE_WARMUP_COOLDOWN_MS,
    prefetchTimeoutMs: VOICE_PREFETCH_TIMEOUT_MS,
  });
  const appStateRef = useRef({});

  useEffect(() => {
    appStateRef.current = { interpreterMode, speakerMode, recording, processing, playing, streaming };
  }, [interpreterMode, speakerMode, recording, processing, playing, streaming]);

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
    };
  }, []);

  // Connection status polling and language loading are handled by useConnectionStatus above.
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
    setStatus('Translating text...');
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
      } else if (data.low_confidence && data.confidence_message) {
        setConfidenceWarningVisible(true);
        setConfidenceWarningMessage(data.confidence_message);
        setStatus(data.confidence_message);
      } else {
        setStatus(brainUpdate?.message || 'Text translated');
        if (settings.ttsVoice === 'browser' && data.translated_text) {
          browserTtsSpeak(data.translated_text, targetLanguage, settings.ttsSpeed ?? 1.0);
        }
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




  // diagnostics + loadDiagnostics come from useDiagnostics(API_URL) above.

  // selfTest + runSelfTest are in useSelfTest above.



  async function shareConversationRoom() {
    const mechanism = await shareRoomUrl({ sessionId, copyToClipboard });
    setStatus(mechanism === 'share' ? 'Room link shared' : 'Room link copied');
    toast(mechanism === 'share' ? 'Room link shared' : 'Room link copied', 'success', 2400);
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
    drainAudioSendQueue();
    clearTtsQueue();
  }

  function activePacketMs() {
    return activePacketMsUtil({ lowBandwidthMode, streamPacketMs: STREAM_PACKET_MS, experimentalIosStreaming: EXPERIMENTAL_IOS_STREAMING });
  }


  async function sendRecorderChunk(socket, event, recorder) {
    if (event.data.size <= 0) return;
    if (ttsPlayingRef.current) return;
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
      setCurrentError(mapTechnicalError(error));
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
      debugLog('UPLOAD: posting audio to', `${liveApiUrl}/translate/audio`, 'size', blob.size);
      const response = await fetch(`${liveApiUrl}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
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
      if (data.type === 'confidence_warning') {
        setPipelineStage('Verify translation');
        setStatus(data.message || 'Low confidence translation');
        setConfidenceWarningVisible(true);
        setConfidenceWarningMessage(data.message || 'Verify this translation with a human before acting on it.');
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
        // Browser TTS fallback: speak live translations directly when backend
        // has no voice for this language (avoids needing Google TTS API key)
        const useBrowserTts = settings.ttsVoice === 'browser' ||
          (settings.partialTts !== false && !PIPER_SUPPORTED_LANGS.has(targetLanguage));
        if (useBrowserTts && data.text && !ttsPlayingRef.current) {
          browserTtsSpeak(data.text, targetLanguage, settings.ttsSpeed ?? 1.0);
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
          setStatus('Confirmation needed before voice');
          return;
        }
        audioSendQueueRef.current = [];
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
        if (!data.partial && isIosOrSafariRecorder() && EXPERIMENTAL_IOS_STREAMING && !shouldKeepContinuousStream(socket)) {
          // Pause mic capture to route audio to speaker reliably on iOS
          resumeAfterTtsRef.current = true;
          finalizeCurrentStream('Playing voice...', { delay: false });
        }
      }
      if (data.type === 'tts_audio_chunk') {
        if (data.partial) {
          // If already playing, skip this chunk -- interrupting mid-word causes choppiness.
          // When idle, play immediately for the smoothest experience.
          if (!ttsPlayingRef.current) {
            ensureAudioUnlocked().catch((e) => console.warn('partial TTS unlock failed:', e));
            enqueueTtsChunk(data.audio_base64, data.mime_type);
          }
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
        enqueueTtsChunk(data.audio_base64, data.mime_type);
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
          setStatus('Confirmation needed before voice');
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
              if (shouldKeepContinuousStream(socket)) {
                setPipelineStage('Listening');
                setStatus('Listening for the next speaker...');
              } else {
                setPipelineStage('Voice played');
                setStatus('Voice played');
              }
              return [];
            }
            debugLog(`Playing ${chunks.length} TTS chunks sequentially (queue was idle)`);
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
        if (data.translated_text) setLiveTranslation(data.translated_text);
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
          if (!ttsPlayingRef.current && !appStateRef.current.playing) {
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
    const buffer = base64ToArrayBuffer(audioBase64);
    const bufferCopy = buffer.slice(0);
    const url = URL.createObjectURL(new Blob([bufferCopy], { type: mimeType || 'audio/wav' }));
    const item = { url, buffer: bufferCopy, mimeType: mimeType || 'audio/wav', objectUrl: true };
    ttsQueueRef.current.push(item);
    setTtsQueueLength(ttsQueueRef.current.length);
    setTtsChunksBuffer((prev) => [...prev, bufferCopy]);
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

    debugLog('playTtsItem: trying AudioContext path with crossfade');
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
            const { buffer: audioBuffer, trimmedDuration, rms } = await createTrimmedBuffer(context, rawAudioBuffer, targetRMS);
            lastChunkRMSRef.current = rms; // Store for next chunk matching
            const duration = trimmedDuration;
            
            debugLog('playTtsItem: decoded buffer, original:', rawAudioBuffer.duration.toFixed(3), 'trimmed:', duration.toFixed(3));
            
            const source = context.createBufferSource();
            source.buffer = audioBuffer;
            source.playbackRate.value = settings.ttsSpeed ?? 1.0;
            source.connect(gainNode);
            
            // Track duration for adaptive timing
            recentDurationsRef.current.push(duration);
            if (recentDurationsRef.current.length > 5) {
              recentDurationsRef.current.shift();
            }
            
            // S-curve crossfade for natural transitions
            const now = context.currentTime;
            const hasMoreChunks = ttsQueueRef.current.length > 0 || nextAudioBufferRef.current;
            applySCurveFade(gainNode, now, duration, true, hasMoreChunks);
            
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
            
            // Initialize lookahead with jitter buffer compensation
            preloadLookaheadChunks();
            if (ttsQueueRef.current.length > 0 && nextAudioBufferRef.current) {
              // Use trimmed duration for precise scheduling
              const jitterCompensation = jitterBufferMs / 1000;
              schedulePreciseNextChunk(context, now + duration + jitterCompensation);
            }
            
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
  const crossfadeDuration = 0.15; // 150ms crossfade for perfectly smooth transitions
  const overlapDuration = 0.05; // 50ms overlap between chunks
  const jitterBufferMs = 50; // Small jitter buffer for network stability
  const recentDurationsRef = useRef([]); // Track durations for adaptive timing
  const silenceThresholdDb = -60; // Silence detection threshold in dB
  const minSilenceMs = 30; // Minimum silence to trim in ms

  function getOrCreateAudioNodes(context) {
    if (!masterGainRef.current || masterGainRef.current.context !== context) {
      // Create master limiter with compressor for smooth dynamics
      masterGainRef.current = context.createGain();
      masterGainRef.current.gain.value = 0.92; // More headroom for crossfades
      
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
      setCurrentError(mapTechnicalError(error));
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
        if (data.session) applySharedSession(data.session);
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          speaker_label: label,
          stage: brainUpdate?.message || 'Complete',
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
  const recentConversationTurns = settings.showConversationHistory !== false ? conversationTurns.slice(-4) : [];
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
  const liveHudMode = liveAssistActive ? 'Instant' : perceivedListening ? 'Audio' : connectionStatus === 'online' ? 'Ready' : connectionStatus === 'warming' ? 'Starting' : 'Offline';
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
      active: playing || ttsPlaying,
    },
    {
      key: 'clear',
      label: 'Clear',
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
          volume={volume}
          onVolumeChange={handleVolumeChange}
          onOpenSettings={() => setSettingsOpen(true)}
          updateAvailable={updateAvailable}
        />
        <ConnectionQualityIndicator
          connectionStatus={connectionStatus}
          latencyMs={latencySummary.average}
          reconnectAttempt={streamReconnectRef.current || 0}
          maxReconnectAttempts={STREAM_RECONNECT_MAX_ATTEMPTS}
          isReconnecting={streaming && connectionStatus !== 'online'}
        />

        {/* Mode toggle */}
        <div className="neo-mode-toggle">
          {[
            { id: 'solo',         label: 'Solo',         icon: '🎤' },
            { id: 'conversation', label: 'Conversation', icon: '👥' },
          ].map(({ id, label, icon }) => (
            <button
              key={id}
              type="button"
              className={`neo-mode-btn${appMode === id ? ' active' : ''}`}
              onClick={() => setAppMode(id)}
            >
              <span className="neo-mode-icon">{icon}</span>
              <span>{label}</span>
            </button>
          ))}
          <span className={`neo-mode-slider ${appMode === 'conversation' ? 'shifted' : ''}`} />
        </div>

        {appMode === 'conversation' ? (
          <>
            <LanguageDock
              sourceLanguageLabel={sourceLanguageLabel}
              targetLanguageLabel={targetLanguageLabel}
              sourceLanguage={sourceLanguage}
              targetLanguage={targetLanguage}
              setSourceLanguage={setSourceLanguage}
              setTargetLanguage={setTargetLanguage}
              recording={recording}
              processing={processing}
              brainUi={brainUi}
              quickActions={quickActions}
            />
            <ConversationMode
              wsAudioUrl={`${liveWsUrl}/ws/audio`}
              authToken={authToken}
              withAuthToken={withAuthToken}
              sourceLanguage={sourceLanguage}
              targetLanguage={targetLanguage}
              sourceLanguageLabel={sourceLanguageLabel}
              targetLanguageLabel={targetLanguageLabel}
            />
          </>
        ) : (
          <>
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
          result={result}
          setClarifyVisible={setClarifyVisible}
          setPipelineStage={setPipelineStage}
          setStatus={setStatus}
          haptic={haptic}
          streaming={streaming}
          processing={processing}
          handleMicClick={handleMicClick}
          enableTypingAnimation={true}
          isTranslationActive={processing && !streaming}
          onTextTranslate={(inputText) => translateText(inputText)}
        />
        {recentConversationTurns.length > 0 && (
          <ConversationActions
            conversationTurns={recentConversationTurns}
            onClear={clearInterpreterScreen}
            onCopy={(text) => copyToClipboard(text, 'conversation')}
            disabled={streaming || processing || playing || ttsPlaying}
          />
        )}

          </>
        )}

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
      <OnboardingTour />
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
    </main>
  );
}

createRoot(document.getElementById('root')).render(<ErrorBoundary><App /></ErrorBoundary>);
