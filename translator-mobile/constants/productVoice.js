/**
 * Product voice — UI copy aligned with Anai's purpose:
 * break language barriers through natural, trusted, human conversation.
 */

export const PRODUCT_NAME = "Anai";
export const PRODUCT_TAGLINE = "Bridge languages · Real conversations";
export const PRODUCT_MISSION = "Two people, one conversation — each in their own language.";

export const FLOW_STEPS = [
  { key: "listen", icon: "ear", label: "Hear", a11y: "Hear what was said" },
  { key: "translate", icon: "heart", label: "Understand", a11y: "Understand the meaning" },
  { key: "bridge", icon: "language", label: "Bridge", a11y: "Carry meaning across languages" },
  { key: "speak", icon: "volume-high", label: "Out loud", a11y: "Bridge meaning out loud in the other language" },
];

export function transcriptHeaderLabel() {
  return "Bridge conversation";
}

export function transcriptExchangeLabel(turnCount = 0) {
  if (turnCount <= 0) return "";
  return `${turnCount} bridge exchange${turnCount === 1 ? "" : "s"}`;
}

export function routeCaptions(twoWay = true) {
  return {
    source: "You speak",
    target: twoWay ? "They hear" : "Bridged out",
  };
}

export function duplexCopy() {
  return {
    title: "Conversation bridge",
    subtitle: "Each person stays in their language",
  };
}

export function brainPanelTitle() {
  return "Meaning check";
}

export function modeChipLabel(twoWay = true) {
  return twoWay ? "Together" : "For you";
}

export function modeChipA11y(twoWay = true) {
  return twoWay
    ? "Together mode — two people, each speaks their language"
    : "For you mode — one-way bridge";
}

export function emptyStateCopy({
  isOffline = false,
  isStreaming = false,
  isPaused = false,
  isInterpreterActive = false,
  twoWay = true,
} = {}) {
  if (isOffline) {
    return {
      title: "Connect your bridge",
      description: "Link to your bridge server on the same Wi‑Fi. Then speak naturally — Anai carries meaning across languages.",
    };
  }
  if (isStreaming) {
    return {
      title: "Bridging live",
      description: twoWay
        ? "Speak in your language. Anai listens, understands, and bridges to the other person — and back."
        : "Speak in your language. Anai understands and bridges your words outward.",
    };
  }
  if (isPaused) {
    return { title: "Bridge paused", description: "Tap Start when you're ready to bridge the conversation again." };
  }
  if (isInterpreterActive) {
    return {
      title: "Bridge is open",
      description: "Your words and theirs will appear below as the conversation flows.",
    };
  }
  return {
    title: "Ready to connect",
    description: twoWay
      ? "Tap Start once, then talk naturally. Anai bridges both sides of the conversation."
      : "Tap Start once, then speak. Anai bridges your words into the other language.",
  };
}

export function micHint({
  needsServerLink = false,
  isStreaming = false,
  isPlayingTts = false,
  isInterpreterActive = false,
  twoWay = true,
} = {}) {
  if (needsServerLink) return "Link to your bridge server to open the conversation";
  if (isStreaming) return "Listening — speak in your natural voice";
  if (isPlayingTts) return "Bridging your words out loud";
  if (isInterpreterActive) {
    return twoWay ? "Bridge live — either person can speak" : "Bridge live — speak anytime";
  }
  return "Tap Start to open the conversation bridge";
}

export function targetPlaceholder({
  twoWay = true,
  isTranslating = false,
  hasSource = false,
  intentLine = "",
} = {}) {
  if (isTranslating) return "Understanding…";
  if (hasSource && intentLine) return intentLine;
  return twoWay
    ? "Bridged words for the other person appear here"
    : "Your bridged words appear here";
}

export function sourcePlaceholder() {
  return "Your words, in your language";
}

export function certTitles() {
  return {
    advisory: "Honor native speech",
    required: "Trust before voice",
  };
}

