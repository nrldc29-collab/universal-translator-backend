import { useState, useEffect, useRef } from "react";
import { View, Text, TextInput, StyleSheet, ScrollView, Pressable } from "react-native";
import { Audio } from "expo-av";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import * as Network from "expo-network";
import { apiToWsUrl, connectWS } from "./services/ws";
import { startAudioStream, stopAudioStream, playTtsAudio } from "./services/audio-stream";
import DuplexMode from "./components/DuplexMode";
import SemanticContext from "./components/SemanticContext";
import SettingsScreen from "./components/SettingsScreen";
import AnimatedCard from "./components/AnimatedCard";
import GradientHeader from "./components/GradientHeader";
import AdvancedFeatures from "./components/AdvancedFeatures";
import Assistant from "./components/Assistant";
import * as Haptics from "expo-haptics";

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || "";
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === "1");
const TOKEN_KEY = "translator_token";
const RECENT_URLS_KEY = "recent_urls";
const MAX_RECENT_URLS = 5;
const TARGET_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "ht", label: "Haitian Creole" },
];

function debugLog(...args) {
  if (DEBUG_LOGS) console.debug(...args);
}

function ActionButton({ title, onPress, tone = "primary", disabled = false, style }) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.actionButton,
        styles[`actionButton_${tone}`],
        disabled && styles.actionButtonDisabled,
        pressed && !disabled && styles.actionButtonPressed,
        style,
      ]}
    >
      <Text style={[styles.actionButtonText, tone === "ghost" && styles.actionButtonTextGhost]}>{title}</Text>
    </Pressable>
  );
}

