import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { View, useWindowDimensions, ScrollView, Modal, Linking, Share, AppState, DevSettings, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Constants from "expo-constants";
import { LinearGradient } from "expo-linear-gradient";
import * as SplashScreen from "expo-splash-screen";
import * as Network from "expo-network";
import * as Haptics from "expo-haptics";
import { apiToWsUrl, connectWS, wsSocketHasAuthToken, MAX_RECONNECT_ATTEMPTS } from "./services/ws";
import {
  startAudioStream,
  stopAudioStream,
  pauseAudioUpload,
  resumeAudioUpload,
  restoreRecordingAudioMode,
  isAudioUploadPaused,
  setAudioStreamQuality,
} from "./services/audio-stream";
import styles from "./AppStyles";
import { useMobileTts } from "./hooks/useMobileTts";
import { useMobileAuth, isJwtExpired } from "./hooks/useMobileAuth";
import { useMobileBrainContext } from "./hooks/useMobileBrainContext";
import { useMobileRecording } from "./hooks/useMobileRecording";
import { useMobileStreamState } from "./hooks/useMobileStreamState";
import { useMobileSession } from "./hooks/useMobileSession";
import { useMobileConnectionState } from "./hooks/useMobileConnectionState";
import { useMobileUiState } from "./hooks/useMobileUiState";
import WelcomeSetupModal from "./components/WelcomeSetupModal";
import ErrorBanner from "./components/ErrorBanner";
import NativeSpeakerCertBanner from "./components/NativeSpeakerCertBanner";
import {
  humanCertStep,
  certificationBanner,
  shouldBlockTtsForCert,
  certTurnFlags,
  resolveConfidenceWarning,
} from "./utils/humanCertification";
import { extractBrainPlan, shouldSkipBrainTts, uniqueStrings } from "./utils/brainPlan";
import ClarifyPill from "./components/ClarifyPill";
import BrainRepairPanel from "./components/BrainRepairPanel";
import SettingsScreen from "./components/SettingsScreen";
import LanguagePickerModal, { LANGUAGE_OPTIONS } from "./components/LanguagePickerModal";
import LoadingScreen from "./components/LoadingScreen";
import Toast from "./components/Toast";
import HelpTipsModal from "./components/HelpTipsModal";
import NeoHeader from "./components/NeoHeader";
import MicOrbButton from "./components/MicOrbButton";
import DebugInsightsPanel from "./components/DebugInsightsPanel";
import SessionInsightsPanel from "./components/SessionInsightsPanel";
import AdvancedFeatures from "./components/AdvancedFeatures";
import LiveStatusPanel from "./components/LiveStatusPanel";
import VoiceMeter from "./components/VoiceMeter";
import ProcessingPill from "./components/ProcessingPill";
import EmptyTranscriptState from "./components/EmptyTranscriptState";
import FloatingMicFab from "./components/FloatingMicFab";
import StatusStrip from "./components/StatusStrip";
import LaneCopyDock from "./components/LaneCopyDock";
import TurnHistoryRail from "./components/TurnHistoryRail";
import ContextChip from "./components/ContextChip";
import SemanticContext from "./components/SemanticContext";
import Assistant from "./components/Assistant";
import LanguageRouteBand from "./components/LanguageRouteBand";
import ControlDock from "./components/ControlDock";
import OfflineConnectCard from "./components/OfflineConnectCard";
import LaneLiveText from "./components/LaneLiveText";
import ConnectionStrip from "./components/ConnectionStrip";
import StopListeningButton from "./components/StopListeningButton";
import MicPanelFrame from "./components/MicPanelFrame";
import FlowRail from "./components/FlowRail";
import SpeakingLaneGlow from "./components/SpeakingLaneGlow";
import LaneBridgeSpan from "./components/LaneBridgeSpan";
import CosmicAmbience from "./components/CosmicAmbience";
import DebugDetailChips from "./components/DebugDetailChips";
import PanelListeningPulse from "./components/PanelListeningPulse";
import LaneHeader from "./components/LaneHeader";
import RouteModeStrip from "./components/RouteModeStrip";
import DuplexConversationPanel from "./components/DuplexConversationPanel";
import TranscriptStackHeader from "./components/TranscriptStackHeader";
import * as Clipboard from "expo-clipboard";
import * as SecureStore from "expo-secure-store";
import { MOBILE_BUILD_ID } from "./constants/mobileBuild";
import {
  getConsumerCloudApiUrl,
  getConsumerDemoCredentials,
  hasConsumerCloudBackend,
} from "./constants/consumerCloud";
import { FOCUSED_PRODUCT_UI, showAdvancedInterpreterChrome } from "./constants/productMode";
import {
  FLOW_STEPS,
  micHint as productMicHint,
  sourcePlaceholder,
  targetPlaceholder,
  transcriptHeaderLabel,
  transcriptExchangeLabel,
  liveStatusLabel,
  statusStripDetail,
  offlineConnectCopy,
  modeToggleStatus,
  modeToggleToast,
  modeToggleA11y,
  processingPillMessage,
  copyToasts,
  primaryMicLabels,
  dockLabels,
  voiceIntentDefault,
  normalizeConnectionStatus,
  bridgeModeDebugLabel,
  reconnectFailureMessage,
  socketStatusMessages,
  laneHeaderLabel,
  clearPanelCopy,
  bandwidthToasts,
  replayStatusMessages,
  pauseBridgeToast,
  connectionLifecycleMessages,
  wsBridgeStatuses,
  bridgeActionMessages,
} from "./constants/productVoice";
import { shouldAutoReloadForMetro } from "./utils/metroBuildReload";
import { AUDIO_QUALITIES, AUDIO_QUALITY_KEY, LOW_BANDWIDTH_KEY } from "./constants/audioQuality";
import { useMobileDiagnostics } from "./hooks/useMobileDiagnostics";
import { mapSessionHistoryToTurns, latestSessionTurn } from "./utils/sessionRestore";
import ConfidenceWarningBanner from "./components/ConfidenceWarningBanner";
import ReconnectFailureBanner from "./components/ReconnectFailureBanner";
import ConversationQualityStack from "./components/ConversationQualityStack";
import { resolvePipelineStageLabel } from "./utils/wsMessageTypes";
import { getFriendlyPanelState, getFriendlyStatusLine } from "./utils/friendlyStatus";
import {
  checkBackendHealthUrl,
  deriveApiUrlFromExpo,
  fetchMobileConnectInfo,
  probeMetroBuildId,
  resolveServerUrl,
  waitForBackendReady,
} from "./utils/discoverServer";
import {
  isLocalLanServerUrl,
  isNetworkTypeKnown,
  isPhoneOnWifi,
  needsWifiForLanServer,
} from "./utils/serverUrl";

const HELP_SEEN_KEY = "translator_help_seen";
const MOBILE_BUILD_KEY = "mobile_build_id";

SplashScreen.preventAutoHideAsync().catch(() => {});

const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  Constants.expoConfig?.extra?.apiUrl ||
  deriveApiUrlFromExpo() ||
  "";
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === "1");
const BRIDGE_CONN = connectionLifecycleMessages();
const WS_STATUS = wsBridgeStatuses();
const BRIDGE_ACTION = bridgeActionMessages();

const LANGUAGES = [
  { code: "en", label: "English", aliases: ["english", "american"] },
  { code: "es", label: "Spanish", aliases: ["spanish", "espanol"] },
  { code: "ht", label: "Haitian Creole", aliases: ["haitian creole", "haitian", "creole"] },
  { code: "fr", label: "French", aliases: ["french"] },
  { code: "de", label: "German", aliases: ["german"] },
  { code: "it", label: "Italian", aliases: ["italian"] },
  { code: "pt", label: "Portuguese", aliases: ["portuguese"] },
  { code: "nl", label: "Dutch", aliases: ["dutch"] },
  { code: "ru", label: "Russian", aliases: ["russian"] },
  { code: "zh", label: "Chinese", aliases: ["chinese", "mandarin"] },
  { code: "ja", label: "Japanese", aliases: ["japanese"] },
  { code: "ko", label: "Korean", aliases: ["korean"] },
  { code: "ar", label: "Arabic", aliases: ["arabic"] },
  { code: "hi", label: "Hindi", aliases: ["hindi"] },
];

const LANGUAGE_BY_CODE = Object.fromEntries(LANGUAGES.map((language) => [language.code, language]));
const LANGUAGE_FLAGS = Object.fromEntries(LANGUAGE_OPTIONS.map((language) => [language.code, language.flag]));