export function certDefaultMessages() {
  return {
    advisory: "Have a fluent native speaker listen — accent and cultural tone matter.",
    required: "Have a native speaker listen before you rely on the spoken bridge.",
  };
}

export function liveStatusDefaults() {
  const titles = certTitles();
  return {
    listening: "Listening — speak in your voice",
    speaking: "Bridging out loud",
    translating: "Understanding…",
    armed: "Bridge open — speak anytime",
    cert_advisory: titles.advisory,
    cert_required: titles.required,
    clarify: "Check meaning — speak again",
  };
}

export function liveStatusLabel(mode, { clarifyMessage = "", certStep = "none" } = {}) {
  if (certStep === "required") return certTitles().required;
  if (certStep === "advisory") return certTitles().advisory;
  if (mode === "clarify" && clarifyMessage) return clarifyMessage;
  return liveStatusDefaults()[mode] || liveStatusDefaults().listening;
}

export function connectionStripStatus({
  isReconnecting = false,
  isListening = false,
  isSpeaking = false,
  reconnectAttempt = 0,
  reconnectMax = 10,
  connectedLabel = "Bridge linked",
} = {}) {
  if (isReconnecting) return `Relinking bridge ${reconnectAttempt}/${reconnectMax}`;
  if (isListening) return "Bridge live";
  if (isSpeaking) return "Bridging out loud";
  return connectedLabel;
}

export function friendlyPanelStates() {
  return {
    bridging: "Bridging",
    listening: "Bridge live",
    bridgeReady: "Bridge ready",
    needsWifi: "Needs Wi‑Fi",
    linking: "Linking…",
    offline: "Offline",
  };
}

export function statusStripDetail({
  activeSource = "",
  activeTarget = "",
  isInterpreterActive = false,
  isConnected = false,
  twoWay = true,
  turnCount = 0,
} = {}) {
  return [
    activeSource && activeTarget ? `${activeSource} → ${activeTarget}` : null,
    isInterpreterActive ? "Bridge listening" : isConnected ? "Tap Start when ready" : null,
    twoWay ? "Together" : "For you",
    turnCount > 0 ? `${turnCount} bridge exchange${turnCount === 1 ? "" : "s"}` : null,
  ].filter(Boolean).join(" · ");
}

export function offlineConnectCopy({ onCellular = false } = {}) {
  return {
    title: "Bridge not linked",
    message: onCellular
      ? "You're on cellular. Join the SAME Wi‑Fi as your PC, then tap Link bridge."
      : "Same Wi‑Fi as your PC? Tap Link bridge to open the conversation.",
  };
}

export function bridgeServerStatusMessages() {
  return {
    checking: "Checking bridge server…",
    reachable: "Bridge server reachable",
    unreachable: "Could not reach bridge server",
    testLink: "Test bridge link",
    testing: "Testing bridge…",
    saveRelink: "Save & relink bridge",
    warming: "Opening bridge server — retry in a few seconds",
    timeout: "Bridge check timed out. Same Wi‑Fi? Firewall open on ports 8000 and 8082?",
    cannotReach: "Cannot reach bridge server. Check URL, Wi‑Fi, and firewall.",
    cannotReachLan: "Cannot reach bridge server. Use your PC's LAN IP and allow HTTP through Windows Firewall.",
  };
}

export function duplexPersonBadge(isListening) {
  return isListening ? "Speaking" : "In turn";
}

export function modeToggleStatus(twoWay = true) {
  return twoWay ? "Together — both sides bridged" : "For you — one-way bridge";
}

export function modeToggleToast(twoWay = true) {
  return twoWay ? "Together mode — conversation bridged both ways" : "For you mode — bridges your words outward";
}

export function modeToggleA11y(twoWay = true) {
  return twoWay ? "Switch to for you mode" : "Switch to together mode";
}

export function processingPillMessage({ queued = false } = {}) {
  return queued ? "Queued — bridging soon…" : "Understanding meaning…";
}

export function copyToasts() {
  return {
    translationCopied: "Bridged text copied",
    originalCopied: "Your words copied",
    turnCopied: "Exchange copied",
    nothingYet: "Nothing to bridge yet",
    nothingShare: "Nothing to share yet",
    reviewWithNative: "Review the bridge with a native speaker",
  };
}

