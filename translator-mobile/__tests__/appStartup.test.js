import React from "react";
import { render } from "@testing-library/react-native";

jest.mock("expo-splash-screen", () => ({
  preventAutoHideAsync: jest.fn(async () => {}),
  hideAsync: jest.fn(async () => {}),
}));

jest.mock("expo-network", () => ({
  getNetworkStateAsync: jest.fn(async () => ({ isConnected: true, type: "WIFI" })),
  addNetworkStateListener: jest.fn(() => ({ remove: jest.fn() })),
}));

jest.mock("expo-constants", () => ({
  expoConfig: { extra: { apiUrl: "http://192.168.12.243:8000" } },
  manifest2: null,
  manifest: null,
}));

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(async () => null),
  setItemAsync: jest.fn(async () => {}),
  deleteItemAsync: jest.fn(async () => {}),
}));

jest.mock("../utils/discoverServer", () => ({
  checkBackendHealthUrl: jest.fn(async () => true),
  deriveApiUrlFromExpo: jest.fn(() => "http://192.168.12.243:8000"),
  fetchMobileConnectInfo: jest.fn(async () => ({ hostname: "192.168.12.243", apiUrl: "http://192.168.12.243:8000" })),
  probeMetroBuildId: jest.fn(async () => ({ buildId: "2026-06-11-fix134", metroBase: "" })),
  resolveServerUrl: jest.fn(async () => ({
    apiUrl: "http://192.168.12.243:8000",
    healthy: true,
    mobileInfo: null,
    hostname: "192.168.12.243",
  })),
  waitForBackendReady: jest.fn(async () => true),
}));

jest.mock("../components/Assistant", () => {
  const { View } = require("react-native");
  return () => <View />;
});

jest.mock("@expo/vector-icons", () => {
  const { Text } = require("react-native");
  const MockIcon = (props) => <Text>{props.name || "icon"}</Text>;
  return {
    Ionicons: MockIcon,
    MaterialIcons: MockIcon,
    FontAwesome: MockIcon,
    Feather: MockIcon,
  };
});

jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: "light" },
}));

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(async () => {}),
}));

jest.mock("expo-linear-gradient", () => {
  const { View } = require("react-native");
  return { LinearGradient: View };
});

jest.mock("../services/ws", () => ({
  apiToWsUrl: jest.fn(() => "ws://192.168.12.243:8000/ws/audio"),
  connectWS: jest.fn(() => ({ close: jest.fn(), updateHandlers: jest.fn(), send: jest.fn() })),
  wsSocketHasAuthToken: jest.fn(() => false),
}));

jest.mock("../services/audio-stream", () => ({
  startAudioStream: jest.fn(async () => {}),
  stopAudioStream: jest.fn(async () => {}),
  pauseAudioUpload: jest.fn(),
  resumeAudioUpload: jest.fn(),
  restoreRecordingAudioMode: jest.fn(async () => {}),
  isAudioUploadPaused: jest.fn(() => false),
  setAudioStreamQuality: jest.fn(),
}));

jest.mock("../hooks/useMobileConnectionState", () => ({
  useMobileConnectionState: () => ({
    status: "Ready",
    setStatus: jest.fn(),
    statusType: "idle",
    setStatusType: jest.fn(),
    isConnected: false,
    setIsConnected: jest.fn(),
    isConnectedRef: { current: false },
    networkState: { isConnected: true, type: "WIFI" },
    setNetworkState: jest.fn(),
  }),
}));

jest.mock("../hooks/useMobileSession", () => ({
  useMobileSession: () => ({
    sourceLanguage: "en",
    setSourceLanguage: jest.fn(),
    targetLanguage: "ht",
    setTargetLanguage: jest.fn(),
    mobileDeviceIdRef: { current: "test-device" },
    mobileSessionIdRef: { current: "test-session" },
  }),
}));

jest.mock("../hooks/useMobileUiState", () => ({
  useMobileUiState: () => ({
    result: { source_text: "", translated_text: "" },
    setResult: jest.fn(),
    showSettings: false,
    setShowSettings: jest.fn(),
  }),
}));

