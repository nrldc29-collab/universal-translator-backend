import { useState, useEffect, useRef } from "react";
import { View, Text, Button, TextInput, StyleSheet, ScrollView, Alert, ActivityIndicator } from "react-native";
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
import * as Haptics from "expo-haptics";

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || "https://universal-translator-phone-production.up.railway.app";
const TOKEN_KEY = "translator_token";
const RECENT_URLS_KEY = "recent_urls";
const MAX_RECENT_URLS = 5;

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
      if (wsControlRef.current?.isConnected && !isConnected) {
        setStatus("Network changed - reconnecting...");
        reconnect();
      }
    } catch (error) {
      console.error("Network check error:", error);
    }
  }

  async function saveRecentUrl(url) {
    try {
      const updated = [url, ...recentUrls.filter(u => u !== url)].slice(0, MAX_RECENT_URLS);
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
        headers: { "Content-Type": "application/json" }
      });
      if (response.ok) {
        setBackendReachable(true);
        return true;
      }
      setBackendReachable(false);
      return false;
    } catch (error) {
      setBackendReachable(false);
      return false;
    }
  }

  function validateUrl(url) {
    try {
      if (!url || url.trim() === "") return false;
      if (!url.startsWith("http://") && !url.startsWith("https://")) return false;
      return true;
    } catch {
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
    console.log("Connecting to:", url);
    
    wsControlRef.current = connectWS(url, handleMessage, setStatusWithType);
    wsControlRef.current.updateHandlers(handleMessage, setStatusWithType);
  }

  function setStatusWithType(status, type = null) {
    setStatus(status);
    if (type) {
      setStatusType(type);
    } else if (status.includes("Connected")) {
      setStatusType("success");
      setIsConnected(true);
      saveRecentUrl(wsUrl);
      // Send start message for streaming
      wsControlRef.current?.send(JSON.stringify({
        type: "start",
        session_id: "mobile-" + Date.now(),
        speaker: "A",
        source_language: sourceLanguage,
        target_language: targetLanguage,
      }));
    } else if (status.includes("Disconnected") || status.includes("failed") || status.includes("error")) {
      setStatusType("error");
      setIsConnected(false);
      setIsStreaming(false);
    } else if (status.includes("Reconnecting") || status.includes("Connecting")) {
      setStatusType("connecting");
    } else if (status.includes("Reconnecting in")) {
      setStatusType("warning");
    }
  }

  function handleMessage(message) {
    console.log("Message:", message.type, message);
    
    switch (message.type) {
      case "pong":
        console.log("Heartbeat pong received");
        break;
      case "final_transcription":
        setPartialTranscript("");
        setResult(prev => ({ ...prev, source_text: message.text }));
        break;
      case "partial_transcription":
        setPartialTranscript(message.text || "");
        break;
      case "final":
      case "live_translation":
        setLiveTranslation("");
        setResult(prev => ({ ...prev, translated_text: message.text || message.translated_text }));
        break;
      case "partial_translation":
        setLiveTranslation(message.text || "");
        break;
      case "tts_audio_chunk":
        handleTtsChunk(message);
        break;
      case "tts_start":
        setStatus(`Streaming voice: 0/${message.chunks || '?'}`);
        break;
      case "tts_end":
        setStatus("Voice stream complete");
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
    
    // Add to queue
    ttsQueueRef.current = [...ttsQueueRef.current, message];
    setTtsQueue(ttsQueueRef.current);
    
    // Start playing if not already
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
    
    // Play next chunk
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
      // Stop streaming
      try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy); } catch(e) {}
      setIsStreaming(false);
      setStatus("Finalizing...");
      wsControlRef.current?.send(JSON.stringify({ type: "finalize" }));
      await stopAudioStream();
    } else {
      // Start streaming
      if (!isConnected) {
        setStatus("Connect to backend first");
        setStatusType("error");
        return;
      }
      
      try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); } catch(e) {}
      setStatus("Starting stream...");
      const started = await startAudioStream(async (chunk) => {
        // Send audio chunk via WebSocket
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
    form.append('audio', {
      uri,
      name: 'recording.m4a',
      type: 'audio/m4a',
    });
    form.append('source_language', sourceLanguage);
    form.append('target_language', targetLanguage);
    form.append('synthesize_audio', 'true');

    try {
      const response = await fetch(`${wsUrl}/translate/audio`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
        body: form,
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || 'Translation failed');
        setStatusType("error");
        return;
      }
      setResult(data);
      setStatus('Audio translated');
      setStatusType("success");
    } catch (error) {
      setStatus('Upload failed: ' + error.message);
      setStatusType("error");
    }
  }

  function getStatusColor() {
    switch (statusType) {
      case "success": return "#16a34a";
      case "error": return "#dc2626";
      case "warning": return "#ca8a04";
      case "connecting": return "#2563eb";
      default: return "#6b7280";
    }
  }

  function getNetworkInfo() {
    if (!networkState) return "Checking network...";
    const type = networkState.type || "unknown";
    const isConnected = networkState.isConnected ? "connected" : "disconnected";
    return `${type} - ${isConnected}`;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <GradientHeader title="Universal Translator" subtitle={`Network: ${getNetworkInfo()}`} />
      
      {backendReachable !== null && (
        <View style={styles.backendStatusCard}>
          <View style={[styles.statusIndicator, { backgroundColor: backendReachable ? "#16a34a" : "#dc2626" }]} />
          <Text style={styles.backendStatusText}>
            Backend: {backendReachable ? "Reachable" : "Not reachable"}
          </Text>
        </View>
      )}
      
      <AnimatedCard delay={100}>
        <Text style={styles.label}>Backend URL</Text>
        <View style={styles.urlRow}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={wsUrl}
            onChangeText={setWsUrl}
            placeholder="Backend URL (e.g., http://192.168.1.100:8000)"
            autoCapitalize="none"
            autoCorrect={false}
          />
          {recentUrls.length > 0 && (
            <Button title="Recent" onPress={() => setShowRecentUrls(!showRecentUrls)} color="#6b7280" />
          )}
        </View>
        {showRecentUrls && recentUrls.length > 0 && (
          <View style={styles.recentUrls}>
            {recentUrls.map((url, index) => (
              <Button key={index} title={url} onPress={() => { setWsUrl(url); setShowRecentUrls(false); }} color="#2563eb" />
            ))}
          </View>
        )}
      </AnimatedCard>
      
      <AnimatedCard delay={200}>
        <Text style={styles.label}>Login</Text>
        <View style={styles.row}>
          <TextInput 
            style={[styles.input, { flex: 1 }]} 
            value={username} 
            onChangeText={setUsername} 
            placeholder="Username" 
            autoCapitalize="none"
          />
          <TextInput 
            style={[styles.input, { flex: 1 }]} 
            value={password} 
            onChangeText={setPassword} 
            placeholder="Password" 
            secureTextEntry 
          />
        </View>
        <View style={styles.row}>
          <Button title={token ? "Logged in" : "Login"} onPress={login} disabled={!!token} color="#2563eb" />
          {token ? <Button title="Logout" onPress={logout} color="#dc2626" /> : null}
        </View>
      </AnimatedCard>
      
      <View style={styles.card}>
        <Text style={styles.label}>Languages</Text>
        <View style={styles.row}>
          <TextInput 
            style={[styles.input, { flex: 1 }]} 
            value={sourceLanguage} 
            onChangeText={setSourceLanguage} 
            placeholder="Source (en)" 
            autoCapitalize="none"
          />
          <TextInput 
            style={[styles.input, { flex: 1 }]} 
            value={targetLanguage} 
            onChangeText={setTargetLanguage} 
            placeholder="Target (es)" 
            autoCapitalize="none"
          />
        </View>
      </View>
      
      <View style={styles.statusCard}>
        <View style={[styles.statusIndicator, { backgroundColor: getStatusColor() }]} />
        <Text style={[styles.status, { color: getStatusColor() }]}>Status: {status}</Text>
      </View>
      
      <View style={styles.buttonGroup}>
        {isConnected ? (
          <Button title="Disconnect" onPress={disconnect} color="#dc2626" />
        ) : (
          <Button title="Connect to Backend" onPress={connect} color="#2563eb" />
        )}
      </View>
      
      <View style={styles.buttonGroup}>
        <Button 
          title={isStreaming ? "Stop Streaming" : "Start Streaming"} 
          onPress={toggleStreaming}
          color={isStreaming ? "#dc2626" : "#16a34a"}
          disabled={!isConnected}
        />
      </View>
      
      <View style={styles.buttonGroup}>
        <Button 
          title={"Record Audio"} 
          onPress={isStreaming ? null : (recording ? stopRecording : startRecording)}
          color={recording ? "#dc2626" : "#16a34a"}
          disabled={!isConnected || isStreaming}
        />
      </View>
      
      {(partialTranscript || liveTranslation) && (
        <View style={styles.translationPreview}>
          {partialTranscript && (
            <>
              <Text style={styles.resultLabel}>Partial Transcription:</Text>
              <Text style={styles.resultText}>{partialTranscript}</Text>
            </>
          )}
          {liveTranslation && (
            <>
              <Text style={styles.resultLabel}>Live Translation:</Text>
              <Text style={styles.resultText}>{liveTranslation}</Text>
            </>
          )}
        </View>
      )}
      
      {result && (
        <View style={styles.resultBox}>
          <Text style={styles.resultLabel}>Source:</Text>
          <Text style={styles.resultText}>{result.source_text || '-'}</Text>
          <Text style={styles.resultLabel}>Translated:</Text>
          <Text style={styles.resultText}>{result.translated_text || '-'}</Text>
        </View>
      )}
      
      {isPlayingTts && (
        <View style={styles.playingIndicator}>
          <Text style={styles.playingText}>🔊 Playing TTS...</Text>
        </View>
      )}
      
      <View style={styles.buttonGroup}>
        <Button 
          title={showSettings ? "Back to Main" : "Settings"} 
          onPress={() => setShowSettings(!showSettings)} 
          color="#6b7280"
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
              console.log(`Speaker ${speaker} transcript:`, text);
            }}
            onTranslationUpdate={(speaker, text) => {
              console.log(`Speaker ${speaker} translation:`, text);
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#07111f' },
  content: { padding: 20 },
  header: { marginBottom: 20 },
  title: { fontSize: 28, fontWeight: "bold", color: '#e5ecff', marginBottom: 8 },
  networkInfo: { fontSize: 12, color: '#93a4bd' },
  backendStatus: { fontSize: 12, marginTop: 4 },
  card: { backgroundColor: '#0c1729', padding: 15, borderRadius: 12, marginBottom: 15, borderWidth: 1, borderColor: '#24344f' },
  label: { color: '#93a4bd', fontSize: 14, marginBottom: 8, fontWeight: 'bold' },
  input: { borderWidth: 1, borderColor: "#334155", padding: 10, marginVertical: 5, borderRadius: 8, color: '#e5ecff', backgroundColor: '#081527' },
  row: { flexDirection: "row", gap: 10, marginVertical: 5 },
  urlRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  recentUrls: { marginTop: 10, gap: 5 },
  statusCard: { flexDirection: "row", alignItems: "center", gap: 10, padding: 15, backgroundColor: '#0c1729', borderRadius: 12, marginBottom: 15, borderWidth: 1, borderColor: '#24344f' },
  statusIndicator: { width: 12, height: 12, borderRadius: 6 },
  status: { fontSize: 16, fontWeight: 'bold' },
  buttonGroup: { marginBottom: 15 },
  translationPreview: { padding: 15, backgroundColor: '#0c1729', borderRadius: 12, borderWidth: 1, borderColor: '#2563eb', marginBottom: 15 },
  resultBox: { padding: 15, backgroundColor: '#0c1729', borderRadius: 12, borderWidth: 1, borderColor: '#2563eb', marginBottom: 15 },
  resultLabel: { color: '#60a5fa', fontWeight: 'bold', marginTop: 10, fontSize: 12, textTransform: 'uppercase' },
  resultText: { color: '#e5ecff', fontSize: 16, lineHeight: 22, marginTop: 5 },
  playingIndicator: { padding: 10, backgroundColor: '#16a34a', borderRadius: 8, marginBottom: 15 },
  playingText: { color: '#fff', textAlign: 'center', fontWeight: 'bold' },
});