export function primaryMicLabels({
  isPlayingTts = false,
  isStreaming = false,
  isInterpreterActive = false,
  needsServerLink = false,
  isConnecting = false,
} = {}) {
  return {
    action: isPlayingTts
      ? "Stop spoken bridge"
      : isStreaming
        ? "Pause listening"
        : isInterpreterActive
          ? "Resume bridge"
          : "Open the conversation bridge",
    button: isPlayingTts
      ? "Stop"
      : isInterpreterActive
        ? (isStreaming ? "Pause" : "Start")
        : needsServerLink
          ? "Link"
          : isConnecting
            ? "Linking"
            : "Start",
  };
}

export function neoConnectionBadge({ isConnecting = false, isConnected = false } = {}) {
  if (isConnecting) return "LINKING";
  if (isConnected) return "LIVE";
  return "OFFLINE";
}

export function voiceIntentDefault() {
  return "Tap Start to open the bridge";
}

export function dockLabels({ isConnected = false, twoWay = true } = {}) {
  return {
    replay: "Replay bridge",
    clear: "Clear bridge",
    mode: modeChipLabel(twoWay),
    connect: isConnected ? "Linked" : "Link bridge",
  };
}

export function bridgeModeDebugLabel(twoWay = true) {
  return modeChipLabel(twoWay);
}

export function loadingScreenMessage() {
  return "Opening the conversation bridge…";
}

export function pauseBridgeLabel() {
  return "Pause bridge";
}

export function reconnectFailureMessage() {
  return "Bridge dropped — tap Retry to reconnect";
}

/** User-visible connection lifecycle copy — keep bridge metaphor consistent. */
export function connectionLifecycleMessages() {
  return {
    linking: "Linking bridge…",
    connectionLost: "Bridge dropped — reconnecting…",
    handshakeTimeout: "Bridge handshake slow — retrying…",
    checkingServer: "Checking bridge server…",
    serverWarming: "Opening bridge server — retrying…",
    joinWifi: "Join same Wi‑Fi as your PC",
    joinWifiFindingRemote: "Join same Wi‑Fi as your PC (or finding remote server…)",
    joinWifiWaitingRemote: "Join same Wi‑Fi as your PC (or waiting for remote server…)",
    networkRestored: "Back online — linking bridge…",
    networkLostChecking: "Bridge offline — checking network…",
    networkLostShort: "Bridge offline",
    lookingRemote: "Finding bridge server…",
    switchingRemote: "Switching bridge server…",
    disconnectedTapLink: "Bridge dropped — tap Link",
    connectionErrorTapLink: "Bridge error — tap Link",
    connectionClosedReconnect: "Bridge closed — reconnecting…",
    connectedTapStart: "Bridge linked — tap Start when ready",
    translationReady: "Meaning bridged",
    listeningSpeak: "Listening — speak anytime",
    understanding: "Understanding…",
    voiceDelivered: "Meaning bridged out loud",
    warmupRetry: "Opening bridge — retrying…",
    handshaking: "Opening bridge…",
  };
}

export function socketStatusMessages() {
  return {
    connected: "Bridge linked",
    readyToListen: "Bridge ready — speak anytime",
    listening: "Listening — speak in your voice",
    disconnected: "Bridge dropped — tap Link",
    voiceDelivered: "Meaning bridged out loud",
    noVoiceReplay: "No bridged voice to replay",
    linking: "Linking bridge…",
    reconnecting: "Reconnecting bridge…",
  };
}

/** WebSocket layer status strings — consumed by services/ws.js. */
export function wsBridgeStatuses() {
  const lifecycle = connectionLifecycleMessages();
  const socket = socketStatusMessages();
  return {
    handshaking: lifecycle.handshaking,
    disconnected: "Bridge dropped",
    reconnecting: socket.reconnecting,
    reconnectIn: (seconds, attempt) => `Relinking bridge in ${seconds}s (attempt ${attempt})`,
    reconnectingEllipsis: "Relinking bridge…",
    timeout: "Bridge link timeout",
    maxRetriesFailed: "Bridge dropped — max retries reached",
  };
}