export default function App() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo");
  const [status, setStatus] = useState("Idle");
  const [statusType, setStatusType] = useState("idle");
  const [wsUrl, setWsUrl] = useState(API_URL);
  const [isConnected, setIsConnected] = useState(false);
  const [sourceLanguage, setSourceLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("es");
  const [result, setResult] = useState(null);
  const [recording, setRecording] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [networkState, setNetworkState] = useState(null);
  const [recentUrls, setRecentUrls] = useState([]);
  const [showRecentUrls, setShowRecentUrls] = useState(false);
  const [backendReachable, setBackendReachable] = useState(null);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [liveTranslation, setLiveTranslation] = useState("");
  const [ttsQueue, setTtsQueue] = useState([]);
  const [isPlayingTts, setIsPlayingTts] = useState(false);
  const [semanticContext, setSemanticContext] = useState(null);
  const [emotionInfo, setEmotionInfo] = useState(null);
  const [conversationBrain, setConversationBrain] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  const wsControlRef = useRef(null);
  const ttsQueueRef = useRef([]);
  const isPlayingTtsRef = useRef(false);
  const resumeAfterTtsRef = useRef(false);
  const mobileDeviceIdRef = useRef("phone-" + Math.random().toString(36).slice(2));
  const mobileSessionIdRef = useRef("mobile-" + Date.now());

  useEffect(() => {
    loadStoredData();
    checkNetworkState();
    const interval = setInterval(checkNetworkState, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadStoredData() {
    try {
      const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
      if (storedToken) {
        setToken(storedToken);
        setStatus("Token restored");
        setStatusType("success");
      }

      const storedUrls = await SecureStore.getItemAsync(RECENT_URLS_KEY);
      if (storedUrls) {
        setRecentUrls(JSON.parse(storedUrls));
      }
    } catch (error) {
      console.error("Error loading stored data:", error);
    }
  }

  async function checkNetworkState() {
    try {
      const state = await Network.getNetworkStateAsync();
      setNetworkState(state);
      
      // Auto-reconnect if network becomes available and we're disconnected
      if (state.isConnected && !isConnected && token && wsUrl) {
        setStatus("Network restored - reconnecting...");
        setTimeout(() => {
          if (!isConnected && token) connect();
        }, 1000);
      }
      
      // Disconnect if network is lost
      if (!state.isConnected && isConnected) {
        setStatus("Network lost - disconnecting...");
        disconnect();
      }
    } catch (error) {
      console.error("Network check error:", error);
    }
  }

  async function saveRecentUrl(url) {
    try {
      const updated = [url, ...recentUrls.filter((item) => item !== url)].slice(0, MAX_RECENT_URLS);
      setRecentUrls(updated);
      await SecureStore.setItemAsync(RECENT_URLS_KEY, JSON.stringify(updated));
    } catch (error) {
      console.error("Error saving recent URL:", error);
    }
  }

  async function checkBackendHealth(url) {
    try {
      setStatus("Checking backend...");
      setStatusType("connecting");
      const response = await fetch(`${url}/health`, {
        method: "GET",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
      });
      setBackendReachable(response.ok);
      return response.ok;
    } catch (error) {
      console.error("Backend health check failed:", error);
      setBackendReachable(false);
      return false;
    }
  }

  function validateUrl(url) {
    try {
      if (!url || url.trim() === "") return false;
      return url.startsWith("http://") || url.startsWith("https://");
    } catch (error) {
      console.error("URL validation error:", error);
      return false;
    }
  }

  async function login() {
    if (!validateUrl(wsUrl)) {
      setStatus("Invalid backend URL format");
      setStatusType("error");
      return;
    }

    try {
      setStatus("Logging in...");
      setStatusType("connecting");

      const isHealthy = await checkBackendHealth(wsUrl);
      if (!isHealthy) {
        setStatus("Backend is not reachable. Check URL and ensure backend is running.");
        setStatusType("error");
        return;
      }

      const response = await fetch(`${wsUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const data = await response.json();
        setStatus("Login failed: " + (data.detail || "Unknown error"));
        setStatusType("error");
        return;
      }
      const data = await response.json();
      await SecureStore.setItemAsync(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      saveRecentUrl(wsUrl);
      setStatus("Logged in as " + username);
      setStatusType("success");
    } catch (error) {
      setStatus("Login error: " + error.message);
      setStatusType("error");
    }
  }

  async function logout() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken("");
    setStatus("Logged out");
    setStatusType("idle");
    if (isConnected) {
      disconnect();
    }
  }

  function connect() {
    if (!validateUrl(wsUrl)) {
      setStatus("Invalid backend URL format");
      setStatusType("error");
      return;
    }

    setStatus("Connecting...");
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
      }));
    } else if (nextStatus.includes("Disconnected") || nextStatus.includes("failed") || nextStatus.includes("error")) {
      setStatusType("error");
      setIsConnected(false);
      setIsStreaming(false);
    } else if (nextStatus.includes("Reconnecting") || nextStatus.includes("Connecting")) {
      setStatusType("connecting");
    } else if (nextStatus.includes("Reconnecting in")) {
      setStatusType("warning");
    }
  }

  function handleMessage(message) {
    debugLog("Message:", message.type, message);

    switch (message.type) {
      case "pong":
        debugLog("Heartbeat pong received");
        break;
      case "final_transcription":
        setPartialTranscript("");
        setResult((previous) => ({ ...previous, source_text: message.text }));
        break;
      case "partial_transcription":
        setPartialTranscript(message.text || "");
        break;
      case "final":
      case "live_translation":
        setLiveTranslation("");
        setResult((previous) => ({ ...previous, translated_text: message.text || message.translated_text }));
        break;
      case "partial_translation":
        setLiveTranslation(message.text || "");
        break;
      case "active_speaker":
        setConversationBrain(`${message.speaker_label || message.speaker || "Speaker"} is speaking`);
        break;
      case "semantic_context":
        setSemanticContext(message);
        break;
      case "tts_audio_chunk":
        handleTtsChunk(message);
        break;
      case "tts_start":
        setStatus(`Streaming voice: 0/${message.chunks || "?"}`);
        if (!message.partial && isStreaming) {
          resumeAfterTtsRef.current = true;
          try { stopAudioStream(); } catch (error) {
            console.error("Error stopping audio stream for TTS:", error);
          }
          setIsStreaming(false);
        }
        break;
      case "tts_end":
        setStatus("Voice stream complete");
        if (!message.partial && resumeAfterTtsRef.current && !isStreaming) {
          resumeAfterTtsRef.current = false;
          setTimeout(() => {
            if (!isStreaming) toggleStreaming();
          }, 350);
        }
        break;
      case "stage":
        setStatus(message.message || message.type);
        break;
      case "vad":
        if (message.speech_detected) {
          setStatus("Speech detected...");
        }
        break;
      default:
        setStatus(`Received: ${message.type || "message"}`);
    }
  }

  async function handleTtsChunk(message) {
    if (!message.audio_base64) return;

    ttsQueueRef.current = [...ttsQueueRef.current, message];
    setTtsQueue(ttsQueueRef.current);

    if (!isPlayingTtsRef.current) {
      playNextTtsChunk();
    }
  }

  async function playNextTtsChunk() {
    if (ttsQueueRef.current.length === 0 || isPlayingTtsRef.current) {
      if (ttsQueueRef.current.length === 0) {
        setIsPlayingTts(false);
        isPlayingTtsRef.current = false;
      }
      return;
    }

    isPlayingTtsRef.current = true;
    setIsPlayingTts(true);

    const message = ttsQueueRef.current.shift();
    setTtsQueue([...ttsQueueRef.current]);

    try {
      await playTtsAudio(message.audio_base64, message.mime_type);
    } catch (error) {
      console.error("TTS playback error:", error);
    }

    isPlayingTtsRef.current = false;
    setIsPlayingTts(false);

    if (ttsQueueRef.current.length > 0) {
      playNextTtsChunk();
    }
  }

  function disconnect() {
    if (wsControlRef.current) {
      wsControlRef.current.close();
      wsControlRef.current = null;
    }
    if (isStreaming) {
      stopAudioStream();
      setIsStreaming(false);
    }
    setIsConnected(false);
    setStatus("Disconnected");
    setStatusType("idle");
  }

  function reconnect() {
    disconnect();
    setTimeout(() => connect(), 1000);
  }

  async function toggleStreaming() {
    if (isStreaming) {
      try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy); } catch (error) {
        console.error("Haptic feedback error:", error);
      }
      setIsStreaming(false);
      setStatus("Finalizing...");
      wsControlRef.current?.send(JSON.stringify({ type: "finalize" }));
      await stopAudioStream();
      return;
    }

    if (!isConnected) {
      setStatus("Connect to backend first");
      setStatusType("error");
      return;
    }

    try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); } catch (error) {
      console.error("Haptic feedback error:", error);
    }
    setStatus("Starting stream...");
    const started = await startAudioStream(async (chunk) => {
      if (wsControlRef.current?.isConnected) {
        const meta = {
          type: "chunk_meta",
          sent_at_ms: Date.now(),
          bytes: chunk.byteLength,
          mime_type: "audio/m4a",
        };
        wsControlRef.current?.send(JSON.stringify(meta));
        wsControlRef.current?.send(chunk);
      }
    }, (error) => {
      setStatus("Stream error: " + error);
      setStatusType("error");
      setIsStreaming(false);
    });

    if (started) {
      setIsStreaming(true);
      setStatus("Streaming audio...");
      setStatusType("connecting");
    }
  }

  async function startRecording() {
    if (!isConnected) {
      setStatus("Connect to backend first");
      setStatusType("error");
      return;
    }
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        setStatus("Microphone permission denied");
        setStatusType("error");
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
      });
      const recordingOptions = Audio.RecordingOptionsPresets.HIGH_QUALITY;
      const { recording: newRecording } = await Audio.Recording.createAsync(recordingOptions);
      setRecording(newRecording);
      setStatus("Recording...");
      setStatusType("connecting");
    } catch (error) {
      setStatus("Could not start microphone: " + error.message);
      setStatusType("error");
    }
  }

  async function stopRecording() {
    if (!recording) return;
    try {
      setStatus("Uploading audio...");
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (!uri) {
        setStatus("No recording captured");
        setStatusType("warning");
        return;
      }
      await uploadAudio(uri);
    } catch (error) {
      setRecording(null);
      setStatus("Recording failed: " + error.message);
      setStatusType("error");
    }
  }

  async function uploadAudio(uri) {
    const form = new FormData();
    form.append("audio", {
      uri,
      name: "recording.m4a",
      type: "audio/m4a",
    });
    form.append("source_language", sourceLanguage);
    form.append("target_language", targetLanguage);
    form.append("synthesize_audio", "true");

    try {
      const response = await fetch(`${wsUrl}/translate/audio`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data",
        },
        body: form,
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || "Translation failed");
        setStatusType("error");
        return;
      }
      setResult(data);
      setStatus("Audio translated");
      setStatusType("success");

      if (data.audio_base64) {
        try {
          isPlayingTtsRef.current = true;
          setIsPlayingTts(true);
          const ok = await playTtsAudio(data.audio_base64, data.mime_type || "audio/wav");
          if (!ok) {
            setStatus("TTS playback failed");
            setStatusType("error");
          }
        } finally {
          isPlayingTtsRef.current = false;
          setIsPlayingTts(false);
        }
      }
    } catch (error) {
      setStatus("Upload failed: " + error.message);
      setStatusType("error");
    }
  }

  function getStatusColor() {
    switch (statusType) {
      case "success": return "#16a34a";
      case "error": return "#dc2626";
      case "warning": return "#ca8a04";
      case "connecting": return "#22d3ee";
      default: return "#64748b";
    }
  }

  function getNetworkInfo() {
    if (!networkState) return "Checking network...";
    const type = networkState.type || "unknown";
    const connected = networkState.isConnected ? "connected" : "disconnected";
    return `${type} - ${connected}`;
  }

  const activeTargetLabel = TARGET_LANGUAGES.find((language) => language.code === targetLanguage)?.label || targetLanguage.toUpperCase();
  const primaryActionLabel = isStreaming ? "Stop Live Voice" : "Start Live Voice";
  const primaryActionDisabled = !isConnected || isPlayingTts;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <GradientHeader title="Anai" subtitle={`Live speech translator • ${getNetworkInfo()}`} />

      {backendReachable !== null && (
        <View style={styles.backendStatusCard}>
          <View style={[styles.statusIndicator, { backgroundColor: backendReachable ? "#16a34a" : "#dc2626" }]} />
          <Text style={styles.backendStatusText}>
            Backend: {backendReachable ? "Reachable" : "Not reachable"}
          </Text>
        </View>
      )}

      <View style={styles.heroPanel}>
        <View style={[styles.heroHalo, isStreaming && styles.heroHaloActive]}>
          <View style={styles.micGrille}>
            {[0, 1, 2, 3, 4, 5, 6].map((bar) => (
              <View key={bar} style={[styles.micBar, isStreaming && styles[`micBarActive${bar % 3}`]]} />
            ))}
          </View>
        </View>
        <Text style={styles.heroKicker}>{isConnected ? "Backend linked" : "Connect backend"}</Text>
        <Text style={styles.heroTitle}>{isStreaming ? "Listening live" : isPlayingTts ? "Speaking translation" : "Ready to interpret"}</Text>
        <Text style={styles.heroSubtitle}>English → {activeTargetLabel}</Text>
        <ActionButton
          title={primaryActionLabel}
          onPress={toggleStreaming}
          tone={isStreaming ? "danger" : "success"}
          disabled={primaryActionDisabled}
          style={styles.primaryMicAction}
        />
      </View>

      <AnimatedCard delay={160}>
        <View style={styles.cardHeader}>
          <Text style={styles.label}>Access</Text>
          <Text style={styles.miniStatus}>{token ? "Signed in" : "Demo login ready"}</Text>
        </View>
        <View style={styles.row}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={username}
            onChangeText={setUsername}
            placeholder="Username"
            placeholderTextColor="#64748b"
            autoCapitalize="none"
          />
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={password}
            onChangeText={setPassword}
            placeholder="Password"
            placeholderTextColor="#64748b"
            secureTextEntry
          />
        </View>
        <View style={styles.actionRow}>
          <ActionButton title={token ? "Logged in" : "Login"} onPress={login} disabled={!!token} />
          {token ? <ActionButton title="Logout" onPress={logout} tone="danger" /> : null}
        </View>
      </AnimatedCard>

      <AnimatedCard delay={220}>
        <View style={styles.cardHeader}>
          <Text style={styles.label}>Language route</Text>
          <Text style={styles.miniStatus}>{sourceLanguage.toUpperCase()} → {targetLanguage.toUpperCase()}</Text>
        </View>
        <View style={styles.languageRoute}>
          <View style={styles.routePill}>
            <Text style={styles.routeCaption}>From</Text>
            <TextInput
              style={styles.routeInput}
              value={sourceLanguage}
              onChangeText={setSourceLanguage}
              placeholder="en"
              placeholderTextColor="#64748b"
              autoCapitalize="none"
            />
          </View>
          <Text style={styles.routeArrow}>→</Text>
          <View style={[styles.routePill, styles.routePillTarget]}>
            <Text style={styles.routeCaption}>To</Text>
            <Text style={styles.routeValue}>{activeTargetLabel}</Text>
          </View>
        </View>
        <View style={styles.languageChips}>
          {TARGET_LANGUAGES.map((language) => (
            <Pressable
              key={language.code}
              onPress={() => setTargetLanguage(language.code)}
              style={[styles.languageChip, targetLanguage === language.code && styles.languageChipActive]}
            >
              <Text style={[styles.languageChipText, targetLanguage === language.code && styles.languageChipTextActive]}>{language.label}</Text>
            </Pressable>
          ))}
        </View>
      </AnimatedCard>

      <AnimatedCard delay={280}>
        <View style={styles.cardHeader}>
          <Text style={styles.label}>Backend URL</Text>
          {recentUrls.length > 0 && (
            <ActionButton title="Recent" onPress={() => setShowRecentUrls(!showRecentUrls)} tone="ghost" style={styles.smallAction} />
          )}
        </View>
        <View style={styles.urlRow}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={wsUrl}
            onChangeText={setWsUrl}
            placeholder="Backend URL (e.g., http://192.168.1.100:8000)"
            placeholderTextColor="#64748b"
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>
        {showRecentUrls && recentUrls.length > 0 && (
          <View style={styles.recentUrls}>
            {recentUrls.map((url, index) => (
              <ActionButton key={index} title={url} onPress={() => { setWsUrl(url); setShowRecentUrls(false); }} tone="ghost" />
            ))}
          </View>
        )}
      </AnimatedCard>

      <View style={styles.statusCard}>
        <View style={[styles.statusIndicator, { backgroundColor: getStatusColor() }]} />
        <View style={styles.statusCopy}>
          <Text style={styles.statusEyebrow}>System status</Text>
          <Text style={[styles.status, { color: getStatusColor() }]}>{status}</Text>
          {conversationBrain ? <Text style={styles.statusMeta}>{conversationBrain}</Text> : null}
          {ttsQueue.length > 0 ? <Text style={styles.statusMeta}>{ttsQueue.length} voice chunks queued</Text> : null}
        </View>
      </View>

      <View style={styles.actionRow}>
        {isConnected ? (
          <ActionButton title="Disconnect" onPress={disconnect} tone="danger" />
        ) : (
          <ActionButton title="Connect Backend" onPress={connect} />
        )}
        <ActionButton
          title={recording ? "Stop Recording" : "Record Audio"}
          onPress={isStreaming ? null : (recording ? stopRecording : startRecording)}
          tone={recording ? "danger" : "success"}
          disabled={!isConnected || isStreaming}
        />
      </View>

      {(partialTranscript || liveTranslation) && (
        <View style={styles.translationPreview}>
          {partialTranscript && (
            <>
              <Text style={styles.resultLabel}>Partial Transcription</Text>
              <Text style={styles.resultText}>{partialTranscript}</Text>
            </>
          )}
          {liveTranslation && (
            <>
              <Text style={styles.resultLabel}>Live Translation</Text>
              <Text style={styles.resultText}>{liveTranslation}</Text>
            </>
          )}
        </View>
      )}

      {result && (
        <View style={styles.resultBox}>
          <Text style={styles.resultLabel}>Source</Text>
          <Text style={styles.resultText}>{result.source_text || "-"}</Text>
          <Text style={styles.resultLabel}>Translated</Text>
          <Text style={styles.resultText}>{result.translated_text || "-"}</Text>
        </View>
      )}

      {isPlayingTts && (
        <View style={styles.playingIndicator}>
          <Text style={styles.playingText}>Playing voice translation...</Text>
        </View>
      )}

      <View style={styles.buttonGroup}>
        <ActionButton
          title={showSettings ? "Back to Main" : "Settings"}
          onPress={() => setShowSettings(!showSettings)}
          tone="ghost"
        />
      </View>

      {showSettings ? (
        <SettingsScreen
          wsUrl={wsUrl}
          setWsUrl={setWsUrl}
          sourceLanguage={sourceLanguage}
          setSourceLanguage={setSourceLanguage}
          targetLanguage={targetLanguage}
          setTargetLanguage={setTargetLanguage}
          onClearData={async () => {
            await SecureStore.deleteItemAsync(TOKEN_KEY);
            await SecureStore.deleteItemAsync(RECENT_URLS_KEY);
            setToken("");
            setRecentUrls([]);
            setStatus("All data cleared");
            setStatusType("idle");
          }}
        />
      ) : (
        <>
          <DuplexMode
            isConnected={isConnected}
            wsControlRef={wsControlRef}
            sourceLanguage={sourceLanguage}
            targetLanguage={targetLanguage}
            onTranscriptUpdate={(speaker, text) => {
              debugLog(`Speaker ${speaker} transcript:`, text);
            }}
            onTranslationUpdate={(speaker, text) => {
              debugLog(`Speaker ${speaker} translation:`, text);
            }}
          />

          <SemanticContext context={semanticContext} />

          <AdvancedFeatures
            noiseLevel={emotionInfo?.noise_level}
            beamforming={emotionInfo?.beamforming}
            speakerDiarization={emotionInfo?.speaker_diarization}
            contextMemory={{
              technicalTerms: emotionInfo?.technical_terms,
              conversationTopics: semanticContext?.topics,
            }}
            emotionalNuance={{
              emotion: emotionInfo?.emotion,
              tone: emotionInfo?.tone,
              prosodyScore: emotionInfo?.prosody_score,
            }}
            streamingStatus={{
              sttPartial: !!partialTranscript,
              translationPartial: !!liveTranslation,
            }}
          />
        </>
      )}

      <Assistant
        apiUrl={API_URL}
        authToken={token}
        getTranslationContext={() => {
          if (!result) return null;
          return {
            source_language: sourceLanguage,
            target_language: targetLanguage,
            source_text: result.source_text || result.original_text || "",
            translated_text: result.translated_text || "",
          };
        }}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#03050a" },
  content: { padding: 18, paddingBottom: 34 },
  backendStatusCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 12,
    backgroundColor: "rgba(15, 23, 42, 0.82)",
    borderRadius: 18,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.18)",
  },
  backendStatusText: { color: "#cbd5e1", fontWeight: "800" },
  heroPanel: {
    alignItems: "center",
    padding: 22,
    marginBottom: 16,
    borderRadius: 32,
    backgroundColor: "#06101f",
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.28)",
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 18 },
    shadowOpacity: 0.22,
    shadowRadius: 32,
    elevation: 8,
  },
  heroHalo: {
    width: 156,
    height: 156,
    borderRadius: 78,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#020617",
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.32)",
    shadowColor: "#06b6d4",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.36,
    shadowRadius: 28,
  },
  heroHaloActive: {
    borderColor: "rgba(52, 211, 153, 0.72)",
    shadowColor: "#34d399",
    shadowOpacity: 0.5,
  },
  micGrille: {
    width: 92,
    height: 104,
    borderRadius: 46,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    backgroundColor: "#000",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    overflow: "hidden",
  },
  micBar: {
    width: 7,
    height: 42,
    borderRadius: 999,
    backgroundColor: "#155e75",
  },
  micBarActive0: { height: 58, backgroundColor: "#67e8f9" },
  micBarActive1: { height: 78, backgroundColor: "#2dd4bf" },
  micBarActive2: { height: 64, backgroundColor: "#f0abfc" },
  heroKicker: {
    marginTop: 16,
    color: "#67e8f9",
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  heroTitle: {
    marginTop: 6,
    color: "#f8fafc",
    fontSize: 26,
    fontWeight: "950",
    textAlign: "center",
  },
  heroSubtitle: {
    marginTop: 6,
    color: "#94a3b8",
    fontSize: 14,
    fontWeight: "800",
  },
  primaryMicAction: { marginTop: 18, minWidth: 210 },
  card: {
    backgroundColor: "#0c1729",
    padding: 15,
    borderRadius: 12,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "#24344f",
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 10,
  },
  label: { color: "#e2e8f0", fontSize: 14, fontWeight: "900", textTransform: "uppercase", letterSpacing: 0.8 },
  miniStatus: { color: "#67e8f9", fontSize: 12, fontWeight: "800" },
  input: {
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.28)",
    padding: 12,
    marginVertical: 5,
    borderRadius: 12,
    color: "#e5ecff",
    backgroundColor: "#081527",
  },
  row: { flexDirection: "row", gap: 10, marginVertical: 5 },
  actionRow: { flexDirection: "row", gap: 10, marginBottom: 15 },
  urlRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  recentUrls: { marginTop: 10, gap: 8 },
  languageRoute: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  routePill: {
    flex: 1,
    minHeight: 58,
    padding: 10,
    borderRadius: 18,
    backgroundColor: "#081527",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.18)",
  },
  routePillTarget: { borderColor: "rgba(45, 212, 191, 0.34)", backgroundColor: "#052e2b" },
  routeCaption: { color: "#64748b", fontSize: 10, fontWeight: "900", textTransform: "uppercase" },
  routeInput: { color: "#f8fafc", fontSize: 18, fontWeight: "900", padding: 0, marginTop: 4 },
  routeValue: { color: "#a7f3d0", fontSize: 16, fontWeight: "900", marginTop: 5 },
  routeArrow: { color: "#67e8f9", fontSize: 22, fontWeight: "900" },
  languageChips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  languageChip: {
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 999,
    backgroundColor: "rgba(15, 23, 42, 0.74)",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.16)",
  },
  languageChipActive: { backgroundColor: "rgba(20, 184, 166, 0.24)", borderColor: "rgba(45, 212, 191, 0.42)" },
  languageChipText: { color: "#94a3b8", fontSize: 12, fontWeight: "800" },
  languageChipTextActive: { color: "#ccfbf1" },
  statusCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 15,
    backgroundColor: "#0c1729",
    borderRadius: 18,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.18)",
  },
  statusIndicator: { width: 12, height: 12, borderRadius: 6 },
  statusCopy: { flex: 1 },
  statusEyebrow: { color: "#64748b", fontSize: 10, fontWeight: "900", textTransform: "uppercase" },
  status: { fontSize: 16, fontWeight: "900" },
  statusMeta: { color: "#94a3b8", fontSize: 12, marginTop: 2 },
  buttonGroup: { marginBottom: 15 },
  actionButton: {
    flex: 1,
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "transparent",
  },
  actionButton_primary: { backgroundColor: "#0891b2", borderColor: "rgba(103, 232, 249, 0.38)" },
  actionButton_success: { backgroundColor: "#059669", borderColor: "rgba(167, 243, 208, 0.38)" },
  actionButton_danger: { backgroundColor: "#dc2626", borderColor: "rgba(254, 202, 202, 0.28)" },
  actionButton_ghost: { backgroundColor: "rgba(15, 23, 42, 0.7)", borderColor: "rgba(148, 163, 184, 0.22)" },
  actionButtonDisabled: { opacity: 0.45 },
  actionButtonPressed: { transform: [{ scale: 0.98 }] },
  actionButtonText: { color: "#f8fafc", fontSize: 14, fontWeight: "900", textAlign: "center" },
  actionButtonTextGhost: { color: "#cbd5e1" },
  smallAction: { flex: 0, minHeight: 34, paddingHorizontal: 12 },
  translationPreview: {
    padding: 15,
    backgroundColor: "#071827",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(96, 165, 250, 0.36)",
    marginBottom: 15,
  },
  resultBox: {
    padding: 15,
    backgroundColor: "#061b18",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(45, 212, 191, 0.34)",
    marginBottom: 15,
  },
  resultLabel: { color: "#67e8f9", fontWeight: "900", marginTop: 10, fontSize: 12, textTransform: "uppercase" },
  resultText: { color: "#e5ecff", fontSize: 16, lineHeight: 22, marginTop: 5 },
  playingIndicator: { padding: 12, backgroundColor: "#059669", borderRadius: 14, marginBottom: 15 },
  playingText: { color: "#fff", textAlign: "center", fontWeight: "900" },
});