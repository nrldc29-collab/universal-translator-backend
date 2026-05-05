import React, { useEffect, useMemo, useRef, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Audio } from 'expo-av';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { StatusBar } from 'expo-status-bar';
import { playAudio, startMic, stopMic } from './services/audio';
import { apiToWsUrl, connectWS } from './services/ws';

const DEFAULT_API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'translator_token';
const SESSION_KEY = 'translator_session_id';

function authHeaders(token, extra = {}) {
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

function randomSessionId() {
  return `mobile-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function App() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish' });
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguage, setTargetLanguage] = useState('es');
  const [sessionId, setSessionId] = useState('');
  const [recording, setRecording] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [result, setResult] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [activeSpeaker, setActiveSpeaker] = useState('A');
  const [lastAudioUri, setLastAudioUri] = useState(null);
  const [playbackStatus, setPlaybackStatus] = useState('Idle');
  const [streamSocket, setStreamSocket] = useState(null);
  const [streamStatus, setStreamStatus] = useState('Disconnected');
  const [streamingAudio, setStreamingAudio] = useState(false);
  const [ttsPlaybackStatus, setTtsPlaybackStatus] = useState('Idle');
  const [audioChunksSent, setAudioChunksSent] = useState(0);
  const [audioBytesSent, setAudioBytesSent] = useState(0);
  const [latencyStatus, setLatencyStatus] = useState('No latency yet');
  const [partialTranslation, setPartialTranslation] = useState('');
  const [ttsStyle, setTtsStyle] = useState(null);
  const streamSocketRef = useRef(null);
  const streamingAudioRef = useRef(false);
  const heartbeatRef = useRef(null);

  const signedIn = useMemo(() => Boolean(token), [token]);

  useEffect(() => {
    restoreState();
  }, []);

  useEffect(() => {
    loadLanguages();
  }, [apiUrl]);

  async function restoreState() {
    const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
    const storedSession = await SecureStore.getItemAsync(SESSION_KEY);
    if (storedToken) setToken(storedToken);
    if (storedSession) {
      setSessionId(storedSession);
    } else {
      const nextSession = randomSessionId();
      setSessionId(nextSession);
      await SecureStore.setItemAsync(SESSION_KEY, nextSession);
    }
  }

  async function loadLanguages() {
    try {
      const response = await fetch(`${apiUrl}/languages`);
      const data = await response.json();
      setLanguages(data.languages || languages);
      setStatus('Backend online');
    } catch {
      setStatus('Backend offline. Set API URL to your computer LAN IP.');
    }
  }

  async function login() {
    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        setStatus('Login failed');
        return;
      }
      const data = await response.json();
      await SecureStore.setItemAsync(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setStatus(`Logged in as ${username}`);
    } catch {
      setStatus('Login request failed');
    }
  }

  async function logout() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken('');
    setStatus('Logged out');
  }

  async function updateSession(value) {
    setSessionId(value);
    await SecureStore.setItemAsync(SESSION_KEY, value);
  }

  async function startRecording() {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        setStatus('Microphone permission denied');
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
      });
      const recordingOptions = Audio.RecordingOptionsPresets.HIGH_QUALITY;
      const { recording: nextRecording } = await Audio.Recording.createAsync(recordingOptions);
      setRecording(nextRecording);
      setStatus('Recording...');
    } catch {
      setStatus('Could not start microphone');
    }
  }

  async function stopRecording() {
    if (!recording) return;
    try {
      setStatus('Uploading audio...');
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (!uri) {
        setStatus('No recording captured');
        return;
      }
      await uploadAudio(uri);
    } catch {
      setRecording(null);
      setStatus('Recording failed');
    }
  }

  async function uploadAudio(uri) {
    if (!token) {
      setStatus('Log in before translating audio');
      return;
    }
    const form = new FormData();
    form.append('audio', {
      uri,
      name: 'recording.m4a',
      type: 'audio/m4a',
    });
    form.append('source_language', sourceLanguage);
    form.append('target_language', targetLanguage);
    form.append('synthesize_audio', 'true');
    form.append('session_id', sessionId);
    form.append('speaker', activeSpeaker);

    try {
      const response = await fetch(`${apiUrl}/translate/audio`, {
        method: 'POST',
        headers: authHeaders(token),
        body: form,
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || 'Translation failed');
        return;
      }
      setResult(data);
      setLastAudioUri(uri);
      setStatus('Audio translated');
    } catch {
      setStatus('Upload failed. Check API URL and network.');
    }
  }

  async function playLastRecording() {
    if (!lastAudioUri) {
      setPlaybackStatus('No audio to play');
      return;
    }
    try {
      setPlaybackStatus('Playing...');
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
      const { sound } = await Audio.Sound.createAsync({ uri: lastAudioUri });
      sound.setOnPlaybackStatusUpdate((state) => {
        if (state.didJustFinish) {
          setPlaybackStatus('Playback complete');
          sound.unloadAsync();
        }
      });
      await sound.playAsync();
    } catch {
      setPlaybackStatus('Playback failed');
    }
  }

  async function startStreamingAudio() {
    if (!streamSocketRef.current || streamSocketRef.current.readyState !== WebSocket.OPEN) {
      setStatus('Connect stream first');
      return;
    }
    const permission = await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      setStatus('Microphone permission denied');
      return;
    }
    streamSocketRef.current.send(JSON.stringify({
      type: 'start',
      session_id: sessionId,
      speaker: activeSpeaker,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    }));
    streamingAudioRef.current = true;
    setStreamingAudio(true);
    setAudioChunksSent(0);
    setAudioBytesSent(0);
    setStreamStatus('Streaming audio chunks...');
    await startMic(async (audioChunk) => {
      if (streamSocketRef.current?.readyState === WebSocket.OPEN) {
        streamSocketRef.current.send(JSON.stringify({ type: 'chunk_meta', sent_at_ms: Date.now(), bytes: audioChunk.byteLength }));
        streamSocketRef.current.send(audioChunk);
        setAudioChunksSent((count) => count + 1);
        setAudioBytesSent((bytes) => bytes + audioChunk.byteLength);
      }
    }, 500);
  }

  async function stopStreamingAudio() {
    streamingAudioRef.current = false;
    setStreamingAudio(false);
    await stopMic();
    if (streamSocketRef.current?.readyState === WebSocket.OPEN) {
      streamSocketRef.current.send(JSON.stringify({ type: 'finalize' }));
    }
    setStreamStatus('Finalizing stream...');
  }

  function toggleStreamConnection() {
    if (streamSocket) {
      clearInterval(heartbeatRef.current);
      streamSocket.close();
      setStreamSocket(null);
      streamSocketRef.current = null;
      setStreamStatus('Disconnected');
      return;
    }
    if (!token) {
      setStatus('Log in before opening stream');
      return;
    }
    const wsUrl = apiToWsUrl(apiUrl, '/ws/audio', token);
    const ws = connectWS(
      wsUrl,
      (message) => {
        if (message.type === 'ready') setStreamStatus('Ready');
        if (message.type === 'pong') setStreamStatus('Pong received');
        if (message.type === 'stage') setStreamStatus(message.message);
        if (message.type === 'latency') {
          setLatencyStatus(`${message.metric}: ${message.ms}ms`);
        }
        if (message.type === 'vad') setStreamStatus(message.speech_detected ? 'Speech detected' : 'Waiting for speech');
        if (message.type === 'final_transcription') {
          setResult((current) => ({ ...(current || {}), source_text: message.text }));
        }
        if (message.type === 'partial_transcription') {
          setResult((current) => ({ ...(current || {}), source_text: message.text }));
        }
        if (message.type === 'partial_translation') {
          setPartialTranslation(message.text);
          setResult((current) => ({ ...(current || {}), translated_text: message.text }));
        }
        if (message.type === 'session_restored') setStreamStatus('Session joined');
        if (message.type === 'live_translation') {
          setResult((current) => ({ ...(current || {}), translated_text: message.text }));
        }
        if (message.type === 'tts_style') {
          setTtsStyle(message);
        }
        if (message.type === 'tts_audio_chunk') {
          setTtsStyle({
            emotion: message.emotion,
            intent: message.intent,
            urgency: message.urgency,
            style: message.tts_style,
          });
          setTtsPlaybackStatus('Playing TTS...');
          playAudio(message.audio_base64, message.mime_type)
            .then(() => setTtsPlaybackStatus('TTS playback started'))
            .catch(() => setTtsPlaybackStatus('TTS playback failed'));
        }
        if (message.type === 'final') {
          setResult(message);
          setStreamStatus('Stream complete');
        }
      },
      setStreamStatus,
    );
    setStreamSocket(ws);
    streamSocketRef.current = ws;
    heartbeatRef.current = setInterval(() => {
      if (streamSocketRef.current?.readyState === WebSocket.OPEN) {
        streamSocketRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
    setStreamStatus('Connecting...');
  }

  async function loadAnalytics() {
    if (!token) {
      setStatus('Log in to view analytics');
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/analytics`, { headers: authHeaders(token) });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || 'Analytics unavailable');
        return;
      }
      setAnalytics(data);
      setStatus('Analytics refreshed');
    } catch {
      setStatus('Analytics request failed');
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.shell} keyboardShouldPersistTaps="handled">
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>Native Mobile Frontend</Text>
          <Text style={styles.title}>Universal Translator</Text>
          <Text style={styles.subtitle}>Use your phone microphone with the existing FastAPI AI backend.</Text>
          <Text style={styles.status}>{status}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>Backend</Text>
          <TextInput style={styles.input} value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" autoCorrect={false} />
          <Text style={styles.help}>On a real phone, use your computer LAN IP, for example http://192.168.1.25:8000.</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>User Session</Text>
          <TextInput style={styles.input} value={username} onChangeText={setUsername} placeholder="Username" placeholderTextColor="#718096" />
          <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder="Password" placeholderTextColor="#718096" secureTextEntry />
          <TextInput style={styles.input} value={sessionId} onChangeText={updateSession} placeholder="Shared session ID" placeholderTextColor="#718096" autoCapitalize="none" />
          <View style={styles.row}>
            <TouchableOpacity style={styles.button} onPress={login}><Text style={styles.buttonText}>Log In</Text></TouchableOpacity>
            <TouchableOpacity style={styles.secondaryButton} onPress={logout}><Text style={styles.buttonText}>Log Out</Text></TouchableOpacity>
          </View>
          <Text style={styles.help}>{signedIn ? 'JWT active' : 'Not signed in'}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>Languages</Text>
          <View style={styles.row}>
            <TextInput style={styles.smallInput} value={sourceLanguage} onChangeText={setSourceLanguage} autoCapitalize="none" />
            <TextInput style={styles.smallInput} value={targetLanguage} onChangeText={setTargetLanguage} autoCapitalize="none" />
          </View>
          <Text style={styles.help}>Available: {Object.entries(languages).slice(0, 8).map(([code, name]) => `${code} ${name}`).join(', ')}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>Live Conversation</Text>
          <View style={styles.segmented}>
            <TouchableOpacity style={activeSpeaker === 'A' ? styles.segmentActive : styles.segment} onPress={() => setActiveSpeaker('A')}>
              <Text style={styles.segmentText}>Speaker A</Text>
            </TouchableOpacity>
            <TouchableOpacity style={activeSpeaker === 'B' ? styles.segmentActive : styles.segment} onPress={() => setActiveSpeaker('B')}>
              <Text style={styles.segmentText}>Speaker B</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={recording ? styles.micButtonRecording : styles.micButton} onPress={recording ? stopRecording : startRecording}>
            <Text style={styles.micIcon}>{recording ? '■' : '🎙️'}</Text>
            <Text style={styles.micText}>{recording ? 'Stop & Translate' : `Hold Space for ${activeSpeaker}`}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={streamSocket ? styles.dangerButton : styles.secondaryButton} onPress={toggleStreamConnection}>
            <Text style={styles.buttonText}>{streamSocket ? 'Disconnect Stream' : 'Connect Stream'}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={streamingAudio ? styles.dangerButton : styles.playButton} onPress={streamingAudio ? stopStreamingAudio : startStreamingAudio}>
            <Text style={styles.buttonText}>{streamingAudio ? 'Stop Streaming Audio' : 'Start Streaming Audio'}</Text>
          </TouchableOpacity>
          <Text style={styles.help}>Stream: {streamStatus}</Text>
          <Text style={styles.help}>Latency: {latencyStatus}</Text>
          <Text style={styles.help}>Chunks sent: {audioChunksSent} ({Math.round(audioBytesSent / 1024)} KB)</Text>
          <Text style={styles.help}>Tap once to record. Tap again to stop and translate.</Text>
        </View>

        <View style={styles.translationBox}>
          <Text style={styles.heading}>Live Translation</Text>
          <Text style={styles.speakerBadge}>Current speaker: {activeSpeaker}</Text>
          <Text style={styles.resultLabel}>Source</Text>
          <Text style={styles.resultText}>{result?.source_text || '-'}</Text>
          <Text style={styles.resultLabel}>Translated</Text>
          <Text style={styles.translationText}>{result?.translated_text || 'Translation will appear here.'}</Text>
          <Text style={styles.help}>Partial: {partialTranslation || '-'}</Text>
          <Text style={styles.help}>Emotion: {ttsStyle?.emotion || '-'}</Text>
          <Text style={styles.help}>Intent: {ttsStyle?.intent || '-'} | Urgency: {ttsStyle?.urgency || '-'}</Text>
          <Text style={styles.help}>Style: {ttsStyle?.style ? `${ttsStyle.style.tone}, ${ttsStyle.style.speed}x` : '-'}</Text>
          <TouchableOpacity style={styles.playButton} onPress={playLastRecording}>
            <Text style={styles.buttonText}>Play Last Recording</Text>
          </TouchableOpacity>
          <Text style={styles.help}>Playback: {playbackStatus}</Text>
          <Text style={styles.help}>TTS: {ttsPlaybackStatus}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>Analytics</Text>
          <TouchableOpacity style={styles.secondaryButton} onPress={loadAnalytics}><Text style={styles.buttonText}>Refresh Analytics</Text></TouchableOpacity>
          <Text style={styles.resultText}>GPU active: {analytics?.gpu_queue?.active ?? '-'}</Text>
          <Text style={styles.resultText}>GPU queued: {analytics?.gpu_queue?.queued ?? '-'}</Text>
          <Text style={styles.resultText}>Rejected: {analytics?.gpu_queue?.rejected ?? '-'}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#07111f' },
  shell: { padding: 18, gap: 16 },
  hero: { padding: 22, borderRadius: 24, backgroundColor: '#10213a', gap: 8 },
  eyebrow: { color: '#60a5fa', fontSize: 12, fontWeight: '800', letterSpacing: 2, textTransform: 'uppercase' },
  title: { color: '#e5ecff', fontSize: 36, fontWeight: '900' },
  subtitle: { color: '#b6c4dc', fontSize: 16, lineHeight: 23 },
  status: { alignSelf: 'flex-start', marginTop: 8, backgroundColor: '#0ea5e9', color: '#ffffff', borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8, fontWeight: '800' },
  card: { padding: 18, borderRadius: 22, backgroundColor: '#0c1729', borderWidth: 1, borderColor: '#24344f', gap: 12 },
  translationBox: { padding: 20, borderRadius: 26, backgroundColor: '#081527', borderWidth: 1, borderColor: '#2563eb', gap: 12 },
  heading: { color: '#e5ecff', fontSize: 22, fontWeight: '900' },
  input: { minHeight: 52, borderRadius: 16, borderWidth: 1, borderColor: '#334155', color: '#e5ecff', backgroundColor: '#081527', paddingHorizontal: 14, fontSize: 16 },
  smallInput: { flex: 1, minHeight: 52, borderRadius: 16, borderWidth: 1, borderColor: '#334155', color: '#e5ecff', backgroundColor: '#081527', paddingHorizontal: 14, fontSize: 16 },
  row: { flexDirection: 'row', gap: 12 },
  button: { flex: 1, minHeight: 54, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: '#2563eb', paddingHorizontal: 16 },
  secondaryButton: { flex: 1, minHeight: 54, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: '#475569', paddingHorizontal: 16 },
  dangerButton: { flex: 1, minHeight: 54, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: '#dc2626', paddingHorizontal: 16 },
  segmented: { flexDirection: 'row', padding: 4, borderRadius: 999, backgroundColor: '#081527', borderWidth: 1, borderColor: '#24344f' },
  segment: { flex: 1, minHeight: 46, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  segmentActive: { flex: 1, minHeight: 46, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: '#2563eb' },
  segmentText: { color: '#ffffff', fontWeight: '900' },
  micButton: { minHeight: 168, borderRadius: 32, alignItems: 'center', justifyContent: 'center', backgroundColor: '#2563eb', gap: 10 },
  micButtonRecording: { minHeight: 168, borderRadius: 32, alignItems: 'center', justifyContent: 'center', backgroundColor: '#dc2626', gap: 10 },
  micIcon: { color: '#ffffff', fontSize: 42, fontWeight: '900' },
  micText: { color: '#ffffff', fontSize: 20, fontWeight: '900' },
  speakerBadge: { alignSelf: 'flex-start', color: '#bfdbfe', backgroundColor: '#1e3a8a', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, fontWeight: '900' },
  translationText: { minHeight: 96, borderRadius: 18, backgroundColor: '#0c1729', color: '#e5ecff', fontSize: 24, lineHeight: 32, fontWeight: '800', padding: 16 },
  playButton: { minHeight: 54, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: '#16a34a', paddingHorizontal: 16 },
  buttonText: { color: '#ffffff', fontWeight: '900', fontSize: 15 },
  help: { color: '#93a4bd', lineHeight: 20 },
  resultLabel: { color: '#60a5fa', fontWeight: '900', textTransform: 'uppercase', fontSize: 12 },
  resultText: { color: '#e5ecff', lineHeight: 22 },
});
