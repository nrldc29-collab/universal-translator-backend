import { useEffect, useRef, useState } from "react";
import { View, Text, TextInput, ScrollView, Pressable } from "react-native";
import { Audio } from "expo-av";
import Constants from "expo-constants";
import * as Network from "expo-network";
import { apiToWsUrl, connectWS } from "./services/ws";
import { startAudioStream, stopAudioStream, playTtsAudio } from "./services/audio-stream";
import SemanticContext from "./components/SemanticContext";
import SettingsScreen from "./components/SettingsScreen";
import AnimatedCard from "./components/AnimatedCard";
import GradientHeader from "./components/GradientHeader";
import AdvancedFeatures from "./components/AdvancedFeatures";
import Assistant from "./components/Assistant";
import ActionButton from "./components/ActionButton";
import styles from "./AppStyles";
import * as Haptics from "expo-haptics";
import { useMobileTts } from "./hooks/useMobileTts";
import { useMobileAuth } from "./hooks/useMobileAuth";
import { useMobileBrainContext } from "./hooks/useMobileBrainContext";
import { useMobileStreamState } from "./hooks/useMobileStreamState";
import { useMobileSession } from "./hooks/useMobileSession";
import { useMobileConnectionState } from "./hooks/useMobileConnectionState";
import { useMobileUiState } from "./hooks/useMobileUiState";
import { useMobileRecording } from "./hooks/useMobileRecording";

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || "";
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === "1");
const TARGET_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "ht", label: "Haitian Creole" },
];

function debugLog(...args) {
  if (DEBUG_LOGS) console.debug(...args);
}

function getStatusColor(statusType) {
  switch (statusType) {
    case "success": return "#16a34a";
    case "error": return "#dc2626";
    case "warning": return "#ca8a04";
    case "connecting": return "#22d3ee";
    default: return "#64748b";
  }
}

function getNetworkInfo(networkState) {
  if (!networkState) return "Checking network...";
  const type = networkState.type || "unknown";
  const connected = networkState.isConnected ? "connected" : "disconnected";
  return `${type} - ${connected}`;
}

