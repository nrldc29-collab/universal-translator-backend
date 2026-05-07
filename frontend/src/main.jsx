import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Mic, Radio, Square, Languages } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';

function isLocalHost(hostname) {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)
  );
}

function isSameOriginBackendHost(hostname) {
  return (
    hostname.endsWith('.trycloudflare.com') ||
    hostname.endsWith('.up.railway.app') ||
    hostname.endsWith('.onrender.com') ||
    hostname.endsWith('.fly.dev')
  );
}

function defaultApiUrl() {
  if (isLocalHost(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  if (isSameOriginBackendHost(window.location.hostname)) {
    return window.location.origin;
  }
  return 'https://your-backend.up.railway.app';
}

function configuredUrl(value) {
  if (!value || value.includes('your-backend')) {
    return '';
  }
  return value;
}

const LOCAL_BACKEND = isLocalHost(window.location.hostname);
const SAME_ORIGIN_BACKEND = isSameOriginBackendHost(window.location.hostname);
const API_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? defaultApiUrl() : (configuredUrl(import.meta.env.VITE_API_URL) || defaultApiUrl())).replace(/\/+$/, '');
const WS_BASE_URL = (LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? API_URL : (configuredUrl(import.meta.env.VITE_WS_URL) || API_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:'))).replace(/\/+$/, '');
const WS_AUDIO_URL = LOCAL_BACKEND || SAME_ORIGIN_BACKEND ? `${WS_BASE_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')}/ws/audio` : (configuredUrl(import.meta.env.VITE_WS_AUDIO_URL) || `${WS_BASE_URL}/ws/audio`);
const INITIAL_TOKEN = localStorage.getItem('translator_token') || '';
const INITIAL_SESSION_ID = localStorage.getItem('translator_session_id') || crypto.randomUUID();
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 250);
localStorage.setItem('translator_session_id', INITIAL_SESSION_ID);
registerServiceWorker();

function preferredAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  return [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/aac',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ].find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

function createAudioRecorder(stream) {
  const mimeType = preferredAudioMimeType();
  return mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
}

function audioFileExtension(mimeType) {
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return '.m4a';
  if (mimeType.includes('ogg')) return '.ogg';
  return '.webm';
}

function withAuthToken(url, token) {
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

function authHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

async function responseErrorMessage(response, fallback) {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const body = await response.json();
      return body.detail || body.message || fallback;
    }
    const text = await response.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

function mediaErrorMessage(error) {
  if (error?.name === 'NotAllowedError') return 'Microphone permission blocked';
  if (error?.name === 'NotFoundError') return 'No microphone found';
  if (error?.name === 'NotSupportedError') return 'Audio recording is not supported in this browser';
  return 'Could not start microphone';
}

function App() {
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish' });
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguage, setTargetLanguage] = useState('es');
  const [text, setText] = useState('Hello, how are you?');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const [micPermission, setMicPermission] = useState('checking');
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [partialTranscript, setPartialTranscript] = useState('');
  const [liveTranslation, setLiveTranslation] = useState('');
  const [pipelineStage, setPipelineStage] = useState('Idle');
  const [duplex, setDuplex] = useState({
    A: { active: false, transcript: '', translation: '', stage: 'Idle' },
    B: { active: false, transcript: '', translation: '', stage: 'Idle' },
  });
  const [conversationBrain, setConversationBrain] = useState('Idle');
  const [semanticContext, setSemanticContext] = useState({ last_intent: 'statement', conversation_mood: 'neutral', topics: [] });
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [accessibilityMode, setAccessibilityMode] = useState('balanced');
  const [speechSpeed, setSpeechSpeed] = useState('normal');
  const [lowBandwidthMode, setLowBandwidthMode] = useState(false);
  const [mobileAudioUnlocked, setMobileAudioUnlocked] = useState(false);
  const [authToken, setAuthToken] = useState(INITIAL_TOKEN);
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const [sessionId, setSessionId] = useState(INITIAL_SESSION_ID);
  const [sharedSession, setSharedSession] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState('checking');
  const [selfTest, setSelfTest] = useState({
    status: 'idle',
    translation: '-',
    websocket: '-',
    message: 'Not run yet',
  });
  const [installPrompt, setInstallPrompt] = useState(null);
  const [pwaInstalled, setPwaInstalled] = useState(window.matchMedia?.('(display-mode: standalone)').matches || false);
  const mediaRecorderRef = useRef(null);
  const streamRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);
  const duplexRefs = useRef({ A: {}, B: {} });
  const recordingStoppedRef = useRef(false);
  const ttsQueueRef = useRef([]);
  const ttsPlayingRef = useRef(false);

  useEffect(() => {
    fetch(`${API_URL}/languages`)
      .then((response) => response.json())
      .then((data) => {
        setLanguages(data.languages || languages);
        setConnectionStatus('online');
      })
      .catch(() => {
        setStatus('Backend offline');
        setConnectionStatus('offline');
      });
  }, []);

  useEffect(() => {
    loadDiagnostics();
  }, []);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission('unavailable');
      return;
    }

    setMicPermission('available');
    navigator.permissions?.query?.({ name: 'microphone' })
      .then((permission) => {
        setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        permission.onchange = () => {
          setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        };
      })
      .catch(() => setMicPermission('available'));
  }, []);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    const handleInstalled = () => {
      setPwaInstalled(true);
      setInstallPrompt(null);
      setStatus('App installed');
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  async function installApp() {
    if (!installPrompt) {
      setStatus('Install prompt is not available yet');
      return;
    }
    installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    setInstallPrompt(null);
    setStatus(choice.outcome === 'accepted' ? 'Installing app' : 'Install dismissed');
  }

  async function requestMicPermission() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission('available');
      setStatus('Microphone ready');
    } catch {
      setMicPermission('denied');
      setStatus('Microphone permission blocked');
    }
  }

  function unlockMobileAudio() {
    const audio = new Audio();
    audio.muted = true;
    audio.play().catch(() => {});
    setMobileAudioUnlocked(true);
    setStatus('Mobile audio unlocked');
  }

  async function translateText() {
    if (processing || !text.trim()) return;
    setProcessing(true);
    setStatus('Translating text...');
    try {
      const response = await fetch(`${API_URL}/translate/text`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text, source_language: sourceLanguage, target_language: targetLanguage, synthesize_audio: false }),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Text translation failed'));
      const data = await response.json();
      setResult(data);
      setStatus('Text translated');
    } catch (error) {
      setStatus(error.message || 'Text translation failed');
    } finally {
      setProcessing(false);
    }
  }

  async function login() {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      setStatus('Login failed');
      return;
    }
    const data = await response.json();
    localStorage.setItem('translator_token', data.access_token);
    setAuthToken(data.access_token);
    setStatus(`Logged in as ${username}`);
  }

  async function loadAnalytics() {
    if (!authToken) {
      setStatus('Log in to view analytics');
      return;
    }
    const response = await fetch(`${API_URL}/analytics`, { headers: authHeaders(authToken) });
    if (!response.ok) {
      setStatus('Analytics unavailable');
      return;
    }
    setAnalytics(await response.json());
    setStatus('Analytics refreshed');
  }

  async function loadDiagnostics() {
    setDiagnosticsStatus('checking');
    try {
      const response = await fetch(`${API_URL}/diagnostics`);
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Diagnostics unavailable'));
      const data = await response.json();
      setDiagnostics(data);
      setDiagnosticsStatus(data.ready ? 'online' : 'checking');
    } catch {
      setDiagnosticsStatus('offline');
    }
  }

  function testAudioSocket() {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, authToken));
      const timeout = window.setTimeout(() => {
        socket.close();
        reject(new Error('Audio socket timed out'));
      }, 6000);

      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'ping' }));
      };
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type !== 'pong') return;
        window.clearTimeout(timeout);
        socket.close();
        resolve('pong');
      };
      socket.onerror = () => {
        window.clearTimeout(timeout);
        reject(new Error('Audio socket failed'));
      };
    });
  }

  async function runSelfTest() {
    setSelfTest({ status: 'running', translation: 'checking', websocket: 'checking', message: 'Running checks...' });
    setStatus('Running self test...');

    const next = {
      status: 'online',
      translation: '-',
      websocket: '-',
      message: 'Self-test passed',
    };
    const failures = [];

    try {
      const response = await fetch(`${API_URL}/translate/text`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text: 'hello world', source_language: 'en', target_language: 'es', synthesize_audio: false }),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Translation test failed'));
      const data = await response.json();
      if (!data.translated_text?.trim()) throw new Error('Translation returned empty text');
      next.translation = data.translated_text;
    } catch (error) {
      next.translation = 'failed';
      failures.push(error.message || 'Translation test failed');
    }

    try {
      next.websocket = await testAudioSocket();
    } catch (error) {
      next.websocket = 'failed';
      failures.push(error.message || 'Audio socket test failed');
    }

    if (failures.length) {
      next.status = 'offline';
      next.message = failures.join(' / ');
      setStatus('Self-test failed');
    } else {
      setStatus('Self-test passed');
    }

    setSelfTest(next);
  }

  function logout() {
    localStorage.removeItem('translator_token');
    setAuthToken('');
    setStatus('Logged out');
  }

  function updateSessionId(value) {
    setSessionId(value);
    localStorage.setItem('translator_session_id', value);
  }

  function applySharedSession(session) {
    if (!session) return;
    setSharedSession(session);
    const latest = session.history?.[session.history.length - 1];
    if (latest) {
      setResult({
        source_text: latest.source_text,
        translated_text: latest.translated_text,
        audio_output_path: null,
      });
      updateDuplexSpeaker(latest.speaker || 'A', {
        transcript: latest.source_text,
        translation: latest.translated_text,
        stage: 'Synced from shared session',
      });
    }
  }

  async function startRecording() {
    if (recording || processing) return;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    setMicPermission('available');
    chunksRef.current = [];
    recordingStoppedRef.current = false;
    const recorder = createAudioRecorder(stream);
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = uploadRecording;
    recorder.start(250);
    setRecording(true);
    setStatus('Listening...');
  }

  function stopRecording() {
    if (recordingStoppedRef.current) return;
    recordingStoppedRef.current = true;
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current?.stream.getTracks().forEach((track) => track.stop());
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

    try {
      const response = await fetch(`${API_URL}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Audio translation failed'));
      const data = await response.json();
      setResult(data);
      setStatus(data.translated_text ? (data.audio_output_path ? 'Playing...' : 'Audio translated') : 'No clear speech recognized');
      if (data.audio_output_path) {
        setPlaying(true);
        window.setTimeout(() => {
          setPlaying(false);
          setStatus('Audio translated');
        }, 900);
      }
    } catch (error) {
      setStatus(error.message || 'Audio translation failed');
    } finally {
      setProcessing(false);
    }
  }

  async function toggleStreaming() {
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ type: 'finalize' }));
      streamRecorderRef.current?.stop();
      streamRecorderRef.current?.stream.getTracks().forEach((track) => track.stop());
      setStreaming(false);
      setProcessing(true);
      setStatus('Processing stream...');
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    setMicPermission('available');
    const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, authToken));
    socketRef.current = socket;
    socket.binaryType = 'arraybuffer';
    socket.onopen = () => {
      setStreaming(true);
      setPartialTranscript('');
      setLiveTranslation('');
      setPipelineStage('Listening');
      setStatus('Streaming audio...');
      socket.send(JSON.stringify({ type: 'start', session_id: sessionId, source_language: sourceLanguage, target_language: targetLanguage }));
      const recorder = createAudioRecorder(stream);
      streamRecorderRef.current = recorder;
      recorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
          socket.send(await event.data.arrayBuffer());
        }
      };
      recorder.start(lowBandwidthMode ? 750 : STREAM_PACKET_MS);
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'session_restored' || data.type === 'session_sync') applySharedSession(data.session?.shared || data.session);
      if (data.type === 'stage') {
        setPipelineStage(data.message);
        setStatus(data.message);
      }
      if (data.type === 'partial_transcription') setPartialTranscript(data.text);
      if (data.type === 'final_transcription') {
        setPartialTranscript(data.text);
        setPipelineStage('Transcription ready');
      }
      if (data.type === 'live_translation') {
        setLiveTranslation(data.text);
        setPipelineStage('Translation ready');
      }
      if (data.type === 'tts_start') {
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
      }
      if (data.type === 'tts_audio_chunk') {
        setPipelineStage(`Streaming voice: ${data.index}/${data.total}`);
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'tts_end') {
        setPipelineStage('Voice stream complete');
      }
      if (data.type === 'error') {
        setProcessing(false);
        setPipelineStage('Needs audio');
        setStatus(data.message || 'Stream failed');
        streamRecorderRef.current?.stop();
        stream.getTracks().forEach((track) => track.stop());
        socket.close();
        socketRef.current = null;
      }
      if (data.type === 'vad' && data.speech_detected) setStatus('Streaming audio... speech detected');
      if (data.type === 'final') {
        setResult(data);
        setProcessing(false);
        setPipelineStage('Complete');
        setStatus('Stream translated');
        socket.close();
        socketRef.current = null;
      }
    };
    socket.onerror = () => {
      setStatus('Stream connection error');
      setPipelineStage('Connection error');
      setProcessing(false);
    };
    socket.onclose = () => {
      setStreaming(false);
      setProcessing(false);
      stream.getTracks().forEach((track) => track.stop());
      if (socketRef.current === socket) socketRef.current = null;
    };
  }

  function enqueueTtsChunk(audioBase64, mimeType) {
    if (lowBandwidthMode) {
      setPipelineStage('Low-bandwidth mode: text translation only');
      return;
    }
    const binary = atob(audioBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: mimeType || 'audio/wav' }));
    ttsQueueRef.current.push(url);
    playNextTtsChunk();
  }

  function playNextTtsChunk() {
    if (ttsPlayingRef.current || ttsQueueRef.current.length === 0) {
      if (ttsQueueRef.current.length === 0) setPlaying(false);
      return;
    }

    ttsPlayingRef.current = true;
    setPlaying(true);
    const url = ttsQueueRef.current.shift();
    const audio = new Audio(url);
    audio.onended = () => {
      URL.revokeObjectURL(url);
      ttsPlayingRef.current = false;
      playNextTtsChunk();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      ttsPlayingRef.current = false;
      playNextTtsChunk();
    };
    audio.play().catch(() => {
      ttsPlayingRef.current = false;
      setPipelineStage('Click page once to allow audio playback');
    });
  }

  function updateDuplexSpeaker(speaker, patch) {
    setDuplex((current) => ({
      ...current,
      [speaker]: { ...current[speaker], ...patch },
    }));
  }

  async function toggleDuplexSpeaker(speaker) {
    const refs = duplexRefs.current[speaker];
    if (refs.socket) {
      refs.manualClose = true;
      refs.shouldReconnect = false;
      refs.socket.send(JSON.stringify({ type: 'finalize' }));
      refs.recorder?.stop();
      refs.recorder?.stream.getTracks().forEach((track) => track.stop());
      updateDuplexSpeaker(speaker, { active: false, stage: 'Processing...' });
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      setMicPermission('denied');
      updateDuplexSpeaker(speaker, { active: false, stage: mediaErrorMessage(error) });
      return;
    }
    setMicPermission('available');
    const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, authToken));
    const source = speaker === 'A' ? sourceLanguage : targetLanguage;
    const target = speaker === 'A' ? targetLanguage : sourceLanguage;
    refs.manualClose = false;
    refs.shouldReconnect = true;
    refs.socket = socket;
    socket.binaryType = 'arraybuffer';

    socket.onopen = () => {
      updateDuplexSpeaker(speaker, { active: true, transcript: '', translation: '', stage: 'Listening' });
      socket.send(JSON.stringify({ type: 'start', session_id: sessionId, speaker, source_language: source, target_language: target }));
      const recorder = createAudioRecorder(stream);
      refs.recorder = recorder;
      recorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
          socket.send(await event.data.arrayBuffer());
        }
      };
      recorder.start(lowBandwidthMode ? 750 : STREAM_PACKET_MS);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'session_restored') {
        applySharedSession(data.session?.shared);
        updateDuplexSpeaker(speaker, { stage: `Rebound session (${data.session.reconnects} reconnects)` });
      }
      if (data.type === 'session_sync') applySharedSession(data.session);
      if (data.type === 'stage') updateDuplexSpeaker(speaker, { stage: data.message });
      if (data.type === 'turn') {
        setConversationBrain(`${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${data.playback_owner ? ` - playback: ${data.playback_owner}` : ''}`);
        if (!data.allowed && data.behavior === 'hold') {
          refs.recorder?.stop();
          refs.recorder?.stream.getTracks().forEach((track) => track.stop());
          socket.close();
          refs.socket = null;
          updateDuplexSpeaker(speaker, { active: false, stage: data.reason });
        }
      }
      if (data.type === 'final_transcription') updateDuplexSpeaker(speaker, { transcript: data.text, stage: 'Transcription ready' });
      if (data.type === 'semantic_context') {
        setSemanticContext({
          last_intent: data.last_intent,
          conversation_mood: data.conversation_mood,
          topics: data.topics || [],
        });
        updateDuplexSpeaker(speaker, { stage: `Intent: ${data.last_intent}, mood: ${data.conversation_mood}` });
      }
      if (data.type === 'live_translation') updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Translation ready' });
      if (data.type === 'tts_audio_chunk') enqueueTtsChunk(data.audio_base64, data.mime_type);
      if (data.type === 'error') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        updateDuplexSpeaker(speaker, { active: false, stage: data.message || 'Stream failed' });
        refs.recorder?.stop();
        refs.recorder?.stream.getTracks().forEach((track) => track.stop());
        socket.close();
        refs.socket = null;
      }
      if (data.type === 'final') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          stage: 'Complete',
        });
        socket.close();
        refs.socket = null;
      }
    };

    socket.onerror = () => {
      updateDuplexSpeaker(speaker, { active: false, stage: 'Connection error' });
      setConversationBrain('WebSocket connection error');
    };
    socket.onclose = () => {
      updateDuplexSpeaker(speaker, { active: false });
      stream.getTracks().forEach((track) => track.stop());
      refs.socket = null;
      if (refs.shouldReconnect && !refs.manualClose) {
        updateDuplexSpeaker(speaker, { stage: 'Reconnecting...' });
        window.setTimeout(() => toggleDuplexSpeaker(speaker), 1500);
      }
    };
  }


  const sourceName = languages[sourceLanguage] || sourceLanguage.toUpperCase();
  const targetName = languages[targetLanguage] || targetLanguage.toUpperCase();
  const sourceText = partialTranscript || result?.source_text || text || 'Tap the mic and speak';
  const translatedText = liveTranslation || result?.translated_text || 'Your translation will appear here';
  const micState = streaming ? 'listening' : processing ? 'translating' : playing ? 'speaking' : 'idle';
  const connectionLabel = connectionStatus === 'online' ? 'Online' : connectionStatus === 'offline' ? 'Offline' : 'Connecting';

  return (
    <main className="app-shell">
      <section className="phone-frame">
        <header className="topbar">
          <div>
            <p className="brand-kicker">Universal Translator</p>
            <h1>Speak freely.</h1>
          </div>
          <div className={`status-pill ${connectionStatus}`}><span />{connectionLabel}</div>
        </header>

        {!authToken && (
          <section className="glass-card signin-card">
            <p className="label">Private session</p>
            <div className="signin-grid">
              <input aria-label="Username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" />
              <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" />
              <button onClick={login}>Log in</button>
            </div>
          </section>
        )}

        <section className="hero-panel">
          <div className="language-row">
            <select aria-label="Source language" value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>
              {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
            <button className="swap-button" onClick={() => { setSourceLanguage(targetLanguage); setTargetLanguage(sourceLanguage); }} aria-label="Swap languages">?</button>
            <select aria-label="Target language" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>
              {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </div>

          <button className={`mic-orb ${micState}`} onClick={toggleStreaming} disabled={processing && !streaming} aria-label={streaming ? 'Stop listening' : 'Start speaking'}>
            <span className="orb-ring" />
            {streaming ? <Square size={42} /> : <Mic size={52} />}
          </button>
          <p className="tap-label">{streaming ? 'Listening...' : processing ? 'Translating...' : playing ? 'Speaking...' : 'Tap to Speak'}</p>
          <p className="quiet-status">{status}</p>
        </section>

        <section className="translation-stack">
          <article className="glass-card transcript-card">
            <p className="label">You said</p>
            <p>{sourceText}</p>
          </article>
          <article className="glass-card translation-card">
            <p className="label">Translation</p>
            <p>{translatedText}</p>
          </article>
        </section>

        <section className="conversation-panel">
          <div className="conversation-header">
            <p className="label">Conversation</p>
            <button onClick={runSelfTest} disabled={selfTest.status === 'running'}>Self test</button>
          </div>
          <div className="speaker-grid">
            <button className={duplex.A.active ? 'speaker active' : 'speaker'} onClick={() => toggleDuplexSpeaker('A')}>
              <span>Speaker A</span>
              <strong>{sourceName}</strong>
            </button>
            <button className={duplex.B.active ? 'speaker active alt' : 'speaker alt'} onClick={() => toggleDuplexSpeaker('B')}>
              <span>Speaker B</span>
              <strong>{targetName}</strong>
            </button>
          </div>
          <div className="timeline">
            {(sharedSession?.history || []).slice(-4).map((turn, index) => (
              <div className="turn" key={`${turn.created_at}-${index}`}>
                <span>{turn.speaker || 'A'}</span>
                <p>{turn.source_text}</p>
                <strong>{turn.translated_text}</strong>
              </div>
            ))}
            {!(sharedSession?.history || []).length && <p className="empty-timeline">Live conversation appears here.</p>}
          </div>
        </section>

        <section className="settings-sheet">
          <details>
            <summary>Settings</summary>
            <div className="settings-grid">
              <label>Voice speed<select value={speechSpeed} onChange={(event) => setSpeechSpeed(event.target.value)}><option value="slow">Slow</option><option value="normal">Normal</option><option value="fast">Fast</option></select></label>
              <label>Audio quality<select value={lowBandwidthMode ? 'low' : 'normal'} onChange={(event) => setLowBandwidthMode(event.target.value === 'low')}><option value="normal">Normal</option><option value="low">Low bandwidth</option></select></label>
              <label>Accessibility<select value={accessibilityMode} onChange={(event) => setAccessibilityMode(event.target.value)}><option value="balanced">Balanced</option><option value="noise">Noisy room</option><option value="accent">Strong accent</option><option value="slow">Slower conversation</option></select></label>
              <button onClick={requestMicPermission}>Allow Microphone</button>
              <button onClick={unlockMobileAudio}>{mobileAudioUnlocked ? 'Audio Ready' : 'Unlock Audio'}</button>
              <button disabled={!installPrompt || pwaInstalled} onClick={installApp}>{pwaInstalled ? 'Installed' : 'Install App'}</button>
              {authToken && <button onClick={logout}>Log out</button>}
            </div>
          </details>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