/** Short action/status toasts during live bridging. */
export function bridgeActionMessages() {
  const certs = certTitles();
  return {
    routeUpdated: "Bridge route updated",
    routeSwapped: "Bridge direction flipped",
    bridgePaused: "Bridge paused",
    bridgeLive: "Bridge live",
    bothSpeakersListening: "Both speakers — bridge listening",
    listeningClearer: "Listening for clearer speech",
    listeningSpeakAgain: "Bridge live — speak again",
    openingMic: "Opening microphone…",
    testBridgeLink: "Test the bridge link before continuing",
    backendUrlNotReady: "Bridge server URL is not ready",
    stopBridgeFirst: "Pause the live bridge first",
    uploadWait: "Bridge upload in progress…",
    stillListening: "Still on the bridge — just speak",
    stoppedPlayback: "Stopped bridged playback",
    speechDetected: "Hearing you…",
    chooseMeaning: "Choose the intended meaning",
    linkingLabel: "Linking",
    turnCancelled: "Bridge turn cleared",
    certRequired: certs.required,
    checkMeaningRepeat: "Check meaning — repeat or rephrase",
    waitingPlayback: "Waiting for bridged voice",
    speakerSwitched: "Speaker switched — bridge listening",
    speakerInterrupted: "Listening — speaker interrupted",
    draftBridgeVoice: "Draft bridge voice…",
    confirmBeforeVoice: "Trust check before voice",
    voiceCommandHandled: "Voice command handled",
    speakingVoiceChunk: (index, total) => `Bridging out loud ${index}/${total}`.trim(),
    trySpeakingAgain: "Try speaking again on the bridge",
    bridgeServerError: "Bridge server error",
    audioFallbackActive: "Backup bridge listening — keep talking",
    micBlocked: "Microphone blocked — open Settings to allow",
    streamError: (detail = "") => (detail ? `Bridge stream error: ${detail}` : "Bridge stream error"),
    invalidServerUrl: "Enter a valid bridge server URL (http:// or https://)",
    lanIpRequired: "Use your PC's LAN IP (not localhost) — your phone cannot reach this machine.",
    sourceSetTo: (language = "") => `You speak · ${language}`.trim(),
    voiceVolumeUpdated: "Bridge voice volume updated",
    voiceSpeedUpdated: "Bridge voice speed updated",
  };
}

export function laneHeaderLabel({ languageName = "", side = "source", twoWay = true } = {}) {
  const name = String(languageName || "").trim();
  if (side === "source") return `You speak · ${name}`;
  return twoWay ? `They hear · ${name}` : `Bridged out · ${name}`;
}

export function turnRailHeader() {
  return "Bridge exchanges · tap to copy";
}

export function turnChipA11y(turn = {}) {
  const speaker = turn.speakerLabel || "Speaker";
  const cert = turn.certStep === "required"
    ? ", trust check required"
    : turn.certStep === "advisory" || turn.nativeListen
      ? ", honor native speech"
      : "";
  return `Copy exchange from ${speaker}${cert}`;
}

export function clearPanelCopy() {
  return {
    voiceIntent: voiceIntentDefault(),
    status: "Bridge cleared",
    toast: "Bridge cleared",
  };
}

export function conversationContextTitle() {
  return "In the conversation";
}

export function assistantWelcomeLine() {
  return "Ask about meaning, request a rephrase, or get a language tip.";
}

export function replayStatusMessages() {
  return {
    replaying: "Replaying bridged voice",
    noReplay: "No bridged voice to replay",
    replayingShort: "Replaying bridge",
  };
}

export function pauseBridgeToast() {
  return "Bridge paused";
}

export function bandwidthToasts() {
  return {
    lowOn: "Low bandwidth — voice waits for final bridge",
    lowOff: "Full bridge voice enabled",
  };
}