export default function App() {
  const { status, setStatus, statusType, setStatusType, isConnected, setIsConnected, isConnectedRef, networkState, setNetworkState } = useMobileConnectionState();
  const { sourceLanguage, setSourceLanguage, targetLanguage, setTargetLanguage, mobileDeviceIdRef, mobileSessionIdRef } = useMobileSession();
  const { result, setResult, showSettings, setShowSettings } = useMobileUiState();
  const {
    isStreaming, setIsStreaming,
    recording, setRecording,
    partialTranscript, setPartialTranscript,
    liveTranslation, setLiveTranslation,
    wsControlRef, resumeAfterTtsRef, isStreamingRef,
  } = useMobileStreamState();
  const { semanticContext, setSemanticContext, emotionInfo, setEmotionInfo, conversationBrain, setConversationBrain } = useMobileBrainContext();

  const { ttsQueue, isPlayingTts, setIsPlayingTts, ttsQueueRef, isPlayingTtsRef, handleTtsChunk, volume, setVolume, playbackSpeed, setPlaybackSpeed, stopTtsPlayback } = useMobileTts();
  const toggleStreamingRef = useRef(null);
  const [debugMode, setDebugMode] = useState(false);
  const {
    token, setToken, username, setUsername, password, setPassword,
    wsUrl, setWsUrl, recentUrls, showRecentUrls, setShowRecentUrls,
    backendReachable, loadStoredData, saveRecentUrl, validateUrl, login, logout, clearAllData,
  } = useMobileAuth({
    defaultUrl: API_URL,
    onStatus: (msg, type) => { setStatus(msg); if (type) setStatusType(type); },
  });


  useEffect(() => {
    loadStoredData();
    checkNetworkState();
    const interval = setInterval(checkNetworkState, 5000);
    return () => clearInterval(interval);
  }, []);

  const langInitializedRef = useRef(false);
  useEffect(() => {
    if (!langInitializedRef.current) {
      langInitializedRef.current = true;
      return;
    }
    if (isConnectedRef.current && wsControlRef.current?.readyState === WebSocket.OPEN) {
      sendSessionStart();
    }
  }, [sourceLanguage, targetLanguage]);


  async function checkNetworkState() {
    try {
      const state = await Network.getNetworkStateAsync();
      setNetworkState(state);
      
      // Auto-reconnect if network becomes available and we're disconnected
      if (state.isConnected && !isConnectedRef.current && token && wsUrl) {
        setStatus("Network restored - reconnecting...");
        setTimeout(() => {
          if (!isConnectedRef.current && token) connect();
        }, 1000);
      }

      // Disconnect if network is lost
      if (!state.isConnected && isConnectedRef.current) {
        setStatus("Network lost - disconnecting...");
        disconnect();
      }
    } catch (error) {
      console.error("Network check error:", error);
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

  function sendSessionStart() {
    wsControlRef.current?.send(JSON.stringify({
      type: "start",
      session_id: mobileSessionIdRef.current,
      device_id: mobileDeviceIdRef.current,
      speaker: "auto",
      speaker_mode: "auto",
      source_language: sourceLanguage,
      target_language: targetLanguage,
      mime_type: "audio/m4a",
    }));
  }

  function setStatusWithType(nextStatus, type = null) {
    setStatus(nextStatus);
    if (type) {
      setStatusType(type);
    } else if (nextStatus.includes("Connected")) {
      setStatusType("success");
      setIsConnected(true);
      saveRecentUrl(wsUrl);
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
      case "ready":
        setIsConnected(true);
        saveRecentUrl(wsUrl);
        setStatus("Connected");
        setStatusType("success");
        sendSessionStart();
        break;
      case "error":
        if (message.warming) {
          setStatus("Models still loading — wait for LIVE");
          setStatusType("warning");
          setIsConnected(false);
          break;
        }
        setStatus(message.message || message.error || "Stream error");
        setStatusType("error");
        break;
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
        if (!message.partial && isStreamingRef.current) {
          resumeAfterTtsRef.current = true;
          try { stopAudioStream(); } catch (error) {
            console.error("Error stopping audio stream for TTS:", error);
          }
          setIsStreaming(false);
        }
        break;
      case "tts_end":
        setStatus("Voice stream complete");
        if (!message.partial && resumeAfterTtsRef.current && !isStreamingRef.current) {
          resumeAfterTtsRef.current = false;
          setTimeout(() => {
            if (!isStreamingRef.current) toggleStreamingRef.current?.();
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
        debugLog("Unhandled message type:", message.type, message);
    }
  }


  function disconnect() {
    if (wsControlRef.current) {
      wsControlRef.current.close();
      wsControlRef.current = null;
    }
    if (isStreamingRef.current) {
      stopAudioStream();
      setIsStreaming(false);
    }
    stopTtsPlayback();
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

  toggleStreamingRef.current = toggleStreaming;

  const { startRecording, stopRecording, audioQuality, setAudioQuality, isUploading, uploadProgress, AUDIO_QUALITIES } = useMobileRecording({
    isConnected, sourceLanguage, targetLanguage, wsUrl, token,
    recording, setRecording, setStatus, setStatusType,
    setResult, isPlayingTtsRef, setIsPlayingTts,
  });

  const activeSourceLabel = TARGET_LANGUAGES.find((language) => language.code === sourceLanguage)?.label || sourceLanguage.toUpperCase();
  const activeTargetLabel = TARGET_LANGUAGES.find((language) => language.code === targetLanguage)?.label || targetLanguage.toUpperCase();
  const heroDirection = `${activeSourceLabel} ↔ ${activeTargetLabel}`;
  const primaryActionLabel = isStreaming ? "Stop Live Voice" : "Start Live Voice";
  const primaryActionDisabled = !isConnected || isPlayingTts;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <GradientHeader title="Anai" subtitle={`Live speech translator • ${getNetworkInfo(networkState)}`} />

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
        <Text style={styles.heroSubtitle}>{heroDirection}</Text>
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
          {token ? <ActionButton title="Logout" onPress={() => logout({ onDisconnect: isConnected ? disconnect : undefined })} tone="danger" /> : null}
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
        <View style={[styles.statusIndicator, { backgroundColor: getStatusColor(statusType) }]} />
        <View style={styles.statusCopy}>
          <Text style={styles.statusEyebrow}>System status</Text>
          <Text style={[styles.status, { color: getStatusColor(statusType) }]}>{status}</Text>
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
            await clearAllData();
            setStatus("All data cleared");
            setStatusType("idle");
          }}
          volume={volume}
          setVolume={setVolume}
          playbackSpeed={playbackSpeed}
          setPlaybackSpeed={setPlaybackSpeed}
          audioQuality={audioQuality}
          setAudioQuality={setAudioQuality}
          AUDIO_QUALITIES={AUDIO_QUALITIES}
          debugMode={debugMode}
          setDebugMode={setDebugMode}
        />
      ) : (
        <>
          <Text style={[styles.backendStatusText, { marginBottom: 12 }]}>
            Use Start Live Voice for EN↔HT translation. Conversation duplex UI is not enabled on mobile yet.
          </Text>

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