async function tapHaptic(style = "light") {
  try {
    if (style === "success") {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } else if (style === "warning") {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    } else if (style === "medium") {
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } else {
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  } catch {
    // Haptics optional on some devices.
  }
}

function debugLog(...args) {
  if (DEBUG_LOGS) console.debug(...args);
}

function getStatusColor(statusType) {
  switch (statusType) {
    case "success":
      return "#16a34a";
    case "error":
      return "#ef4444";
    case "warning":
      return "#f59e0b";
    case "connecting":
      return "#22d3ee";
    default:
      return "#94a3b8";
  }
}

function getLanguageLabel(code) {
  return LANGUAGE_BY_CODE[code]?.label || String(code || "").toUpperCase();
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeSpeech(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^(hey\s+)?(anai|translator)\s+/, "");
}

function languageMentions(text) {
  const hits = [];
  for (const language of LANGUAGES) {
    let firstIndex = -1;
    for (const alias of language.aliases) {
      const match = text.match(new RegExp(`\\b${escapeRegex(alias)}\\b`));
      if (match?.index !== undefined && (firstIndex < 0 || match.index < firstIndex)) {
        firstIndex = match.index;
      }
    }
    if (firstIndex >= 0) {
      hits.push({ code: language.code, index: firstIndex });
    }
  }
  return hits.sort((a, b) => a.index - b.index);
}

function isSingleLanguageCommand(phrase, code) {
  const language = LANGUAGE_BY_CODE[code];
  if (!language) return false;
  return language.aliases.some((alias) => {
    const aliasPattern = escapeRegex(alias);
    return new RegExp(`^(to|into|in|speak|say|translate|interpret|set|switch|change)?\\s*${aliasPattern}\\s*(please)?$`).test(phrase);
  });
}

function parseVoiceIntent(text, sourceLanguage, targetLanguage) {
  const phrase = normalizeSpeech(text);
  if (!phrase) return null;

  if (/\b(barrier|conversation|interpreter|two way|both ways)\s+(mode\s+)?(on|start|enable)\b/.test(phrase)) {
    return { type: "barrier", enabled: true };
  }
  if (/\b(barrier|conversation|interpreter|two way|both ways)\s+(mode\s+)?(off|stop|disable)\b/.test(phrase)) {
    return { type: "barrier", enabled: false };
  }
  if (/^(stop|pause|end|finish)(\s+(listening|translation|translating|interpreting|interpreter|stream|session))?$/.test(phrase)) {
    return { type: "stop" };
  }
  if (/^(start|begin|resume|listen)(\s+(listening|translation|translating|interpreting|interpreter|stream|session))?$/.test(phrase)) {
    return { type: "start" };
  }
  if (/\b(connect|reconnect|link)\b/.test(phrase)) {
    return { type: "connect" };
  }
  if (/^(disconnect|unlink|close link|close connection)(\s+(translator|connection|link))?$/.test(phrase)) {
    return { type: "disconnect" };
  }
  if (/^(clear|reset)$/.test(phrase) || /\b(clear|reset)\s+(conversation|screen|panel|translation)\b/.test(phrase)) {
    return { type: "clear" };
  }
  if (
    /^(replay|repeat|play again)(\s+(that|last|voice|translation|last translation|last voice))?$/.test(phrase) ||
    /^say\s+(that\s+)?again$/.test(phrase)
  ) {
    return { type: "replay" };
  }
  if (/^(swap|flip)$/.test(phrase) || /\b(swap|flip)\s+(languages|sides|direction)\b/.test(phrase)) {
    return { type: "swap" };
  }
  if (/\b(louder|volume up|turn up|increase volume)\b/.test(phrase)) {
    return { type: "volume", delta: 0.12 };
  }
  if (/\b(quieter|volume down|turn down|decrease volume|softer)\b/.test(phrase)) {
    return { type: "volume", delta: -0.12 };
  }
  if (/\b(slower|slow down|speak slower)\b/.test(phrase)) {
    return { type: "speed", delta: -0.08 };
  }
  if (/\b(faster|speed up|speak faster)\b/.test(phrase)) {
    return { type: "speed", delta: 0.08 };
  }

  const mentions = languageMentions(phrase);
  const routeIntent = /\b(translate|interpret|speak|language|switch|change|set|from|to|into|in|between|conversation|barrier|two way|both ways)\b/.test(phrase);
  if ((routeIntent || /\b(from|to|into|between)\b/.test(phrase)) && mentions.length >= 2) {
    const barrierRoute = /\b(between|conversation|barrier|two way|both ways|interpreter)\b/.test(phrase);
    const oneWayRoute = /\b(one way|from)\b/.test(phrase) && /\bto\b/.test(phrase) && !barrierRoute;
    return {
      type: "route",
      source: mentions[0].code,
      target: mentions[1].code,
      barrier: !oneWayRoute,
    };
  }
  if ((routeIntent || isSingleLanguageCommand(phrase, mentions[0]?.code)) && mentions.length === 1) {
    return {
      type: "route",
      source: sourceLanguage,
      target: mentions[0].code || targetLanguage,
    };
  }

  return null;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function asBool(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (value == null) return false;
  return ["1", "true", "yes", "on", "auto", "barrier"].includes(String(value).trim().toLowerCase());
}

export default function App({ bootstrapApiUrl = "" } = {}) {
  const appStateRef = useRef(AppState.currentState || "active");
  const { height, width } = useWindowDimensions();
  const { status, setStatus, statusType, setStatusType, isConnected, setIsConnected, isConnectedRef, networkState, setNetworkState } = useMobileConnectionState();
  const { sourceLanguage, setSourceLanguage, targetLanguage, setTargetLanguage, mobileDeviceIdRef, mobileSessionIdRef } = useMobileSession();
  const { result, setResult, showSettings, setShowSettings } = useMobileUiState();
  const {
    isStreaming,
    setIsStreaming,
    partialTranscript,
    setPartialTranscript,
    liveTranslation,
    setLiveTranslation,
    wsControlRef,
    resumeAfterTtsRef,
    isStreamingRef,
    recording,
    setRecording,
  } = useMobileStreamState();
  const {
    semanticContext,
    setSemanticContext,
    conversationBrain,
    setConversationBrain,
    emotionInfo,
    setEmotionInfo,
    clarifyVisible,
    setClarifyVisible,
    clarifyMessage,
    setClarifyMessage,
    brainUi,
    setBrainUi,
    brainHintsRef,
    brainPlanRef,
    resetBrainRuntimeUi,
  } = useMobileBrainContext();
  const {
    ttsQueue,
    isPlayingTts,
    setIsPlayingTts,
    isPlayingTtsRef,
    handleTtsChunk,
    playNextTtsChunk,
    ttsQueueRef,
    replayLastTts,
    clearTtsQueue,
    clearReplayAudio,
    volume,
    setVolume,
    playbackSpeed,
    setPlaybackSpeed,
    stopTtsPlayback,
    applyTtsStyle,
    setOnPlaybackIdle,
    hasReplayAudio,
  } = useMobileTts(appStateRef);
  const {
    token,
    setToken,
    wsUrl,
    editWsUrl,
    username,
    setUsername,
    password,
    setPassword,
    recentUrls,
    showRecentUrls,
    setShowRecentUrls,
    backendReachable,
    markBackendReachable,
    setupComplete,
    discoveryComplete,
    isCheckingBackend,
    loadStoredData,
    saveWsUrl,
    markSetupComplete,
    validateUrl,
    checkBackendHealth,
    login,
    logout,
    clearAllData,
    saveRecentUrl,
    cancelLogin,
    cancelDiscovery,
  } = useMobileAuth({
    defaultUrl: bootstrapApiUrl || API_URL,
    onStatus: (message, type) => {
      if (message === "Token restored" && !isConnectedRef.current) return;
      setStatus(message);
      if (type && !(type === "success" && !isConnectedRef.current && /restored|logged in/i.test(message))) {
        setStatusType(type);
      }
    },
  });

  const [showSetup, setShowSetup] = useState(false);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [showDebugDetails, setShowDebugDetails] = useState(false);
  const [dismissedError, setDismissedError] = useState("");
  const [languagePicker, setLanguagePicker] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [showAssistant, setShowAssistant] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const toggleStreamingRef = useRef(null);
  const autoConnectStartedRef = useRef(false);
  const autoLoginAttemptedRef = useRef(false);
  const userPausedConnectionRef = useRef(false);
  const lastProbedUrlRef = useRef(null);
  const lastConnectedApiUrlRef = useRef("");
  const prevNetworkConnectedRef = useRef(null);
  const prevNetworkTypeRef = useRef(null);
  const networkStateRef = useRef(null);
  const beginServerConnectionRef = useRef(() => {});
  const retryConnectionRef = useRef(() => {});
  const lastConnectAttemptRef = useRef(0);
  const connectScheduleRef = useRef(null);
  const connectInFlightRef = useRef(false);
  const loginInFlightRef = useRef(false);
  const scheduleServerConnectionRef = useRef(() => {});
  const wsUrlRef = useRef(wsUrl);
  const setupCompleteRef = useRef(setupComplete);
  const tokenRef = useRef("");
  const sessionHandshakeRef = useRef(false);
  const serverReadyRef = useRef(false);
  const handshakeTimerRef = useRef(null);
  const handshakeWaitTimerRef = useRef(null);
  const helpTimerRef = useRef(null);
  const warmingRetryTimerRef = useRef(null);
  const recoverableRetryTimerRef = useRef(null);
  const tunnelFallbackInFlightRef = useRef(false);
  const tunnelRefreshInFlightRef = useRef(false);
  const tunnelFallbackCooldownRef = useRef(0);
  const lanConnectFailRef = useRef(0);
  const backendReachableRef = useRef(null);
  const mobileConnectInfoRef = useRef(null);
  const isInterpreterActiveRef = useRef(false);
  const startingStreamRef = useRef(false);
  const autoResumeTimerRef = useRef(null);
  const suppressTurnAudioRef = useRef(false);
  const suppressReleaseTimerRef = useRef(null);
  const latencyStartRef = useRef({});
  const streamStartedAtRef = useRef(0);
  const firstAudioSeenRef = useRef(false);
  const lowBandwidthModeRef = useRef(false);
  const [isInterpreterActive, setIsInterpreterActive] = useState(false);
  const [turnCount, setTurnCount] = useState(0);
  const [audioQuality, setAudioQuality] = useState("HIGH");
  const [audioEnvironment, setAudioEnvironment] = useState("auto");
  const audioEnvironmentRef = useRef("auto");
  const [lowBandwidthMode, setLowBandwidthMode] = useState(false);
  const [confidenceWarningVisible, setConfidenceWarningVisible] = useState(false);
  const [confidenceWarningMessage, setConfidenceWarningMessage] = useState("");
  const {
    startRecording: startBatchRecording,
    stopRecording: stopBatchRecording,
    cancelUpload: cancelBatchUpload,
    isUploading: isBatchUploading,
    uploadProgress: batchUploadProgress,
  } = useMobileRecording({
    isConnected,
    isStreaming,
    sourceLanguage,
    targetLanguage,
    wsUrl,
    token,
    recording,
    setRecording,
    setStatus,
    setStatusType,
    setResult,
    isPlayingTtsRef,
    setIsPlayingTts,
    audioQuality,
    shouldUpload: () => appStateRef.current === "active",
  });
  const [voiceIntent, setVoiceIntent] = useState(voiceIntentDefault());
  const [barrierMode, setBarrierMode] = useState(true);
  const [liveAudioLevel, setLiveAudioLevel] = useState(0);
  const [mobileConnectInfo, setMobileConnectInfo] = useState(null);
  const liveAudioLevelRef = useRef(0);
  const [transcriptScrolled, setTranscriptScrolled] = useState(false);
  const transcriptScrollRef = useRef(null);
  const translationLaneOffsetRef = useRef(0);
  const volumeToastTimerRef = useRef(null);
  const speedToastTimerRef = useRef(null);
  const reconcileDebounceRef = useRef(null);
  const networkRecheckRef = useRef(null);
  const networkDisconnectDebounceRef = useRef(null);
  const mountedRef = useRef(true);
  const connectGenerationRef = useRef(0);
  const activeHandlerGenerationRef = useRef(0);
  const handleMessageRef = useRef(() => {});
  const setStatusWithTypeRef = useRef(() => {});
  const [speakerRoute, setSpeakerRoute] = useState({
    speakerLabel: "Person 1",
    speakerIndex: 1,
    listenerLabel: "Person 2",
    sourceLanguage,
    targetLanguage,
    routeConfidence: 1,
    detectedLanguage: sourceLanguage,
  });
  const [meaningCheck, setMeaningCheck] = useState("");
  const [humanCertificationStep, setHumanCertificationStep] = useState("none");
  const humanCertStepRef = useRef("none");
  const [reconnectProgress, setReconnectProgress] = useState(null);
  const [reconnectFailureVisible, setReconnectFailureVisible] = useState(false);
  const [sessionReconnects, setSessionReconnects] = useState(0);
  const [conversationTurns, setConversationTurns] = useState([]);
  const [latencyMetrics, setLatencyMetrics] = useState({
    sttLatency: 0,
    translationLatency: 0,
    ttsLatency: 0,
    endToEndLatency: 0,
    lastUpdate: 0,
  });

  const apiBaseUrl = useMemo(() => String(wsUrl || API_URL || "").trim().replace(/\/+$/, ""), [wsUrl]);
  const { diagnostics, diagnosticsStatus, loadDiagnostics } = useMobileDiagnostics(apiBaseUrl);
  const activeSource = getLanguageLabel(sourceLanguage);
  const activeTarget = getLanguageLabel(targetLanguage);
  const routeSource = getLanguageLabel(speakerRoute.sourceLanguage || sourceLanguage);
  const routeTarget = getLanguageLabel(speakerRoute.targetLanguage || targetLanguage);
  const activeSpeakerLabel = speakerRoute.speakerLabel || "Person 1";
  const routeConfidence = Number(speakerRoute.routeConfidence || 0);
  const routeConfidenceLabel = routeConfidence > 0 ? `${Math.round(routeConfidence * 100)}% route` : null;
  const barrierLabel = bridgeModeDebugLabel(barrierMode);
  const compactLayout = height < 730 || width < 370;
  const tinyLayout = height < 650;
  const advancedChrome = showAdvancedInterpreterChrome(showDebugDetails);
  const systemColor = getStatusColor(statusType);
  const isConnecting = statusType === "connecting";
  const onCellularWithLanServer = needsWifiForLanServer(networkState, wsUrl);
  const panelState = getFriendlyPanelState({
    isPlayingTts,
    isStreaming,
    isInterpreterActive,
    isConnected,
    isConnecting,
    needsWifi: onCellularWithLanServer,
    status,
  });
  const friendlyStatusLine = getFriendlyStatusLine(status, {
    isConnected,
    isConnecting,
    needsWifi: onCellularWithLanServer,
  });
  const sourceText = partialTranscript || result?.source_text || result?.original_text || "";
  const translatedText = liveTranslation || result?.translated_text || "";
  const intentLine = useMemo(() => {
    if (semanticContext?.last_intent) return semanticContext.last_intent;
    if (semanticContext?.intent) return semanticContext.intent;
    return voiceIntent;
  }, [semanticContext, voiceIntent]);
  const flowDetail = conversationBrain || intentLine;
  const isTranslating = !isPlayingTts && /translat|understand/i.test(status || "");
  const flowActiveKey = isPlayingTts
    ? "speak"
    : isTranslating
      ? "translate"
      : translatedText && !isStreaming
        ? "bridge"
        : isStreaming || isInterpreterActive
          ? "listen"
          : "";
  const liveStatusMode = humanCertificationStep === "required"
    ? "cert_required"
    : humanCertificationStep === "advisory"
      ? "cert_advisory"
      : clarifyVisible
        ? "clarify"
        : isPlayingTts
          ? "speaking"
          : isTranslating
            ? "translating"
            : isStreaming
              ? "listening"
              : "armed";
  const liveStatusVisible = isConnected && (
    isStreaming
    || isPlayingTts
    || isTranslating
    || isInterpreterActive
    || humanCertificationStep !== "none"
    || clarifyVisible
  );
  const liveStatusText = liveStatusLabel(liveStatusMode, {
    clarifyMessage,
    certStep: humanCertificationStep,
  });
  const translationCertAttention = humanCertificationStep === "required"
    ? "required"
    : humanCertificationStep === "advisory"
      ? "advisory"
      : "";

  useEffect(() => {
    if (!isConnected) return undefined;
    if (
      humanCertificationStep === "none"
      && !clarifyVisible
      && !brainUi?.visible
      && !confidenceWarningVisible
    ) {
      return undefined;
    }
    const timer = setTimeout(() => {
      const offset = Math.max(0, translationLaneOffsetRef.current - 12);
      transcriptScrollRef.current?.scrollTo({ y: offset, animated: true });
    }, 160);
    return () => clearTimeout(timer);
  }, [
    isConnected,
    humanCertificationStep,
    clarifyVisible,
    brainUi?.visible,
    confidenceWarningVisible,
  ]);

  const latestLatency = latencyMetrics.endToEndLatency || latencyMetrics.ttsLatency || latencyMetrics.translationLatency;
  const phoneSetupUrl = useMemo(() => {
    const base = String(wsUrl || API_URL || "").trim().replace(/\/+$/, "");
    return base ? `${base}/mobile` : "";
  }, [wsUrl]);
  const webAppUrl = useMemo(() => {
    const base = String(wsUrl || API_URL || "").trim().replace(/\/+$/, "");
    return base ? `${base}/mobile/app` : "";
  }, [wsUrl]);
  const webAppHttpsUrl = useMemo(() => {
    const fromInfo = String(mobileConnectInfo?.web_app_https_url || "").trim();
    if (fromInfo) return fromInfo;
    const httpsBase = String(mobileConnectInfo?.backend_https_url || "").trim().replace(/\/+$/, "");
    if (httpsBase) return `${httpsBase}/mobile/app`;
    const base = String(wsUrl || API_URL || "").trim().replace(/\/+$/, "");
    if (!base) return "";
    const httpsPort = Number(mobileConnectInfo?.https_port) || 8443;
    try {
      const parsed = new URL(base);
      parsed.protocol = "https:";
      parsed.port = String(httpsPort);
      parsed.pathname = "/mobile/app";
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString();
    } catch {
      return "";
    }
  }, [wsUrl, mobileConnectInfo]);
  const preferredWebAppUrl = Platform.OS === "ios" && webAppHttpsUrl ? webAppHttpsUrl : webAppUrl;
  const buildTag = MOBILE_BUILD_ID.replace(/^.*-/, "");
  const friendlyStatusDetail = statusStripDetail({
    activeSource,
    activeTarget,
    isInterpreterActive,
    isConnected,
    twoWay: barrierMode,
    turnCount,
  });
  const offlineStatusDetail = onCellularWithLanServer
    ? "Join same Wi‑Fi as your PC · then Link bridge"
    : isConnecting
      ? `Linking bridge · Build ${MOBILE_BUILD_ID}`
      : `Build ${MOBILE_BUILD_ID} · tap Link bridge or Start`;
  const debugStatusDetail = [
    flowDetail,
    barrierLabel,
    meaningCheck ? "Check meaning" : null,
    routeConfidenceLabel,
    latestLatency ? `${latestLatency}ms` : null,
    ttsQueue.length > 0 ? `${ttsQueue.length} queued` : null,
  ].filter(Boolean).join(" | ");
  const statusDetail = !isConnected
    ? offlineStatusDetail
    : showDebugDetails
      ? debugStatusDetail
      : friendlyStatusDetail;
  const visibleStatusLine = !isConnected
    ? (friendlyStatusLine || panelState)
    : showDebugDetails
      ? (status || panelState)
      : (friendlyStatusLine || panelState);
  const blockingError = (() => {
    if (dismissedError && status === dismissedError) return null;
    if (onCellularWithLanServer && !isConnected) {
      return {
        message: "Phone is on cellular — join the SAME Wi‑Fi as your PC, or wait while we find a remote bridge server.",
        action: "Retry",
        handler: async () => {
          await checkNetworkState();
          tunnelFallbackCooldownRef.current = 0;
          await attemptTunnelFallbackForNetwork(networkStateRef.current);
          retryConnection();
        },
      };
    }
    if (networkState?.isConnected === false && !isLocalLanServerUrl(wsUrl)) {
      return {
        message: "No network connection. Join Wi‑Fi to link the bridge (internet not required for local server).",
        action: "Retry",
        handler: async () => {
          await checkNetworkState();
          retryConnection();
        },
      };
    }
    if (!isConnected && setupComplete && validateUrl(wsUrl)) {
      if (backendReachable === false) {
        const apNote = isPhoneOnWifi(networkState) && isLocalLanServerUrl(wsUrl)
          ? " Router may block phone-to-PC — trying remote server."
          : "";
        return {
          message: `Cannot reach ${wsUrl}. Same Wi‑Fi as PC? Firewall open on port 8000?${apNote}`,
          action: "Retry",
          handler: async () => {
            tunnelFallbackCooldownRef.current = 0;
            await attemptRemoteServerFallback();
            retryConnection();
          },
        };
      }
      if (!isConnecting && !/connecting|handshaking|reconnect/i.test(status || "")) {
        return {
          message: `Bridge not linked. Tap Link bridge to open the conversation (server: ${wsUrl}).`,
          action: "Link bridge",
          handler: retryConnection,
        };
      }
    }
    if (statusType === "error") {
      if (/microphone|mic/i.test(status || "")) {
        return {
          message: status,
          action: "Open Settings",
          handler: async () => {
            try {
              await Linking.openSettings();
            } catch {
              showToast("Settings → Expo Go → Microphone ON", "error", 4000);
            }
          },
        };
      }
      if (/backend|url|reachable|connection failed/i.test(status || "")) {
        return { message: status, action: "Bridge setup", handler: () => setShowSetup(true) };
      }
      return { message: status, action: "Retry", handler: retryConnection };
    }
    return null;
  })();
  const needsServerLink = !isConnected && !isConnecting;
  const micLabels = primaryMicLabels({
    isPlayingTts,
    isStreaming,
    isInterpreterActive,
    needsServerLink,
    isConnecting,
  });
  const primaryActionLabel = micLabels.action;
  const primaryButtonText = micLabels.button;
  const dockCopy = dockLabels({ isConnected, twoWay: barrierMode });
  const toasts = copyToasts();
  const primaryIcon = isPlayingTts
    ? "stop"
    : isStreaming
      ? "pause"
      : needsServerLink
      ? "link"
      : isConnecting && !isInterpreterActive
        ? "sync"
        : isInterpreterActive
          ? "radio"
          : "mic";
  const showOfflineCta = authLoaded && !showSetup && !isConnected && !isConnecting && validateUrl(wsUrl);
  const micHint = isStreaming
    ? "Tap to pause listening"
    : productMicHint({
      needsServerLink,
      isStreaming,
      isPlayingTts,
      isInterpreterActive,
      twoWay: barrierMode,
    });

  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  useEffect(() => {
    backendReachableRef.current = backendReachable;
  }, [backendReachable]);

  useEffect(() => {
    mobileConnectInfoRef.current = mobileConnectInfo;
  }, [mobileConnectInfo]);

  useEffect(() => {
    networkStateRef.current = networkState;
  }, [networkState]);

  useEffect(() => {
    if (!authLoaded || !token || userPausedConnectionRef.current || appStateRef.current !== "active") return;
    const activeUrl = getActiveWsUrl();
    if (!validateUrl(activeUrl)) return;
    const expectedUrl = apiToWsUrl(activeUrl, "/ws/audio", token);
    const socketUrl = wsControlRef.current?.getUrl?.() || "";
    if (socketUrl && socketUrl !== expectedUrl) {
      scheduleServerConnectionRef.current(200);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, token, wsUrl]);

  useEffect(() => {
    wsUrlRef.current = wsUrl;
  }, [wsUrl]);

  useEffect(() => {
    const base = String(wsUrl || "").trim().replace(/\/+$/, "");
    if (!validateUrl(base)) {
      setMobileConnectInfo(null);
      return;
    }
    if (appStateRef.current !== "active") return;
    let cancelled = false;
    fetchMobileConnectInfo(base, {
      shouldAbort: () => cancelled || appStateRef.current !== "active",
    })
      .then(async (info) => {
        if (
          cancelled
          || !mountedRef.current
          || appStateRef.current !== "active"
          || userPausedConnectionRef.current
        ) return;
        setMobileConnectInfo(info);
        const tunnelUrl = String(info?.tunnel_backend_url || "").trim().replace(/\/+$/, "");
        const activeUrl = getActiveWsUrl();
        if (
          tunnelUrl
          && validateUrl(tunnelUrl)
          && isLocalLanServerUrl(activeUrl)
          && tunnelUrl !== activeUrl
          && !isSocketBusy()
          && (
            needsWifiForLanServer(networkStateRef.current, activeUrl)
            || backendReachableRef.current === false
          )
        ) {
          tunnelFallbackCooldownRef.current = 0;
          if (
            !cancelled
            && mountedRef.current
            && appStateRef.current === "active"
            && !userPausedConnectionRef.current
          ) {
            await attemptRemoteServerFallback();
          }
        }
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) setMobileConnectInfo(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl]);

  useEffect(() => {
    setupCompleteRef.current = setupComplete;
  }, [setupComplete]);

  function reloadApp() {
    try {
      DevSettings.reload();
    } catch (error) {
      console.error("DevSettings.reload failed:", error);
      showToast("Shake phone and tap Reload in Expo Go", "error");
    }
  }

  useEffect(() => {
    if (!authLoaded) return;
    let cancelled = false;
    (async () => {
      try {
        const seenBuild = await SecureStore.getItemAsync(MOBILE_BUILD_KEY);
        if (cancelled) return;
        if (!seenBuild || seenBuild !== MOBILE_BUILD_ID) {
          // Bundle in memory is already MOBILE_BUILD_ID; only persist — do not reload here.
          // BootstrapGate handles Metro-ahead reloads via shouldAutoReloadForMetro.
          await SecureStore.setItemAsync(MOBILE_BUILD_KEY, MOBILE_BUILD_ID);
        }
      } catch (error) {
        console.error("Build version check failed:", error);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoaded]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await SecureStore.getItemAsync(AUDIO_QUALITY_KEY);
        if (cancelled || !stored || !AUDIO_QUALITIES[stored]) return;
        setAudioQuality(stored);
        setAudioStreamQuality(stored);
      } catch {
        // Keep default HIGH quality.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await SecureStore.getItemAsync(LOW_BANDWIDTH_KEY);
        if (cancelled) return;
        const enabled = stored === "1" || stored === "true";
        lowBandwidthModeRef.current = enabled;
        setLowBandwidthMode(enabled);
      } catch {
        // Keep default off.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    lowBandwidthModeRef.current = lowBandwidthMode;
  }, [lowBandwidthMode]);

  async function updateLowBandwidthMode(enabled) {
    setLowBandwidthMode(enabled);
    lowBandwidthModeRef.current = enabled;
    try {
      await SecureStore.setItemAsync(LOW_BANDWIDTH_KEY, enabled ? "1" : "0");
    } catch {
      // Non-fatal if persistence fails.
    }
    const bw = bandwidthToasts();
    showToast(enabled ? bw.lowOn : bw.lowOff, "success");
  }

  async function updateAudioQuality(quality) {
    if (!AUDIO_QUALITIES[quality]) return;
    setAudioQuality(quality);
    setAudioStreamQuality(quality);
    try {
      await SecureStore.setItemAsync(AUDIO_QUALITY_KEY, quality);
    } catch {
      // Non-fatal if persistence fails.
    }
    showToast(`${AUDIO_QUALITIES[quality].label} audio quality`, "success");
  }

  async function probeRemoteBuildId() {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return;
    let preferredPort = "";
    const activeUrl = getActiveWsUrl();
    if (validateUrl(activeUrl)) {
      try {
        const info = await fetchMobileConnectInfo(activeUrl, {
          shouldAbort: () => !mountedRef.current || appStateRef.current !== "active",
        });
        if (!mountedRef.current) return;
        preferredPort = String(info?.expo_port || "").trim();
      } catch {
        // Non-fatal if /mobile/info is unreachable.
      }
    }
    const metroProbe = await probeMetroBuildId(undefined, preferredPort, {
      shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
    });
    if (!mountedRef.current) return;
    const metroBuild = String(metroProbe?.buildId || "").trim();
    if (!metroBuild || metroBuild === MOBILE_BUILD_ID) return;
    if (!mountedRef.current) return;
    if (await shouldAutoReloadForMetro(metroBuild, MOBILE_BUILD_ID)) {
      await SecureStore.setItemAsync(MOBILE_BUILD_KEY, MOBILE_BUILD_ID);
      reloadApp();
    }
  }

  useEffect(() => {
    if (!authLoaded) return;
    probeRemoteBuildId();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded]);

  useEffect(() => {
    if (!authLoaded) return;
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active") probeRemoteBuildId();
    });
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded]);

  useEffect(() => {
    if (!authLoaded || isConnected) return;
    setShowDebugDetails(false);
    if (/network restored/i.test(status || "")) {
      setStatus(onCellularWithLanServer ? BRIDGE_CONN.joinWifi : BRIDGE_CONN.linking);
      setStatusType(onCellularWithLanServer ? "warning" : "connecting");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, isConnected, onCellularWithLanServer]);

  useEffect(() => {
    if (!isStreaming) {
      liveAudioLevelRef.current = 0;
      setLiveAudioLevel(0);
      return undefined;
    }
    const timer = setInterval(() => {
      if (appStateRef.current !== "active") return;
      setLiveAudioLevel((prev) => {
        const next = liveAudioLevelRef.current;
        return Math.abs(prev - next) > 0.02 ? next : prev;
      });
    }, 80);
    return () => clearInterval(timer);
  }, [isStreaming]);

  async function openExternalUrl(url, label = "link") {
    const target = String(url || "").trim();
    if (!target) {
      showToast(`${label} not ready yet`, "error");
      return;
    }
    try {
      const opened = await Linking.openURL(target);
      if (!opened) showToast(`Open in Safari: ${target}`, "info");
    } catch {
      showToast(`Open in Safari: ${target}`, "info");
    }
  }

  async function openPhoneSetupPage() {
    await openExternalUrl(phoneSetupUrl, "Setup page");
  }

  async function openWebInterpreter() {
    await openExternalUrl(preferredWebAppUrl || webAppUrl, "Safari bridge");
  }

  useEffect(() => {
    let cancelled = false;
    const splashFallback = setTimeout(() => {
      SplashScreen.hideAsync().catch(() => {});
    }, 3000);

    (async () => {
      try {
        await loadStoredData();
      } catch (error) {
        console.error("Error loading stored auth data:", error);
      } finally {
        if (!cancelled) {
          setAuthLoaded(true);
          SplashScreen.hideAsync().catch(() => {});
          clearTimeout(splashFallback);
        }
      }
    })();

    checkNetworkState();
    const interval = setInterval(() => {
      if (appStateRef.current === "active") checkNetworkState();
    }, 5000);
    const networkSubscription = Network.addNetworkStateListener((state) => {
      applyNetworkState(state);
    });
    return () => {
      cancelled = true;
      clearTimeout(splashFallback);
      clearInterval(interval);
      networkSubscription.remove();
      cancelLogin();
      cancelDiscovery();
      cancelScheduledConnection();
      clearTransientTimers();
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
        toastTimerRef.current = null;
      }
      if (wsControlRef.current) {
        const ctrl = wsControlRef.current;
        wsControlRef.current = null;
        shutdownSocketControl(ctrl);
      }
    };
    // This starts the app's network poller once; recreating it on every render would duplicate connection attempts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!authLoaded || !discoveryComplete) return;
    if (hasConsumerCloudBackend() && setupComplete && validateUrl(wsUrl)) {
      setShowSetup(false);
      return;
    }
    if (!setupComplete || !validateUrl(wsUrl)) {
      setShowSetup(true);
    } else {
      setShowSetup(false);
    }
  }, [authLoaded, discoveryComplete, setupComplete, validateUrl, wsUrl]);

  const bakedApiUrl = useMemo(() => {
    const candidate = String(bootstrapApiUrl || API_URL || "").trim().replace(/\/+$/, "");
    return validateUrl(candidate) ? candidate : "";
  }, [bootstrapApiUrl, validateUrl]);

  useEffect(() => {
    if (!authLoaded || !bakedApiUrl) return;
    const current = getActiveWsUrl();
    if (!current) {
      pinActiveWsUrl(bakedApiUrl);
      saveWsUrl(bakedApiUrl);
      return;
    }
    if (current === bakedApiUrl) return;
    if (
      isLocalLanServerUrl(current)
      && !isLocalLanServerUrl(bakedApiUrl)
      && validateUrl(bakedApiUrl)
    ) {
      pinActiveWsUrl(bakedApiUrl);
      saveWsUrl(bakedApiUrl);
      autoLoginAttemptedRef.current = false;
      return;
    }
    if (
      isLocalLanServerUrl(current)
      && isLocalLanServerUrl(bakedApiUrl)
      && validateUrl(bakedApiUrl)
    ) {
      try {
        const curHost = new URL(current).hostname;
        const bakedHost = new URL(bakedApiUrl).hostname;
        if (curHost !== bakedHost) {
          pinActiveWsUrl(bakedApiUrl);
          saveWsUrl(bakedApiUrl);
          autoLoginAttemptedRef.current = false;
          return;
        }
      } catch {
        // Ignore malformed URLs.
      }
    }
    // Do not overwrite a fresher LAN URL chosen by loadStoredData / Expo discovery.
    if (!/localhost|127\.0\.0\.1/i.test(current)) return;
    pinActiveWsUrl(bakedApiUrl);
    saveWsUrl(bakedApiUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, bakedApiUrl]);

  function getActiveWsUrl() {
    return String(wsUrlRef.current || wsUrl || "").trim().replace(/\/+$/, "");
  }

  function pinActiveWsUrl(url) {
    const trimmed = String(url || "").trim().replace(/\/+$/, "");
    if (trimmed) {
      wsUrlRef.current = trimmed;
    }
    return trimmed;
  }

  function normalizeApiOrigin(url) {
    try {
      const parsed = new URL(String(url || "").trim());
      return `${parsed.protocol}//${parsed.host}`.toLowerCase();
    } catch {
      return String(url || "").trim().toLowerCase();
    }
  }

  async function persistWsUrl(url) {
    const previous = getActiveWsUrl();
    const trimmed = pinActiveWsUrl(url);
    if (trimmed) {
      const originChanged = Boolean(
        previous
        && trimmed
        && normalizeApiOrigin(previous) !== normalizeApiOrigin(trimmed),
      );
      if (originChanged) {
        await SecureStore.deleteItemAsync("translator_token");
        tokenRef.current = "";
        setToken("");
        autoLoginAttemptedRef.current = false;
      }
      await saveWsUrl(trimmed);
    }
    return trimmed;
  }

  function socketControlIsLive(ctrl) {
    if (!ctrl) return false;
    if (ctrl.isReconnecting?.()) return true;
    const state = ctrl.readyState;
    // CONNECTING or OPEN — CLOSING must not block a fresh connect.
    return state === 0 || state === 1;
  }

  function isSocketBusy() {
    return socketControlIsLive(wsControlRef.current);
  }

  function abandonClosingSocket() {
    const ctrl = wsControlRef.current;
    if (!ctrl || ctrl.readyState !== 2) return false;
    wsControlRef.current = null;
    ctrl.dispose?.() ?? ctrl.close?.();
    return true;
  }

  function abandonStaleConnectingSocket(maxAgeMs = 22000) {
    const ctrl = wsControlRef.current;
    if (!ctrl || ctrl.readyState !== 0) return false;
    const connectingForMs = Number(ctrl.connectionDuration) || 0;
    if (connectingForMs < maxAgeMs) return false;
    wsControlRef.current = null;
    isConnectedRef.current = false;
    resetSessionHandshake();
    ctrl.dispose?.() ?? ctrl.close?.(4001, "Stale connecting socket");
    return true;
  }

  function shutdownSocketControl(ctrl) {
    if (!ctrl) return;
    ctrl.dispose?.() ?? ctrl.close?.();
  }

  function closeSocketControlIfLive(ctrl) {
    if (!socketControlIsLive(ctrl)) return;
    ctrl.close();
  }

  function clearTransientTimers() {
    if (reconcileDebounceRef.current) {
      clearTimeout(reconcileDebounceRef.current);
      reconcileDebounceRef.current = null;
    }
    if (networkRecheckRef.current) {
      clearTimeout(networkRecheckRef.current);
      networkRecheckRef.current = null;
    }
    if (networkDisconnectDebounceRef.current) {
      clearTimeout(networkDisconnectDebounceRef.current);
      networkDisconnectDebounceRef.current = null;
    }
    if (suppressReleaseTimerRef.current) {
      clearTimeout(suppressReleaseTimerRef.current);
      suppressReleaseTimerRef.current = null;
    }
    if (volumeToastTimerRef.current) {
      clearTimeout(volumeToastTimerRef.current);
      volumeToastTimerRef.current = null;
    }
    if (speedToastTimerRef.current) {
      clearTimeout(speedToastTimerRef.current);
      speedToastTimerRef.current = null;
    }
    if (recoverableRetryTimerRef.current) {
      clearTimeout(recoverableRetryTimerRef.current);
      recoverableRetryTimerRef.current = null;
    }
    if (warmingRetryTimerRef.current) {
      clearTimeout(warmingRetryTimerRef.current);
      warmingRetryTimerRef.current = null;
    }
    if (helpTimerRef.current) {
      clearTimeout(helpTimerRef.current);
      helpTimerRef.current = null;
    }
    if (suppressReleaseTimerRef.current) {
      clearTimeout(suppressReleaseTimerRef.current);
      suppressReleaseTimerRef.current = null;
    }
    if (autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
    clearHandshakeWait();
    clearHandshakeWatchdog();
  }

  function reconcileStaleConnectionState() {
    if (isSocketOpen() && serverReadyRef.current && !isConnectedRef.current) {
      markSocketConnected(isInterpreterActiveRef.current ? socketStatusMessages().readyToListen : socketStatusMessages().connected);
      return;
    }
    if (!isConnectedRef.current || isSocketOpen() || isSocketBusy()) return;
    isConnectedRef.current = false;
    setIsConnected(false);
    resetSessionHandshake();
    if (!userPausedConnectionRef.current && appStateRef.current === "active") {
      setStatus(BRIDGE_CONN.connectionLost);
      setStatusType("connecting");
      if (reconcileDebounceRef.current) clearTimeout(reconcileDebounceRef.current);
      reconcileDebounceRef.current = setTimeout(() => {
        reconcileDebounceRef.current = null;
        if (
          !mountedRef.current
          || appStateRef.current !== "active"
          || userPausedConnectionRef.current
        ) return;
        beginServerConnectionRef.current();
      }, 0);
    }
  }

  function clearHandshakeWatchdog() {
    if (handshakeTimerRef.current) {
      clearTimeout(handshakeTimerRef.current);
      handshakeTimerRef.current = null;
    }
  }

  function clearHandshakeWait() {
    if (handshakeWaitTimerRef.current) {
      clearTimeout(handshakeWaitTimerRef.current);
      handshakeWaitTimerRef.current = null;
    }
  }

  function startHandshakeWatchdog() {
    clearHandshakeWatchdog();
    serverReadyRef.current = false;
    const generation = connectGenerationRef.current;
    handshakeTimerRef.current = setTimeout(() => {
      if (
        mountedRef.current
        && appStateRef.current === "active"
        && !userPausedConnectionRef.current
        && connectGenerationRef.current === generation
        && !serverReadyRef.current
        && wsControlRef.current?.isConnected
      ) {
        setStatus(BRIDGE_CONN.handshakeTimeout);
        setStatusType("connecting");
        retryConnectionRef.current();
      }
    }, 25000);
  }

  function canAttemptServerConnection() {
    reconcileStaleConnectionState();
    if (appStateRef.current !== "active" || userPausedConnectionRef.current) return false;
    if (isConnectedRef.current) return false;
    if (isSocketBusy()) return false;
    const activeUrl = getActiveWsUrl();
    const net = networkStateRef.current;
    if (net?.isConnected === false) return false;
    if (needsWifiForLanServer(net, activeUrl)) return false;
    if (
      isLocalLanServerUrl(activeUrl)
      && !isNetworkTypeKnown(net)
      && backendReachableRef.current !== true
    ) {
      return false;
    }
    if (isLocalLanServerUrl(activeUrl)) return true;
    return net?.isConnected !== false;
  }

  function cancelScheduledConnection() {
    if (connectScheduleRef.current) {
      clearTimeout(connectScheduleRef.current);
      connectScheduleRef.current = null;
    }
    if (!loginInFlightRef.current) {
      connectInFlightRef.current = false;
    }
  }

  function releaseConnectOrchestration() {
    connectInFlightRef.current = false;
  }

  function scheduleServerConnection(delayMs = 300) {
    if (userPausedConnectionRef.current || appStateRef.current !== "active") return;
    if (connectScheduleRef.current) clearTimeout(connectScheduleRef.current);
    connectScheduleRef.current = setTimeout(() => {
      connectScheduleRef.current = null;
      if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
      beginServerConnectionRef.current();
    }, delayMs);
  }
  scheduleServerConnectionRef.current = scheduleServerConnection;

  function noteLanConnectFailure() {
    const activeUrl = getActiveWsUrl();
    if (!isLocalLanServerUrl(activeUrl)) return;
    lanConnectFailRef.current += 1;
    const failThreshold = isPhoneOnWifi(networkStateRef.current) ? 1 : 2;
    if (lanConnectFailRef.current >= failThreshold) {
      lanConnectFailRef.current = 0;
      tunnelFallbackCooldownRef.current = 0;
      if (!isSocketBusy() && appStateRef.current === "active") {
        attemptRemoteServerFallback().catch(() => {});
      }
    }
  }

  async function beginServerConnection() {
    if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
    if (connectInFlightRef.current) {
      if (!userPausedConnectionRef.current) {
        scheduleServerConnection(400);
      }
      return;
    }
    if (connectScheduleRef.current) {
      clearTimeout(connectScheduleRef.current);
      connectScheduleRef.current = null;
    }
    connectInFlightRef.current = true;
    const releaseConnect = () => {
      connectInFlightRef.current = false;
    };
    abandonClosingSocket();
    abandonStaleConnectingSocket();
    const activeUrl = pinActiveWsUrl(getActiveWsUrl());
    if (!validateUrl(activeUrl) || !setupCompleteRef.current) {
      releaseConnect();
      return;
    }
    if (isLocalLanServerUrl(activeUrl) && !isNetworkTypeKnown(networkStateRef.current)) {
      releaseConnect();
      checkNetworkState().catch(() => {});
      scheduleServerConnection(1500);
      return;
    }
    if (!canAttemptServerConnection()) {
      if (needsWifiForLanServer(networkStateRef.current, activeUrl)) {
        tryTunnelFallbackForNetwork(networkStateRef.current);
      } else if (
        isLocalLanServerUrl(activeUrl)
        && backendReachableRef.current === false
        && !isSocketBusy()
      ) {
        if (appStateRef.current === "active") {
          attemptRemoteServerFallback().catch(() => {});
        }
      }
      releaseConnect();
      return;
    }
    const existing = wsControlRef.current;
    if (existing?.isConnected) {
      const connectedBase = lastConnectedApiUrlRef.current || getActiveWsUrl();
      if (connectedBase === activeUrl) {
        if (serverReadyRef.current) {
          markSocketConnected(isInterpreterActiveRef.current ? socketStatusMessages().readyToListen : socketStatusMessages().connected);
          if (!sessionHandshakeRef.current) {
            sendSessionStart();
          }
        }
        releaseConnect();
        return;
      }
      wsControlRef.current = null;
      shutdownSocketControl(existing);
      lastConnectedApiUrlRef.current = "";
      isConnectedRef.current = false;
      setIsConnected(false);
      resetSessionHandshake();
    }
    const now = Date.now();
    const liveSocket = wsControlRef.current;
    if (liveSocket?.readyState === 0 && now - lastConnectAttemptRef.current < 4000) {
      releaseConnect();
      return;
    }
    lastConnectAttemptRef.current = now;
    autoConnectStartedRef.current = true;
    setStatus(BRIDGE_CONN.linking);
    setStatusType("connecting");
    if (tokenRef.current && isJwtExpired(tokenRef.current)) {
      tokenRef.current = "";
      setToken("");
      SecureStore.deleteItemAsync("translator_token").catch(() => {});
      autoLoginAttemptedRef.current = false;
    }
    if (!tokenRef.current) {
      if (!autoLoginAttemptedRef.current && !loginInFlightRef.current) {
        autoLoginAttemptedRef.current = true;
        loginInFlightRef.current = true;
        login({
          skipHealthCheck: true,
          apiUrl: activeUrl,
          onSuccess: (accessToken) => {
            if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
            connect(accessToken);
          },
        })
          .then((ok) => {
            if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
            if (!ok) {
              autoLoginAttemptedRef.current = false;
              noteLanConnectFailure();
              scheduleServerConnection(3000);
            }
          })
          .catch((error) => {
            if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
            autoLoginAttemptedRef.current = false;
            console.error("Auto-login failed:", error);
            noteLanConnectFailure();
            scheduleServerConnection(3000);
          })
          .finally(() => {
            loginInFlightRef.current = false;
            if (!mountedRef.current) {
              releaseConnect();
              return;
            }
            releaseConnect();
          });
      } else {
        autoLoginAttemptedRef.current = false;
        releaseConnect();
        scheduleServerConnection(2500);
      }
      return;
    }
    connect(tokenRef.current);
  }

  async function openAudioWebSocket(nextWsUrl, authTokenOverride) {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) {
      releaseConnectOrchestration();
      return;
    }
    const activeUrl = getActiveWsUrl();
    const generation = connectGenerationRef.current + 1;
    connectGenerationRef.current = generation;
    const existingControl = wsControlRef.current;
    if (existingControl) {
      wsControlRef.current = null;
      shutdownSocketControl(existingControl);
    }
    if (!serverReadyRef.current) {
      setStatus(BRIDGE_CONN.checkingServer);
      setStatusType("connecting");
      const ready = await waitForBackendReady(activeUrl, {
        maxAttempts: 10,
        delayMs: 1500,
        shouldAbort: () =>
          !mountedRef.current
          || appStateRef.current !== "active"
          || userPausedConnectionRef.current
          || connectGenerationRef.current !== generation,
      });
      if (connectGenerationRef.current !== generation) {
        releaseConnectOrchestration();
        return;
      }
      if (userPausedConnectionRef.current) {
        releaseConnectOrchestration();
        return;
      }
      if (!ready && getActiveWsUrl() === activeUrl) {
        setStatus(BRIDGE_CONN.serverWarming);
        setStatusType("connecting");
        releaseConnectOrchestration();
        if (warmingRetryTimerRef.current) clearTimeout(warmingRetryTimerRef.current);
        const warmupScheduleGen = connectGenerationRef.current;
        warmingRetryTimerRef.current = setTimeout(() => {
          warmingRetryTimerRef.current = null;
          if (
            !mountedRef.current
            || appStateRef.current !== "active"
            || userPausedConnectionRef.current
            || connectGenerationRef.current !== warmupScheduleGen
          ) return;
          scheduleServerConnection(0);
        }, 2500);
        return;
      }
    }
    if (connectGenerationRef.current !== generation) {
      releaseConnectOrchestration();
      return;
    }
    const wsControl = connectWS(nextWsUrl, handleMessage, setStatusWithType, {
      shouldReconnect: () =>
        mountedRef.current
        && appStateRef.current === "active"
        && !userPausedConnectionRef.current,
      onReconnectProgress: (progress) => {
        if (connectGenerationRef.current !== generation || wsControlRef.current !== wsControl) return;
        setReconnectProgress(progress || null);
      },
      onReconnectFailed: () => {
        if (connectGenerationRef.current !== generation || wsControlRef.current !== wsControl) return;
        setReconnectFailureVisible(true);
        setReconnectProgress(null);
      },
      onOpen: () => {
        if (connectGenerationRef.current !== generation || wsControlRef.current !== wsControl) return;
        activeHandlerGenerationRef.current = generation;
        setReconnectProgress(null);
        setReconnectFailureVisible(false);
        releaseConnectOrchestration();
        startHandshakeWatchdog();
        if (isStreamingRef.current && isInterpreterActiveRef.current && isAudioUploadPaused()) {
          resumeAudioUpload();
        }
        wsControl.flushQueue?.();
      },
      onClose: ({ willReconnect, code } = {}) => {
        if (connectGenerationRef.current !== generation || wsControlRef.current !== wsControl) return;
        resetSessionHandshake();
        if (code === 1013) {
          releaseConnectOrchestration();
          setStatus(BRIDGE_CONN.serverWarming);
          setStatusType("connecting");
          if (warmingRetryTimerRef.current) clearTimeout(warmingRetryTimerRef.current);
          const closeWarmGen = connectGenerationRef.current;
          warmingRetryTimerRef.current = setTimeout(() => {
            warmingRetryTimerRef.current = null;
            if (
              !mountedRef.current
              || appStateRef.current !== "active"
              || userPausedConnectionRef.current
              || connectGenerationRef.current !== closeWarmGen
            ) return;
            scheduleServerConnection(0);
          }, 2500);
          return;
        }
        if (willReconnect) {
          pauseAudioUpload();
          if (userPausedConnectionRef.current) {
            releaseConnectOrchestration();
            wsControl.close();
            isConnectedRef.current = false;
            setIsConnected(false);
            setStatus(socketStatusMessages().disconnected);
            setStatusType("warning");
            return;
          }
          isConnectedRef.current = false;
          setIsConnected(false);
          setStatusType("connecting");
          return;
        }
        releaseConnectOrchestration();
        lastConnectedApiUrlRef.current = "";
        isConnectedRef.current = false;
        setIsConnected(false);
        setStatus(socketStatusMessages().disconnected);
        setStatusType("warning");
        if (!userPausedConnectionRef.current && isInterpreterActiveRef.current) {
          setReconnectFailureVisible(true);
        }
        if (!userPausedConnectionRef.current && setupCompleteRef.current) {
          noteLanConnectFailure();
          scheduleServerConnection(2000);
        }
      },
    });
    if (connectGenerationRef.current !== generation) {
      shutdownSocketControl(wsControl);
      releaseConnectOrchestration();
      return;
    }
    wsControlRef.current = wsControl;
    wsControl.updateHandlers(handleMessage, setStatusWithType);
  }

  useEffect(() => {
    if (!authLoaded || !validateUrl(wsUrl)) return;
    const previousUrl = lastProbedUrlRef.current;
    if (previousUrl === wsUrl) return;

    if (previousUrl && previousUrl !== wsUrl) {
      connectGenerationRef.current += 1;
      userPausedConnectionRef.current = false;
      prepareForSocketReconnect();
      if (wsControlRef.current) {
        const stale = wsControlRef.current;
        wsControlRef.current = null;
        shutdownSocketControl(stale);
      }
      autoLoginAttemptedRef.current = false;
      lastConnectAttemptRef.current = 0;
    }

    lastProbedUrlRef.current = wsUrl;
    checkBackendHealth(wsUrl, {
      quiet: true,
      shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
    }).then((healthy) => {
      if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
      if (!healthy && isLocalLanServerUrl(wsUrl) && !isSocketBusy()) {
        attemptRemoteServerFallback().catch(() => {});
      } else if (!healthy && !isLocalLanServerUrl(wsUrl)) {
        attemptTunnelRefresh().catch(() => {});
      }
      if (setupCompleteRef.current && canAttemptServerConnection()) {
        scheduleServerConnection(300);
      }
    }).catch(() => {});
    // Re-probe when env URL or stored URL changes (e.g. Start-MobilePhoneMode.ps1 refreshed LAN IP).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, wsUrl, setupComplete]);

  useEffect(() => {
    if (!authLoaded) return;
    if (!setupComplete) {
      autoConnectStartedRef.current = false;
    }
  }, [authLoaded, setupComplete]);

  useEffect(() => {
    if (!authLoaded || !setupComplete || !validateUrl(wsUrl)) return;
    if (!canAttemptServerConnection()) return;
    const timer = setTimeout(() => {
      if (appStateRef.current === "active") scheduleServerConnection(0);
    }, 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, setupComplete, networkState?.isConnected, wsUrl, token]);

  useEffect(() => {
    if (!authLoaded || !setupComplete || !validateUrl(wsUrl)) return;
    const interval = setInterval(() => {
      if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
      const activeUrl = wsUrlRef.current;
      if (!isConnectedRef.current && validateUrl(activeUrl)) {
        checkBackendHealth(activeUrl, {
          quiet: true,
          shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
        }).then((healthy) => {
          if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
          if (!healthy && isLocalLanServerUrl(activeUrl) && !isSocketBusy()) {
            attemptRemoteServerFallback().catch(() => {});
          } else if (!healthy && !isLocalLanServerUrl(activeUrl)) {
            attemptTunnelRefresh().catch(() => {});
          }
        }).catch(() => {});
      }
      if (!canAttemptServerConnection()) {
        const blockedUrl = wsUrlRef.current;
        if (needsWifiForLanServer(networkStateRef.current, blockedUrl) && appStateRef.current === "active") {
          tryTunnelFallbackForNetwork(networkStateRef.current);
        }
        return;
      }
      scheduleServerConnection(300);
    }, 12000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoaded, setupComplete, wsUrl, networkState?.isConnected]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      appStateRef.current = nextState;
      if (nextState === "background" || nextState === "inactive") {
        cancelScheduledConnection();
        cancelLogin();
        cancelDiscovery();
        loginInFlightRef.current = false;
        connectInFlightRef.current = false;
        if (toastTimerRef.current) {
          clearTimeout(toastTimerRef.current);
          toastTimerRef.current = null;
        }
        clearTransientTimers();
        clearHandshakeWatchdog();
        releaseCommandMute();
        tunnelFallbackInFlightRef.current = false;
        tunnelRefreshInFlightRef.current = false;
        resumeAfterTtsRef.current = false;
        if (isStreamingRef.current && isInterpreterActiveRef.current) {
          pauseAudioUpload();
        }
        return;
      }
      if (nextState !== "active" || !setupCompleteRef.current || !validateUrl(wsUrlRef.current)) return;
      if (userPausedConnectionRef.current) return;
      if (isStreamingRef.current && isInterpreterActiveRef.current && isAudioUploadPaused()) {
        restoreRecordingAudioMode()
          .then(() => resumeAudioUpload())
          .catch(() => {});
      }
      if (
        isConnectedRef.current
        && needsWifiForLanServer(networkStateRef.current, wsUrlRef.current)
      ) {
        prepareForSocketReconnect();
        if (wsControlRef.current) {
          const stale = wsControlRef.current;
          wsControlRef.current = null;
          shutdownSocketControl(stale);
        }
        if (isStreamingRef.current && isInterpreterActiveRef.current) {
          pauseAudioUpload();
        }
        tryTunnelFallbackForNetwork(networkStateRef.current);
        setStatus(BRIDGE_CONN.joinWifiFindingRemote);
        setStatusType("warning");
        scheduleServerConnection(300);
      }
      abandonClosingSocket();
      abandonStaleConnectingSocket();
      reconcileStaleConnectionState();
      if (ttsQueueRef.current.length > 0 && !isPlayingTtsRef.current) {
        playNextTtsChunk();
      }
      const activeUrl = wsUrlRef.current;
      checkBackendHealth(activeUrl, {
        quiet: true,
        shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
      }).then((healthy) => {
        if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
        if (!healthy && isLocalLanServerUrl(activeUrl) && !isSocketBusy()) {
          attemptRemoteServerFallback().catch(() => {});
        } else if (!healthy && !isLocalLanServerUrl(activeUrl)) {
          attemptTunnelRefresh().catch(() => {});
        } else if (needsWifiForLanServer(networkStateRef.current, activeUrl)) {
          tryTunnelFallbackForNetwork(networkStateRef.current);
        }
        scheduleServerConnection(200);
      }).catch(() => {
        if (mountedRef.current && !userPausedConnectionRef.current && appStateRef.current === "active") {
          scheduleServerConnection(200);
        }
      });
    });
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isConnected) return;
    sendRouteConfig(sourceLanguage, targetLanguage, barrierMode);
    // Route config depends on route values and connection state; the sender function is stable enough for this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceLanguage, targetLanguage, barrierMode, isConnected]);

  useEffect(() => {
    isInterpreterActiveRef.current = isInterpreterActive;
    if (!isInterpreterActive && autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
  }, [isInterpreterActive]);

  useEffect(() => {
    if (!isInterpreterActive || !isConnected || isPlayingTts || startingStreamRef.current) return;
    if (isStreaming && !isAudioUploadPaused()) return;
    if (autoResumeTimerRef.current) clearTimeout(autoResumeTimerRef.current);
    autoResumeTimerRef.current = setTimeout(() => {
      autoResumeTimerRef.current = null;
      if (
        mountedRef.current
        && appStateRef.current === "active"
        && !userPausedConnectionRef.current
        && activeHandlerGenerationRef.current === connectGenerationRef.current
        && isInterpreterActiveRef.current
        && isSocketOpen()
        && serverReadyRef.current
        && sessionHandshakeRef.current
        && !isPlayingTtsRef.current
      ) {
        startListening();
      }
    }, 260);
    return () => {
      if (autoResumeTimerRef.current) {
        clearTimeout(autoResumeTimerRef.current);
        autoResumeTimerRef.current = null;
      }
    };
    // The loop intentionally follows state flags; startListening reads the latest refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInterpreterActive, isConnected, isStreaming, isPlayingTts]);

  useEffect(() => {
    setOnPlaybackIdle(() => {
      if (
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current
        || activeHandlerGenerationRef.current !== connectGenerationRef.current
      ) return;
      if (resumeAfterTtsRef.current && isInterpreterActiveRef.current) {
        resumeMicAfterPlayback().catch((error) => console.error("Error resuming mic after playback:", error));
      }
    });
    // Playback resumption is ref-driven; resetting this handler on every render would interrupt continuous mode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setOnPlaybackIdle]);

  useEffect(() => {
    wsControlRef.current?.updateHandlers?.(
      (message) => handleMessageRef.current(message),
      (nextStatus, type) => setStatusWithTypeRef.current(nextStatus, type),
    );
  }, [sourceLanguage, targetLanguage, barrierMode, token, isConnected, wsControlRef]);

  useEffect(() => () => {
    mountedRef.current = false;
    connectGenerationRef.current += 1;
    connectInFlightRef.current = false;
    cancelLogin();
    cancelDiscovery();
    tunnelFallbackInFlightRef.current = false;
    tunnelRefreshInFlightRef.current = false;
    releaseCommandMute();
    clearHandshakeWatchdog();
    clearHandshakeWait();
    cancelScheduledConnection();
    clearTransientTimers();
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    if (wsControlRef.current) {
      try {
        wsControlRef.current.close();
      } catch {
        // Socket may already be closed.
      }
      wsControlRef.current = null;
    }
    stopAudioStream().catch(() => {});
    stopTtsPlayback();
    // This teardown must remain mount-scoped; the referenced helpers read current refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopTtsPlayback]);

  function showToast(message, variant = "info", durationMs = 2200) {
    setToast({ message, variant });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      toastTimerRef.current = null;
      if (!mountedRef.current || appStateRef.current !== "active") return;
      setToast(null);
    }, durationMs);
  }

  async function copyTranslatedText() {
    const text = String(translatedText || "").trim();
    if (!text || text === voiceIntent) {
      showToast(toasts.nothingYet, "error");
      return;
    }
    await Clipboard.setStringAsync(text);
    await tapHaptic("success");
    showToast(toasts.translationCopied, "success");
  }

  async function copyTurnHistory(turn) {
    const text = `${turn?.sourceText || ""}\n${turn?.translatedText || ""}`.trim();
    if (!text) {
      showToast(toasts.nothingYet, "error");
      return;
    }
    await Clipboard.setStringAsync(text);
    showToast(toasts.turnCopied, "success");
  }

  async function copySourceText() {
    const text = String(sourceText || "").trim();
    if (!text) {
      showToast(toasts.nothingYet, "error");
      return;
    }
    await Clipboard.setStringAsync(text);
    await tapHaptic("success");
    showToast(toasts.originalCopied, "success");
  }

  async function shareTranslatedText() {
    const text = String(translatedText || "").trim();
    if (!text || text === voiceIntent) {
      showToast(toasts.nothingShare, "error");
      return;
    }
    try {
      await Share.share({ message: text });
      await tapHaptic("success");
    } catch {
      // User dismissed share sheet
    }
  }

  async function shareSourceText() {
    const text = String(sourceText || "").trim();
    if (!text) {
      showToast(toasts.nothingShare, "error");
      return;
    }
    try {
      await Share.share({ message: text });
      await tapHaptic("success");
    } catch {
      // User dismissed share sheet
    }
  }

  function applyBarrierMode(nextBarrierMode, { haptic = true, toast = true } = {}) {
    if (nextBarrierMode === barrierMode) return;
    setBarrierMode(nextBarrierMode);
    setMeaningCheck("");
    sendRouteConfig(sourceLanguage, targetLanguage, nextBarrierMode);
    setStatus(modeToggleStatus(nextBarrierMode));
    setStatusType("success");
    if (haptic) tapHaptic("light");
    if (toast) {
      showToast(modeToggleToast(nextBarrierMode), "success");
    }
  }

  function toggleBarrierMode() {
    applyBarrierMode(!barrierMode);
  }

  async function shareSession() {
    const lines = [];
    if (sourceText) lines.push(`${routeSource}: ${sourceText}`);
    if (translatedText && translatedText !== voiceIntent) lines.push(`${routeTarget}: ${translatedText}`);
    if (!lines.length) {
      showToast(toasts.nothingShare, "error");
      return;
    }
    try {
      await Share.share({
        message: `Anai\n${activeSource} → ${activeTarget}\n\n${lines.join("\n\n")}`,
      });
      await tapHaptic("success");
    } catch {
      // User dismissed share sheet
    }
  }

  const contextChipLabel = useMemo(() => {
    const mood = semanticContext?.conversation_mood || semanticContext?.mood;
    const intent = semanticContext?.last_intent || semanticContext?.intent;
    if (mood && intent && mood !== "neutral") return `${intent} · ${mood}`;
    if (intent && intent !== "statement") return String(intent);
    if (mood && mood !== "neutral") return String(mood);
    return "";
  }, [semanticContext]);
  const showSemanticTopics = Boolean(
    !showDebugDetails
    && Array.isArray(semanticContext?.topics)
    && semanticContext.topics.length > 0,
  );
  const assistantApiUrl = useMemo(() => {
    const base = String(wsUrl || API_URL || "").trim().replace(/\/+$/, "");
    return validateUrl(base) ? base : "";
  }, [validateUrl, wsUrl]);
  const getAssistantContext = useCallback(() => ({
    source_text: sourceText,
    translated_text: translatedText,
    source_language: sourceLanguage,
    target_language: targetLanguage,
    barrier_mode: barrierMode,
    semantic_context: semanticContext,
    conversation_brain: conversationBrain,
    recent_turns: conversationTurns.slice(-5),
    human_certification_step: humanCertificationStep,
    certification_message: meaningCheck || clarifyMessage || confidenceWarningMessage || "",
    clarify_visible: clarifyVisible,
    brain_message: brainUi?.message || "",
    brain_repair_options: brainUi?.repairOptions || [],
    low_bandwidth_mode: lowBandwidthMode,
    session_reconnects: sessionReconnects,
  }), [
    sourceText,
    translatedText,
    sourceLanguage,
    targetLanguage,
    barrierMode,
    semanticContext,
    conversationBrain,
    conversationTurns,
    humanCertificationStep,
    meaningCheck,
    clarifyMessage,
    confidenceWarningMessage,
    clarifyVisible,
    brainUi?.message,
    brainUi?.repairOptions,
    lowBandwidthMode,
    sessionReconnects,
  ]);

  async function switchToRemoteApiUrl(apiUrl) {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return false;
    if (wsControlRef.current) {
      const stale = wsControlRef.current;
      wsControlRef.current = null;
      shutdownSocketControl(stale);
    }
    prepareForSocketReconnect();
    connectGenerationRef.current += 1;
    await persistWsUrl(apiUrl);
    if (!mountedRef.current || userPausedConnectionRef.current) return false;
    lanConnectFailRef.current = 0;
    lastProbedUrlRef.current = null;
    autoLoginAttemptedRef.current = false;
    userPausedConnectionRef.current = false;
    setStatus(BRIDGE_CONN.switchingRemote);
    setStatusType("connecting");
    scheduleServerConnection(300);
    return true;
  }

  async function attemptTunnelRefresh() {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current || isSocketBusy()) return false;
    const url = wsUrlRef.current;
    if (!validateUrl(url) || isLocalLanServerUrl(url)) return false;
    if (tunnelRefreshInFlightRef.current) return false;
    tunnelRefreshInFlightRef.current = true;
    try {
      const resolved = await resolveServerUrl(url, {
        preferOffLan: true,
        shouldAbort: () =>
          !mountedRef.current
          || appStateRef.current !== "active"
          || userPausedConnectionRef.current,
      });
      if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return false;
      if (!resolved?.healthy || !resolved.apiUrl || !validateUrl(resolved.apiUrl)) return false;
      if (resolved.apiUrl === url) return false;
      return await switchToRemoteApiUrl(resolved.apiUrl);
    } catch (error) {
      console.error("Tunnel refresh failed:", error);
      return false;
    } finally {
      tunnelRefreshInFlightRef.current = false;
    }
  }

  async function attemptRemoteServerFallback() {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current || isSocketBusy()) return false;
    const url = wsUrlRef.current;
    if (!validateUrl(url) || !isLocalLanServerUrl(url)) return false;
    const now = Date.now();
    if (now - tunnelFallbackCooldownRef.current < 12000) return false;
    if (tunnelFallbackInFlightRef.current) return false;
    tunnelFallbackInFlightRef.current = true;
    tunnelFallbackCooldownRef.current = now;
    try {
      const seen = new Set();
      const fastCandidates = [];
      const addCandidate = (raw) => {
        const normalized = String(raw || "").trim().replace(/\/+$/, "");
        if (!normalized || seen.has(normalized)) return;
        seen.add(normalized);
        fastCandidates.push(normalized);
      };
      addCandidate(mobileConnectInfoRef.current?.tunnel_backend_url);
      addCandidate(process.env.EXPO_PUBLIC_TUNNEL_API_URL);
      const tunnelEnv = String(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "").trim().replace(/\/+$/, "");
      if (tunnelEnv && validateUrl(tunnelEnv)) {
        try {
          const tunnelInfo = await fetchMobileConnectInfo(tunnelEnv, {
            shouldAbort: () =>
              !mountedRef.current
              || appStateRef.current !== "active"
              || userPausedConnectionRef.current,
          });
          addCandidate(tunnelInfo?.tunnel_backend_url);
          addCandidate(tunnelInfo?.backend_url);
        } catch {
          // Tunnel info optional.
        }
      }
      for (const candidate of fastCandidates) {
        if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return false;
        if (!validateUrl(candidate) || candidate === url || isLocalLanServerUrl(candidate)) continue;
        if (await checkBackendHealthUrl(candidate, { timeoutMs: 8000, requireReady: true })) {
          return await switchToRemoteApiUrl(candidate);
        }
      }
      const resolved = await resolveServerUrl(url, {
        preferOffLan: true,
        shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
      });
      if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return false;
      if (!resolved?.healthy || !resolved.apiUrl || !validateUrl(resolved.apiUrl)) return false;
      if (resolved.apiUrl === url || isLocalLanServerUrl(resolved.apiUrl)) return false;
      return await switchToRemoteApiUrl(resolved.apiUrl);
    } catch (error) {
      console.error("Remote server fallback failed:", error);
      return false;
    } finally {
      tunnelFallbackInFlightRef.current = false;
    }
  }

  async function attemptTunnelFallbackForNetwork(state) {
    const url = wsUrlRef.current;
    if (!validateUrl(url)) return false;
    if (needsWifiForLanServer(state, url)) {
      return attemptRemoteServerFallback();
    }
    if (
      isLocalLanServerUrl(url)
      && isPhoneOnWifi(state)
      && backendReachableRef.current === false
    ) {
      return attemptRemoteServerFallback();
    }
    return false;
  }

  function tryTunnelFallbackForNetwork(state) {
    attemptTunnelFallbackForNetwork(state).catch(() => {});
  }

  function applyNetworkState(state) {
    const wasDisconnected = prevNetworkConnectedRef.current === false;
    const nowConnected = state.isConnected !== false;
    prevNetworkConnectedRef.current = state.isConnected;
    setNetworkState(state);
    networkStateRef.current = state;

    const url = wsUrlRef.current;
    const prevType = prevNetworkTypeRef.current;
    prevNetworkTypeRef.current = state?.type ?? null;
    const gainedWifi = isPhoneOnWifi(state) && prevType != null && !isPhoneOnWifi({ type: prevType });
    const wrongNetworkForLan = needsWifiForLanServer(state, url);

    if (nowConnected && networkDisconnectDebounceRef.current) {
      clearTimeout(networkDisconnectDebounceRef.current);
      networkDisconnectDebounceRef.current = null;
    }

    reconcileStaleConnectionState();

    if (
      nowConnected
      && isLocalLanServerUrl(url)
      && !isNetworkTypeKnown(state)
      && setupCompleteRef.current
      && !isConnectedRef.current
    ) {
      if (networkRecheckRef.current) clearTimeout(networkRecheckRef.current);
      networkRecheckRef.current = setTimeout(() => {
        networkRecheckRef.current = null;
        if (mountedRef.current && !userPausedConnectionRef.current && appStateRef.current === "active") {
          checkNetworkState().catch(() => {});
        }
      }, 1200);
    }

    if (
      (nowConnected && wasDisconnected || gainedWifi) &&
      !userPausedConnectionRef.current &&
      appStateRef.current === "active" &&
      !isConnectedRef.current &&
      validateUrl(url) &&
      setupCompleteRef.current &&
      !wsControlRef.current?.isReconnecting?.()
    ) {
      if (wrongNetworkForLan) {
        tryTunnelFallbackForNetwork(state);
        setStatus(BRIDGE_CONN.joinWifiFindingRemote);
        setStatusType("warning");
      } else {
        setStatus(BRIDGE_CONN.networkRestored);
        setStatusType("connecting");
        wsControlRef.current?.resetReconnectState?.();
        const restoreUrl = wsUrlRef.current;
        if (isLocalLanServerUrl(restoreUrl)) {
          checkBackendHealth(restoreUrl, {
            quiet: true,
            shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
          }).then((healthy) => {
            if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
            if (!healthy) {
              attemptRemoteServerFallback().catch(() => {});
            }
            scheduleServerConnection(200);
          }).catch(() => {
            if (!mountedRef.current || userPausedConnectionRef.current || appStateRef.current !== "active") return;
            scheduleServerConnection(200);
          });
        } else {
          scheduleServerConnection(200);
        }
      }
    } else if (wrongNetworkForLan && !isConnectedRef.current && setupCompleteRef.current && appStateRef.current === "active") {
      tryTunnelFallbackForNetwork(state);
      setStatus(BRIDGE_CONN.joinWifiWaitingRemote);
      setStatusType("warning");
    }

    if (networkDisconnectDebounceRef.current && nowConnected) {
      clearTimeout(networkDisconnectDebounceRef.current);
      networkDisconnectDebounceRef.current = null;
    }

    if (isConnectedRef.current) {
      const lostNetwork = state.isConnected === false;
      if (wrongNetworkForLan) {
        if (networkDisconnectDebounceRef.current) {
          clearTimeout(networkDisconnectDebounceRef.current);
          networkDisconnectDebounceRef.current = null;
        }
        setStatus(BRIDGE_CONN.joinWifi);
        setStatusType("warning");
        if (appStateRef.current === "active") {
          prepareForSocketReconnect();
          if (wsControlRef.current) {
            const stale = wsControlRef.current;
            wsControlRef.current = null;
            shutdownSocketControl(stale);
          }
          if (isStreamingRef.current && isInterpreterActiveRef.current) {
            pauseAudioUpload();
          }
          tryTunnelFallbackForNetwork(state);
          scheduleServerConnection(300);
        }
      } else if (lostNetwork) {
        setStatus(BRIDGE_CONN.networkLostChecking);
        setStatusType("warning");
        if (networkDisconnectDebounceRef.current) clearTimeout(networkDisconnectDebounceRef.current);
        networkDisconnectDebounceRef.current = setTimeout(() => {
          networkDisconnectDebounceRef.current = null;
          if (
            !mountedRef.current
            || appStateRef.current !== "active"
            || userPausedConnectionRef.current
          ) return;
          if (networkStateRef.current?.isConnected === false && isConnectedRef.current) {
            setStatus(BRIDGE_CONN.networkLostShort);
            prepareForSocketReconnect();
            if (wsControlRef.current) {
              const stale = wsControlRef.current;
              wsControlRef.current = null;
              shutdownSocketControl(stale);
            }
            if (isStreamingRef.current && isInterpreterActiveRef.current) {
              pauseAudioUpload();
            }
          }
        }, 1500);
      }
    }
  }

  async function checkNetworkState() {
    try {
      const state = await Network.getNetworkStateAsync();
      applyNetworkState(state);
    } catch (error) {
      console.error("Network check error:", error);
    }
  }

  function isSocketOpen() {
    return Boolean(wsControlRef.current?.isConnected);
  }

  function markSocketConnected(nextStatus = socketStatusMessages().connected) {
    lanConnectFailRef.current = 0;
    lastConnectedApiUrlRef.current = getActiveWsUrl();
    isConnectedRef.current = true;
    setIsConnected(true);
    setStatusType("success");
    setStatus(normalizeConnectionStatus(nextStatus));
    markBackendReachable(true);
    saveRecentUrl(getActiveWsUrl());
    wsControlRef.current?.flushQueue?.();
  }

  function sendSessionStart() {
    if (!isSocketOpen() || sessionHandshakeRef.current) return;
    if (appStateRef.current !== "active" || userPausedConnectionRef.current) return;
    if (activeHandlerGenerationRef.current !== connectGenerationRef.current) return;
    const sent = wsControlRef.current?.send(JSON.stringify({
      type: "start",
      session_id: mobileSessionIdRef.current,
      device_id: mobileDeviceIdRef.current,
      speaker_name: "Mobile",
      speaker_mode: "auto",
      source_language: sourceLanguage,
      target_language: targetLanguage,
      barrier_mode: barrierMode,
      mime_type: "audio/m4a",
    }));
    if (sent) {
      sessionHandshakeRef.current = true;
    }
  }

  function resetSessionHandshake() {
    sessionHandshakeRef.current = false;
    serverReadyRef.current = false;
    activeHandlerGenerationRef.current = 0;
    clearHandshakeWatchdog();
  }

  function prepareForSocketReconnect() {
    isConnectedRef.current = false;
    setIsConnected(false);
    lastConnectedApiUrlRef.current = "";
    resetSessionHandshake();
  }

  async function retryConnection() {
    if (!mountedRef.current || appStateRef.current !== "active") return;
    cancelScheduledConnection();
    const activeUrl = getActiveWsUrl();
    if (!validateUrl(activeUrl)) {
      setShowSetup(true);
      return;
    }
    if (!setupComplete) {
      setShowSetup(true);
      return;
    }
    clearTransientTimers();
    connectGenerationRef.current += 1;
    if (autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }
    userPausedConnectionRef.current = false;
    autoLoginAttemptedRef.current = false;
    prepareForSocketReconnect();
    if (wsControlRef.current) {
      const stale = wsControlRef.current;
      stale.resetReconnectState?.();
      wsControlRef.current = null;
      shutdownSocketControl(stale);
    }
    lastConnectAttemptRef.current = 0;
    connectInFlightRef.current = false;
    setDismissedError("");
    lanConnectFailRef.current = 0;
    if (needsWifiForLanServer(networkStateRef.current, activeUrl)) {
      setStatus(BRIDGE_CONN.lookingRemote);
      setStatusType("connecting");
      tunnelFallbackCooldownRef.current = 0;
      const switched = await attemptTunnelFallbackForNetwork(networkStateRef.current);
      if (!switched && needsWifiForLanServer(networkStateRef.current, getActiveWsUrl())) {
        setStatus(BRIDGE_CONN.joinWifi);
        setStatusType("warning");
        return;
      }
    } else if (isLocalLanServerUrl(activeUrl)) {
      setStatus(BRIDGE_CONN.checkingServer);
      setStatusType("connecting");
      const ready = await waitForBackendReady(activeUrl, {
        maxAttempts: 8,
        delayMs: 1000,
        shouldAbort: () =>
        !mountedRef.current
        || appStateRef.current !== "active"
        || userPausedConnectionRef.current,
      });
      if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return;
      if (ready) {
        markBackendReachable(true);
        backendReachableRef.current = true;
      } else {
        markBackendReachable(false);
        backendReachableRef.current = false;
        setStatus(BRIDGE_CONN.lookingRemote);
        setStatusType("connecting");
        tunnelFallbackCooldownRef.current = 0;
        await attemptRemoteServerFallback();
      }
    }
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return;
    beginServerConnection();
  }

  function connect(authTokenOverride) {
    if (!mountedRef.current) {
      releaseConnectOrchestration();
      return;
    }
    if (!authTokenOverride && appStateRef.current !== "active") {
      releaseConnectOrchestration();
      return;
    }
    if (userPausedConnectionRef.current && !authTokenOverride) {
      releaseConnectOrchestration();
      return;
    }
    abandonClosingSocket();
    abandonStaleConnectingSocket();
    const activeUrl = pinActiveWsUrl(getActiveWsUrl());
    const authToken = authTokenOverride ?? tokenRef.current;
    if (authToken && isJwtExpired(authToken)) {
      tokenRef.current = "";
      setToken("");
      SecureStore.deleteItemAsync("translator_token").catch(() => {});
      autoLoginAttemptedRef.current = false;
      releaseConnectOrchestration();
      if (appStateRef.current === "active") beginServerConnection();
      return;
    }
    const nextWsUrl = apiToWsUrl(activeUrl, "/ws/audio", authToken);

    if (isSocketOpen() && !authTokenOverride) {
      const socketUrl = wsControlRef.current?.getUrl?.() || "";
      const urlMismatch = Boolean(socketUrl && nextWsUrl && socketUrl !== nextWsUrl);
      const needsTokenUpgrade = Boolean(authToken && socketUrl && !wsSocketHasAuthToken(socketUrl));
      const serverMismatch = lastConnectedApiUrlRef.current && lastConnectedApiUrlRef.current !== activeUrl;
      if (!urlMismatch && !needsTokenUpgrade && !serverMismatch) {
        if (serverReadyRef.current) {
          markSocketConnected(isInterpreterActiveRef.current ? socketStatusMessages().readyToListen : socketStatusMessages().connected);
          tapHaptic("success");
        } else if (!sessionHandshakeRef.current) {
          sendSessionStart();
        }
        releaseConnectOrchestration();
        return;
      }
    }

    let existing = wsControlRef.current;
    if (existing && !socketControlIsLive(existing)) {
      wsControlRef.current = null;
      existing.dispose?.() ?? existing.close?.();
      existing = null;
    }
    if (existing?.readyState === 2) {
      abandonClosingSocket();
      existing = wsControlRef.current;
    }
    if (existing?.readyState === 0) {
      const socketUrl = existing.getUrl?.() || "";
      const urlMismatch = Boolean(socketUrl && nextWsUrl && socketUrl !== nextWsUrl);
      const needsTokenUpgrade = Boolean(authToken && socketUrl && !wsSocketHasAuthToken(socketUrl));
      const connectingForMs = Number(existing.connectionDuration) || 0;
      const stuckConnecting = !authTokenOverride && !urlMismatch && !needsTokenUpgrade && connectingForMs >= 15000;
      if (authTokenOverride || urlMismatch || needsTokenUpgrade || stuckConnecting) {
        prepareForSocketReconnect();
        setStatus(BRIDGE_CONN.linking);
        setStatusType("connecting");
        existing.updateUrl?.(nextWsUrl);
        existing.forceReconnect?.(nextWsUrl);
        wsControlRef.current?.updateHandlers?.(handleMessage, setStatusWithType);
      }
      releaseConnectOrchestration();
      return;
    }
    if (existing?.isReconnecting?.()) {
      wsControlRef.current = null;
      shutdownSocketControl(existing);
      existing = null;
    }
    if (existing) {
      if (authTokenOverride && existing.updateUrl) {
        prepareForSocketReconnect();
        setStatus(BRIDGE_CONN.linking);
        setStatusType("connecting");
        existing.updateUrl(nextWsUrl);
        existing.forceReconnect(nextWsUrl);
        wsControlRef.current.updateHandlers(handleMessage, setStatusWithType);
        releaseConnectOrchestration();
        return;
      }
      closeSocketControlIfLive(existing);
      wsControlRef.current = null;
    }

    if (!validateUrl(activeUrl)) {
      setStatus(BRIDGE_ACTION.backendUrlNotReady);
      setStatusType("error");
      setShowSetup(true);
      releaseConnectOrchestration();
      return;
    }
    if (/localhost|127\.0\.0\.1/i.test(activeUrl)) {
      setStatus(BRIDGE_ACTION.lanIpRequired);
      setStatusType("error");
      setShowSetup(true);
      releaseConnectOrchestration();
      return;
    }
    if (needsWifiForLanServer(networkStateRef.current, activeUrl)) {
      tryTunnelFallbackForNetwork(networkStateRef.current);
      setStatus(BRIDGE_CONN.joinWifiFindingRemote);
      setStatusType("warning");
      releaseConnectOrchestration();
      return;
    }

    setStatus(BRIDGE_CONN.linking);
    setStatusType("connecting");
    tapHaptic("light");
    debugLog("Connecting to:", nextWsUrl);
    void openAudioWebSocket(nextWsUrl, authTokenOverride);
  }

  beginServerConnectionRef.current = beginServerConnection;
  retryConnectionRef.current = retryConnection;

  function setStatusWithType(nextStatus, type = null) {
    setStatus(nextStatus);
    if (type) {
      setStatusType(type);
    } else if (nextStatus === "Disconnected" || nextStatus === WS_STATUS.disconnected) {
      setStatusType("idle");
      resetSessionHandshake();
      isConnectedRef.current = false;
      setIsConnected(false);
    } else if (
      nextStatus === "Connected"
      || nextStatus === "Ready to listen"
      || /^Listening — speak/.test(nextStatus)
    ) {
      if (serverReadyRef.current) {
        markSocketConnected(nextStatus);
        if (!sessionHandshakeRef.current) {
          sendSessionStart();
        }
      }
    } else if (nextStatus.includes("Relinking bridge in") || nextStatus.includes("Reconnecting in") || /timeout/i.test(nextStatus)) {
      setStatusType("warning");
    } else if (
      /relink|reconnect|connecting|handshaking|linking bridge|opening bridge/i.test(nextStatus)
    ) {
      setStatusType("connecting");
    } else if (
      nextStatus.includes("failed")
      || /error/i.test(nextStatus)
    ) {
      setStatusType("error");
      resetSessionHandshake();
      isConnectedRef.current = false;
      setIsConnected(false);
      if (nextStatus.includes("max retries")) {
        autoLoginAttemptedRef.current = false;
        if (!userPausedConnectionRef.current && setupCompleteRef.current) {
          noteLanConnectFailure();
          scheduleServerConnection(2000);
        }
      }
      if (isStreamingRef.current || startingStreamRef.current) {
        startingStreamRef.current = false;
        if (nextStatus.includes("max retries")) {
          setIsStreaming(false);
          stopAudioStream().catch((error) => console.error("Error stopping mic after disconnect:", error));
        } else if (isInterpreterActiveRef.current) {
          pauseAudioUpload();
        } else {
          setIsStreaming(false);
          stopAudioStream().catch((error) => console.error("Error stopping mic after disconnect:", error));
        }
      }
      if (nextStatus.includes("max retries")) {
        setIsInterpreterActive(false);
      }
    }
  }

  function sendGlossaryCorrectionFromResult(context = "general") {
    if (!isSocketOpen()) return;
    const sourceText = result?.source_text || partialTranscript || "";
    const translatedText = result?.translated_text || liveTranslation || "";
    if (!sourceText || !translatedText) return;
    wsControlRef.current?.send(JSON.stringify({
      type: "glossary_correction",
      session_id: mobileSessionIdRef.current,
      source_text: sourceText,
      corrected_text: translatedText,
      source_language: sourceLanguage,
      target_language: targetLanguage,
      context,
    }));
    clearHumanCertification();
    showToast("Saved native-verified phrasing for this session.", "success");
  }

  function sendRouteConfig(nextSource, nextTarget, nextBarrierMode = barrierMode) {
    if (
      !isSocketOpen()
      || appStateRef.current !== "active"
      || activeHandlerGenerationRef.current !== connectGenerationRef.current
    ) return;
    wsControlRef.current?.send(JSON.stringify({
      type: "config",
      session_id: mobileSessionIdRef.current,
      device_id: mobileDeviceIdRef.current,
      speaker: "auto",
      speaker_mode: "auto",
      source_language: nextSource,
      target_language: nextTarget,
      barrier_mode: nextBarrierMode,
      environment: audioEnvironmentRef.current || "auto",
    }));
  }

  function syncRouteFromMessage(message) {
    if (Object.prototype.hasOwnProperty.call(message, "barrier_mode")) {
      setBarrierMode(asBool(message.barrier_mode));
    }
    const nextSource = message.source_language || speakerRoute.sourceLanguage || sourceLanguage;
    const nextTarget = message.target_language || speakerRoute.targetLanguage || targetLanguage;
    const speakerIndex = Number(message.speaker_index || speakerRoute.speakerIndex || 1);
    const routeConfidence = Number(message.route_confidence ?? message.confidence ?? speakerRoute.routeConfidence ?? 1);
    const listenerLabel = message.listener_label || (speakerIndex === 2 ? "Person 1" : "Person 2");
    setSpeakerRoute((previous) => ({
      ...previous,
      speakerLabel: message.speaker_label || previous.speakerLabel || `Person ${speakerIndex}`,
      speakerIndex,
      listenerLabel,
      sourceLanguage: nextSource,
      targetLanguage: nextTarget,
      detectedLanguage: message.detected_language || nextSource,
      detectedLanguageConfidence: Number(message.detected_language_confidence ?? previous.detectedLanguageConfidence ?? routeConfidence),
      routeConfidence,
      needsConfirmation: asBool(message.needs_confirmation) || routeConfidence < 0.5,
    }));
    if (asBool(message.needs_confirmation) || routeConfidence < 0.5) {
      setMeaningCheck("Check meaning");
      setStatusType("warning");
    }
  }

  function syncHumanCertStep(step) {
    const next = step === "advisory" || step === "required" ? step : "none";
    humanCertStepRef.current = next;
    setHumanCertificationStep((previous) => (previous === next ? previous : next));
  }

  function clearHumanCertification({ keepTtsBlock = false } = {}) {
    syncHumanCertStep("none");
    setMeaningCheck("");
    if (!keepTtsBlock) {
      suppressTurnAudioRef.current = false;
    }
  }

  function applyCertificationFromMessage(message) {
    const step = humanCertStep(message);
    const banner = certificationBanner(message, step);
    syncHumanCertStep(step);
    if (step === "required" || step === "advisory") {
      setMeaningCheck(banner);
      setStatusType("warning");
      if (step === "required") {
        setClarifyMessage(banner);
        setClarifyVisible(true);
      }
      return step;
    }
    return "none";
  }

  function shouldSuppressTtsPlayback(message = null) {
    if (lowBandwidthModeRef.current && message?.partial) return true;
    return suppressTurnAudioRef.current
      || shouldBlockTtsForCert(humanCertStepRef.current)
      || shouldSkipBrainTts(message, brainHintsRef.current);
  }

  function applyConfidenceSignals(payload = {}) {
    const warning = resolveConfidenceWarning(payload);
    if (!warning) {
      setConfidenceWarningVisible((previous) => (previous ? false : previous));
      setConfidenceWarningMessage((previous) => (previous ? "" : previous));
      return;
    }
    setConfidenceWarningVisible((previous) => (previous ? previous : true));
    setConfidenceWarningMessage((previous) => (previous === warning ? previous : warning));
  }

  function applySharedSession(session) {
    if (!session) return;
    const reconnects = Number(session.reconnects || session.shared?.reconnects || 0);
    if (reconnects > 0) setSessionReconnects(reconnects);
    const history = session.turns || session.history || session.shared?.history || [];
    if (history.length) {
      setConversationTurns(mapSessionHistoryToTurns(history, 3));
    }
    const latest = latestSessionTurn(session);
    if (latest?.source_text || latest?.translated_text) {
      setResult((previous) => ({
        ...previous,
        source_text: latest.source_text || previous.source_text,
        translated_text: latest.translated_text || previous.translated_text,
      }));
      if (latest.translated_text) setLiveTranslation(latest.translated_text);
      if (latest.source_text) setPartialTranscript(latest.source_text);
      if (latest.speaker_label) {
        setConversationBrain(`${latest.speaker_label}: session restored`);
      }
    }
  }

  function applyBrainPayload(payload = {}, origin = "translation") {
    applyConfidenceSignals(payload);
    const { plan, hints, repairOptions } = extractBrainPlan(payload);
    if (!plan && Object.keys(hints).length === 0 && repairOptions.length === 0) return null;

    const repeatedTerms = repairOptions
      .filter((option) => option?.type === "repeat_terms")
      .flatMap((option) => option.terms || []);
    const highlightTerms = uniqueStrings(repeatedTerms.length ? repeatedTerms : (hints.highlight_terms || []));
    const repairedLanguage = hints.repaired_source_language || plan?.suggested_source_language;
    const languageAutoRepaired = Boolean(hints.language_auto_repaired);
    const suggestSwitch = Boolean(hints.suggest_source_language_switch);
    const skipTts = Boolean(hints.skip_tts || hints.tts_mode === "skip");
    const activeSpeakerId = hints.active_speaker || plan?.turn_policy?.active_speaker || "";
    const speakerShift = Boolean(hints.speaker_shift || plan?.turn_policy?.speaker_shift);
    const activeSpeakerLabel = activeSpeakerId
      ? (payload.speaker_label || `Person ${activeSpeakerId}`)
      : "";
    const riskScore = Number.isFinite(Number(plan?.meaning_risk_score))
      ? Number(plan.meaning_risk_score)
      : Number.isFinite(Number(payload.meaning_risk_score))
        ? Number(payload.meaning_risk_score)
        : null;

    brainHintsRef.current = hints;
    brainPlanRef.current = plan;

    let message = "";
    if (languageAutoRepaired && repairedLanguage) {
      message = `Source auto-switched to ${getLanguageLabel(repairedLanguage)}`;
      if (repairedLanguage !== sourceLanguage) {
        setSourceLanguage(repairedLanguage);
      }
      setClarifyVisible(false);
    } else if (suggestSwitch && repairedLanguage) {
      message = `Source sounds like ${getLanguageLabel(repairedLanguage)}`;
    } else if (repairOptions.some((option) => option?.type === "repeat_terms")) {
      message = "Exact term check needed";
    } else if (repairOptions.some((option) => option?.type === "confirm_exact")) {
      message = "Confirm exact words before speaking";
    } else if (plan?.turn_policy?.mode === "guarded_translate") {
      message = "Guarded translation active";
    } else if (skipTts) {
      message = "Voice skipped for confirmation";
    } else if (speakerShift && activeSpeakerLabel) {
      message = `${activeSpeakerLabel} speaking now`;
    }

    if (speakerShift && activeSpeakerLabel) {
      setConversationBrain(`${activeSpeakerLabel}: active speaker shift`);
    }

    if (skipTts) {
      stopTtsPlayback();
      clearTtsQueue();
      suppressTurnAudioRef.current = true;
    } else if (!shouldBlockTtsForCert(humanCertStepRef.current)) {
      suppressTurnAudioRef.current = false;
    }

    const next = {
      visible: Boolean(
        message
        || repairOptions.length
        || highlightTerms.length
        || hints.ask_before_speaking
        || suggestSwitch
        || languageAutoRepaired
        || speakerShift
        || skipTts,
      ),
      message,
      mode: plan?.turn_policy?.mode || "",
      strategy: plan?.strategy || "",
      hints,
      repairOptions,
      highlightTerms,
      riskScore,
      skipTts,
      speakerShift,
      activeSpeakerLabel,
      origin,
    };
    setBrainUi((previous) => {
      if (
        previous.visible === next.visible
        && previous.message === next.message
        && previous.mode === next.mode
        && previous.strategy === next.strategy
        && previous.skipTts === next.skipTts
        && previous.speakerShift === next.speakerShift
        && previous.activeSpeakerLabel === next.activeSpeakerLabel
        && previous.riskScore === next.riskScore
        && previous.origin === next.origin
        && previous.repairOptions.length === next.repairOptions.length
        && previous.highlightTerms.length === next.highlightTerms.length
      ) {
        return previous;
      }
      return next;
    });
    return next;
  }

  function runRepairOption(option = {}) {
    tapHaptic("light");
    if ((option.type === "switch_source_language" || option.type === "auto_switch_source_language") && option.language) {
      setSourceLanguage(option.language);
      sendRouteConfig(option.language, targetLanguage, barrierMode);
      setBrainUi((current) => ({
        ...current,
        message: `Source set to ${getLanguageLabel(option.language)}`,
        visible: true,
      }));
      setStatus(BRIDGE_ACTION.sourceSetTo(getLanguageLabel(option.language)));
      setStatusType("success");
      return;
    }
    if (option.type === "choose_meaning" && option.word) {
      const choices = Array.isArray(option.options) ? option.options.join(" / ") : "the intended meaning";
      setClarifyMessage(`For "${option.word}", say: ${choices}`);
      setClarifyVisible(true);
      setStatus(BRIDGE_ACTION.chooseMeaning);
      setStatusType("warning");
      return;
    }
    setClarifyVisible(false);
    setStatus(option.label || "Please repeat");
    setStatusType("warning");
    if (!isStreamingRef.current && !isPlayingTtsRef.current && isInterpreterActiveRef.current) {
      startListening().catch((error) => console.error("Error restarting listening after repair:", error));
    }
  }

  function rememberConversationTurn(message) {
    const sourceTextValue = message.source_text || message.original_text || result?.source_text || "";
    const translatedTextValue = message.translated_text || message.text || result?.translated_text || "";
    if (!sourceTextValue && !translatedTextValue) return;
    const speakerIndex = Number(message.speaker_index || speakerRoute.speakerIndex || 1);
    const routeConfidence = Number(message.route_confidence ?? speakerRoute.routeConfidence ?? 1);
    const flags = certTurnFlags(message);
    const turn = {
      id: `${Date.now()}-${message.speaker || speakerIndex}`,
      speakerLabel: message.speaker_label || speakerRoute.speakerLabel || `Person ${speakerIndex}`,
      listenerLabel: message.listener_label || speakerRoute.listenerLabel || (speakerIndex === 2 ? "Person 1" : "Person 2"),
      sourceText: sourceTextValue,
      translatedText: translatedTextValue,
      sourceLanguage: message.source_language || speakerRoute.sourceLanguage || sourceLanguage,
      targetLanguage: message.target_language || speakerRoute.targetLanguage || targetLanguage,
      routeConfidence,
      clarify: flags.clarify || routeConfidence < 0.5,
      certStep: flags.certStep,
      nativeListen: flags.nativeListen,
    };
    setConversationTurns((previous) => [...previous, turn].slice(-3));
  }

  function muteCommandTurn() {
    suppressTurnAudioRef.current = true;
    if (suppressReleaseTimerRef.current) clearTimeout(suppressReleaseTimerRef.current);
    suppressReleaseTimerRef.current = setTimeout(() => {
      suppressReleaseTimerRef.current = null;
      if (!mountedRef.current || appStateRef.current !== "active") return;
      suppressTurnAudioRef.current = false;
    }, 2500);
  }

  function releaseCommandMute() {
    suppressTurnAudioRef.current = false;
    if (suppressReleaseTimerRef.current) {
      clearTimeout(suppressReleaseTimerRef.current);
      suppressReleaseTimerRef.current = null;
    }
  }

  function applyVoiceCommand(text) {
    const command = parseVoiceIntent(text, sourceLanguage, targetLanguage);
    if (!command) return false;

    muteCommandTurn();
    const heard = String(text || "").trim();

    if (command.type === "route") {
      const nextSource = command.source || sourceLanguage;
      const nextTarget = command.target || targetLanguage;
      const nextBarrierMode = typeof command.barrier === "boolean" ? command.barrier : barrierMode;
      setSourceLanguage(nextSource);
      setTargetLanguage(nextTarget);
      setBarrierMode(nextBarrierMode);
      sendRouteConfig(nextSource, nextTarget, nextBarrierMode);
      clearReplayAudio();
      setMeaningCheck("");
      setSpeakerRoute({
        speakerLabel: "Person 1",
        speakerIndex: 1,
        listenerLabel: "Person 2",
        sourceLanguage: nextSource,
        targetLanguage: nextTarget,
        detectedLanguage: nextSource,
        routeConfidence: 1,
      });
      const summary = nextBarrierMode
        ? `${getLanguageLabel(nextSource)} and ${getLanguageLabel(nextTarget)}`
        : `${getLanguageLabel(nextSource)} to ${getLanguageLabel(nextTarget)}`;
      setVoiceIntent(summary);
      setResult({ source_text: heard, translated_text: summary });
      setStatus(BRIDGE_ACTION.routeUpdated);
      setStatusType("success");
      return true;
    }

    if (command.type === "swap") {
      const nextSource = targetLanguage;
      const nextTarget = sourceLanguage;
      setSourceLanguage(nextSource);
      setTargetLanguage(nextTarget);
      sendRouteConfig(nextSource, nextTarget, barrierMode);
      clearReplayAudio();
      const summary = `${getLanguageLabel(nextSource)} to ${getLanguageLabel(nextTarget)}`;
      setVoiceIntent(summary);
      setResult({ source_text: heard, translated_text: summary });
      setStatus(BRIDGE_ACTION.routeSwapped);
      setStatusType("success");
      return true;
    }

    if (command.type === "clear") {
      clearPanel();
      const cleared = clearPanelCopy();
      setVoiceIntent(cleared.voiceIntent);
      setStatus(cleared.status);
      setStatusType("success");
      return true;
    }

    if (command.type === "barrier") {
      applyBarrierMode(command.enabled, { haptic: false, toast: false });
      setVoiceIntent(command.enabled ? "Together mode" : "For you mode");
      setStatus(modeToggleStatus(command.enabled));
      setStatusType("success");
      return true;
    }

    if (command.type === "replay") {
      replayLastTranslation().catch((error) => console.error("Replay command failed:", error));
      const replayMsgs = replayStatusMessages();
      setVoiceIntent(hasReplayAudio ? replayMsgs.replayingShort : replayMsgs.noReplay);
      setStatus(hasReplayAudio ? replayMsgs.replaying : replayMsgs.noReplay);
      setStatusType(hasReplayAudio ? "success" : "warning");
      return true;
    }

    if (command.type === "connect") {
      setIsInterpreterActive(true);
      retryConnection();
      setVoiceIntent("Reconnecting");
      return true;
    }

    if (command.type === "disconnect") {
      userDisconnect();
      setVoiceIntent("Bridge dropped");
      return true;
    }

    if (command.type === "start") {
      activateInterpreter();
      setVoiceIntent("Listening");
      return true;
    }

    if (command.type === "stop") {
      pauseInterpreter();
      setVoiceIntent("Paused");
      return true;
    }

    if (command.type === "volume") {
      const nextVolume = clamp(volume + command.delta, 0.1, 1);
      setVolume(nextVolume);
      setVoiceIntent(`Volume ${Math.round(nextVolume * 100)} percent`);
      setStatus(BRIDGE_ACTION.voiceVolumeUpdated);
      setStatusType("success");
      queueVolumeToast(nextVolume);
      return true;
    }

    if (command.type === "speed") {
      const nextSpeed = clamp(playbackSpeed + command.delta, 0.7, 1.25);
      setPlaybackSpeed(nextSpeed);
      setVoiceIntent(`Voice speed ${nextSpeed.toFixed(2)}x`);
      setStatus(BRIDGE_ACTION.voiceSpeedUpdated);
      setStatusType("success");
      queueSpeedToast(nextSpeed);
      return true;
    }

    return false;
  }

  function handleMessage(message) {
    if (!mountedRef.current) return;
    if (activeHandlerGenerationRef.current !== connectGenerationRef.current) return;
    debugLog("Message:", message.type, message);
    const now = Date.now();
    const uiActive = appStateRef.current === "active";

    switch (message.type) {
      case "pong":
        break;
      case "ready":
        serverReadyRef.current = true;
        clearHandshakeWatchdog();
        markSocketConnected(socketStatusMessages().connected);
        if (!sessionHandshakeRef.current) {
          sendSessionStart();
        }
        if (
          appStateRef.current === "active"
          && !userPausedConnectionRef.current
          && isInterpreterActiveRef.current
          && !isStreamingRef.current
          && !startingStreamRef.current
          && !isPlayingTtsRef.current
        ) {
          startListening();
        }
        break;
      case "listening":
        markSocketConnected(socketStatusMessages().listening);
        if (isStreamingRef.current && isInterpreterActiveRef.current && isAudioUploadPaused()) {
          resumeAudioUpload();
        }
        if (
          appStateRef.current === "active"
          && !userPausedConnectionRef.current
          && isInterpreterActiveRef.current
          && !isStreamingRef.current
          && !startingStreamRef.current
          && !isPlayingTtsRef.current
        ) {
          startListening();
        }
        break;
      case "cip": {
        const brainUpdate = applyBrainPayload(message, "stream");
        if (brainUpdate?.message && uiActive) {
          setStatus(brainUpdate.message);
          setStatusType("warning");
        }
        break;
      }
      case "session_sync":
      case "session_restored":
        syncRouteFromMessage(message);
        applySharedSession(message.session);
        if (isStreamingRef.current && isInterpreterActiveRef.current && isAudioUploadPaused()) {
          resumeAudioUpload();
        }
        wsControlRef.current?.flushQueue?.();
        break;
      case "config_ack":
        syncRouteFromMessage(message);
        if (uiActive) {
          setVoiceIntent(asBool(message.barrier_mode) ? `${getLanguageLabel(message.source_language)} and ${getLanguageLabel(message.target_language)}` : `${getLanguageLabel(message.source_language)} to ${getLanguageLabel(message.target_language)}`);
        }
        break;
      case "speaker_detected":
        syncRouteFromMessage(message);
        if (uiActive) {
          setVoiceIntent(`${message.speaker_label || "Person"}: ${getLanguageLabel(message.source_language)} to ${getLanguageLabel(message.target_language)}`);
        }
        break;
      case "final_transcription": {
        syncRouteFromMessage(message);
        if (!uiActive) break;
        setPartialTranscript("");
        const handled = applyVoiceCommand(message.text);
        if (!handled) {
          setResult((previous) => ({ ...previous, source_text: message.text }));
          releaseCommandMute();
        }
        if (latencyStartRef.current.stt) {
          const sttLatency = now - latencyStartRef.current.stt;
          setLatencyMetrics((previous) => ({ ...previous, sttLatency, lastUpdate: now }));
          delete latencyStartRef.current.stt;
        }
        break;
      }
      case "partial_transcription":
        syncRouteFromMessage(message);
        if (!uiActive) break;
        if (humanCertStepRef.current !== "required") {
          suppressTurnAudioRef.current = false;
        }
        syncHumanCertStep("none");
        setClarifyVisible(false);
        setClarifyMessage("");
        setPartialTranscript(message.text || "");
        if (message.stage === "partial_low_confidence") {
          setMeaningCheck("Listening for clearer speech…");
        } else {
          setMeaningCheck("");
        }
        if (!suppressTurnAudioRef.current) setStatus(socketStatusMessages().listening);
        break;
      case "translation":
        syncRouteFromMessage(message);
        if (!uiActive) break;
        applyBrainPayload(message, "translation");
        if (message.semantic_context) setSemanticContext(message.semantic_context);
        setResult({
          source_text: message.source_text || message.original_text || "",
          translated_text: message.translated_text || message.text || "",
        });
        setLiveTranslation(message.translated_text || message.text || "");
        applyCertificationFromMessage(message);
        rememberConversationTurn(message);
        setStatus(BRIDGE_CONN.translationReady);
        setStatusType("success");
        break;
      case "final":
      case "live_translation":
        syncRouteFromMessage(message);
        if (!uiActive) break;
        applyBrainPayload(message, message.type === "final" ? "final" : "live");
        if (message.semantic_context) {
          setSemanticContext(message.semantic_context);
        }
        if (message.type === "live_translation") {
          applyConfidenceSignals(message);
          if (shouldSkipBrainTts(message, brainHintsRef.current)) {
            stopTtsPlayback();
            clearTtsQueue();
            suppressTurnAudioRef.current = true;
            const gateMsg = message.confidence_message || message.certification_message || message.clarify_message || "Check meaning";
            if (
              shouldBlockTtsForCert(humanCertStep(message))
              || asBool(message.needs_confirmation)
              || message.stage === "cip_clarification"
            ) {
              setClarifyMessage(gateMsg);
              setClarifyVisible(true);
            } else {
              setMeaningCheck(gateMsg);
            }
            setStatusType("warning");
          } else {
            suppressTurnAudioRef.current = false;
            const liveThreshold = typeof message.confidence_threshold === "number" ? message.confidence_threshold : 0.72;
            const liveConfidenceLow = message.low_confidence
              || (typeof message.confidence === "number" && message.confidence < liveThreshold);
            if (liveConfidenceLow) {
              setMeaningCheck(message.confidence_message || "Listening for clearer speech…");
              setStatusType("warning");
            }
          }
        }
        if (!suppressTurnAudioRef.current) {
          if (message.type === "live_translation") {
            setLiveTranslation(message.text || "");
          } else {
            setLiveTranslation("");
          }
          setResult((previous) => ({
            ...previous,
            translated_text: message.text || message.translated_text,
            source_text: message.source_text || previous.source_text,
          }));
          setStatus(message.type === "final" ? BRIDGE_CONN.listeningSpeak : BRIDGE_CONN.understanding);
        }
        if (latencyStartRef.current.translation) {
          const translationLatency = now - latencyStartRef.current.translation;
          setLatencyMetrics((previous) => ({ ...previous, translationLatency, lastUpdate: now }));
          delete latencyStartRef.current.translation;
        }
        if (message.session) {
          applySharedSession(message.session);
        }
        if (message.type === "final") {
          const certStep = applyCertificationFromMessage(message);
          applyConfidenceSignals(message);
          const blockContinuousAudio = shouldSkipBrainTts(message, brainHintsRef.current)
            || asBool(message.needs_confirmation)
            || message.stage === "cip_clarification";
          if (blockContinuousAudio) {
            if (shouldSkipBrainTts(message, brainHintsRef.current)) {
              stopTtsPlayback();
              clearTtsQueue();
            }
            suppressTurnAudioRef.current = true;
            setMeaningCheck(message.confidence_message || message.clarify_message || "Check meaning");
            setStatusType("warning");
          } else {
            suppressTurnAudioRef.current = false;
            if (brainHintsRef.current?.skip_tts || brainHintsRef.current?.tts_mode === "skip") {
              brainHintsRef.current = { ...brainHintsRef.current, skip_tts: false, tts_mode: undefined };
            }
            if (asBool(message.low_confidence)) {
              setMeaningCheck(message.confidence_message || "Moderate confidence — double-check important details.");
              setStatusType("warning");
            }
          }
          rememberConversationTurn(message);
          setPartialTranscript("");
          if (isInterpreterActiveRef.current && isStreamingRef.current && !isPlayingTtsRef.current) {
            resumeAudioUpload();
            if (certStep === "none" && !blockContinuousAudio) {
              setStatusType("success");
            }
          }
        }
        break;
      case "partial_translation":
        syncRouteFromMessage(message);
        if (!uiActive) break;
        if (!suppressTurnAudioRef.current) {
          setLiveTranslation(message.text || "");
          setStatus(BRIDGE_CONN.understanding);
          const partialThreshold = typeof message.confidence_threshold === "number" ? message.confidence_threshold : 0.72;
          applyBrainPayload(message, "partial");
          const partialCertStep = applyCertificationFromMessage(message);
          if (partialCertStep === "required") {
            setClarifyMessage(certificationBanner(message, partialCertStep));
            setClarifyVisible(true);
          } else if (partialCertStep === "none" && (
            message.low_confidence
            || (typeof message.confidence === "number" && message.confidence < partialThreshold)
          )) {
            const partialHint = message.confidence_message || "Listening for clearer speech…";
            setMeaningCheck(partialHint);
            setStatusType("warning");
          }
        }
        break;
      case "active_speaker":
        syncRouteFromMessage(message);
        {
          const env = String(message.optimization?.environment || audioEnvironmentRef.current || "").toLowerCase();
          if (env && env !== "auto") {
            audioEnvironmentRef.current = env;
            setAudioEnvironment(env);
          }
          if (["restaurant", "street", "crowded", "noisy"].includes(env) && audioQuality !== "MEDIUM") {
            updateAudioQuality("MEDIUM");
          } else if (["quiet", "office"].includes(env) && audioQuality === "MEDIUM") {
            updateAudioQuality("HIGH");
          }
        }
        if (uiActive) {
          setConversationBrain(`${message.speaker_label || message.speaker || "Speaker"} is speaking`);
        }
        break;
      case "tts_style":
        syncRouteFromMessage(message);
        applyTtsStyle(message);
        break;
      case "turn":
        syncRouteFromMessage(message);
        {
          const brainUpdate = applyBrainPayload(message, "turn");
          if (brainUpdate?.speakerShift && brainUpdate.message && uiActive) {
            setStatus(brainUpdate.message);
          }
        }
        if (message.behavior === "hold" || message.behavior === "playback") {
          if (isPlayingTtsRef.current) stopTtsPlayback();
          pauseAudioUpload();
          if (uiActive) setStatus(message.reason || BRIDGE_ACTION.waitingPlayback);
        } else if (message.behavior === "interruption" || message.behavior === "turn_shift") {
          stopTtsPlayback();
          resumeAudioUpload();
          if (uiActive) setStatus(message.behavior === "turn_shift" ? BRIDGE_ACTION.speakerSwitched : BRIDGE_ACTION.speakerInterrupted);
        } else if (message.behavior === "overlap") {
          pauseAudioUpload();
          if (uiActive) setStatus(BRIDGE_ACTION.bothSpeakersListening);
        } else if (message.allowed === false) {
          pauseAudioUpload();
        } else if (isInterpreterActiveRef.current) {
          if (!isPlayingTtsRef.current) {
            resumeAudioUpload();
          }
        }
        break;
      case "semantic_context":
        if (!uiActive) break;
        setSemanticContext(message);
        if (message.emotion || message.tone || message.mood || message.conversation_mood || message.prosody_score) {
          setEmotionInfo({
            emotion: message.emotion,
            tone: message.tone || message.conversation_mood || message.mood,
            prosodyScore: message.prosody_score,
          });
        }
        break;
      case "clarify":
        syncRouteFromMessage(message);
        if (!uiActive) break;
        if (message.stage === "partial_low_confidence" || message.stage === "final_low_confidence") {
          syncHumanCertStep("none");
          suppressTurnAudioRef.current = false;
          setMeaningCheck(
            message.message || (message.stage === "partial_low_confidence"
              ? "Listening for clearer speech…"
              : "Moderate confidence — double-check important details."),
          );
          setStatus(message.stage === "partial_low_confidence" ? BRIDGE_ACTION.listeningClearer : BRIDGE_CONN.listeningSpeak);
          setStatusType("warning");
          break;
        }
        stopTtsPlayback();
        {
          applyBrainPayload(message, "clarify");
          const certStep = applyCertificationFromMessage(message);
          const clarifyText = certificationBanner(message, certStep) || message.message || "Check meaning";
          if (certStep === "required" || message.stage === "cip_clarification" || asBool(message.needs_confirmation)) {
            suppressTurnAudioRef.current = true;
            setMeaningCheck(clarifyText);
            setClarifyMessage(clarifyText);
            setClarifyVisible(true);
          } else {
            suppressTurnAudioRef.current = false;
            setMeaningCheck(clarifyText);
          }
          setStatus(certStep === "required" ? BRIDGE_ACTION.certRequired : BRIDGE_ACTION.checkMeaningRepeat);
          setStatusType("warning");
        }
        break;
      case "cancelled":
        stopTtsPlayback();
        clearTtsQueue();
        if (uiActive) {
          setStatus(BRIDGE_ACTION.turnCancelled);
          setStatusType("warning");
        }
        break;
      case "vad_error":
        if (uiActive) {
          setStatus(message.message || BRIDGE_ACTION.audioFallbackActive);
          setStatusType("warning");
        }
        break;
      case "tts_start":
        syncRouteFromMessage(message);
        if (message.partial) {
          if (shouldSuppressTtsPlayback(message) || userPausedConnectionRef.current || appStateRef.current !== "active") break;
          setIsPlayingTts(true);
          if (uiActive) setStatus(BRIDGE_ACTION.draftBridgeVoice);
          break;
        }
        if (
          shouldSuppressTtsPlayback(message)
          || userPausedConnectionRef.current
          || appStateRef.current !== "active"
        ) {
          stopTtsPlayback();
          clearTtsQueue();
          setStatus(shouldSuppressTtsPlayback(message) ? BRIDGE_ACTION.confirmBeforeVoice : BRIDGE_ACTION.voiceCommandHandled);
          break;
        }
        setStatus(message.chunks ? BRIDGE_ACTION.speakingVoiceChunk(1, message.chunks) : BRIDGE_CONN.voiceDelivered);
        pauseMicForPlayback().catch((error) => console.error("Error pausing mic for TTS:", error));
        break;
      case "tts_audio_chunk":
        syncRouteFromMessage(message);
        if (shouldSuppressTtsPlayback(message) || userPausedConnectionRef.current || appStateRef.current !== "active") break;
        if (!message.partial && message.index === 1 && !firstAudioSeenRef.current) {
          firstAudioSeenRef.current = true;
          if (streamStartedAtRef.current > 0) {
            const firstAudio = now - streamStartedAtRef.current;
            setLatencyMetrics((previous) => ({ ...previous, first_audio: firstAudio, lastUpdate: now }));
          }
        }
        if (message.index === 1 && !message.partial) setTurnCount((previous) => previous + 1);
        handleTtsChunk(message);
        if (latencyStartRef.current.tts && message.index === 1) {
          const ttsLatency = now - latencyStartRef.current.tts;
          setLatencyMetrics((previous) => ({ ...previous, ttsLatency, lastUpdate: now }));
          delete latencyStartRef.current.tts;
        }
        break;
      case "tts_end":
        syncRouteFromMessage(message);
        if (message.partial) break;
        if (shouldSuppressTtsPlayback(message)) {
          releaseCommandMute();
          break;
        }
        if (uiActive) setStatus(BRIDGE_CONN.voiceDelivered);
        if (latencyStartRef.current.endToEnd) {
          const endToEndLatency = now - latencyStartRef.current.endToEnd;
          setLatencyMetrics((previous) => ({ ...previous, endToEndLatency, lastUpdate: now }));
          delete latencyStartRef.current.endToEnd;
        }
        if (
          isInterpreterActiveRef.current
          && appStateRef.current === "active"
          && !userPausedConnectionRef.current
        ) {
          resumeAfterTtsRef.current = true;
          setStatus(BRIDGE_CONN.listeningSpeak);
          if (!isPlayingTtsRef.current) {
            resumeMicAfterPlayback().catch((error) => console.error("Error resuming mic after TTS:", error));
          }
        } else {
          resumeAfterTtsRef.current = false;
        }
        break;
      case "stage": {
        const stageLabel = resolvePipelineStageLabel(message.stage, message.message);
        if (message.stage === "queued") {
          if (uiActive) {
            setStatus(stageLabel);
            setStatusType("connecting");
          }
          break;
        }
        if (message.stage === "translation" || message.stage === "stt" || message.stage === "tts") {
          if (uiActive) setStatus(stageLabel);
          break;
        }
        if (message.stage === "tts_skipped") {
          const skipReason = String(message.message || stageLabel || "");
          const benignSkip = /already streamed|browser voice handles|live voice/i.test(skipReason);
          if (benignSkip) {
            if (brainHintsRef.current?.skip_tts || brainHintsRef.current?.tts_mode === "skip") {
              brainHintsRef.current = { ...brainHintsRef.current, skip_tts: false, tts_mode: undefined };
            }
            suppressTurnAudioRef.current = false;
            if (isInterpreterActiveRef.current && isStreamingRef.current && isAudioUploadPaused()) {
              resumeAudioUpload();
            }
          } else {
            stopTtsPlayback();
            clearTtsQueue();
            suppressTurnAudioRef.current = true;
          }
          if (uiActive) {
            setStatus(stageLabel);
            setStatusType(benignSkip ? "success" : "warning");
          }
          break;
        }
        if (message.stage === "smoothing") {
          if (uiActive) {
            setStatus(stageLabel);
            setStatusType("success");
          }
          break;
        }
        if (message.stage === "partial_timeout" || message.stage === "live_text_timeout") {
          if (uiActive) {
            setStatus(stageLabel);
            setStatusType("warning");
          }
          break;
        }
        if (
          message.stage === "partial_degraded"
          || message.stage === "turn_held"
          || message.stage === "weak_audio"
        ) {
          if (uiActive) {
            setStatus(stageLabel);
            setStatusType("warning");
          }
          break;
        }
        if (uiActive && !suppressTurnAudioRef.current) setStatus(stageLabel || message.type);
        break;
      }
      case "vad":
        if (message.speech_detected) {
          if (uiActive) setStatus(BRIDGE_ACTION.speechDetected);
          latencyStartRef.current.endToEnd = now;
        }
        break;
      case "latency":
        if (message.metric && message.ms) {
          setLatencyMetrics((previous) => ({ ...previous, [message.metric]: message.ms, lastUpdate: now }));
        }
        break;
      case "error":
        if (message.warming) {
          if (activeHandlerGenerationRef.current !== connectGenerationRef.current) break;
          setStatus(message.message || BRIDGE_CONN.warmupRetry);
          setStatusType("connecting");
          prepareForSocketReconnect();
          const warmingCtrl = wsControlRef.current;
          if (warmingCtrl) {
            wsControlRef.current = null;
            shutdownSocketControl(warmingCtrl);
          }
          if (warmingRetryTimerRef.current) clearTimeout(warmingRetryTimerRef.current);
          const warmingGen = connectGenerationRef.current;
          warmingRetryTimerRef.current = setTimeout(() => {
            warmingRetryTimerRef.current = null;
            if (
              !mountedRef.current
              || appStateRef.current !== "active"
              || userPausedConnectionRef.current
              || connectGenerationRef.current !== warmingGen
            ) return;
            const retryWsUrl = apiToWsUrl(getActiveWsUrl(), "/ws/audio", tokenRef.current);
            if (wsControlRef.current?.forceReconnect) {
              wsControlRef.current.forceReconnect(retryWsUrl);
            } else {
              connect(tokenRef.current || undefined);
            }
          }, 2500);
          break;
        }
        if (message.recoverable && isInterpreterActiveRef.current) {
          if (activeHandlerGenerationRef.current !== connectGenerationRef.current) break;
          setStatus(message.message || BRIDGE_ACTION.trySpeakingAgain);
          setStatusType("warning");
          if (isStreamingRef.current && isAudioUploadPaused()) {
            resumeAudioUpload();
          }
          if (!isStreamingRef.current && !startingStreamRef.current && !isPlayingTtsRef.current) {
            if (recoverableRetryTimerRef.current) clearTimeout(recoverableRetryTimerRef.current);
            recoverableRetryTimerRef.current = setTimeout(() => {
              recoverableRetryTimerRef.current = null;
              if (
                mountedRef.current
                && appStateRef.current === "active"
                && !userPausedConnectionRef.current
                && activeHandlerGenerationRef.current === connectGenerationRef.current
                && isInterpreterActiveRef.current
                && isSocketOpen()
                && serverReadyRef.current
                && sessionHandshakeRef.current
              ) {
                startListening();
              }
            }, 350);
          }
          break;
        }
        if (activeHandlerGenerationRef.current !== connectGenerationRef.current) break;
        setStatus(message.message || message.error || BRIDGE_ACTION.bridgeServerError);
        setStatusType("error");
        if (message.message?.includes("No audio received") && isInterpreterActiveRef.current) {
          if (
            mountedRef.current
            && appStateRef.current === "active"
            && !userPausedConnectionRef.current
            && activeHandlerGenerationRef.current === connectGenerationRef.current
            && !isStreamingRef.current
            && !startingStreamRef.current
            && !isPlayingTtsRef.current
            && serverReadyRef.current
            && sessionHandshakeRef.current
          ) {
            startListening();
          }
        }
        break;
      default:
        debugLog("Unhandled message type:", message.type, message);
    }
  }

  handleMessageRef.current = handleMessage;
  setStatusWithTypeRef.current = setStatusWithType;

  function userDisconnect() {
    userPausedConnectionRef.current = true;
    autoConnectStartedRef.current = false;
    cancelScheduledConnection();
    disconnect();
  }

  function disconnect() {
    connectGenerationRef.current += 1;
    cancelLogin();
    cancelDiscovery();
    autoLoginAttemptedRef.current = false;
    loginInFlightRef.current = false;
    connectInFlightRef.current = false;
    cancelScheduledConnection();
    clearHandshakeWatchdog();
    clearHandshakeWait();
    clearTransientTimers();
    if (autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }
    lanConnectFailRef.current = 0;
    tunnelFallbackInFlightRef.current = false;
    tunnelRefreshInFlightRef.current = false;
    setShowAssistant(false);
    setIsInterpreterActive(false);
    resumeAfterTtsRef.current = false;
    resetSessionHandshake();
    if (wsControlRef.current) {
      const ctrl = wsControlRef.current;
      wsControlRef.current = null;
      shutdownSocketControl(ctrl);
    }
    if (isStreamingRef.current) {
      stopAudioStream();
      setIsStreaming(false);
    }
    clearTtsQueue();
    stopTtsPlayback();
    lastConnectedApiUrlRef.current = "";
    isConnectedRef.current = false;
    setIsConnected(false);
    setStatus(socketStatusMessages().disconnected);
    setStatusType("idle");
  }

  async function startListening() {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) return;
    if (startingStreamRef.current || isPlayingTtsRef.current) return;
    if (isStreamingRef.current) {
      if (isAudioUploadPaused()) {
        try {
          await restoreRecordingAudioMode();
        } catch (error) {
          console.error("Error restoring recording audio mode:", error);
        }
        resumeAudioUpload();
        setStatus(BRIDGE_CONN.listeningSpeak);
        setStatusType("success");
      }
      return;
    }
    if (!isSocketOpen() || !serverReadyRef.current) {
      setStatus(BRIDGE_CONN.linking);
      setStatusType("connecting");
      connect(tokenRef.current || undefined);
      return;
    }
    if (!sessionHandshakeRef.current) {
      sendSessionStart();
      const handshakeWaitGen = connectGenerationRef.current;
      await new Promise((resolve) => {
        clearHandshakeWait();
        handshakeWaitTimerRef.current = setTimeout(() => {
          handshakeWaitTimerRef.current = null;
          resolve();
        }, 350);
      });
      if (
        !mountedRef.current
        || appStateRef.current !== "active"
        || !isInterpreterActiveRef.current
        || userPausedConnectionRef.current
        || connectGenerationRef.current !== handshakeWaitGen
      ) {
        startingStreamRef.current = false;
        return;
      }
    }

    startingStreamRef.current = true;
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      console.error("Haptic feedback error:", error);
    }
    setStatus(BRIDGE_ACTION.openingMic);
    const streamConnectGen = connectGenerationRef.current;
    const started = await startAudioStream(async (chunk, meta = {}) => {
      if (
        connectGenerationRef.current !== streamConnectGen
        || userPausedConnectionRef.current
        || appStateRef.current !== "active"
        || !wsControlRef.current?.isConnected
        || isAudioUploadPaused()
      ) return;
      if (typeof meta.audioLevel === "number" && Number.isFinite(meta.audioLevel)) {
        liveAudioLevelRef.current = Math.max(0, Math.min(1, meta.audioLevel));
      }
      const chunkMeta = {
        type: "chunk_meta",
        sent_at_ms: Date.now(),
        bytes: meta.byteLength ?? chunk.byteLength,
        mime_type: "audio/m4a",
        audio_level: meta.audioLevel ?? 0,
        metering_available: meta.meteringAvailable !== false,
        client_voice_active: meta.finalizeUtterance ? true : (meta.voiceActive ?? true),
        voice_active: meta.finalizeUtterance ? true : (meta.voiceActive ?? true),
      };
      wsControlRef.current.send(JSON.stringify(chunkMeta));
      wsControlRef.current.send(chunk);
      if (meta.finalizeUtterance) {
        wsControlRef.current.send(JSON.stringify({ type: "finalize" }));
      }
    }, (error) => {
      if (!mountedRef.current || appStateRef.current !== "active" || connectGenerationRef.current !== streamConnectGen) return;
      const blocked = /permission denied|microphone blocked/i.test(String(error || ""));
      setStatus(blocked ? BRIDGE_ACTION.micBlocked : BRIDGE_ACTION.streamError(error));
      setStatusType("error");
      setIsStreaming(false);
      setIsInterpreterActive(false);
      isInterpreterActiveRef.current = false;
      if (blocked) {
        showToast("Allow microphone for Expo Go in iPhone Settings", "error", 4000);
      }
    }, (activity = {}) => {
      if (
        connectGenerationRef.current !== streamConnectGen
        || userPausedConnectionRef.current
        || appStateRef.current !== "active"
        || !wsControlRef.current?.isConnected
        || isAudioUploadPaused()
      ) return;
      if (typeof activity.audioLevel === "number" && Number.isFinite(activity.audioLevel)) {
        liveAudioLevelRef.current = Math.max(0, Math.min(1, activity.audioLevel));
      }
      wsControlRef.current.send(JSON.stringify({
        type: "chunk_meta",
        heartbeat: true,
        sent_at_ms: Date.now(),
        mime_type: "audio/m4a",
        audio_level: activity.audioLevel ?? liveAudioLevelRef.current ?? 0,
        metering_available: activity.meteringAvailable !== false,
        client_voice_active: activity.voiceActive ?? false,
        voice_active: activity.voiceActive ?? false,
      }));
    });
    startingStreamRef.current = false;

    if (
      !mountedRef.current
      || appStateRef.current !== "active"
      || userPausedConnectionRef.current
      || connectGenerationRef.current !== streamConnectGen
    ) {
      if (started) await stopAudioStream();
      return;
    }

    if (started && isInterpreterActiveRef.current) {
      streamStartedAtRef.current = Date.now();
      firstAudioSeenRef.current = false;
      setIsStreaming(true);
      setStatus(socketStatusMessages().listening);
      setStatusType("success");
    } else if (started) {
      await stopAudioStream();
    } else {
      setIsInterpreterActive(false);
      isInterpreterActiveRef.current = false;
    }
  }

  async function stopListening(finalize = true) {
    if (!isStreamingRef.current && !startingStreamRef.current) return;
    startingStreamRef.current = false;
    setIsStreaming(false);
    if (
      finalize
      && appStateRef.current === "active"
      && isSocketOpen()
      && activeHandlerGenerationRef.current === connectGenerationRef.current
    ) {
      setStatus(BRIDGE_CONN.understanding);
      wsControlRef.current?.send(JSON.stringify({ type: "finalize" }));
    }
    await stopAudioStream();
  }

  async function pauseMicForPlayback() {
    if (userPausedConnectionRef.current || appStateRef.current !== "active") {
      resumeAfterTtsRef.current = false;
      if (isStreamingRef.current || startingStreamRef.current) {
        pauseAudioUpload();
      }
      return;
    }
    resumeAfterTtsRef.current = isInterpreterActiveRef.current;
    if (isStreamingRef.current || startingStreamRef.current) {
      pauseAudioUpload();
    }
  }

  async function resumeMicAfterPlayback() {
    if (!mountedRef.current || appStateRef.current !== "active" || userPausedConnectionRef.current) {
      resumeAfterTtsRef.current = false;
      return;
    }
    if (!isInterpreterActiveRef.current) {
      resumeAfterTtsRef.current = false;
      return;
    }
    resumeAfterTtsRef.current = false;
    if (isStreamingRef.current) {
      try {
        await restoreRecordingAudioMode();
      } catch (error) {
        console.error("Error restoring recording audio mode:", error);
      }
      resumeAudioUpload();
      setStatus(BRIDGE_CONN.listeningSpeak);
      setStatusType("success");
      return;
    }
    if (
      !isPlayingTtsRef.current
      && !startingStreamRef.current
      && isSocketOpen()
      && serverReadyRef.current
      && sessionHandshakeRef.current
      && activeHandlerGenerationRef.current === connectGenerationRef.current
    ) {
      startListening();
    }
  }

  function activateInterpreter() {
    if (!mountedRef.current || appStateRef.current !== "active") return;
    userPausedConnectionRef.current = false;
    setIsInterpreterActive(true);
    isInterpreterActiveRef.current = true;
    setVoiceIntent(barrierMode ? `${activeSource} and ${activeTarget}` : `${activeSource} to ${activeTarget}`);
    if (!isSocketOpen() || !serverReadyRef.current) {
      connect(tokenRef.current || undefined);
    } else if (sessionHandshakeRef.current) {
      startListening();
    } else {
      sendSessionStart();
    }
  }

  async function pauseInterpreter() {
    setIsInterpreterActive(false);
    isInterpreterActiveRef.current = false;
    resumeAfterTtsRef.current = false;
    if (autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
    await stopListening(true);
    if (!mountedRef.current) return;
    clearTtsQueue();
    setStatus(BRIDGE_ACTION.bridgePaused);
    setStatusType(isConnectedRef.current ? "success" : "idle");
    showToast(pauseBridgeToast(), "success");
  }

  async function toggleInterpreter() {
    if (!mountedRef.current || appStateRef.current !== "active") return;
    if (isPlayingTts) {
      await tapHaptic("light");
      stopTtsPlayback();
      setStatus(BRIDGE_ACTION.stoppedPlayback);
      setStatusType(isConnectedRef.current ? "success" : "idle");
      return;
    }
    if (isInterpreterActive) {
      if (isStreamingRef.current) {
        await tapHaptic("light");
        await pauseInterpreter();
        return;
      }
      await tapHaptic("light");
      setStatus(BRIDGE_ACTION.stillListening);
      setStatusType("success");
      if (!startingStreamRef.current && !isPlayingTtsRef.current) {
        startListening();
      }
      return;
    }
    await tapHaptic("medium");
    activateInterpreter();
  }

  function applyLanguageSelection(side, code) {
    if (!code || (side === "source" && code === sourceLanguage) || (side === "target" && code === targetLanguage)) {
      setLanguagePicker(null);
      return;
    }
    const nextSource = side === "source" ? code : sourceLanguage;
    const nextTarget = side === "target" ? code : targetLanguage;
    setSourceLanguage(nextSource);
    setTargetLanguage(nextTarget);
    sendRouteConfig(nextSource, nextTarget, barrierMode);
    setSpeakerRoute((current) => ({
      ...current,
      sourceLanguage: nextSource,
      targetLanguage: nextTarget,
      detectedLanguage: side === "source" ? nextSource : current.detectedLanguage,
    }));
    setVoiceIntent(
      barrierMode
        ? `${getLanguageLabel(nextSource)} ↔ ${getLanguageLabel(nextTarget)}`
        : `${getLanguageLabel(nextSource)} → ${getLanguageLabel(nextTarget)}`
    );
    setLanguagePicker(null);
    tapHaptic("success");
  }

  function clearPanel() {
    setPartialTranscript("");
    setLiveTranslation("");
    setResult(null);
    setTurnCount(0);
    const cleared = clearPanelCopy();
    setVoiceIntent(cleared.voiceIntent);
    clearHumanCertification();
    resetBrainRuntimeUi();
    setConfidenceWarningVisible(false);
    setConfidenceWarningMessage("");
    setConversationTurns([]);
    setSemanticContext(null);
    setConversationBrain(null);
    setEmotionInfo(null);
    setSpeakerRoute({
      speakerLabel: "Person 1",
      speakerIndex: 1,
      listenerLabel: "Person 2",
      sourceLanguage,
      targetLanguage,
      detectedLanguage: sourceLanguage,
      routeConfidence: 1,
    });
    clearTtsQueue();
    clearReplayAudio();
    showToast(cleared.toast, "success");
  }

  function scrollToTranslationLane() {
    const offset = Math.max(0, translationLaneOffsetRef.current - 12);
    transcriptScrollRef.current?.scrollTo({ y: offset, animated: true });
    setTranscriptScrolled(offset > 96);
  }

  function queueVolumeToast(nextVolume) {
    if (volumeToastTimerRef.current) clearTimeout(volumeToastTimerRef.current);
    volumeToastTimerRef.current = setTimeout(() => {
      volumeToastTimerRef.current = null;
      if (!mountedRef.current || appStateRef.current !== "active") return;
      showToast(`Volume ${Math.round(Number(nextVolume) * 100)}%`, "success");
    }, 450);
  }

  function queueSpeedToast(nextSpeed) {
    if (speedToastTimerRef.current) clearTimeout(speedToastTimerRef.current);
    speedToastTimerRef.current = setTimeout(() => {
      speedToastTimerRef.current = null;
      if (!mountedRef.current || appStateRef.current !== "active") return;
      showToast(`Speed ${Number(nextSpeed).toFixed(1)}x`, "success");
    }, 450);
  }

  function swapRoute() {
    tapHaptic("light");
    const nextSource = targetLanguage;
    const nextTarget = sourceLanguage;
    setSourceLanguage(nextSource);
    setTargetLanguage(nextTarget);
    sendRouteConfig(nextSource, nextTarget, barrierMode);
    clearReplayAudio();
    setMeaningCheck("");
    setSpeakerRoute({
      speakerLabel: "Person 1",
      speakerIndex: 1,
      listenerLabel: "Person 2",
      sourceLanguage: nextSource,
      targetLanguage: nextTarget,
      detectedLanguage: nextSource,
      routeConfidence: 1,
    });
    setVoiceIntent(barrierMode ? `${getLanguageLabel(nextSource)} and ${getLanguageLabel(nextTarget)}` : `${getLanguageLabel(nextSource)} to ${getLanguageLabel(nextTarget)}`);
  }

  async function replayLastTranslation() {
    if (!hasReplayAudio || isPlayingTts) return;
    await pauseMicForPlayback();
    setStatus(replayStatusMessages().replaying);
    setStatusType("success");
    const replayed = await replayLastTts();
    if (!mountedRef.current) return;
    const socketMsgs = socketStatusMessages();
    setStatus(
      replayed && isInterpreterActiveRef.current
        ? socketMsgs.readyToListen
        : replayed
          ? socketMsgs.voiceDelivered
          : socketMsgs.noVoiceReplay,
    );
    setStatusType(replayed ? "success" : "warning");
  }

  toggleStreamingRef.current = toggleInterpreter;

  async function showFirstRunHelpIfNeeded() {
    try {
      const helpSeen = await SecureStore.getItemAsync(HELP_SEEN_KEY);
      if (!mountedRef.current) return;
      if (!helpSeen) {
        await SecureStore.setItemAsync(HELP_SEEN_KEY, "1");
        if (!mountedRef.current) return;
        if (helpTimerRef.current) clearTimeout(helpTimerRef.current);
        helpTimerRef.current = setTimeout(() => {
          helpTimerRef.current = null;
          if (mountedRef.current && appStateRef.current === "active" && !userPausedConnectionRef.current) {
            setShowHelp(true);
          }
        }, 700);
      }
    } catch {
      // Non-fatal if secure storage is unavailable
    }
  }

  async function handleStartCloud() {
    const cloud = getConsumerCloudApiUrl();
    if (!cloud || !validateUrl(cloud)) {
      setStatus(BRIDGE_ACTION.invalidServerUrl);
      setStatusType("error");
      return;
    }
    const demo = getConsumerDemoCredentials();
    pinActiveWsUrl(cloud);
    await persistWsUrl(cloud);
    if (demo.username) setUsername(demo.username);
    if (demo.password) setPassword(demo.password);
    const ok = await checkBackendHealth(cloud);
    if (!mountedRef.current) return;
    if (!ok) {
      setStatus(BRIDGE_ACTION.testBridgeLink);
      setStatusType("error");
      return;
    }
    await login({
      apiUrl: cloud,
      username: demo.username,
      password: demo.password,
      onSuccess: async (accessToken) => {
        if (!mountedRef.current) return;
        await markSetupComplete();
        setShowSetup(false);
        setDismissedError("");
        userPausedConnectionRef.current = false;
        autoConnectStartedRef.current = true;
        if (appStateRef.current === "active" && networkStateRef.current?.isConnected !== false) {
          connect(accessToken);
        }
        await showFirstRunHelpIfNeeded();
      },
    });
  }

  async function finishSetup() {
    const trimmed = String(wsUrl || "").trim().replace(/\/+$/, "");
    if (!validateUrl(trimmed)) {
      setStatus(BRIDGE_ACTION.invalidServerUrl);
      setStatusType("error");
      return;
    }
    if (/localhost|127\.0\.0\.1/i.test(trimmed)) {
      setStatus(BRIDGE_ACTION.lanIpRequired);
      setStatusType("error");
      return;
    }
    const ok = await checkBackendHealth(trimmed);
    if (!mountedRef.current) return;
    if (!ok) {
      setStatus(BRIDGE_ACTION.testBridgeLink);
      setStatusType("error");
      return;
    }
    await persistWsUrl(trimmed);
    if (!mountedRef.current) return;
    await markSetupComplete();
    if (!mountedRef.current) return;
    setShowSetup(false);
    setDismissedError("");
    userPausedConnectionRef.current = false;
    autoConnectStartedRef.current = true;
    lastConnectAttemptRef.current = 0;
    if (appStateRef.current === "active" && networkStateRef.current?.isConnected !== false) {
      scheduleServerConnection(0);
    }
    await showFirstRunHelpIfNeeded();
  }

  async function handleSaveServerUrl(url) {
    const trimmed = String(url || "").trim().replace(/\/+$/, "");
    if (!validateUrl(trimmed)) {
      setStatus(BRIDGE_ACTION.invalidServerUrl);
      setStatusType("error");
      return;
    }
    if (/localhost|127\.0\.0\.1/i.test(trimmed)) {
      setStatus(BRIDGE_ACTION.lanIpRequired);
      setStatusType("error");
      return;
    }
    const previousUrl = getActiveWsUrl();
    await persistWsUrl(trimmed);
    if (!mountedRef.current) return;
    setDismissedError("");
    checkBackendHealth(trimmed, { quiet: true });
    userPausedConnectionRef.current = false;
    autoConnectStartedRef.current = true;
    if (previousUrl === trimmed) {
      retryConnection();
    }
    // URL change: wsUrl effect closes any live socket and reconnects after saveWsUrl updates state.
    setShowSettings(false);
  }

  if (!authLoaded || (hasConsumerCloudBackend() && !discoveryComplete)) {
    return (
      <SafeAreaView style={styles.container}>
        <LoadingScreen />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <LanguagePickerModal
        visible={languagePicker === "source"}
        title="Speak in language"
        variant="source"
        selectedCode={sourceLanguage}
        onSelect={(code) => applyLanguageSelection("source", code)}
        onClose={() => setLanguagePicker(null)}
      />
      <LanguagePickerModal
        visible={languagePicker === "target"}
        title="Translate to language"
        variant="target"
        selectedCode={targetLanguage}
        onSelect={(code) => applyLanguageSelection("target", code)}
        onClose={() => setLanguagePicker(null)}
      />

      <HelpTipsModal
        visible={showHelp}
        onClose={() => setShowHelp(false)}
        onOpenAssistant={isConnected && assistantApiUrl ? () => {
          setShowHelp(false);
          setShowAssistant(true);
        } : undefined}
      />

      <WelcomeSetupModal
        visible={showSetup}
        wsUrl={wsUrl}
        setWsUrl={editWsUrl}
        username={username}
        setUsername={setUsername}
        password={password}
        setPassword={setPassword}
        cloudApiUrl={hasConsumerCloudBackend() ? getConsumerCloudApiUrl() : ""}
        onStartCloud={handleStartCloud}
        onTestConnection={() => checkBackendHealth(wsUrl)}
        onLogin={async () => {
          const trimmed = String(wsUrl || "").trim().replace(/\/+$/, "");
          if (validateUrl(trimmed)) {
            pinActiveWsUrl(trimmed);
            await persistWsUrl(trimmed);
          }
          await login({
            onSuccess: async (accessToken) => {
              await markSetupComplete();
              setShowSetup(false);
              setDismissedError("");
              userPausedConnectionRef.current = false;
              autoConnectStartedRef.current = true;
              if (appStateRef.current === "active" && networkStateRef.current?.isConnected !== false) {
                connect(accessToken);
              }
              await showFirstRunHelpIfNeeded();
            },
          });
        }}
        onContinue={finishSetup}
        onDismiss={finishSetup}
        backendReachable={backendReachable}
        isChecking={isCheckingBackend}
      />

      <Modal visible={showSettings} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowSettings(false)}>
        <SafeAreaView style={styles.settingsOverlay}>
          <SettingsScreen
            wsUrl={wsUrl}
            setWsUrl={editWsUrl}
            onSaveUrl={handleSaveServerUrl}
            onClose={() => setShowSettings(false)}
            onTestConnection={() => checkBackendHealth(wsUrl)}
            onLogin={() => {
              const trimmed = String(wsUrl || "").trim().replace(/\/+$/, "");
              pinActiveWsUrl(trimmed);
              return login({
              apiUrl: trimmed || wsUrl,
              onSuccess: (accessToken) => {
                if (!mountedRef.current || appStateRef.current !== "active") return;
                userPausedConnectionRef.current = false;
                autoConnectStartedRef.current = true;
                prepareForSocketReconnect();
                if (wsControlRef.current) {
                  closeSocketControlIfLive(wsControlRef.current);
                  wsControlRef.current = null;
                }
                connect(accessToken);
              },
            });
            }}
            onLogout={() => {
              autoLoginAttemptedRef.current = false;
              tokenRef.current = "";
              logout({ onDisconnect: userDisconnect });
            }}
            username={username}
            setUsername={setUsername}
            password={password}
            setPassword={setPassword}
            isLoggedIn={Boolean(token)}
            recentUrls={recentUrls}
            showRecentUrls={showRecentUrls}
            setShowRecentUrls={setShowRecentUrls}
            backendReachable={backendReachable}
            isCheckingBackend={isCheckingBackend}
            sourceLanguage={sourceLanguage}
            setSourceLanguage={setSourceLanguage}
            targetLanguage={targetLanguage}
            setTargetLanguage={setTargetLanguage}
            volume={volume}
            setVolume={(nextVolume) => {
              setVolume(nextVolume);
              queueVolumeToast(nextVolume);
            }}
            playbackSpeed={playbackSpeed}
            setPlaybackSpeed={(speed) => {
              setPlaybackSpeed(speed);
              queueSpeedToast(speed);
            }}
            debugMode={showDebugDetails}
            setDebugMode={setShowDebugDetails}
            barrierMode={barrierMode}
            setBarrierMode={(enabled) => applyBarrierMode(enabled, { haptic: false })}
            audioQuality={audioQuality}
            setAudioQuality={updateAudioQuality}
            audioEnvironment={audioEnvironment}
            setAudioEnvironment={(value) => {
              const next = String(value || "auto").toLowerCase();
              audioEnvironmentRef.current = next;
              setAudioEnvironment(next);
              sendRouteConfig(sourceLanguage, targetLanguage, barrierMode);
            }}
            lowBandwidthMode={lowBandwidthMode}
            setLowBandwidthMode={updateLowBandwidthMode}
            diagnostics={diagnostics}
            diagnosticsStatus={diagnosticsStatus}
            onRefreshDiagnostics={loadDiagnostics}
            latencyMetrics={latencyMetrics}
            batchRecording={Boolean(recording)}
            isBatchUploading={isBatchUploading}
            batchUploadProgress={batchUploadProgress}
            batchRecordDisabled={isStreaming || isInterpreterActive || isPlayingTts}
            onStartBatchRecord={isConnected ? startBatchRecording : undefined}
            onStopBatchRecord={stopBatchRecording}
            onCancelBatchUpload={cancelBatchUpload}
            onClearData={async () => {
              disconnect();
              await clearAllData();
              userPausedConnectionRef.current = false;
              autoConnectStartedRef.current = false;
              autoLoginAttemptedRef.current = false;
              lastProbedUrlRef.current = null;
              setShowSettings(false);
              setShowSetup(true);
              if (validateUrl(API_URL)) {
                await persistWsUrl(API_URL);
                lastProbedUrlRef.current = API_URL;
                checkBackendHealth(API_URL, { quiet: true });
              }
            }}
          />
        </SafeAreaView>
      </Modal>

      <LinearGradient
        colors={["#03050a", "#071018", "#0a1628", "#03050a"]}
        locations={[0, 0.35, 0.7, 1]}
        style={styles.pageGradient}
      >
      {advancedChrome ? <CosmicAmbience /> : null}
      <View style={[styles.page, compactLayout && styles.pageCompact]}>
        <View style={[
          styles.interpreterPanel,
          compactLayout && styles.interpreterPanelCompact,
          tinyLayout && styles.interpreterPanelTiny,
          isConnected && styles.interpreterPanelOnline,
          isStreaming && styles.interpreterPanelListening,
        ]}>
          <View style={[styles.panelAura, isConnected && styles.panelAuraOnline]} pointerEvents="none" />
          <PanelListeningPulse visible={isConnected && isStreaming} />
          <LinearGradient
            colors={["rgba(103, 232, 249, 0.45)", "rgba(45, 212, 191, 0.2)", "transparent"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.panelTopShine}
            pointerEvents="none"
          />
          <LinearGradient
            colors={["transparent", "rgba(45, 212, 191, 0.18)", "rgba(103, 232, 249, 0.32)"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.panelBottomShine}
            pointerEvents="none"
          />
          <NeoHeader
            isConnected={isConnected}
            isConnecting={isConnecting}
            isListening={isStreaming}
            isSpeaking={isPlayingTts}
            statusLabel={panelState}
            buildTag={buildTag}
            volume={volume}
            onVolumeChange={(nextVolume) => {
              setVolume(nextVolume);
              queueVolumeToast(nextVolume);
            }}
            compact={compactLayout}
            statusColor={isConnected ? "#34d399" : isConnecting ? "#67e8f9" : "#f87171"}
            onHelp={() => setShowHelp(true)}
            onAssistant={advancedChrome && isConnected && assistantApiUrl ? () => setShowAssistant(true) : undefined}
            assistantEnabled={advancedChrome && isConnected && Boolean(assistantApiUrl)}
            onShare={advancedChrome ? shareSession : undefined}
            shareEnabled={advancedChrome && Boolean(sourceText || (translatedText && translatedText !== voiceIntent))}
            focusedMode={FOCUSED_PRODUCT_UI && !showDebugDetails}
            onSettings={() => setShowSettings(true)}
            onStatusPress={isConnected ? userDisconnect : retryConnection}
          />

          {advancedChrome ? (
          <ConnectionStrip
            visible={isConnected || Boolean(reconnectProgress)}
            isListening={isStreaming && !reconnectProgress}
            isSpeaking={isPlayingTts && !reconnectProgress}
            isReconnecting={Boolean(reconnectProgress)}
            reconnectAttempt={reconnectProgress?.attempt || wsControlRef.current?.reconnectAttempts || 0}
            reconnectMax={reconnectProgress?.maxAttempts || MAX_RECONNECT_ATTEMPTS}
            label={sessionReconnects > 0 ? `Bridge linked · ${sessionReconnects} recoveries` : "Bridge linked"}
          />
          ) : null}

          <ErrorBanner
            message={blockingError?.message}
            actionLabel={blockingError?.action}
            onAction={blockingError?.handler}
            onDismiss={() => setDismissedError(status)}
          />
          <ConversationQualityStack>
            {humanCertificationStep !== "none" && meaningCheck ? (
              <NativeSpeakerCertBanner
                step={humanCertificationStep}
                message={meaningCheck}
                onReview={() => {
                  scrollToTranslationLane();
                  sendGlossaryCorrectionFromResult(humanCertificationStep === "required" ? "medical" : "general");
                  showToast(toasts.reviewWithNative, "info");
                }}
                onDismiss={() => {
                  if (humanCertStepRef.current === "required") {
                    setMeaningCheck("");
                  } else {
                    clearHumanCertification();
                  }
                }}
              />
            ) : meaningCheck && !clarifyVisible ? (
              <ErrorBanner
                message={meaningCheck || "This translation may need a quick double-check before you rely on it."}
                variant="warning"
                actionLabel="Review"
                onAction={() => {
                  scrollToTranslationLane();
                  setMeaningCheck("");
                  showToast(toasts.reviewWithNative, "info");
                }}
                onDismiss={() => setMeaningCheck("")}
              />
            ) : null}
            <ClarifyPill
              visible={clarifyVisible}
              message={clarifyMessage}
              onSpeakAgain={() => {
                setClarifyVisible(false);
                setClarifyMessage("");
                setMeaningCheck("");
                suppressTurnAudioRef.current = false;
                setStatus(BRIDGE_ACTION.listeningSpeakAgain);
                setStatusType("success");
                if (isInterpreterActiveRef.current && !isStreamingRef.current && !isPlayingTtsRef.current) {
                  startListening().catch((error) => console.error("Error resuming after clarify:", error));
                }
              }}
              onDismiss={() => {
                setClarifyVisible(false);
                setClarifyMessage("");
              }}
            />
            <ConfidenceWarningBanner
              visible={confidenceWarningVisible && humanCertificationStep === "none"}
              message={confidenceWarningMessage}
              onDismiss={() => {
                setConfidenceWarningVisible(false);
                setConfidenceWarningMessage("");
              }}
            />
          </ConversationQualityStack>
          <View style={styles.qualityAlertStack}>
            <ReconnectFailureBanner
              visible={reconnectFailureVisible}
              message={reconnectFailureMessage()}
              onRetry={() => {
                setReconnectFailureVisible(false);
                userPausedConnectionRef.current = false;
                retryConnection();
              }}
              onDismiss={() => setReconnectFailureVisible(false)}
            />
          </View>
          {showOfflineCta ? (
            <OfflineConnectCard
              buildId={MOBILE_BUILD_ID}
              title={offlineConnectCopy({ onCellular: onCellularWithLanServer }).title}
              message={
                onCellularWithLanServer
                  ? offlineConnectCopy({ onCellular: true }).message
                  : `${offlineConnectCopy().message} Stuck on old UI? Use Safari bridge or Reload.`
              }
              isConnecting={isConnecting}
              hasWebApp={Boolean(preferredWebAppUrl || webAppUrl)}
              hasPhoneSetup={Boolean(phoneSetupUrl)}
              onOpenWeb={openWebInterpreter}
              onConnect={retryConnection}
              onReload={reloadApp}
              onSetupHelp={openPhoneSetupPage}
              webAppLabel={Platform.OS === "ios" ? "Open in Safari (mic needs HTTPS)" : "Open in Safari (works now)"}
            />
          ) : null}

          <View style={styles.speechWorkspace}>
          <LanguageRouteBand
            sourceFlag={LANGUAGE_FLAGS[sourceLanguage] || "🌐"}
            targetFlag={LANGUAGE_FLAGS[targetLanguage] || "🌐"}
            sourceLabel={activeSource}
            targetLabel={activeTarget}
            sourceActive={Number(speakerRoute.speakerIndex) === 1}
            targetActive={Number(speakerRoute.speakerIndex) === 2}
            twoWay={barrierMode}
            isBridging={isStreaming || isPlayingTts}
            compact={compactLayout}
            onPickSource={() => setLanguagePicker("source")}
            onPickTarget={() => setLanguagePicker("target")}
            onSwap={swapRoute}
          />

          {advancedChrome ? (
          <RouteModeStrip
            sourceLabel={activeSource}
            targetLabel={activeTarget}
            twoWay={barrierMode}
            onToggleMode={toggleBarrierMode}
            speakerLabel={isConnected && routeConfidence > 0 ? `${activeSpeakerLabel} · on the bridge` : ""}
          />
          ) : null}

          {advancedChrome ? (
          <DuplexConversationPanel
            visible={isConnected && barrierMode}
            compact={compactLayout}
            sourceLabel={activeSource}
            targetLabel={activeTarget}
            activeSpeakerIndex={speakerRoute.speakerIndex}
            activeSpeakerLabel={activeSpeakerLabel}
            routeConfidence={routeConfidence}
            isStreaming={isStreaming}
          />
          ) : null}

          <MicPanelFrame isListening={isStreaming} isArmed={isInterpreterActive} isBridgingOut={isPlayingTts}>
            <MicOrbButton
              onPress={needsServerLink ? retryConnection : toggleInterpreter}
              disabled={isConnecting && !isInterpreterActive && !needsServerLink}
              isListening={isStreaming}
              isSpeaking={isPlayingTts}
              isArmed={isInterpreterActive}
              isOffline={needsServerLink}
              isConnecting={isConnecting && !isInterpreterActive}
              isBusy={isConnecting && !isInterpreterActive && !needsServerLink}
              isProcessing={isTranslating && !isStreaming}
              audioLevel={liveAudioLevel}
              icon={primaryIcon}
              label={isConnecting && !isInterpreterActive ? BRIDGE_ACTION.linkingLabel : primaryButtonText}
              hint={micHint}
              compact={compactLayout}
              tiny={tinyLayout}
              accessibilityLabel={needsServerLink ? "Link the bridge server" : primaryActionLabel}
            />
            {isConnected && (isStreaming || isInterpreterActive) ? (
              <StopListeningButton onPress={pauseInterpreter} />
            ) : null}
            <VoiceMeter
              active={isConnected && isStreaming}
              idle={isConnected && isInterpreterActive && !isStreaming}
              level={liveAudioLevel}
            />
            <LiveStatusPanel visible={liveStatusVisible} mode={liveStatusMode} label={liveStatusText} />
            <ProcessingPill
              visible={isConnected && !isStreaming && !isPlayingTts && (isTranslating || /queued/i.test(status || ""))}
              message={processingPillMessage({ queued: /queued/i.test(status || "") })}
            />
          </MicPanelFrame>
          </View>

          {advancedChrome ? (
          <FlowRail
            compact={compactLayout}
            muted={!isConnected}
            steps={FLOW_STEPS.map((step) => ({
              ...step,
              active: flowActiveKey === step.key,
            }))}
          />
          ) : null}

          <ScrollView
            ref={transcriptScrollRef}
            style={styles.scrollPanel}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            onScroll={(event) => {
              const offsetY = event.nativeEvent.contentOffset.y;
              setTranscriptScrolled(offsetY > 96);
            }}
            scrollEventThrottle={32}
          >
          <View style={[styles.transcriptStack, compactLayout && styles.transcriptStackCompact, tinyLayout && styles.transcriptStackTiny]}>
            <TranscriptStackHeader
              label={transcriptHeaderLabel()}
              sublabel={transcriptExchangeLabel(turnCount)}
              turnCount={turnCount}
            />
            <EmptyTranscriptState
              visible={!sourceText && !translatedText && (isConnected || showOfflineCta)}
              isOffline={showOfflineCta}
              isPaused={isConnected && !isInterpreterActive && !isStreaming}
              isStreaming={isStreaming}
              isInterpreterActive={isInterpreterActive}
              twoWay={barrierMode}
              onStart={needsServerLink ? undefined : toggleInterpreter}
              onConnect={showOfflineCta ? retryConnection : undefined}
            />
            {advancedChrome && contextChipLabel ? <ContextChip label={contextChipLabel} /> : null}
            {advancedChrome && showSemanticTopics ? <SemanticContext context={semanticContext} /> : null}
            <BrainRepairPanel
              visible={brainUi.visible}
              message={brainUi.message}
              repairOptions={brainUi.repairOptions}
              highlightTerms={brainUi.highlightTerms}
              riskScore={brainUi.riskScore}
              onRepairPress={runRepairOption}
              panelStyle={styles.brainRepairPanelInline}
            />
            <View style={[
              styles.transcriptLane,
              compactLayout && styles.transcriptLaneCompact,
              Boolean(sourceText) && styles.transcriptLaneLive,
            ]}>
              <View style={[styles.laneAccent, Boolean(sourceText) && styles.laneAccentSourceLive]} />
              <View style={[styles.laneBody, compactLayout && styles.laneBodyCompact, Boolean(sourceText) && styles.laneBodyWithActions]}>
                <View style={styles.laneSheen} pointerEvents="none" />
                <LaneHeader
                  flag={LANGUAGE_FLAGS[sourceLanguage] || "🌐"}
                  label={laneHeaderLabel({ languageName: routeSource, side: "source", twoWay: barrierMode })}
                  isLive={Boolean(sourceText)}
                  tone="source"
                />
                <LaneLiveText
                  text={sourceText}
                  placeholder={sourcePlaceholder()}
                  style={styles.laneText}
                  placeholderStyle={[styles.laneText, styles.lanePlaceholder]}
                  numberOfLines={4}
                />
                <LaneCopyDock
                  visible={Boolean(sourceText)}
                  onShare={shareSourceText}
                  onCopy={copySourceText}
                  tone="source"
                />
              </View>
            </View>
            <LaneBridgeSpan active={isStreaming || isTranslating || isPlayingTts} />
            <View
              onLayout={(event) => {
                translationLaneOffsetRef.current = event.nativeEvent.layout.y;
              }}
              style={[
              styles.translationLane,
              compactLayout && styles.translationLaneCompact,
              Boolean(translatedText) && styles.translationLaneLive,
              isTranslating && !translatedText && styles.translationLaneBusy,
              isPlayingTts && styles.translationLaneSpeaking,
              translationCertAttention === "required" && styles.translationLaneCertRequired,
              translationCertAttention === "advisory" && styles.translationLaneCertAdvisory,
            ]}>
              <SpeakingLaneGlow visible={isPlayingTts} />
              <View style={[styles.laneAccent, Boolean(translatedText) && styles.laneAccentTargetLive]} />
              <View style={[styles.laneBody, compactLayout && styles.laneBodyCompact, Boolean(translatedText) && styles.laneBodyWithActions]}>
                <View style={styles.laneSheen} pointerEvents="none" />
                <LaneHeader
                  flag={LANGUAGE_FLAGS[targetLanguage] || "🌐"}
                  label={laneHeaderLabel({ languageName: routeTarget, side: "target", twoWay: barrierMode })}
                  isLive={Boolean(translatedText)}
                  isBusy={isTranslating && !translatedText}
                  tone="target"
                  attention={translationCertAttention}
                />
                <LaneLiveText
                  text={translatedText}
                  placeholder={targetPlaceholder({
                    twoWay: barrierMode,
                    isTranslating,
                    hasSource: Boolean(sourceText),
                    intentLine: voiceIntent,
                  })}
                  style={styles.translationText}
                  placeholderStyle={[styles.translationText, styles.lanePlaceholder]}
                  numberOfLines={5}
                />
                <LaneCopyDock
                  visible={Boolean(translatedText)}
                  onShare={shareTranslatedText}
                  onCopy={copyTranslatedText}
                  tone="target"
                />
              </View>
            </View>
            {advancedChrome ? <TurnHistoryRail turns={conversationTurns} onTurnPress={copyTurnHistory} /> : null}
          </View>
          </ScrollView>

          <StatusStrip
            onPress={!isConnected ? retryConnection : () => setShowDebugDetails((current) => !current)}
            compact={compactLayout}
            isConnected={isConnected}
            isConnecting={isConnecting}
            isStreaming={isStreaming}
            isTranslating={isTranslating}
            isPlayingTts={isPlayingTts}
            onCellularWithLanServer={onCellularWithLanServer}
            systemColor={systemColor}
            visibleStatusLine={visibleStatusLine}
            statusDetail={showDebugDetails ? "" : statusDetail}
            buildMeta={
              isConnected
                ? `Build ${MOBILE_BUILD_ID}${onCellularWithLanServer ? " · needs Wi‑Fi" : isPhoneOnWifi(networkState) ? " · Wi‑Fi" : ""}`
                : ""
            }
            debugExpanded={showDebugDetails}
            accessibilityLabel={isConnected ? "Status details" : "Tap to connect to server"}
            accessibilityHint={isConnected ? "Tap to show technical details" : "Retries the server link"}
          />

          <DebugDetailChips visible={isConnected && showDebugDetails} detail={statusDetail} />

          <SessionInsightsPanel
            visible={isConnected && !showDebugDetails}
            semanticContext={semanticContext}
            conversationBrain={conversationBrain}
            brainMessage={brainUi.message}
            emotionInfo={emotionInfo}
            isStreaming={isStreaming}
            isTranslating={isTranslating}
          />

          <DebugInsightsPanel
            visible={isConnected && showDebugDetails}
            semanticContext={semanticContext}
            conversationBrain={conversationBrain}
            brainMessage={brainUi.message}
            emotionInfo={emotionInfo}
            latencyMetrics={latencyMetrics}
            isStreaming={isStreaming}
            isTranslating={isTranslating}
            hasPartialStt={Boolean(partialTranscript)}
            hasPartialTranslation={Boolean(liveTranslation)}
            diagnostics={diagnostics}
            diagnosticsStatus={diagnosticsStatus}
          />

          {isConnected && showDebugDetails ? (
            <AdvancedFeatures
              noiseLevel={Math.round((liveAudioLevel || 0) * 100)}
              speakerDiarization={routeConfidence > 0}
              streamingStatus={{
                sttPartial: Boolean(partialTranscript),
                translationPartial: Boolean(liveTranslation),
              }}
              contextMemory={{
                technicalTerms: semanticContext?.technical_terms,
                conversationTopics: semanticContext?.topics,
              }}
              emotionalNuance={{
                emotion: semanticContext?.emotion,
                tone: semanticContext?.tone,
                prosodyScore: semanticContext?.prosody_score,
              }}
            />
          ) : null}

          {advancedChrome ? (
          <ControlDock
            compact={compactLayout}
            items={[
              {
                key: "replay",
                icon: hasReplayAudio ? "play-back" : "play-back-outline",
                label: dockCopy.replay,
                onPress: replayLastTranslation,
                disabled: !hasReplayAudio || isPlayingTts,
                active: hasReplayAudio && !isPlayingTts,
                accessibilityLabel: "Replay last bridged voice",
              },
              {
                key: "mode",
                icon: barrierMode ? "people" : "arrow-forward",
                label: dockCopy.mode,
                onPress: toggleBarrierMode,
                active: barrierMode,
                accessibilityLabel: modeToggleA11y(barrierMode),
              },
              {
                key: "connect",
                icon: isConnected ? "radio" : "refresh",
                label: dockCopy.connect,
                onPress: isConnected ? userDisconnect : retryConnection,
                active: isConnected,
                bridgeLinked: isConnected,
                urgent: !isConnected && !isConnecting,
                accessibilityLabel: isConnected ? "Disconnect bridge" : "Link conversation bridge",
              },
              {
                key: "clear",
                icon: "trash",
                label: dockCopy.clear,
                onPress: clearPanel,
                danger: true,
                accessibilityLabel: "Clear conversation bridge",
              },
            ]}
          />
          ) : null}
        </View>
      </View>
      </LinearGradient>
      <FloatingMicFab
        visible={isConnected && transcriptScrolled && !showOfflineCta}
        onPress={() => {
          transcriptScrollRef.current?.scrollTo({ y: 0, animated: true });
          setTranscriptScrolled(false);
          if (!isInterpreterActive || (!isStreaming && !isPlayingTts)) {
            toggleInterpreter();
          }
        }}
        isListening={isStreaming}
        isArmed={isInterpreterActive}
        audioLevel={liveAudioLevel}
        disabled={isConnecting && !isInterpreterActive}
        accessibilityLabel={
          isStreaming
            ? "Scroll to microphone"
            : isInterpreterActive
              ? "Scroll up and resume listening"
              : "Scroll up and start listening"
        }
      />
      <Assistant
        apiUrl={assistantApiUrl}
        authToken={token || ""}
        getTranslationContext={getAssistantContext}
        open={showAssistant}
        onOpenChange={setShowAssistant}
        renderFab={false}
      />
      <Toast message={toast?.message} variant={toast?.variant} />
    </SafeAreaView>
  );
}