jest.mock("../hooks/useMobileStreamState", () => ({
  useMobileStreamState: () => ({
    isStreaming: false,
    setIsStreaming: jest.fn(),
    partialTranscript: "",
    setPartialTranscript: jest.fn(),
    liveTranslation: "",
    setLiveTranslation: jest.fn(),
    wsControlRef: { current: null },
    resumeAfterTtsRef: { current: false },
    isStreamingRef: { current: false },
    recording: null,
    setRecording: jest.fn(),
  }),
}));

jest.mock("../hooks/useMobileBrainContext", () => ({
  useMobileBrainContext: () => ({
    semanticContext: null,
    setSemanticContext: jest.fn(),
    conversationBrain: "",
    setConversationBrain: jest.fn(),
    emotionInfo: null,
    setEmotionInfo: jest.fn(),
    clarifyVisible: false,
    setClarifyVisible: jest.fn(),
    clarifyMessage: "",
    setClarifyMessage: jest.fn(),
    brainUi: { visible: false, message: "", repairOptions: [], highlightTerms: [] },
    setBrainUi: jest.fn(),
    brainHintsRef: { current: {} },
    brainPlanRef: { current: null },
    resetBrainRuntimeUi: jest.fn(),
  }),
}));

jest.mock("../hooks/useMobileTts", () => ({
  useMobileTts: () => ({
    ttsQueue: [],
    isPlayingTts: false,
    setIsPlayingTts: jest.fn(),
    isPlayingTtsRef: { current: false },
    handleTtsChunk: jest.fn(),
    playNextTtsChunk: jest.fn(),
    ttsQueueRef: { current: [] },
    replayLastTts: jest.fn(),
    clearTtsQueue: jest.fn(),
    clearReplayAudio: jest.fn(),
    volume: 0.8,
    setVolume: jest.fn(),
    playbackSpeed: 1,
    setPlaybackSpeed: jest.fn(),
    stopTtsPlayback: jest.fn(),
    setOnPlaybackIdle: jest.fn(),
    hasReplayAudio: false,
  }),
}));

jest.mock("../hooks/useMobileAuth", () => ({
  isJwtExpired: jest.fn(() => false),
  useMobileAuth: () => ({
    token: "",
    setToken: jest.fn(),
    wsUrl: "http://192.168.12.243:8000",
    setWsUrl: jest.fn(),
    editWsUrl: "http://192.168.12.243:8000",
    username: "",
    setUsername: jest.fn(),
    password: "",
    setPassword: jest.fn(),
    recentUrls: [],
    showRecentUrls: false,
    setShowRecentUrls: jest.fn(),
    backendReachable: true,
    markBackendReachable: jest.fn(),
    setupComplete: true,
    isCheckingBackend: false,
    loadStoredData: jest.fn(async () => {}),
    saveWsUrl: jest.fn(async () => {}),
    markSetupComplete: jest.fn(async () => {}),
    validateUrl: jest.fn((url) => Boolean(url && !/localhost/i.test(url))),
    checkBackendHealth: jest.fn(async () => true),
    login: jest.fn(async () => {}),
    logout: jest.fn(async () => {}),
    clearAllData: jest.fn(async () => {}),
    saveRecentUrl: jest.fn(async () => {}),
    cancelLogin: jest.fn(),
    cancelDiscovery: jest.fn(),
  }),
}));

jest.mock("../hooks/useMobileRecording", () => ({
  useMobileRecording: () => ({
    startRecording: jest.fn(async () => {}),
    stopRecording: jest.fn(async () => {}),
    cancelUpload: jest.fn(),
    isUploading: false,
    uploadProgress: 0,
  }),
}));

import App from "../App";

describe("App startup render", () => {
  it("renders without throwing when hooks are wired", () => {
    const { unmount } = render(<App bootstrapApiUrl="http://192.168.12.243:8000" />);
    unmount();
  });
});
