import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Mic, Radio, Square, Languages } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const WS_URL = API_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
const INITIAL_TOKEN = localStorage.getItem('translator_token') || '';
const INITIAL_SESSION_ID = localStorage.getItem('translator_session_id') || crypto.randomUUID();
const STREAM_PACKET_MS = Number(import.meta.env.VITE_STREAM_PACKET_MS || 250);
localStorage.setItem('translator_session_id', INITIAL_SESSION_ID);
registerServiceWorker();

function withAuthToken(url, token) {
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

function authHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

function App() {
  const [languages, setLanguages] = useState({ en: 'English', es: 'Spanish' });
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguage, setTargetLanguage] = useState('es');
  const [text, setText] = useState('Hello, how are you?');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const [micPermission, setMicPermission] = useState('unknown');
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
      setMicPermission('granted');
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
      setResult(await response.json());
      setStatus('Text translated');
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
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    setMicPermission('granted');
    chunksRef.current = [];
    recordingStoppedRef.current = false;
    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
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
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    if (blob.size === 0) {
      setProcessing(false);
      setStatus('No audio captured');
      return;
    }
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');
    formData.append('source_language', sourceLanguage);
    formData.append('target_language', targetLanguage);
    formData.append('synthesize_audio', 'true');

    try {
      const response = await fetch(`${API_URL}/translate/audio`, { method: 'POST', headers: authHeaders(authToken), body: formData });
      const data = await response.json();
      setResult(data);
      setStatus(data.audio_output_path ? 'Playing...' : 'Audio translated');
      if (data.audio_output_path) {
        setPlaying(true);
        window.setTimeout(() => {
          setPlaying(false);
          setStatus('Audio translated');
        }, 900);
      }
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

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    setMicPermission('granted');
    const socket = new WebSocket(withAuthToken(`${WS_URL}/ws/audio`, authToken));
    socketRef.current = socket;
    socket.binaryType = 'arraybuffer';
    socket.onopen = () => {
      setStreaming(true);
      setPartialTranscript('');
      setLiveTranslation('');
      setPipelineStage('Listening');
      setStatus('Streaming audio...');
      socket.send(JSON.stringify({ type: 'start', session_id: sessionId, source_language: sourceLanguage, target_language: targetLanguage }));
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
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
    };
    socket.onclose = () => {
      setStreaming(false);
      if (processing) setStatus('Stream disconnected. Try reconnecting.');
      stream.getTracks().forEach((track) => track.stop());
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

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    setMicPermission('granted');
    const socket = new WebSocket(withAuthToken(`${WS_URL}/ws/audio`, authToken));
    const source = speaker === 'A' ? sourceLanguage : targetLanguage;
    const target = speaker === 'A' ? targetLanguage : sourceLanguage;
    refs.manualClose = false;
    refs.shouldReconnect = true;
    refs.socket = socket;
    socket.binaryType = 'arraybuffer';

    socket.onopen = () => {
      updateDuplexSpeaker(speaker, { active: true, transcript: '', translation: '', stage: 'Listening' });
      socket.send(JSON.stringify({ type: 'start', session_id: sessionId, speaker, source_language: source, target_language: target }));
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
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

  return (
    <main className="shell">
      <section className="card hero">
        <div>
          <p className="eyebrow">Self-hosted AI translation</p>
          <h1>Universal Translator</h1>
          <p>Record your voice, translate text, and synthesize speech locally with Whisper, MarianMT, and Piper.</p>
        </div>
        <div className="status-stack">
          <div className={`status ${connectionStatus}`}>Backend {connectionStatus}</div>
          <div className={`status mic-${micPermission}`}>Mic {micPermission}</div>
          <div className="status">PWA {pwaInstalled ? 'installed' : 'ready'}</div>
          <div className="status">{status}</div>
        </div>
      </section>

      <section className="card install-card">
        <div>
          <p className="eyebrow">Phase 1 PWA</p>
          <h2>Install mobile web app</h2>
          <p>Add Live Translator to your home screen for a fullscreen mobile app experience without app store approval.</p>
        </div>
        <div className="actions">
          <button disabled={!installPrompt || pwaInstalled} onClick={installApp}>{pwaInstalled ? 'Installed' : 'Install App'}</button>
        </div>
      </section>

      {showOnboarding && (
        <section className="card onboarding">
          <div>
            <p className="eyebrow">Welcome</p>
            <h2>Set up your interpreter in three steps</h2>
            <ol>
              <li><strong>Connect:</strong> make sure the backend indicator is online.</li>
              <li><strong>Allow mic:</strong> grant microphone permission before starting.</li>
              <li><strong>Choose languages:</strong> set who speaks first and who hears the translation.</li>
            </ol>
          </div>
          <div className="onboarding-actions">
            <button onClick={requestMicPermission}>Allow Microphone</button>
            <button onClick={() => setShowOnboarding(false)}>Continue</button>
          </div>
        </section>
      )}

      <section className="card language-picker">
        <div>
          <p className="eyebrow">Languages</p>
          <h2>Choose conversation direction</h2>
        </div>
        <div className="controls">
          <label>Speaker / Source<select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>{Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label>
          <label>Listener / Target<select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label>
        </div>
      </section>

      <section className="card auth">
        <h2>User Session</h2>
        <div className="controls">
          <label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          <label>Shared session ID<input value={sessionId} onChange={(event) => updateSessionId(event.target.value)} /></label>
          <label>Connected devices<input readOnly value={Object.keys(sharedSession?.devices || {}).length || 0} /></label>
        </div>
        <div className="actions">
          <button onClick={login}>Log In</button>
          <button onClick={logout}>Log Out</button>
        </div>
        <p><strong>Session:</strong> {authToken ? 'Active' : 'Not signed in'} - share `{sessionId}` with another device to join the same conversation.</p>
      </section>

      <section className="card settings">
        <h2>Conversation Settings</h2>
        <div className="controls">
          <label>Accessibility profile<select value={accessibilityMode} onChange={(event) => setAccessibilityMode(event.target.value)}><option value="balanced">Balanced</option><option value="noise">Noisy room</option><option value="accent">Strong accent</option><option value="slow">Slower conversation</option></select></label>
          <label>Speech playback speed<select value={speechSpeed} onChange={(event) => setSpeechSpeed(event.target.value)}><option value="slow">Slow</option><option value="normal">Normal</option><option value="fast">Fast</option></select></label>
          <label>Mobile bandwidth<select value={lowBandwidthMode ? 'low' : 'normal'} onChange={(event) => setLowBandwidthMode(event.target.value === 'low')}><option value="normal">Normal</option><option value="low">Low bandwidth</option></select></label>
          <label>Mobile audio<button onClick={unlockMobileAudio}>{mobileAudioUnlocked ? 'Audio Ready' : 'Unlock Audio'}</button></label>
        </div>
        <p><strong>Tip:</strong> {accessibilityMode === 'noise' ? 'Use headphones and move closer to the speaker.' : accessibilityMode === 'accent' ? 'Let the speaker finish full phrases before interrupting.' : accessibilityMode === 'slow' ? 'Pause longer between turns for cleaner interpretation.' : 'Use a quiet space and speak in complete phrases.'}</p>
        <p><strong>Multi-device:</strong> Open this same frontend on two devices and assign one device to Speaker A and one to Speaker B.</p>
      </section>

      <section className="card workspace">
        <textarea value={text} onChange={(event) => setText(event.target.value)} />
        <div className="actions">
          <button disabled={processing || recording} onClick={translateText}><Languages size={18} /> Translate Text</button>
          <button disabled={processing} className={recording ? 'danger' : ''} onClick={recording ? stopRecording : startRecording}>{recording ? <Square size={18} /> : <Mic size={18} />} {recording ? 'Stop Recording' : 'Record Mic'}</button>
          <button disabled={processing || recording} className={streaming ? 'danger' : ''} onClick={toggleStreaming}><Radio size={18} /> {streaming ? 'Finalize Stream' : 'Stream Audio'}</button>
        </div>
        <div className="indicators">
          <span className={recording ? 'active' : ''}>Listening</span>
          <span className={processing ? 'active' : ''}>Processing</span>
          <span className={playing ? 'active' : ''}>Playing</span>
        </div>
        <div className="live">
          <p><strong>Pipeline:</strong> {pipelineStage}</p>
          <p><strong>Partial transcription:</strong> {partialTranscript || '-'}</p>
          <p><strong>Live translation:</strong> {liveTranslation || '-'}</p>
        </div>
      </section>

      <section className="card result">
        <h2>Result</h2>
        <p><strong>Source:</strong> {result?.source_text || '-'}</p>
        <p><strong>Translated:</strong> {result?.translated_text || '-'}</p>
        <p><strong>Audio:</strong> {result?.audio_output_path || '-'}</p>
        <h3>Shared Session History</h3>
        {(sharedSession?.history || []).slice(-5).map((turn, index) => (
          <p key={`${turn.created_at}-${index}`}><strong>{turn.speaker}:</strong> {turn.source_text} =&gt; {turn.translated_text}</p>
        ))}
      </section>

      <section className="card analytics">
        <h2>Analytics Dashboard</h2>
        <div className="actions">
          <button onClick={loadAnalytics}>Refresh Analytics</button>
        </div>
        <div className="duplex-grid">
          <div>
            <h3>GPU Queue</h3>
            <p><strong>Active:</strong> {analytics?.gpu_queue?.active ?? '-'}</p>
            <p><strong>Queued:</strong> {analytics?.gpu_queue?.queued ?? '-'}</p>
            <p><strong>Rejected:</strong> {analytics?.gpu_queue?.rejected ?? '-'}</p>
            <p><strong>Avg wait:</strong> {analytics?.gpu_queue?.avg_wait_seconds ?? '-'}s</p>
          </div>
          <div>
            <h3>Latency and Errors</h3>
            <p><strong>Errors:</strong> {analytics?.observability?.counters?.translation_failures_total ?? '-'}</p>
            <p><strong>Disconnects:</strong> {analytics?.observability?.counters?.websocket_disconnects_total ?? '-'}</p>
            <p><strong>Text avg:</strong> {analytics?.observability?.latency_seconds?.text_translation?.avg ?? '-'}s</p>
            <p><strong>Audio avg:</strong> {analytics?.observability?.latency_seconds?.audio_translation?.avg ?? '-'}s</p>
          </div>
        </div>
        <h3>Usage / Billing</h3>
        {Object.entries(analytics?.billing_usage || {}).map(([user, usage]) => (
          <p key={user}><strong>{user}:</strong> {usage.text_translations} text, {usage.audio_translations} audio, {usage.streaming_segments} streams, {usage.audio_minutes} audio minutes, {usage.errors} errors</p>
        ))}
      </section>

      <section className="card duplex">
        <h2>Full Duplex Conversation</h2>
        <p><strong>Session:</strong> {sessionId}</p>
        <p><strong>Conversation Brain:</strong> {conversationBrain}</p>
        <p><strong>Semantic Layer:</strong> intent {semanticContext.last_intent}, mood {semanticContext.conversation_mood}, topics {semanticContext.topics.join(', ') || '-'}</p>
        <div className="duplex-grid">
          <div>
            <h3>Speaker A -&gt; Speaker B</h3>
            <button className={duplex.A.active ? 'danger' : ''} onClick={() => toggleDuplexSpeaker('A')}>{duplex.A.active ? 'Finalize A' : 'Start A Mic'}</button>
            <p><strong>Stage:</strong> {duplex.A.stage}</p>
            <p><strong>A said:</strong> {duplex.A.transcript || '-'}</p>
            <p><strong>To B:</strong> {duplex.A.translation || '-'}</p>
          </div>
          <div>
            <h3>Speaker B -&gt; Speaker A</h3>
            <button className={duplex.B.active ? 'danger' : ''} onClick={() => toggleDuplexSpeaker('B')}>{duplex.B.active ? 'Finalize B' : 'Start B Mic'}</button>
            <p><strong>Stage:</strong> {duplex.B.stage}</p>
            <p><strong>B said:</strong> {duplex.B.transcript || '-'}</p>
            <p><strong>To A:</strong> {duplex.B.translation || '-'}</p>
          </div>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);

