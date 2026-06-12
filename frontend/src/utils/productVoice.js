/**
 * Product voice — desktop web UI copy aligned with Anai's conversation bridge.
 */

export const PRODUCT_TAGLINE = 'Bridge languages · Real conversations';

export function transcriptExchangeLabel(turnCount = 0) {
  if (turnCount <= 0) return '';
  return turnCount === 1 ? '1 bridge exchange' : `${turnCount} bridge exchanges`;
}

export function targetPlaceholder() {
  return 'Bridged words appear here';
}

export function micLabels({ connectionStatus, micReady, playing, perceivedListening, processing }) {
  if (connectionStatus === 'checking') return 'Linking bridge…';
  if (connectionStatus === 'warming') return 'Opening bridge…';
  if (!micReady) {
    return connectionStatus !== 'online' ? 'Bridge offline' : 'Mic unavailable';
  }
  if (playing) return 'Bridging out loud';
  if (perceivedListening) return 'Listening — speak in your voice';
  if (processing) return 'Understanding…';
  return 'Tap mic to open bridge';
}

export function micHints({ perceivedListening, processing, playing, connectionStatus }) {
  if (perceivedListening) return 'Speak naturally — pause the bridge when you are done';
  if (processing) return 'Understanding your words…';
  if (playing) return 'Meaning bridges out loud — mic resumes automatically';
  if (connectionStatus === 'online') return 'One tap opens the conversation bridge';
  return 'Link to the bridge server to begin';
}

export function pipelineStages() {
  return {
    bridging: 'Bridging out loud',
    bridgingLive: 'Bridging out loud',
    bridgingStatus: 'Bridging meaning out loud…',
    understanding: 'Understanding…',
    liveBridge: 'Bridging live',
    guarded: 'Guarded bridge active',
    lowBandwidth: 'Low bandwidth — text bridge only',
    playVoice: 'Playing bridged voice…',
    playVoiceManual: 'Playing bridged voice…',
  };
}

/** Canonical pipeline stage strings — use with setPipelineStage in main.jsx. */
export function pipelineStageLabels() {
  const s = pipelineStages();
  const b = bridgeStatusMessages();
  return {
    idle: 'Idle',
    ready: 'Bridge open',
    readyToListen: b.bridgeReadySpeak,
    readyToRepair: 'Ready to check meaning',
    listening: b.listeningSpeak,
    processing: s.understanding,
    understanding: s.understanding,
    stopped: b.bridgePaused,
    playingVoice: s.bridging,
    directionSwitched: 'Bridge direction flipped',
    clarificationNeeded: 'Meaning check',
    keepSpeaking: b.keepSpeaking,
    offline: 'Bridge offline',
    micUnavailable: 'Mic unavailable',
    permissionBlocked: 'Microphone blocked',
    audioFallback: b.audioFallback,
    voiceSkipped: 'Bridge voice skipped',
    voiceTimedOut: 'Bridge voice timed out',
    voiceUnavailable: 'Bridge voice unavailable',
    voicePlayed: b.voicePlayed,
    bridgeReady: b.bridgeReady,
    bridgeTimedOut: 'Bridge timed out',
    recordingUnsupported: 'Recording unavailable',
    safetyReset: 'Bridge reset',
    speakerTestPlayed: 'Speaker check played',
    loadingTestVoice: 'Loading bridge voice check',
    voiceTestFailed: 'Bridge voice check failed',
    testingMicrophone: 'Testing microphone for bridge',
    micPlaybackFailed: 'Mic check playback failed',
    micTestPlayed: 'Mic check played',
    micPlaybackBlocked: 'Mic check blocked',
    recording: 'Recording bridge check…',
    micTestFailed: 'Mic check failed',
    transcriptionReady: 'Words captured',
    preparingBridgedVoice: 'Preparing bridged voice…',
    waitingBridgedVoice: 'Waiting for bridged voice…',
    draftBridgeVoice: 'Draft bridge voice…',
    voiceStreamComplete: 'Bridged voice ready',
    holdAndSpeakLonger: 'Keep speaking for a moment…',
    complete: 'Bridge complete',
    connectionError: 'Bridge link error',
    connectionLost: 'Bridge dropped',
  };
}

export function dockQuickActionLabels() {
  return {
    typeToBridge: 'Type to bridge',
    flip: 'Flip direction',
    replay: 'Replay bridge',
    clear: 'Clear bridge',
  };
}

export function routeCaptions(twoWay = true) {
  return {
    source: 'You speak',
    target: twoWay ? 'They hear' : 'Bridged out',
  };
}

export function languagePickerTitle(variant, { twoWay = true } = {}) {
  if (variant === 'source') return routeCaptions(twoWay).source;
  return routeCaptions(twoWay).target;
}

export function clarifyMessages() {
  return {
    checkMeaning: 'Check meaning before trusting the spoken bridge.',
    honorNative: 'Honor native speech before relying on the spoken bridge.',
    tapPlayVoice: 'Tap Play bridged voice to hear the bridge',
  };
}

export function bridgeErrors() {
  return {
    text: 'Could not bridge text',
    speech: 'Could not bridge speech',
    audio: 'Could not bridge audio',
  };
}

export function conversationHistoryLabel(count = 0) {
  if (count === 1) return '1 bridge exchange';
  return `${count} bridge exchanges`;
}

