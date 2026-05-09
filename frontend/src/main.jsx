import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowLeftRight, Download, Mic, Square } from 'lucide-react';
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
  return 'https://universal-translator-phone-production.up.railway.app';
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
const INITIAL_DEVICE_ID = localStorage.getItem('translator_device_id') || crypto.randomUUID();
const INITIAL_SPEAKER_NAME = localStorage.getItem('translator_speaker_name') || '';
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 80);
const STREAM_AUDIO_BITRATE = Number(import.meta.env.VITE_STREAM_AUDIO_BITRATE || 32000);
const HEALTH_POLL_MS = 3000;
const STREAM_HEARTBEAT_MS = 2500;
const STREAM_HEARTBEAT_MAX_MISSES = 2;
const STREAM_RECONNECT_MS = 1000;
const STREAM_RECONNECT_MAX_ATTEMPTS = 5;
const MAX_AUDIO_SEND_QUEUE = 10;
const MAX_BUFFERED_AUDIO_CHUNKS = 30;
const HOLD_TO_TALK_DELAY_MS = 260;
const MIN_STREAM_CAPTURE_MS = Number(import.meta.env.VITE_MIN_STREAM_CAPTURE_MS || 1800);
localStorage.setItem('translator_session_id', INITIAL_SESSION_ID);
localStorage.setItem('translator_device_id', INITIAL_DEVICE_ID);
registerServiceWorker();

function fallbackSpeakerLabel(speaker) {
  const value = String(speaker || '').trim();
  if (!value || value === '-') return 'Person';
  const numericId = value.match(/(\d+)$/)?.[1];
  if (numericId) return `Person ${numericId}`;
  return value.replace(/^speaker[-_\s]*/i, 'Person ').trim() || 'Person';
}

function isManualInstallBrowser() {
  const userAgent = navigator.userAgent || '';
  const isIos = /iphone|ipad|ipod/i.test(userAgent);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg/i.test(userAgent);
  return isIos || isSafari;
}

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
  if (!window.MediaRecorder) {
    window.alert?.('Recording not supported on this device/browser');
    throw new Error('Recording not supported on this device/browser');
  }
  const options = {};
  if (MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus')) {
    options.mimeType = 'audio/webm;codecs=opus';
  } else if (MediaRecorder.isTypeSupported?.('audio/mp4')) {
    options.mimeType = 'audio/mp4';
  }
  return new MediaRecorder(stream, options);
}

