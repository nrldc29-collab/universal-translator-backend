import { useEffect, useMemo, useRef, useState } from "react";
import { SafeAreaView, View, Text, Pressable, useWindowDimensions, ScrollView, Modal, Linking } from "react-native";
import Constants from "expo-constants";
import * as Network from "expo-network";
import * as Haptics from "expo-haptics";
import { Ionicons } from "@expo/vector-icons";
import { apiToWsUrl, connectWS } from "./services/ws";
import { startAudioStream, stopAudioStream } from "./services/audio-stream";
import styles from "./AppStyles";
import { useMobileTts } from "./hooks/useMobileTts";
import { useMobileAuth } from "./hooks/useMobileAuth";
import { useMobileBrainContext } from "./hooks/useMobileBrainContext";
import { useMobileStreamState } from "./hooks/useMobileStreamState";
import { useMobileSession } from "./hooks/useMobileSession";
import { useMobileConnectionState } from "./hooks/useMobileConnectionState";
import { useMobileUiState } from "./hooks/useMobileUiState";
import WelcomeSetupModal from "./components/WelcomeSetupModal";
import ErrorBanner from "./components/ErrorBanner";
import SettingsScreen from "./components/SettingsScreen";

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || "";
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === "1");

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

function IconControl({ icon, label, onPress, disabled = false, active = false, danger = false, accessibilityLabel = label }) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled, selected: active }}
      hitSlop={8}
      style={({ pressed }) => [
        styles.iconControl,
        active && styles.iconControlActive,
        danger && styles.iconControlDanger,
        disabled && styles.iconControlDisabled,
        pressed && !disabled && styles.iconControlPressed,
      ]}
    >
      <Ionicons name={icon} size={20} color={danger ? "#fecaca" : active ? "#07131f" : "#dbeafe"} />
      <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.72} style={[styles.iconControlText, active && styles.iconControlTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function FlowStep({ icon, label, active = false }) {
  return (
    <View
      style={[styles.flowStep, active && styles.flowStepActive]}
      accessibilityRole="text"
      accessibilityLabel={`${label}${active ? ", active" : ""}`}
    >
      <Ionicons name={icon} size={14} color={active ? "#07131f" : "#a5b4fc"} />
      <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.flowStepText, active && styles.flowStepTextActive]}>
        {label}
      </Text>
    </View>
  );
}