export function clarifyActions() {
  return {
    speakAgain: 'Speak on the bridge',
    ready: 'Bridge open — speak anytime',
  };
}

export function formatBrainModeLabel(mode = '', strategy = '') {
  const raw = String(mode || strategy || '').trim();
  const labels = {
    guarded_translate: 'Guarded bridge',
    instant: 'Instant bridge',
    clarify: 'Meaning check',
    repair: 'Meaning check',
  };
  return labels[raw] || raw.replace(/_/g, ' ');
}

/** Common live-status strings for desktop main.jsx and connection UI. */
export function bridgeStatusMessages() {
  return {
    serverOffline: 'Bridge server offline',
    linkFirst: 'Link the bridge server first',
    bridgeReady: 'Bridge ready',
    bridgeReadySpeak: 'Bridge ready — speak anytime',
    listeningSpeak: 'Listening — speak in your voice',
    listeningLive: 'Bridge live — listening…',
    understandingText: 'Understanding text…',
    understandingSpeech: 'Understanding speech…',
    processingSpeech: 'Understanding…',
    bridgePaused: 'Bridge paused',
    noSpeech: 'No speech heard',
    listeningNextSpeaker: 'Listening for the next speaker…',
    keepSpeaking: 'Keep speaking for a moment…',
    shareTitle: 'Anai — bridged conversation',
    bridgeDroppedRestart: 'Bridge dropped — tap to restart',
    streamError: 'Bridge stream error',
    voicePlayed: 'Bridged voice played',
    listeningEllipsis: 'Listening…',
    understandingEllipsis: 'Understanding…',
    speakerSwitched: 'Speaker switched — listening',
    speakerInterrupted: 'Listening — speaker interrupted',
    bothSpeakers: 'Both speakers — bridge listening',
    speechDetected: 'Hearing you…',
    audioFallback: 'Backup bridge listening…',
    usingAudioFallback: 'Using backup bridge…',
    confirmBeforeVoice: 'Trust check before voice',
    readyTryAgain: 'Bridge ready — try again',
    bridgeServerError: 'Bridge server error',
    chooseMeaning: 'Choose the intended meaning',
    networkSlowReady: 'Network slow — bridge ready to try again',
    audioFallbackListening: 'Backup bridge listening…',
    clearBridgeHistory: 'Clear bridge history?',
  };
}

export function connectionQualityLabels() {
  return {
    relinking: (attempt, max) => `Relinking bridge… (${attempt}/${max})`,
    syncing: 'Linking bridge…',
    offline: 'Bridge offline',
    warming: 'Opening bridge…',
    error: 'Bridge link error',
    linked: 'Bridge linked',
  };
}

/** Maps technical pipeline stage strings to conversation-bridge copy for status UI. */
export function normalizePipelineStage(stage = '') {
  const raw = String(stage || '').trim();
  if (!raw || raw === 'Idle') return raw;
  const lower = raw.toLowerCase();
  const s = pipelineStages();
  const b = bridgeStatusMessages();
  const exact = {
    ready: 'Bridge open',
    'ready to listen': b.bridgeReadySpeak,
    'ready to repair': 'Ready to check meaning',
    listening: b.listeningSpeak,
    'listening…': b.listeningEllipsis,
    processing: s.understanding,
    understanding: s.understanding,
    stopped: b.bridgePaused,
    'playing voice': s.bridging,
    'playing voice...': s.bridging,
    'direction switched': 'Bridge direction flipped',
    'clarification needed': 'Meaning check',
    'keep speaking': b.keepSpeaking,
    offline: 'Bridge offline',
    'mic unavailable': 'Mic unavailable',
    'permission blocked': 'Microphone blocked',
    'audio fallback': b.audioFallback,
    'voice skipped': 'Bridge voice skipped',
    'voice timed out': 'Bridge voice timed out',
    'voice unavailable': 'Bridge voice unavailable',
    'voice played': b.voicePlayed,
    'bridge ready': b.bridgeReady,
    'bridge timed out': 'Bridge timed out',
    'recording unsupported': 'Recording unavailable',
    'safety reset': 'Bridge reset',
    'speaker test played': 'Speaker check played',
    'loading test voice': 'Loading bridge voice check',
    'voice test failed': 'Bridge voice check failed',
    'testing microphone': 'Testing microphone for bridge',
    'mic playback failed': 'Mic check playback failed',
    'mic test played': 'Mic check played',
    'mic playback blocked': 'Mic check blocked',
    'recording...': 'Recording bridge check…',
    'mic test failed': 'Mic check failed',
    'speaker blocked': 'Speaker blocked',
  };
  if (exact[lower]) return exact[lower];
  if (/^listening/.test(lower)) return b.listeningSpeak;
  if (/^processing|^understanding/.test(lower)) return s.understanding;
  if (/^playing voice/.test(lower)) return s.bridging;
  if (/^stopped|^paused/.test(lower)) return b.bridgePaused;
  if (/^offline/.test(lower)) return 'Bridge offline';
  if (/^direction switched/.test(lower)) return 'Bridge direction flipped';
  if (/^clarification/.test(lower)) return 'Meaning check';
  if (/^speaker blocked/.test(lower)) return raw.replace(/^speaker blocked/i, 'Speaker blocked');
  if (/ to /.test(lower) && !/bridge/.test(lower)) {
    return raw.replace(/\bto\b/i, '→');
  }
  return raw;
}