function logAudioStream(stream) {
  console.log('AUDIO STREAM:', stream);
  console.log('AUDIO TRACKS:', stream.getAudioTracks());
  stream.getAudioTracks().forEach((track) => {
    console.log('TRACK ENABLED:', track.enabled);
    console.log('TRACK STATE:', track.readyState);
  });
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
  const [instantListening, setInstantListening] = useState(false);
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
  const [audioReplayAvailable, setAudioReplayAvailable] = useState(false);
  const [interpreterMode, setInterpreterMode] = useState(false);
  const [speakerMode, setSpeakerMode] = useState('auto');
  const [detectedSpeaker, setDetectedSpeaker] = useState('-');
  const [latencyStats, setLatencyStats] = useState({ mic_to_backend: '-', backend_response: '-', first_audio: '-' });
  const [authToken, setAuthToken] = useState(INITIAL_TOKEN);
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const [sessionId, setSessionId] = useState(INITIAL_SESSION_ID);
  const [sharedSession, setSharedSession] = useState(null);
  const [conversationTurns, setConversationTurns] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState('checking');
  const [wsDebug, setWsDebug] = useState({ url: WS_AUDIO_URL, close: '-', error: '-' });
  const [selfTest, setSelfTest] = useState({
    status: 'idle',
    translation: '-',
    websocket: '-',
    message: 'Not run yet',
  });
  const [installPrompt, setInstallPrompt] = useState(null);
  const [pwaInstalled, setPwaInstalled] = useState(() => window.matchMedia?.('(display-mode: standalone)').matches || window.navigator?.standalone === true);
  const mediaRecorderRef = useRef(null);
  const streamRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);
  const duplexRefs = useRef({ A: {}, B: {} });
  const speakerLabelsRef = useRef({});
  const recordingStoppedRef = useRef(false);
  const streamFinalizePendingRef = useRef(false);
  const streamFinalizeTimerRef = useRef(null);
  const streamStartedAtRef = useRef(0);
  const streamRecordingStartedAtRef = useRef(0);
  const firstAudioSeenRef = useRef(false);
  const streamHeartbeatRef = useRef({ timer: null, missed: 0 });
  const streamReconnectRef = useRef({ enabled: false, options: null, attempts: 0 });
  const holdToTalkTimerRef = useRef(null);
  const holdToTalkActiveRef = useRef(false);
  const holdToTalkReleasePendingRef = useRef(false);
  const ignoreNextMicClickRef = useRef(false);
  const ttsQueueRef = useRef([]);
  const lastTtsItemRef = useRef(null);
  const ttsPlayingRef = useRef(false);
  const audioSendQueueRef = useRef([]);
  const wakeLockRef = useRef(null);
  const audioContextRef = useRef(null);
  const streamSafetyTimeoutRef = useRef(null);

  function haptic(pattern = 12) {
    window.navigator?.vibrate?.(pattern);
  }

  async function ensureAudioContext() {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return null;
    if (!audioContextRef.current) audioContextRef.current = new AudioContextCtor();
    if (audioContextRef.current.state === 'suspended') await audioContextRef.current.resume?.();
    return audioContextRef.current;
  }

  async function requestWakeLock() {
    try {
      wakeLockRef.current = await navigator.wakeLock?.request?.('screen') || null;
    } catch {
      wakeLockRef.current = null;
    }
  }

  async function releaseWakeLock() {
    try {
      await wakeLockRef.current?.release?.();
    } catch {
    } finally {
      wakeLockRef.current = null;
    }
  }

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
    let cancelled = false;
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_URL}/health`, { cache: 'no-store' });
        if (!response.ok) throw new Error('Backend health check failed');
        if (!cancelled) setConnectionStatus('online');
      } catch {
        if (!cancelled) setConnectionStatus('offline');
      }
    };

    checkHealth();
    const timer = window.setInterval(checkHealth, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    loadDiagnostics();
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && (streaming || instantListening) && !wakeLockRef.current) {
        requestWakeLock();
      }
      if (document.visibilityState === 'hidden' && socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [streaming, instantListening]);

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
      window.location.href = '/install.html';
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

  async function unlockMobileAudio() {
    const context = await ensureAudioContext();
    if (context) {
      const buffer = context.createBuffer(1, 1, 22050);
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      source.start(0);
    }
    const audio = new Audio();
    audio.muted = true;
    audio.play().catch(() => {});
    setMobileAudioUnlocked(true);
    setStatus('Mobile audio unlocked');
  }

  async function playSpeakerTestSound() {
    try {
      const context = await ensureAudioContext();
      if (!context) {
        setStatus('Speaker test unavailable in this browser');
        return;
      }
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.28);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(context.currentTime);
      oscillator.stop(context.currentTime + 0.3);
      setMobileAudioUnlocked(true);
      setPipelineStage('Speaker test played');
      setStatus('Speaker test played');
    } catch (error) {
      setPipelineStage(`Speaker blocked: ${error?.name || 'tap again'}`);
      setStatus('Speaker blocked. Check mute switch and volume.');
    }
  }

  async function playServerVoiceTest() {
    try {
      await unlockMobileAudio();
      setPipelineStage('Loading test voice');
      setStatus('Loading test voice...');
      const response = await fetch(`${API_URL}/debug/tts-sample.wav?ts=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Voice test unavailable'));
      const buffer = await response.arrayBuffer();
      const url = URL.createObjectURL(new Blob([buffer], { type: response.headers.get('content-type') || 'audio/wav' }));
      const item = { url, buffer, mimeType: 'audio/wav' };
      if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
      lastTtsItemRef.current = item;
      setAudioReplayAvailable(true);
      playTtsItem(item, { revokeOnFinish: false, manual: true });
    } catch (error) {
      setPipelineStage('Voice test failed');
      setStatus(error.message || 'Voice test failed');
    }
  }

  async function testMicrophoneAndPlayback() {
    try {
      await unlockMobileAudio();
      setPipelineStage('Testing microphone');
      setStatus('Tap to record, then playback...');
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.preload = 'auto';
        audio.playsInline = true;
        audio.muted = false;
        audio.volume = 1;
        audio.onended = () => URL.revokeObjectURL(url);
        audio.onerror = () => {
          setPipelineStage('Mic playback failed');
          setStatus('Mic playback failed');
        };
        audio.play().then(() => {
          setPipelineStage('Mic test played');
          setStatus('Mic test: recording played back');
        }).catch((error) => {
          setPipelineStage('Mic playback blocked');
          setStatus('Mic playback blocked: ' + (error?.name || 'unknown'));
        });
      };
      
      mediaRecorder.start();
      setPipelineStage('Recording...');
      setStatus('Recording 1 second...');
      
      setTimeout(() => {
        mediaRecorder.stop();
      }, 1000);
    } catch (error) {
      setPipelineStage('Mic test failed');
      setStatus(error.message || 'Microphone unavailable');
    }
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

  async function ensureAuthToken() {
    if (authToken) return authToken;
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'demo', password: 'demo' }),
    });
    if (!response.ok) {
      const message = await responseErrorMessage(response, 'Auto-login failed');
      console.log('AUTH: auto-login failed, continuing anonymously', message);
      return '';
    }
    const data = await response.json();
    localStorage.setItem('translator_token', data.access_token);
    setAuthToken(data.access_token);
    return data.access_token;
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

  function rememberSpeaker(data = {}) {
    const speakerId = data.speaker || '';
    const label = data.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    if (label && label !== 'Person') setDetectedSpeaker(label);
    return label;
  }

  function normalizeConversationTurn(turn, index = 0) {
    const speakerId = turn.speaker || '';
    const label = turn.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    return {
      id: `${turn.created_at || Date.now()}-${speakerId || index}-${index}`,
      speaker: speakerId,
      speaker_label: label,
      source_text: turn.source_text || '',
      translated_text: turn.translated_text || '',
      created_at: turn.created_at || Date.now() / 1000,
    };
  }

  function appendConversationTurn(turn) {
    const normalized = normalizeConversationTurn(turn);
    setConversationTurns((current) => {
      const nextKey = `${normalized.speaker}-${normalized.created_at}-${normalized.source_text}`;
      const withoutDuplicate = current.filter((item) => `${item.speaker}-${item.created_at}-${item.source_text}` !== nextKey);
      return [...withoutDuplicate, normalized].slice(-6);
    });
  }

  function updateLatency(metric, ms) {
    setLatencyStats((current) => ({ ...current, [metric]: `${ms}ms` }));
  }

  function resetStreamState() {
    if (streamSafetyTimeoutRef.current) {
      window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = null;
    }
    if (streamFinalizeTimerRef.current) {
      window.clearTimeout(streamFinalizeTimerRef.current);
      streamFinalizeTimerRef.current = null;
    }
    setRecording(false);
    setStreaming(false);
    setInstantListening(false);
    setProcessing(false);
    setPlaying(false);
    setInterpreterMode(false);
    ttsPlayingRef.current = false;
    streamFinalizePendingRef.current = false;
    streamRecordingStartedAtRef.current = 0;
    holdToTalkReleasePendingRef.current = false;
  }

  function activePacketMs() {
    if (lowBandwidthMode) return 500;
    return Math.min(STREAM_PACKET_MS, 100);
  }

  function sendAudioPacket(socket, packet) {
    if (socket.readyState !== WebSocket.OPEN) return false;
    try {
      console.log('sending audio chunk', packet.meta.bytes, packet.meta.mime_type);
      socket.send(JSON.stringify(packet.meta));
      socket.send(packet.buffer);
      return true;
    } catch {
      return false;
    }
  }

  function queueAudioPacket(packet) {
    const queue = audioSendQueueRef.current;
    if (queue.length >= MAX_BUFFERED_AUDIO_CHUNKS) queue.shift();
    queue.push(packet);
  }

  function flushAudioSendQueue(socket) {
    const queue = audioSendQueueRef.current;
    while (queue.length > 0 && socket.readyState === WebSocket.OPEN) {
      const packet = queue[0];
      if (!sendAudioPacket(socket, packet)) break;
      queue.shift();
    }
  }

  async function sendRecorderChunk(socket, event, recorder) {
    if (event.data.size <= 0) return;
    console.log('AUDIO CHUNK:', event.data);
    if (audioSendQueueRef.current.length >= MAX_AUDIO_SEND_QUEUE && socket.readyState === WebSocket.OPEN) {
      audioSendQueueRef.current.shift();
    }
    const buffer = await event.data.arrayBuffer();
    const packet = {
      meta: {
        type: 'chunk_meta',
        sent_at_ms: Date.now(),
        captured_at_ms: performance.now(),
        bytes: buffer.byteLength,
        mime_type: recorder?.mimeType || event.data.type || preferredAudioMimeType(),
      },
      buffer,
    };
    if (!sendAudioPacket(socket, packet)) queueAudioPacket(packet);
  }

  function stopTracks(stream) {
    stream?.getTracks().forEach((track) => track.stop());
  }

  function clearStreamHeartbeat() {
    if (streamHeartbeatRef.current?.timer) {
      window.clearInterval(streamHeartbeatRef.current.timer);
    }
    streamHeartbeatRef.current = { timer: null, missed: 0 };
  }

  function markStreamPong() {
    streamHeartbeatRef.current.missed = 0;
    setConnectionStatus('online');
  }

  function startStreamHeartbeat(socket) {
    clearStreamHeartbeat();
    streamHeartbeatRef.current = { timer: null, missed: 0 };
    const timer = window.setInterval(() => {
      if (socketRef.current !== socket) {
        clearStreamHeartbeat();
        return;
      }
      if (socket.readyState !== WebSocket.OPEN) return;
      streamHeartbeatRef.current.missed += 1;
      if (streamHeartbeatRef.current.missed > STREAM_HEARTBEAT_MAX_MISSES) {
        setPipelineStage('Connection heartbeat missed');
        setStatus('Reconnecting stream...');
        socket.close();
        return;
      }
      socket.send(JSON.stringify({ type: 'ping' }));
    }, STREAM_HEARTBEAT_MS);
    streamHeartbeatRef.current.timer = timer;
  }

  function disableStreamReconnect() {
    streamReconnectRef.current = { ...streamReconnectRef.current, enabled: false };
  }

  function finalizeCurrentStream(nextStatus = 'Processing stream...', options = {}) {
    if (!socketRef.current) return false;
    if (socketRef.current.readyState !== WebSocket.OPEN && !streamRecorderRef.current) return false;
    const recorder = streamRecorderRef.current;
    if (options.delay !== false && recorder?.state === 'recording' && streamRecordingStartedAtRef.current) {
      const remainingMs = MIN_STREAM_CAPTURE_MS - (performance.now() - streamRecordingStartedAtRef.current);
      if (remainingMs > 0) {
        if (!streamFinalizeTimerRef.current) {
          setPipelineStage('Keep speaking');
          setStatus('Keep speaking for a moment...');
          streamFinalizeTimerRef.current = window.setTimeout(() => {
            streamFinalizeTimerRef.current = null;
            finalizeCurrentStream(nextStatus, { delay: false });
          }, remainingMs);
        }
        return true;
      }
    }
    if (streamFinalizeTimerRef.current) {
      window.clearTimeout(streamFinalizeTimerRef.current);
      streamFinalizeTimerRef.current = null;
    }
    disableStreamReconnect();
    clearStreamHeartbeat();
    streamFinalizePendingRef.current = true;
    if (recorder?.state === 'recording') {
      recorder.requestData?.();
      recorder.stop();
    } else if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'finalize' }));
    }
    setStreaming(false);
    setInstantListening(false);
    setProcessing(true);
    releaseWakeLock();
    setPipelineStage('Processing');
    setStatus(nextStatus);
    return true;
  }

  function handleMicClick() {
    console.log('MIC BUTTON CLICKED');
    if (ignoreNextMicClickRef.current) {
      ignoreNextMicClickRef.current = false;
      return;
    }
    haptic(socketRef.current ? 8 : 14);
    setInstantListening(!socketRef.current);
    toggleStreaming({ interpreter: true, speakerMode: 'auto' });
  }

  function handleMicPointerDown(event) {
    console.log('MIC BUTTON CLICKED');
    if (socketRef.current || processing || playing) return;
    haptic(8);
    setInstantListening(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    holdToTalkTimerRef.current = window.setTimeout(() => {
      holdToTalkActiveRef.current = true;
      holdToTalkReleasePendingRef.current = false;
      ignoreNextMicClickRef.current = true;
      toggleStreaming({ interpreter: true, speakerMode: 'auto', holdToTalk: true });
    }, HOLD_TO_TALK_DELAY_MS);
  }

  function handleMicPointerUp() {
    if (holdToTalkTimerRef.current) {
      window.clearTimeout(holdToTalkTimerRef.current);
      holdToTalkTimerRef.current = null;
    }
    if (!holdToTalkActiveRef.current) {
      setInstantListening(false);
      return;
    }
    haptic([8, 24, 8]);
    holdToTalkActiveRef.current = false;
    ignoreNextMicClickRef.current = true;
    if (!finalizeCurrentStream('Processing speech...')) {
      holdToTalkReleasePendingRef.current = true;
    }
  }

  function downloadPwaInstaller() {
    const appUrl = window.location.origin;
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Install Universal Translator</title></head><body style="font-family:system-ui;margin:24px;line-height:1.5"><h1>Install Universal Translator</h1><p>Open <a href="${appUrl}">${appUrl}</a>, then use your browser's Add to Home Screen or Install app option.</p><p><a href="${appUrl}">Open app now</a></p></body></html>`;
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'universal-translator-install.html';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus('Installer file downloaded');
  }

  function applySharedSession(session) {
    if (!session) return;
    setSharedSession(session);
    Object.values(session.speakers || {}).forEach((profile) => {
      if (profile?.speaker) {
        speakerLabelsRef.current = {
          ...speakerLabelsRef.current,
          [profile.speaker]: profile.speaker_label || fallbackSpeakerLabel(profile.speaker),
        };
      }
    });
    if (session.history?.length) {
      setConversationTurns(session.history.map((turn, index) => normalizeConversationTurn(turn, index)).slice(-6));
    }
    const latest = session.history?.[session.history.length - 1];
    if (latest) {
      const latestLabel = latest.speaker_label || speakerLabelsRef.current[latest.speaker] || fallbackSpeakerLabel(latest.speaker);
      setResult({
        source_text: latest.source_text,
        translated_text: latest.translated_text,
        audio_output_path: null,
      });
      setDetectedSpeaker(latestLabel);
      updateDuplexSpeaker(latest.speaker || 'A', {
        transcript: latest.source_text,
        translation: latest.translated_text,
        speaker_label: latestLabel,
        stage: 'Synced from shared session',
      });
    }
  }

  async function startRecording() {
    if (recording || processing) return;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('MIC STREAM ACTIVE:', stream);
      logAudioStream(stream);
    } catch (error) {
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    setMicPermission('available');
    chunksRef.current = [];
    recordingStoppedRef.current = false;
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      setStatus(error.message || 'Recording not supported');
      return;
    }
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      console.log('MOBILE AUDIO SIZE:', event.data.size);
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

  async function toggleStreaming(options = {}) {
    if (socketRef.current) {
      finalizeCurrentStream();
      return;
    }

    const reconnecting = options.reconnect === true;
    const cleanOptions = { ...options };
    delete cleanOptions.reconnect;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      logAudioStream(stream);
    } catch (error) {
      disableStreamReconnect();
      setMicPermission('denied');
      setStatus(mediaErrorMessage(error));
      return;
    }
    const selectedSpeakerMode = cleanOptions.speakerMode || speakerMode;
    setMicPermission('available');
    await unlockMobileAudio();
    requestWakeLock();
    setInterpreterMode(Boolean(cleanOptions.interpreter || selectedSpeakerMode === 'auto'));
    setDetectedSpeaker('-');
    setLatencyStats({ mic_to_backend: '-', backend_response: '-', first_audio: '-' });
    firstAudioSeenRef.current = false;
    streamStartedAtRef.current = performance.now();
    streamReconnectRef.current = {
      enabled: true,
      options: {
        ...cleanOptions,
        interpreter: Boolean(cleanOptions.interpreter || selectedSpeakerMode === 'auto'),
        speakerMode: selectedSpeakerMode,
      },
      attempts: reconnecting ? streamReconnectRef.current.attempts : 0,
    };
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      disableStreamReconnect();
      resetStreamState();
      setStatus(error.message || 'Recording not supported');
      setPipelineStage('Recording unsupported');
      return;
    }
    const activeAuthToken = await ensureAuthToken();
    const socketUrl = withAuthToken(WS_AUDIO_URL, activeAuthToken);
    setWsDebug({ url: WS_AUDIO_URL, close: 'connecting', error: '-' });
    const socket = new WebSocket(socketUrl);
    socketRef.current = socket;
    socket.binaryType = 'arraybuffer';
    recorder.ondataavailable = async (event) => {
      await sendRecorderChunk(socket, event, recorder);
    };
    recorder.onstop = () => {
      if (streamFinalizePendingRef.current && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'finalize' }));
      }
      stopTracks(stream);
    };
    socket.onopen = () => {
      if (streamSafetyTimeoutRef.current) window.clearTimeout(streamSafetyTimeoutRef.current);
      streamSafetyTimeoutRef.current = window.setTimeout(() => {
        resetStreamState();
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) socket.close();
        if (socketRef.current === socket) socketRef.current = null;
        setStatus('Ready to try again');
        setPipelineStage('Safety reset');
      }, 15000);
      streamFinalizePendingRef.current = false;
      setConnectionStatus('online');
      setStreaming(true);
      setInstantListening(false);
      setResult(null);
      setPartialTranscript('');
      setLiveTranslation('');
      setPipelineStage('Listening');
      setStatus(selectedSpeakerMode === 'auto' ? 'Interpreter mode listening...' : 'Streaming audio...');
      socket.send(JSON.stringify({
        type: 'start',
        session_id: sessionId,
        device_id: INITIAL_DEVICE_ID,
        speaker_name: INITIAL_SPEAKER_NAME,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        speaker_mode: selectedSpeakerMode,
        speaker: selectedSpeakerMode === 'auto' ? 'auto' : 'A',
        mime_type: recorder.mimeType || preferredAudioMimeType(),
      }));
      flushAudioSendQueue(socket);
      startStreamHeartbeat(socket);
      streamRecorderRef.current = recorder;
      console.log('STEP 9: starting recorder');
      recorder.start(activePacketMs());
      streamRecordingStartedAtRef.current = performance.now();
      console.log('STEP 10: recorder started, state=', recorder.state);
      if (cleanOptions.holdToTalk && holdToTalkReleasePendingRef.current) {
        holdToTalkReleasePendingRef.current = false;
        finalizeCurrentStream('Processing speech...');
      }
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WS MESSAGE:', event.data);
      if (data.type === 'pong') {
        markStreamPong();
        return;
      }
      if (data.type === 'session_restored' || data.type === 'session_sync') applySharedSession(data.session?.shared || data.session);
      if (data.type === 'speaker_detected') {
        const label = rememberSpeaker(data);
        setPipelineStage(`${label} detected`);
      }
      if (data.type === 'latency') {
        updateLatency(data.metric, data.ms);
      }
      if (data.type === 'stage') {
        setPipelineStage(data.message);
        setStatus(data.message);
      }
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        const playback = data.playback_owner_label || data.playback_owner;
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${playback ? ` - playback: ${playback}` : ''}`);
      }
      if (data.type === 'partial_transcription') {
        rememberSpeaker(data);
        setPartialTranscript(data.text);
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        setLiveTranslation(data.text);
        setPipelineStage('Live translation');
      }
      if (data.type === 'final_transcription') {
        rememberSpeaker(data);
        setPartialTranscript(data.text);
        setPipelineStage('Transcription ready');
      }
      if (data.type === 'live_translation') {
        rememberSpeaker(data);
        setLiveTranslation(data.text);
        setPipelineStage('Translation ready');
      }
      if (data.type === 'tts_start') {
        setPlaying(true);
        setPipelineStage(`Streaming voice: 0/${data.chunks}`);
      }
      if (data.type === 'tts_audio_chunk') {
        if (!firstAudioSeenRef.current) {
          firstAudioSeenRef.current = true;
          updateLatency('first_audio', Math.round(performance.now() - streamStartedAtRef.current));
        }
        setPipelineStage(`Streaming voice: ${data.index}/${data.total}`);
        enqueueTtsChunk(data.audio_base64, data.mime_type);
      }
      if (data.type === 'tts_end') {
        setPipelineStage('Voice stream complete');
      }
      if (data.type === 'error') {
        console.log('WS ERROR MESSAGE:', data);
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        resetStreamState();
        setPipelineStage('Hold and speak longer');
        setStatus(data.message || 'Stream failed');
        streamFinalizePendingRef.current = false;
        holdToTalkReleasePendingRef.current = false;
        if (streamRecorderRef.current?.state === 'recording') streamRecorderRef.current.stop();
        else stopTracks(stream);
        socket.close();
        socketRef.current = null;
      }
      if (data.type === 'vad' && data.speech_detected) setStatus('Streaming audio... speech detected');
      if (data.type === 'final') {
        disableStreamReconnect();
        clearStreamHeartbeat();
        audioSendQueueRef.current = [];
        rememberSpeaker(data);
        setResult(data);
        if (data.session) {
          applySharedSession(data.session);
        } else {
          appendConversationTurn(data);
        }
        setProcessing(false);
        setPipelineStage('Complete');
        setStatus('Stream translated');
        if (streamRecorderRef.current?.state === 'recording') {
          streamFinalizePendingRef.current = false;
          streamRecorderRef.current.stop();
        }
        socket.close();
        socketRef.current = null;
      }
    };
    socket.onerror = (event) => {
      setWsDebug((current) => ({ ...current, error: 'socket error' }));
      setStatus('Stream connection error');
      setPipelineStage('Connection error');
      resetStreamState();
    };
    socket.onclose = (event) => {
      setWsDebug((current) => ({
        ...current,
        close: `${event.code || 'no-code'} ${event.reason || 'no-reason'} clean:${event.wasClean ? 1 : 0}`,
      }));
      clearStreamHeartbeat();
      resetStreamState();
      streamFinalizePendingRef.current = false;
      holdToTalkReleasePendingRef.current = false;
      if (streamRecorderRef.current === recorder) {
        if (streamRecorderRef.current.state === 'recording') {
          streamRecorderRef.current.stop();
        } else {
          stopTracks(stream);
        }
        streamRecorderRef.current = null;
      } else {
        stopTracks(stream);
      }
      if (socketRef.current === socket) socketRef.current = null;
      if (!streamReconnectRef.current.enabled) return;

      if (streamReconnectRef.current.attempts >= STREAM_RECONNECT_MAX_ATTEMPTS) {
        disableStreamReconnect();
        audioSendQueueRef.current = [];
        releaseWakeLock();
        setStatus('Connection lost. Tap to restart.');
        setPipelineStage('Connection lost');
        setConnectionStatus('offline');
        return;
      }

      streamReconnectRef.current.attempts += 1;
      setStatus('Reconnecting stream...');
      setPipelineStage(`Reconnecting ${streamReconnectRef.current.attempts}/${STREAM_RECONNECT_MAX_ATTEMPTS}`);
      window.setTimeout(() => {
        if (!streamReconnectRef.current.enabled || socketRef.current) return;
        toggleStreaming({ ...(streamReconnectRef.current.options || {}), reconnect: true });
      }, STREAM_RECONNECT_MS);
    };
  }

  function enqueueTtsChunk(audioBase64, mimeType) {
    if (lowBandwidthMode) {
      setPipelineStage('Low-bandwidth mode: text translation only');
      return;
    }
    ensureAudioContext().catch(() => {});
    const binary = atob(audioBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const url = URL.createObjectURL(new Blob([buffer], { type: mimeType || 'audio/wav' }));
    const item = { url, buffer, mimeType: mimeType || 'audio/wav' };
    if (lastTtsItemRef.current?.url) URL.revokeObjectURL(lastTtsItemRef.current.url);
    lastTtsItemRef.current = item;
    setAudioReplayAvailable(true);
    ttsQueueRef.current.push(item);
    playNextTtsChunk();
  }

  function playTtsItem(item, { revokeOnFinish = true, manual = false } = {}) {
    if (!item) return;
    ttsPlayingRef.current = true;
    setPlaying(true);
    setPipelineStage(manual ? 'Playing translation voice' : 'Playing voice');
    setStatus(manual ? 'Playing translation voice...' : 'Playing voice...');
    haptic(6);
    const finish = () => {
      if (revokeOnFinish) URL.revokeObjectURL(item.url);
      ttsPlayingRef.current = false;
      if (manual) {
        setPlaying(false);
        setPipelineStage('Voice played');
        setStatus('Voice played');
        return;
      }
      playNextTtsChunk();
    };
    const playWithHtmlAudio = () => {
      const audio = new Audio(item.url);
      audio.preload = 'auto';
      audio.playsInline = true;
      audio.muted = false;
      audio.volume = 1;
      audio.onended = finish;
      audio.onerror = finish;
      audio.play().catch((error) => {
        ttsPlayingRef.current = false;
        setPlaying(false);
        setAudioReplayAvailable(true);
        setPipelineStage(`Audio playback blocked: ${error?.name || 'tap play voice'}`);
        setStatus('Tap Play Voice to hear translation');
      });
    };
    ensureAudioContext()
      .then((context) => {
        if (!context || context.state !== 'running') {
          playWithHtmlAudio();
          return;
        }
        return context.decodeAudioData(item.buffer.slice(0))
          .then((audioBuffer) => {
            const source = context.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(context.destination);
            source.onended = finish;
            source.start(0);
          })
          .catch(playWithHtmlAudio);
      })
      .catch(playWithHtmlAudio);
  }

  async function playTranslationAudio() {
    await unlockMobileAudio();
    playTtsItem(lastTtsItemRef.current, { revokeOnFinish: false, manual: true });
  }

  function playNextTtsChunk() {
    if (ttsPlayingRef.current || ttsQueueRef.current.length === 0) {
      if (ttsQueueRef.current.length === 0) {
        setPlaying(false);
        setPipelineStage('Ready to listen');
        setStatus('Ready to listen');
      }
      return;
    }

    const item = ttsQueueRef.current.shift();
    playTtsItem(item, { revokeOnFinish: false });
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
      refs.finalizePending = true;
      if (refs.recorder?.state === 'recording') {
        refs.recorder.requestData?.();
        refs.recorder.stop();
      } else if (refs.socket.readyState === WebSocket.OPEN) {
        refs.socket.send(JSON.stringify({ type: 'finalize' }));
      }
      updateDuplexSpeaker(speaker, { active: false, stage: 'Processing...' });
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('MIC STREAM ACTIVE:', stream);
      logAudioStream(stream);
    } catch (error) {
      setMicPermission('denied');
      updateDuplexSpeaker(speaker, { active: false, stage: mediaErrorMessage(error) });
      return;
    }
    setMicPermission('available');
    const activeAuthToken = await ensureAuthToken();
    const socket = new WebSocket(withAuthToken(WS_AUDIO_URL, activeAuthToken));
    const source = speaker === 'A' ? sourceLanguage : targetLanguage;
    const target = speaker === 'A' ? targetLanguage : sourceLanguage;
    refs.manualClose = false;
    refs.shouldReconnect = true;
    refs.finalizePending = false;
    refs.socket = socket;
    socket.binaryType = 'arraybuffer';
    let recorder;
    try {
      recorder = createAudioRecorder(stream);
    } catch (error) {
      stopTracks(stream);
      updateDuplexSpeaker(speaker, { active: false, stage: error.message || 'Recording not supported' });
      return;
    }
    refs.recorder = recorder;
    recorder.ondataavailable = async (event) => {
      console.log('MOBILE AUDIO SIZE:', event.data.size);
      await sendRecorderChunk(socket, event, recorder);
    };
    recorder.onstop = () => {
      if (refs.finalizePending && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'finalize' }));
      }
      stopTracks(stream);
    };

    socket.onopen = () => {
      updateDuplexSpeaker(speaker, { active: true, transcript: '', translation: '', stage: 'Listening' });
      socket.send(JSON.stringify({
        type: 'start',
        session_id: sessionId,
        device_id: `${INITIAL_DEVICE_ID}-${speaker}`,
        speaker,
        speaker_label: `Speaker ${speaker}`,
        speaker_mode: 'manual',
        source_language: source,
        target_language: target,
        mime_type: recorder.mimeType || preferredAudioMimeType(),
      }));
      recorder.start(activePacketMs());
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'session_restored') {
        applySharedSession(data.session?.shared);
        updateDuplexSpeaker(speaker, { stage: `Rebound session (${data.session.reconnects} reconnects)` });
      }
      if (data.type === 'session_sync') applySharedSession(data.session);
      if (data.type === 'speaker_detected') {
        const label = rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { speaker_label: label, stage: `${label} connected` });
      }
      if (data.type === 'stage') updateDuplexSpeaker(speaker, { stage: data.message });
      if (data.type === 'turn') {
        const label = rememberSpeaker(data);
        setConversationBrain(`${label}: ${data.reason}${data.behavior ? ` - ${data.behavior}` : ''}${data.playback_owner ? ` - playback: ${data.playback_owner}` : ''}`);
        if (!data.allowed && data.behavior === 'hold') {
          refs.recorder?.stop();
          refs.recorder?.stream.getTracks().forEach((track) => track.stop());
          socket.close();
          refs.socket = null;
          updateDuplexSpeaker(speaker, { active: false, stage: data.reason });
        }
      }
      if (data.type === 'final_transcription') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { transcript: data.text, stage: 'Transcription ready' });
      }
      if (data.type === 'semantic_context') {
        setSemanticContext({
          last_intent: data.last_intent,
          conversation_mood: data.conversation_mood,
          topics: data.topics || [],
        });
        updateDuplexSpeaker(speaker, { stage: `Intent: ${data.last_intent}, mood: ${data.conversation_mood}` });
      }
      if (data.type === 'live_translation') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Translation ready' });
      }
      if (data.type === 'partial_translation') {
        rememberSpeaker(data);
        updateDuplexSpeaker(speaker, { translation: data.text, stage: 'Live translation' });
      }
      if (data.type === 'tts_audio_chunk') enqueueTtsChunk(data.audio_base64, data.mime_type);
      if (data.type === 'error') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        updateDuplexSpeaker(speaker, { active: false, stage: data.message || 'Stream failed' });
        refs.finalizePending = false;
        if (refs.recorder?.state === 'recording') refs.recorder.stop();
        else stopTracks(stream);
        socket.close();
        refs.socket = null;
      }
      if (data.type === 'final') {
        refs.manualClose = true;
        refs.shouldReconnect = false;
        const label = rememberSpeaker(data);
        if (data.session) applySharedSession(data.session);
        updateDuplexSpeaker(speaker, {
          active: false,
          transcript: data.source_text,
          translation: data.translated_text,
          speaker_label: label,
          stage: 'Complete',
        });
        if (refs.recorder?.state === 'recording') {
          refs.finalizePending = false;
          refs.recorder.stop();
        }
        socket.close();
        refs.socket = null;
      }
    };

    socket.onerror = () => {
      updateDuplexSpeaker(speaker, { active: false, stage: 'Connection error' });
      setConversationBrain('WebSocket connection error');
      resetStreamState();
    };
    socket.onclose = () => {
      updateDuplexSpeaker(speaker, { active: false });
      refs.finalizePending = false;
      stopTracks(stream);
      refs.socket = null;
      resetStreamState();
      if (refs.shouldReconnect && !refs.manualClose) {
        updateDuplexSpeaker(speaker, { stage: 'Reconnecting...' });
        window.setTimeout(() => toggleDuplexSpeaker(speaker), 1500);
      }
    };
  }


  const sourceText = partialTranscript || result?.source_text || 'Ready to listen';
  const translatedText = liveTranslation || result?.translated_text || 'Translation appears here';
  const perceivedListening = streaming || instantListening;
  const micState = playing ? 'speaking' : perceivedListening ? 'listening' : processing ? 'processing' : 'idle';
  const micLabel = playing ? 'Speaking' : streaming ? 'Listening' : processing ? 'Processing' : 'Tap to Speak';
  const statusText = pipelineStage && pipelineStage !== 'Idle' ? pipelineStage : status;

  return (
    <main className="app-shell">
      <section className="phone-frame" data-connection={connectionStatus} data-smoke-check="Self Test">
        <header className="clean-header">
          <h1 className="app-title">
            <span className="brand-mark">Anai</span>
            <sub>nrldc</sub>
          </h1>
          <div className="connection-indicator" data-status={connectionStatus}>
            <span className="connection-dot" />
            <span className="connection-label">{connectionStatus}</span>
          </div>
        </header>

        <section className="mic-panel">
          <button
            className={`mic-orb ${micState} ${perceivedListening ? 'listening-pulse' : ''}`}
            onClick={handleMicClick}
            onPointerDown={handleMicPointerDown}
            onPointerUp={handleMicPointerUp}
            onPointerCancel={handleMicPointerUp}
            onContextMenu={(event) => event.preventDefault()}
            disabled={playing || (processing && !streaming)}
            aria-label={micLabel}
            aria-live="polite"
          >
            <span className="orb-ring" />
            <span className="orb-spin" />
            <span className="sr-only">{micLabel}</span>
            {streaming ? <Square size={46} /> : <Mic size={58} />}
          </button>
          <p className="mic-label">{micLabel}</p>
          <p className="status-line">{statusText}</p>
          <div className="sound-actions">
            <button className="play-voice-button" type="button" onClick={playSpeakerTestSound} disabled={playing}>
              Test Sound
            </button>
            <button className="play-voice-button" type="button" onClick={playServerVoiceTest} disabled={playing}>
              Test Voice
            </button>
            <button className="play-voice-button" type="button" onClick={testMicrophoneAndPlayback} disabled={playing}>
              Test Mic
            </button>
            {audioReplayAvailable && (
              <button className="play-voice-button" type="button" onClick={playTranslationAudio} disabled={playing}>
                Play Voice
              </button>
            )}
          </div>
          {processing && !streaming && !playing && <p className="thinking">Translating...</p>}
        </section>

        <section className="translation-stack">
          <article className="transcript-card">
            <p className="transcript-text fade-in" key={sourceText}>{sourceText}</p>
          </article>
          <article className="translation-card">
            <p className="translation-text fade-in" key={translatedText}>{translatedText}</p>
          </article>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