export default function App() {
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
  } = useMobileStreamState();
  const { semanticContext, setSemanticContext, conversationBrain, setConversationBrain } = useMobileBrainContext();
  const {
    ttsQueue,
    isPlayingTts,
    isPlayingTtsRef,
    handleTtsChunk,
    replayLastTts,
    clearTtsQueue,
    clearReplayAudio,
    volume,
    setVolume,
    playbackSpeed,
    setPlaybackSpeed,
    stopTtsPlayback,
    hasReplayAudio,
  } = useMobileTts();
  const {
    token,
    wsUrl,
    setWsUrl,
    username,
    setUsername,
    password,
    setPassword,
    recentUrls,
    backendReachable,
    setupComplete,
    isCheckingBackend,
    loadStoredData,
    saveWsUrl,
    markSetupComplete,
    validateUrl,
    checkBackendHealth,
    login,
    logout,
    clearAllData,
  } = useMobileAuth({
    defaultUrl: API_URL,
    onStatus: (message, type) => {
      setStatus(message);
      if (type) setStatusType(type);
    },
  });

  const [showSetup, setShowSetup] = useState(false);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [showDebugDetails, setShowDebugDetails] = useState(false);
  const [dismissedError, setDismissedError] = useState("");

  const toggleStreamingRef = useRef(null);
  const autoConnectStartedRef = useRef(false);
  const isInterpreterActiveRef = useRef(false);
  const startingStreamRef = useRef(false);
  const autoResumeTimerRef = useRef(null);
  const suppressTurnAudioRef = useRef(false);
  const suppressReleaseTimerRef = useRef(null);
  const latencyStartRef = useRef({});
  const [isInterpreterActive, setIsInterpreterActive] = useState(false);
  const [turnCount, setTurnCount] = useState(0);
  const [voiceIntent, setVoiceIntent] = useState("Tap Start and speak");
  const [barrierMode, setBarrierMode] = useState(true);
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
  const [conversationTurns, setConversationTurns] = useState([]);
  const [latencyMetrics, setLatencyMetrics] = useState({
    sttLatency: 0,
    translationLatency: 0,
    ttsLatency: 0,
    endToEndLatency: 0,
    lastUpdate: 0,
  });

  const activeSource = getLanguageLabel(sourceLanguage);
  const activeTarget = getLanguageLabel(targetLanguage);
  const routeSource = getLanguageLabel(speakerRoute.sourceLanguage || sourceLanguage);
  const routeTarget = getLanguageLabel(speakerRoute.targetLanguage || targetLanguage);
  const activeSpeakerLabel = speakerRoute.speakerLabel || "Person 1";
  const activeListenerLabel = speakerRoute.listenerLabel || (Number(speakerRoute.speakerIndex) === 2 ? "Person 1" : "Person 2");
  const routeConfidence = Number(speakerRoute.routeConfidence || 0);
  const routeConfidenceLabel = routeConfidence > 0 ? `${Math.round(routeConfidence * 100)}% route` : null;
  const barrierLabel = barrierMode ? "Barrier" : "One way";
  const compactLayout = height < 730 || width < 370;
  const tinyLayout = height < 650;
  const primaryIconSize = tinyLayout ? 32 : compactLayout ? 36 : 42;
  const systemColor = getStatusColor(statusType);
  const panelState = isPlayingTts
    ? "Speaking"
    : isStreaming
      ? "Listening"
      : isInterpreterActive && isConnected
        ? "Ready"
        : isInterpreterActive
          ? "Connecting"
          : isConnected
            ? "Standby"
            : "Offline";
  const sourceText = partialTranscript || result?.source_text || result?.original_text || "";
  const translatedText = liveTranslation || result?.translated_text || "";
  const intentLine = useMemo(() => {
    if (semanticContext?.last_intent) return semanticContext.last_intent;
    if (semanticContext?.intent) return semanticContext.intent;
    return voiceIntent;
  }, [semanticContext, voiceIntent]);
  const flowDetail = conversationBrain || intentLine;
  const isTranslating = !isPlayingTts && /translat/i.test(status || "");
  const latestLatency = latencyMetrics.endToEndLatency || latencyMetrics.ttsLatency || latencyMetrics.translationLatency;
  const friendlyStatusDetail = [
    isInterpreterActive ? "Listening continuously" : isConnected ? "Tap Start when ready" : null,
    barrierMode ? "Two-way conversation" : "One-way translation",
    turnCount > 0 ? `${turnCount} phrase${turnCount === 1 ? "" : "s"} translated` : null,
  ].filter(Boolean).join(" · ");
  const debugStatusDetail = [
    flowDetail,
    barrierLabel,
    meaningCheck ? "Check meaning" : null,
    routeConfidenceLabel,
    latestLatency ? `${latestLatency}ms` : null,
    ttsQueue.length > 0 ? `${ttsQueue.length} queued` : null,
  ].filter(Boolean).join(" | ");
  const statusDetail = showDebugDetails ? debugStatusDetail : friendlyStatusDetail;
  const blockingError = useMemo(() => {
    if (dismissedError && status === dismissedError) return null;
    if (!networkState?.isConnected) {
      return { message: "No internet connection. Check Wi‑Fi or mobile data.", action: "Retry", handler: checkNetworkState };
    }
    if (statusType === "error") {
      if (/microphone|mic/i.test(status || "")) {
        return { message: status, action: "Open Settings", handler: () => Linking.openSettings() };
      }
      if (/backend|url|reachable|connection failed/i.test(status || "")) {
        return { message: status, action: "Server setup", handler: () => setShowSetup(true) };
      }
      return { message: status, action: "Retry", handler: connect };
    }
    return null;
  }, [dismissedError, networkState?.isConnected, status, statusType]);
  const primaryActionLabel = isPlayingTts
    ? "Stop spoken translation"
    : isInterpreterActive
      ? "Pause interpreter"
      : "Start interpreter";
  const primaryButtonText = isPlayingTts ? "Stop" : isInterpreterActive ? "Pause" : "Start";
  const primaryIcon = isPlayingTts ? "stop" : isInterpreterActive ? (isStreaming ? "pause" : "radio") : "mic";

  useEffect(() => {
    loadStoredData().then(() => setAuthLoaded(true));
    checkNetworkState();
    const interval = setInterval(checkNetworkState, 5000);
    return () => clearInterval(interval);
    // This starts the app's network poller once; recreating it on every render would duplicate connection attempts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!authLoaded) return;
    if (!setupComplete || !validateUrl(wsUrl)) {
      setShowSetup(true);
    } else {
      setShowSetup(false);
    }
  }, [authLoaded, setupComplete, wsUrl]);

  useEffect(() => {
    if (autoConnectStartedRef.current || !networkState?.isConnected || !wsUrl) return;
    autoConnectStartedRef.current = true;
    const timer = setTimeout(() => connect(), 450);
    return () => clearTimeout(timer);
    // Auto-connect should fire once when URL/network become available, not whenever handler identities change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [networkState?.isConnected, wsUrl]);

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
    if (!isInterpreterActive || !isConnected || isStreaming || isPlayingTts || startingStreamRef.current) return;
    if (autoResumeTimerRef.current) clearTimeout(autoResumeTimerRef.current);
    autoResumeTimerRef.current = setTimeout(() => {
      autoResumeTimerRef.current = null;
      if (isInterpreterActiveRef.current && isConnectedRef.current && !isStreamingRef.current && !isPlayingTtsRef.current) {
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

  useEffect(() => () => {
    releaseCommandMute();
    if (autoResumeTimerRef.current) clearTimeout(autoResumeTimerRef.current);
  }, []);

  async function checkNetworkState() {
    try {
      const state = await Network.getNetworkStateAsync();
      setNetworkState(state);

      if (state.isConnected && !isConnectedRef.current && wsUrl && autoConnectStartedRef.current) {
        setStatus("Network restored");
        setTimeout(() => {
          if (!isConnectedRef.current) connect();
        }, 700);
      }

      if (!state.isConnected && isConnectedRef.current) {
        setStatus("Network lost");
        disconnect();
      }
    } catch (error) {
      console.error("Network check error:", error);
    }
  }

  function connect() {
    if (wsControlRef.current?.isConnected) {
      setIsConnected(true);
      setStatus(isInterpreterActiveRef.current ? "Ready to listen" : "Connected");
      setStatusType("success");
      return;
    }

    if (!validateUrl(wsUrl)) {
      setStatus("Backend URL is not ready");
      setStatusType("error");
      return;
    }

    setStatus("Connecting");
    setStatusType("connecting");
    const url = apiToWsUrl(wsUrl, "/ws/audio", token);
    debugLog("Connecting to:", url);
    wsControlRef.current = connectWS(url, handleMessage, setStatusWithType);
    wsControlRef.current.updateHandlers(handleMessage, setStatusWithType);
  }

  function setStatusWithType(nextStatus, type = null) {
    setStatus(nextStatus);
    if (type) {
      setStatusType(type);
    } else if (nextStatus.includes("Connected")) {
      setStatusType("success");
      setIsConnected(true);
      saveRecentUrl(wsUrl);
      wsControlRef.current?.send(JSON.stringify({
        type: "start",
        session_id: mobileSessionIdRef.current,
        device_id: mobileDeviceIdRef.current,
        speaker: "auto",
        speaker_mode: "auto",
        source_language: sourceLanguage,
        target_language: targetLanguage,
        barrier_mode: barrierMode,
      }));
    } else if (nextStatus.includes("Reconnecting in")) {
      setStatusType("warning");
    } else if (nextStatus.includes("Reconnecting") || nextStatus.includes("Connecting")) {
      setStatusType("connecting");
    } else if (nextStatus.includes("Disconnected") || nextStatus.includes("failed") || nextStatus.includes("error")) {
      setStatusType("error");
      setIsConnected(false);
      if (isStreamingRef.current || startingStreamRef.current) {
        startingStreamRef.current = false;
        setIsStreaming(false);
        stopAudioStream().catch((error) => console.error("Error stopping mic after disconnect:", error));
      }
      if (nextStatus.includes("max retries")) {
        setIsInterpreterActive(false);
      }
    }
  }

  function sendRouteConfig(nextSource, nextTarget, nextBarrierMode = barrierMode) {
    wsControlRef.current?.send(JSON.stringify({
      type: "config",
      session_id: mobileSessionIdRef.current,
      device_id: mobileDeviceIdRef.current,
      speaker: "auto",
      speaker_mode: "auto",
      source_language: nextSource,
      target_language: nextTarget,
      barrier_mode: nextBarrierMode,
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

  function rememberConversationTurn(message) {
    const sourceTextValue = message.source_text || message.original_text || result?.source_text || "";
    const translatedTextValue = message.translated_text || message.text || result?.translated_text || "";
    if (!sourceTextValue && !translatedTextValue) return;
    const speakerIndex = Number(message.speaker_index || speakerRoute.speakerIndex || 1);
    const routeConfidence = Number(message.route_confidence ?? speakerRoute.routeConfidence ?? 1);
    const turn = {
      id: `${Date.now()}-${message.speaker || speakerIndex}`,
      speakerLabel: message.speaker_label || speakerRoute.speakerLabel || `Person ${speakerIndex}`,
      listenerLabel: message.listener_label || speakerRoute.listenerLabel || (speakerIndex === 2 ? "Person 1" : "Person 2"),
      sourceText: sourceTextValue,
      translatedText: translatedTextValue,
      sourceLanguage: message.source_language || speakerRoute.sourceLanguage || sourceLanguage,
      targetLanguage: message.target_language || speakerRoute.targetLanguage || targetLanguage,
      routeConfidence,
      clarify: asBool(message.clarify) || asBool(message.needs_confirmation) || routeConfidence < 0.5,
    };
    setConversationTurns((previous) => [...previous, turn].slice(-3));
  }

  function muteCommandTurn() {
    suppressTurnAudioRef.current = true;
    if (suppressReleaseTimerRef.current) clearTimeout(suppressReleaseTimerRef.current);
    suppressReleaseTimerRef.current = setTimeout(() => {
      suppressTurnAudioRef.current = false;
      suppressReleaseTimerRef.current = null;
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
      setStatus("Route updated");
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
      setStatus("Route swapped");
      setStatusType("success");
      return true;
    }

    if (command.type === "clear") {
      clearPanel();
      setVoiceIntent("Panel cleared");
      setStatus("Cleared");
      setStatusType("success");
      return true;
    }

    if (command.type === "barrier") {
      setBarrierMode(command.enabled);
      sendRouteConfig(sourceLanguage, targetLanguage, command.enabled);
      setMeaningCheck("");
      setVoiceIntent(command.enabled ? "Barrier Mode" : "One way");
      setStatus(command.enabled ? "Barrier Mode active" : "One-way mode");
      setStatusType("success");
      return true;
    }

    if (command.type === "replay") {
      replayLastTranslation().catch((error) => console.error("Replay command failed:", error));
      setVoiceIntent(hasReplayAudio ? "Replaying" : "No voice to replay");
      setStatus(hasReplayAudio ? "Replaying voice" : "No voice to replay");
      setStatusType(hasReplayAudio ? "success" : "warning");
      return true;
    }

    if (command.type === "connect") {
      setIsInterpreterActive(true);
      connect();
      setVoiceIntent("Reconnecting");
      return true;
    }

    if (command.type === "disconnect") {
      disconnect();
      setVoiceIntent("Disconnected");
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
      setStatus("Voice volume updated");
      setStatusType("success");
      return true;
    }

    if (command.type === "speed") {
      const nextSpeed = clamp(playbackSpeed + command.delta, 0.7, 1.25);
      setPlaybackSpeed(nextSpeed);
      setVoiceIntent(`Voice speed ${nextSpeed.toFixed(2)}x`);
      setStatus("Voice speed updated");
      setStatusType("success");
      return true;
    }

    return false;
  }

  function handleMessage(message) {
    debugLog("Message:", message.type, message);
    const now = Date.now();

    switch (message.type) {
      case "pong":
        break;
      case "config_ack":
        syncRouteFromMessage(message);
        setVoiceIntent(asBool(message.barrier_mode) ? `${getLanguageLabel(message.source_language)} and ${getLanguageLabel(message.target_language)}` : `${getLanguageLabel(message.source_language)} to ${getLanguageLabel(message.target_language)}`);
        break;
      case "speaker_detected":
        syncRouteFromMessage(message);
        setVoiceIntent(`${message.speaker_label || "Person"}: ${getLanguageLabel(message.source_language)} to ${getLanguageLabel(message.target_language)}`);
        break;
      case "final_transcription": {
        syncRouteFromMessage(message);
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
        setPartialTranscript(message.text || "");
        if (!suppressTurnAudioRef.current) setStatus("Listening");
        break;
      case "final":
      case "live_translation":
        syncRouteFromMessage(message);
        if (!suppressTurnAudioRef.current) {
          setLiveTranslation("");
          setResult((previous) => ({ ...previous, translated_text: message.text || message.translated_text }));
          setStatus("Translating");
        }
        if (latencyStartRef.current.translation) {
          const translationLatency = now - latencyStartRef.current.translation;
          setLatencyMetrics((previous) => ({ ...previous, translationLatency, lastUpdate: now }));
          delete latencyStartRef.current.translation;
        }
        if (message.type === "final") {
          rememberConversationTurn(message);
          setMeaningCheck(asBool(message.clarify) || asBool(message.needs_confirmation) ? "Check meaning" : "");
        }
        break;
      case "partial_translation":
        syncRouteFromMessage(message);
        if (!suppressTurnAudioRef.current) {
          setLiveTranslation(message.text || "");
          setStatus("Translating");
        }
        break;
      case "active_speaker":
        syncRouteFromMessage(message);
        setConversationBrain(`${message.speaker_label || message.speaker || "Speaker"} is speaking`);
        break;
      case "semantic_context":
        setSemanticContext(message);
        break;
      case "clarify":
        syncRouteFromMessage(message);
        setMeaningCheck(message.message || "Check meaning");
        setResult((previous) => ({ ...previous, translated_text: message.message || "Check meaning" }));
        setStatus("Check meaning");
        setStatusType("warning");
        break;
      case "tts_start":
        syncRouteFromMessage(message);
        if (suppressTurnAudioRef.current) {
          setStatus("Voice command handled");
          break;
        }
        setStatus(`Speaking voice ${message.chunks ? `1/${message.chunks}` : ""}`.trim());
        pauseMicForPlayback().catch((error) => console.error("Error pausing mic for TTS:", error));
        break;
      case "tts_audio_chunk":
        syncRouteFromMessage(message);
        if (suppressTurnAudioRef.current) break;
        if (message.index === 1) setTurnCount((previous) => previous + 1);
        handleTtsChunk(message);
        if (latencyStartRef.current.tts && message.index === 1) {
          const ttsLatency = now - latencyStartRef.current.tts;
          setLatencyMetrics((previous) => ({ ...previous, ttsLatency, lastUpdate: now }));
          delete latencyStartRef.current.tts;
        }
        break;
      case "tts_end":
        syncRouteFromMessage(message);
        if (suppressTurnAudioRef.current) {
          releaseCommandMute();
          break;
        }
        setStatus("Voice delivered");
        if (latencyStartRef.current.endToEnd) {
          const endToEndLatency = now - latencyStartRef.current.endToEnd;
          setLatencyMetrics((previous) => ({ ...previous, endToEndLatency, lastUpdate: now }));
          delete latencyStartRef.current.endToEnd;
        }
        if (resumeAfterTtsRef.current && isInterpreterActiveRef.current) {
          setStatus("Ready to listen");
        } else {
          resumeAfterTtsRef.current = false;
        }
        break;
      case "stage":
        if (!suppressTurnAudioRef.current) setStatus(message.message || message.type);
        break;
      case "vad":
        if (message.speech_detected) {
          setStatus("Speech detected");
          latencyStartRef.current.endToEnd = now;
        }
        break;
      case "latency":
        if (message.metric && message.ms) {
          setLatencyMetrics((previous) => ({ ...previous, [message.metric]: message.ms, lastUpdate: now }));
        }
        break;
      case "error":
        setStatus(message.message || message.error || "Server error");
        setStatusType("error");
        break;
      default:
        debugLog("Unhandled message type:", message.type, message);
    }
  }

  function disconnect() {
    setIsInterpreterActive(false);
    resumeAfterTtsRef.current = false;
    if (wsControlRef.current) {
      wsControlRef.current.close();
      wsControlRef.current = null;
    }
    if (isStreamingRef.current) {
      stopAudioStream();
      setIsStreaming(false);
    }
    clearTtsQueue();
    stopTtsPlayback();
    setIsConnected(false);
    setStatus("Disconnected");
    setStatusType("idle");
  }

  async function startListening() {
    if (startingStreamRef.current || isStreamingRef.current || isPlayingTtsRef.current) return;
    if (!isConnectedRef.current) {
      setStatus("Connecting");
      setStatusType("connecting");
      connect();
      return;
    }

    startingStreamRef.current = true;
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      console.error("Haptic feedback error:", error);
    }
    setStatus("Opening microphone");
    const started = await startAudioStream(async (chunk) => {
      if (wsControlRef.current?.isConnected) {
        wsControlRef.current?.send(JSON.stringify({
          type: "chunk_meta",
          sent_at_ms: Date.now(),
          bytes: chunk.byteLength,
          mime_type: "audio/m4a",
        }));
        wsControlRef.current?.send(chunk);
      }
    }, (error) => {
      setStatus(error === "Microphone permission denied" ? "Microphone blocked" : `Stream error: ${error}`);
      setStatusType("error");
      setIsStreaming(false);
      setIsInterpreterActive(false);
    });
    startingStreamRef.current = false;

    if (started && isInterpreterActiveRef.current) {
      setIsStreaming(true);
      setStatus("Listening");
      setStatusType("success");
    } else if (started) {
      await stopAudioStream();
    } else {
      setIsInterpreterActive(false);
    }
  }

  async function stopListening(finalize = true) {
    if (!isStreamingRef.current && !startingStreamRef.current) return;
    startingStreamRef.current = false;
    setIsStreaming(false);
    if (finalize) {
      setStatus("Translating");
      wsControlRef.current?.send(JSON.stringify({ type: "finalize" }));
    }
    await stopAudioStream();
  }

  async function pauseMicForPlayback() {
    if (isStreamingRef.current || startingStreamRef.current) {
      resumeAfterTtsRef.current = isInterpreterActiveRef.current;
      await stopListening(false);
    } else if (isInterpreterActiveRef.current) {
      resumeAfterTtsRef.current = true;
    }
  }

  function activateInterpreter() {
    setIsInterpreterActive(true);
    setVoiceIntent(barrierMode ? `${activeSource} and ${activeTarget}` : `${activeSource} to ${activeTarget}`);
    if (!isConnectedRef.current) {
      connect();
    } else {
      startListening();
    }
  }

  async function pauseInterpreter() {
    setIsInterpreterActive(false);
    resumeAfterTtsRef.current = false;
    if (autoResumeTimerRef.current) {
      clearTimeout(autoResumeTimerRef.current);
      autoResumeTimerRef.current = null;
    }
    await stopListening(true);
    clearTtsQueue();
    setStatus("Paused");
    setStatusType(isConnectedRef.current ? "success" : "idle");
  }

  async function toggleInterpreter() {
    if (isInterpreterActive) {
      await pauseInterpreter();
    } else {
      activateInterpreter();
    }
  }

  function clearPanel() {
    setPartialTranscript("");
    setLiveTranslation("");
    setResult(null);
    setTurnCount(0);
    setVoiceIntent("Tap Start and speak");
    setMeaningCheck("");
    setConversationTurns([]);
    clearTtsQueue();
    clearReplayAudio();
  }

  function swapRoute() {
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
    setStatus("Replaying voice");
    setStatusType("success");
    const replayed = await replayLastTts();
    setStatus(replayed && isInterpreterActiveRef.current ? "Ready to listen" : replayed ? "Voice delivered" : "No voice to replay");
    setStatusType(replayed ? "success" : "warning");
  }

  toggleStreamingRef.current = toggleInterpreter;

  async function finishSetup() {
    const trimmed = String(wsUrl || "").trim();
    if (!validateUrl(trimmed)) {
      setStatus("Enter a valid server URL starting with http:// or https://");
      setStatusType("error");
      return;
    }
    await saveWsUrl(trimmed);
    await markSetupComplete();
    setShowSetup(false);
    setDismissedError("");
    if (networkState?.isConnected) connect();
  }

  async function handleSaveServerUrl(url) {
    await saveWsUrl(url);
    setDismissedError("");
    disconnect();
    setTimeout(() => connect(), 400);
    setShowSettings(false);
  }

  return (
    <SafeAreaView style={styles.container}>
      <WelcomeSetupModal
        visible={showSetup}
        wsUrl={wsUrl}
        setWsUrl={setWsUrl}
        username={username}
        setUsername={setUsername}
        password={password}
        setPassword={setPassword}
        onTestConnection={() => checkBackendHealth(wsUrl)}
        onLogin={() => login({ onSuccess: () => markSetupComplete() })}
        onContinue={finishSetup}
        backendReachable={backendReachable}
        isChecking={isCheckingBackend}
      />

      <Modal visible={showSettings} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowSettings(false)}>
        <SafeAreaView style={styles.settingsOverlay}>
          <SettingsScreen
            wsUrl={wsUrl}
            setWsUrl={setWsUrl}
            onSaveUrl={handleSaveServerUrl}
            onClose={() => setShowSettings(false)}
            onTestConnection={() => checkBackendHealth(wsUrl)}
            onLogin={() => login()}
            onLogout={() => logout({ onDisconnect: disconnect })}
            username={username}
            setUsername={setUsername}
            password={password}
            setPassword={setPassword}
            isLoggedIn={Boolean(token)}
            recentUrls={recentUrls}
            sourceLanguage={sourceLanguage}
            setSourceLanguage={setSourceLanguage}
            targetLanguage={targetLanguage}
            setTargetLanguage={setTargetLanguage}
            volume={volume}
            setVolume={setVolume}
            playbackSpeed={playbackSpeed}
            setPlaybackSpeed={setPlaybackSpeed}
            debugMode={showDebugDetails}
            setDebugMode={setShowDebugDetails}
            onClearData={async () => {
              await clearAllData();
              setShowSettings(false);
              setShowSetup(true);
            }}
          />
        </SafeAreaView>
      </Modal>

      <View style={[styles.page, compactLayout && styles.pageCompact]}>
        <View style={[styles.interpreterPanel, compactLayout && styles.interpreterPanelCompact, tinyLayout && styles.interpreterPanelTiny]}>
          <View style={[styles.topBar, compactLayout && styles.topBarCompact]}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={styles.brand}>ANAI</Text>
              <Text numberOfLines={1} style={styles.brandSubline}>Live voice interpreter</Text>
            </View>
            <View style={styles.topBarActions}>
              <Pressable
                onPress={() => setShowSettings(true)}
                style={styles.settingsBtn}
                accessibilityRole="button"
                accessibilityLabel="Open settings"
              >
                <Ionicons name="settings-outline" size={20} color="#e2e8f0" />
              </Pressable>
              <View style={styles.connectionBadge}>
                <View style={[styles.connectionDot, { backgroundColor: systemColor }]} accessibilityLabel={`Status ${panelState}`} />
                <Text numberOfLines={1} style={styles.connectionText}>{panelState}</Text>
              </View>
            </View>
          </View>

          <ErrorBanner
            message={blockingError?.message}
            actionLabel={blockingError?.action}
            onAction={blockingError?.handler}
            onDismiss={() => setDismissedError(status)}
          />
          {meaningCheck ? (
            <ErrorBanner
              message={meaningCheck || "This translation may need a quick double-check before you rely on it."}
              variant="warning"
              onDismiss={() => setMeaningCheck("")}
            />
          ) : null}
          {!isInterpreterActive && !sourceText && !translatedText ? (
            <View style={styles.hintStrip}>
              <Text style={styles.hintStripText}>Tap the mic button to start. Speak naturally — translation plays automatically.</Text>
            </View>
          ) : null}

          <View style={[styles.routeBand, compactLayout && styles.routeBandCompact]}>
            <View
              style={[styles.routeSide, Number(speakerRoute.speakerIndex) === 1 && styles.routeSideActive, compactLayout && styles.routeSideCompact]}
              accessibilityLabel={`Person 1 speaks ${activeSource}`}
            >
              <Text style={styles.routeCaption}>Person 1</Text>
              <Text numberOfLines={1} adjustsFontSizeToFit style={styles.routeLanguage}>{activeSource}</Text>
            </View>
            <Pressable
              onPress={isConnected ? swapRoute : undefined}
              disabled={!isConnected}
              accessibilityRole="button"
              accessibilityLabel="Swap source and target languages"
              accessibilityState={{ disabled: !isConnected }}
              hitSlop={8}
              style={({ pressed }) => [
                styles.routeCenter,
                !isConnected && styles.routeCenterDisabled,
                pressed && isConnected && styles.routeCenterPressed,
              ]}
            >
              <Ionicons name="swap-horizontal" size={21} color="#0f172a" />
            </Pressable>
            <View
              style={[styles.routeSide, Number(speakerRoute.speakerIndex) === 2 && styles.routeSideActive, compactLayout && styles.routeSideCompact]}
              accessibilityLabel={`Person 2 speaks ${activeTarget}`}
            >
              <Text style={styles.routeCaption}>Person 2</Text>
              <Text numberOfLines={1} adjustsFontSizeToFit style={styles.routeLanguage}>{activeTarget}</Text>
            </View>
          </View>

          <Pressable
            onPress={toggleInterpreter}
            accessibilityRole="button"
            accessibilityLabel={primaryActionLabel}
            accessibilityHint="Starts or pauses continuous speech translation."
            accessibilityState={{ selected: isInterpreterActive, busy: isPlayingTts || startingStreamRef.current }}
            hitSlop={10}
            style={({ pressed }) => [
              styles.voiceButton,
              compactLayout && styles.voiceButtonCompact,
              tinyLayout && styles.voiceButtonTiny,
              isInterpreterActive && styles.voiceButtonArmed,
              isStreaming && styles.voiceButtonListening,
              isPlayingTts && styles.voiceButtonSpeaking,
              pressed && styles.voiceButtonPressed,
            ]}
          >
            <View style={[styles.voiceCore, compactLayout && styles.voiceCoreCompact, tinyLayout && styles.voiceCoreTiny]}>
              <Ionicons
                name={primaryIcon}
                size={primaryIconSize}
                color="#f8fafc"
              />
              <Text numberOfLines={1} adjustsFontSizeToFit style={styles.voiceButtonText}>
                {primaryButtonText}
              </Text>
            </View>
          </Pressable>

          <View style={[styles.flowRail, compactLayout && styles.flowRailCompact]}>
            <FlowStep icon="ear" label="Listen" active={isStreaming} />
            <FlowStep icon="language" label="Translate" active={isTranslating} />
            <FlowStep icon="volume-high" label="Speak" active={isPlayingTts} />
          </View>

          <ScrollView
            style={styles.scrollPanel}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
          <View style={[styles.transcriptStack, compactLayout && styles.transcriptStackCompact, tinyLayout && styles.transcriptStackTiny]}>
            <View style={[styles.transcriptLane, compactLayout && styles.transcriptLaneCompact]}>
              <Text style={styles.laneLabel}>{activeSpeakerLabel} said {routeSource}</Text>
              <Text
                numberOfLines={2}
                adjustsFontSizeToFit
                minimumFontScale={0.72}
                accessibilityLiveRegion="polite"
                style={[styles.laneText, !sourceText && styles.lanePlaceholder]}
              >
                {sourceText || "Your words will appear here"}
              </Text>
            </View>
            <View style={[styles.translationLane, compactLayout && styles.translationLaneCompact]}>
              <Text style={styles.laneLabel}>{activeListenerLabel} hears {routeTarget}</Text>
              <Text
                numberOfLines={3}
                adjustsFontSizeToFit
                minimumFontScale={0.68}
                accessibilityLiveRegion="polite"
                style={[styles.translationText, !translatedText && styles.lanePlaceholder]}
              >
                {translatedText || voiceIntent}
              </Text>
            </View>
            {conversationTurns.length > 0 && (
              <View style={styles.turnRail}>
                {conversationTurns.slice(-2).map((turn) => (
                  <View key={turn.id} style={[styles.turnChip, turn.clarify && styles.turnChipWarning]}>
                    <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.72} style={styles.turnChipText}>
                      {turn.speakerLabel}: {turn.sourceText} to {turn.translatedText}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
          </ScrollView>

          <Pressable
            onPress={() => setShowDebugDetails((current) => !current)}
            style={[styles.statusStrip, compactLayout && styles.statusStripCompact]}
            accessibilityRole="button"
            accessibilityLabel="Status details"
            accessibilityHint="Tap to show technical details"
          >
            <Ionicons name="pulse" size={18} color={systemColor} />
            <View style={styles.statusTextWrap}>
              <Text numberOfLines={2} accessibilityLiveRegion="polite" style={[styles.statusLine, { color: systemColor }]}>{status || panelState}</Text>
              {statusDetail ? (
                <Text numberOfLines={2} style={styles.statusDetail}>
                  {statusDetail}
                </Text>
              ) : null}
            </View>
          </Pressable>

          <View style={[styles.controlDock, compactLayout && styles.controlDockCompact]}>
            <IconControl
              icon={hasReplayAudio ? "play-back" : "play-back-outline"}
              label="Replay"
              onPress={replayLastTranslation}
              disabled={!hasReplayAudio || isPlayingTts}
              active={hasReplayAudio && !isPlayingTts}
              accessibilityLabel="Replay last spoken translation"
            />
            <IconControl
              icon={barrierMode ? "people" : "arrow-forward"}
              label="Two-way"
              onPress={() => {
                const nextBarrierMode = !barrierMode;
                setBarrierMode(nextBarrierMode);
                setMeaningCheck("");
                sendRouteConfig(sourceLanguage, targetLanguage, nextBarrierMode);
                setStatus(nextBarrierMode ? "Two-way mode on" : "One-way mode");
                setStatusType("success");
              }}
              active={barrierMode}
              accessibilityLabel={barrierMode ? "Switch to one-way translation" : "Switch to two-way conversation"}
            />
            <IconControl
              icon={isConnected ? "radio" : "refresh"}
              label="Connect"
              onPress={isConnected ? disconnect : connect}
              active={isConnected}
              accessibilityLabel={isConnected ? "Disconnect from server" : "Connect to server"}
            />
            <IconControl icon="trash" label="Clear" onPress={clearPanel} danger accessibilityLabel="Clear conversation" />
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}