export function normalizeConnectionStatus(status = "") {
  const raw = String(status || "").trim();
  if (!raw) return socketStatusMessages().connected;
  const lower = raw.toLowerCase();
  const messages = socketStatusMessages();
  const lifecycle = connectionLifecycleMessages();
  if (lower === "connected") return messages.connected;
  if (/ready to listen/.test(lower)) return messages.readyToListen;
  if (/^listening/.test(lower)) return messages.listening;
  if (/disconnected|tap connect/.test(lower)) return messages.disconnected;
  if (/voice delivered|speaking translation/.test(lower)) return messages.voiceDelivered;
  if (/no voice/.test(lower)) return messages.noVoiceReplay;
  if (/translation ready/.test(lower)) return lifecycle.translationReady;
  if (/^translating$/.test(lower)) return lifecycle.understanding;
  if (/connection lost|connection closed/.test(lower)) return messages.reconnecting;
  if (/handshake timeout|handshaking/.test(lower)) return lifecycle.handshaking;
  if (/checking server/.test(lower)) return lifecycle.checkingServer;
  if (/server warming|warming up/.test(lower)) return lifecycle.serverWarming;
  if (/connecting to server|connecting\.\.\.|^connecting$/.test(lower)) return messages.linking;
  if (/reconnect/.test(lower)) return messages.reconnecting;
  return raw;
}

export function helpTips() {
  return [
    { icon: "mic", title: "Open the bridge", body: "Tap Start to connect, then speak naturally. Anai hears you, understands meaning, and bridges it to the other language — out loud." },
    { icon: "cloud-offline-outline", title: "Link the bridge", body: "If you see Offline, tap Link bridge in the dock or open Settings to check your server URL." },
    { icon: "swap-horizontal", title: "Change languages", body: "Tap the language pills to pick a language. Use the center swap button to reverse direction." },
    { icon: "sparkles-outline", title: "NAIA assistant", body: "Tap the sparkles icon in the header to ask about meaning, request a rephrase, or get language tips." },
    { icon: "pause-circle-outline", title: "Pause the bridge", body: "Tap the mic orb while listening is active, or use Pause bridge below the orb. Tap Start again when you're ready to continue." },
    { icon: "radio-outline", title: "Disconnect", body: "Tap LIVE in the header or Linked in the dock to disconnect without closing the app." },
    { icon: "people", title: "Together mode", body: "With Together on, either person speaks their language — Anai bridges meaning to the other side automatically." },
    { icon: "ear-outline", title: "Honor native speech", body: "For slang, strong accents, or emotional tone, have a fluent native speaker listen before you trust the spoken bridge. Anai prompts you when that matters." },
    { icon: "settings-outline", title: "Bridge server & account", body: "Open Settings (gear icon) to change your bridge server URL, sign in, or adjust voice volume and speed." },
    { icon: "share-outline", title: "Share or copy", body: "Use the share and copy icons on each card to send or save what was said and bridged." },
    { icon: "help-circle-outline", title: "Status strip", body: "Tap the status bar at the bottom to switch between simple and detailed connection info." },
    { icon: "help-circle-outline", title: "Check meaning", body: "If meaning looks uncertain, tap Speak on the bridge on the yellow pill. Rephrase slowly or repeat key names." },
    { icon: "git-branch-outline", title: "Meaning check chips", body: "When the meaning check panel appears, tap a chip to switch source language, repeat exact terms, or choose meaning." },
    { icon: "cellular-outline", title: "Low bandwidth", body: "In Settings, turn on Low bandwidth on slow Wi‑Fi. Text still streams; voice waits until the final bridge is ready." },
    { icon: "speedometer-outline", title: "Debug insights", body: "Tap the status strip to show CIP mode, STT provider, latency, and first-audio timing while connected." },
    { icon: "cloud-offline-outline", title: "Connection retry", body: "If Wi‑Fi drops, the strip shows reconnect progress. When retries fail, tap Retry on the red banner to reconnect." },
  ];
}
