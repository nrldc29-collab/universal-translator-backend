/**
 * useAutoConversation -- production-grade fully automatic bidirectional translation.
 *
 * Fixes from audit:
 * - nextEndTime now tracked correctly in AudioPlayer
 * - liveText uses a ref (no stale closures)
 * - Separate ttsEndTimers per direction
 * - Sockets reopen when languages change
 * - Exponential backoff reconnect
 * - Real mic level via AnalyserNode
 * - Alternate recognition language per turn for better detection
 */
import { useRef, useState, useCallback, useEffect } from 'react';

import { BACKEND_TTS_LANGS, detectLanguagePair, speechRecognitionLanguage, languagePairNeedsBackendStt, createAudioRecorder, preferredAudioMimeType } from '../utils';

// ─── Language config ─────────────────────────────────────────────────────
const BROWSER_TTS_MAP = {
  en:'en-US', es:'es-MX', fr:'fr-FR', de:'de-DE', it:'it-IT',
  pt:'pt-BR', ru:'ru-RU', zh:'zh-CN', ja:'ja-JP', ko:'ko-KR',
  ar:'ar-SA', hi:'hi-IN', ht:'ht-HT', nl:'nl-NL',
};

// ─── Language detection ──────────────────────────────────────────────────
const detectLanguage = detectLanguagePair;

// ─── Browser TTS ─────────────────────────────────────────────────────────
function speakBrowser(text, lang, { onEnd } = {}) {
  if (!window.speechSynthesis || !text || lang === 'ht') { onEnd?.(); return () => {}; }
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = BROWSER_TTS_MAP[lang] || 'en-US';
  utt.rate = 1.02;
  const tryVoice = () => {
    const vv = window.speechSynthesis.getVoices();
    const v = vv.find(x => !x.localService && x.lang.startsWith(utt.lang.slice(0,2)))
           || vv.find(x => x.lang.startsWith(utt.lang.slice(0,2)));
    if (v) utt.voice = v;
  };
  tryVoice();
  const safety = setTimeout(() => onEnd?.(), Math.max(5000, text.length * 75));
  utt.onend = utt.onerror = () => { clearTimeout(safety); onEnd?.(); };
  window.speechSynthesis.speak(utt);
  return () => { clearTimeout(safety); window.speechSynthesis.cancel(); };
}

// ─── Seamless AudioContext player ─────────────────────────────────────────
function createAudioPlayer() {
  let ctx = null;
  let gainNode = null;
  let scheduledEndTime = 0; // tracks when last chunk ends

  function ensureCtx() {
    if (!ctx || ctx.state === 'closed') {
      ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 22050 });
      gainNode = ctx.createGain();
      gainNode.connect(ctx.destination);
      scheduledEndTime = 0;
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    return { ctx, gainNode };
  }

  async function playChunk(base64) {
    const { ctx: c, gainNode: gn } = ensureCtx();
    try {
      const bytes = atob(base64);
      const arr = new Uint8Array(bytes.length);
      for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
      const buffer = await c.decodeAudioData(arr.buffer.slice(0));
      const src = c.createBufferSource();
      src.buffer = buffer;
      src.connect(gn);
      const start = Math.max(c.currentTime + 0.02, scheduledEndTime);
      src.start(start);
      scheduledEndTime = start + buffer.duration;
      return buffer.duration;
    } catch { return 0; }
  }

  function remainingMs() {
    if (!ctx) return 0;
    return Math.max(0, (scheduledEndTime - ctx.currentTime) * 1000);
  }

  function reset() { scheduledEndTime = ctx ? ctx.currentTime : 0; }

  function close() {
    if (ctx && ctx.state !== 'closed') ctx.close().catch(() => {});
    ctx = null; gainNode = null; scheduledEndTime = 0;
  }

  // Analyser for mic level (attached separately)
  return { playChunk, remainingMs, reset, close };
}

// ─── Mic level analyser ───────────────────────────────────────────────────
function createMicAnalyser(stream) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    return {
      getLevel() {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const v of data) sum += Math.abs(v - 128);
        return Math.min(1, (sum / data.length) / 40);
      },
      close() { try { ctx.close(); } catch {} },
    };
  } catch {
    return { getLevel: () => 0, close: () => {} };
  }
}

// ─── WebSocket with exponential backoff ──────────────────────────────────
function createTranslationSocket(urlFn, srcLang, tgtLang, handlers, socketMeta = {}) {
  let ws = null;
  let ready = false;
  let queue = [];
  let retryCount = 0;
  let closed = false;
  let retryTimer = null;
  const {
    sessionId = 'default',
    deviceId = null,
    speaker = 'auto',
    speakerLabel = 'Auto',
  } = socketMeta;

  function buildStartPayload() {
    return {
      type: 'start',
      source_language: srcLang,
      target_language: tgtLang,
      session_id: sessionId,
      device_id: deviceId,
      speaker_mode: 'manual',
      speaker,
      speaker_label: speakerLabel,
    };
  }

  function buildLiveTextPayload(text, isFinal) {
    return {
      type: 'live_text',
      text,
      final: isFinal,
      session_id: sessionId,
      device_id: deviceId,
      source_language: srcLang,
      target_language: tgtLang,
      speaker,
      speaker_label: speakerLabel,
      speaker_mode: 'manual',
    };
  }

  function connect() {
    if (closed) return;
    ws = new WebSocket(urlFn());
    ws.onopen = () => {
      retryCount = 0;
    };
    ws.onmessage = ({ data }) => {
      try {
        const d = JSON.parse(data);
        if (d.type === 'ready') {
          ws.send(JSON.stringify(buildStartPayload()));
          ready = true;
          queue.splice(0).forEach((m) => ws.send(m));
          handlers.onReady?.();
          return;
        }
        if (d.type === 'error') {
          handlers.onError?.(d);
          if (d.warming) {
            closed = true;
            ws.close();
          }
          return;
        }
        if (d.type === 'live_translation') {
          handlers.onTranslation?.(d.text, Boolean(d.final), d);
        } else if (d.type === 'partial_translation') {
          handlers.onTranslation?.(d.text, false, d);
        } else if (d.type === 'final') {
          handlers.onFinal?.(d);
        }
        if (d.type === 'tts_audio_chunk' && d.audio_base64) handlers.onTtsChunk?.(d.audio_base64, d.mime_type, d);
        if (d.type === 'tts_end' && !d.partial) handlers.onTtsEnd?.(d);
      } catch {}
    };
    ws.onerror = () => { ready = false; handlers.onError?.({ message: 'WebSocket error' }); };
    ws.onclose = () => {
      ready = false;
      if (!closed) {
        const delay = Math.min(10000, 500 * Math.pow(2, retryCount++));
        retryTimer = setTimeout(connect, delay);
        handlers.onReconnecting?.(retryCount);
      }
    };
  }

  function send(text, isFinal = true) {
    const msg = JSON.stringify(buildLiveTextPayload(text, isFinal));
    if (ready && ws?.readyState === WebSocket.OPEN) ws.send(msg);
    else queue.push(msg);
  }

  function destroy() {
    closed = true;
    clearTimeout(retryTimer);
    ready = false;
    queue = [];
    if (ws) { ws.onclose = null; ws.close(); ws = null; }
  }

  connect();
  return { send, destroy };
}

// ─── Main hook ────────────────────────────────────────────────────────────
export function useAutoConversation({
  wsAudioUrl,
  authToken,
  sourceLanguage,
  targetLanguage,
  sessionId = 'default',
  deviceId = 'conversation',
  withAuthToken,
  backendReady = true,
  onStatus,
}) {
  const [active, setActive]       = useState(false);
  const [phase, setPhase]         = useState('idle'); // idle|listening|ready|processing|speaking
  const [detectedLang, setDetLang]= useState(null);
  const [liveText, setLiveText]   = useState('');
  const [liveTrans, setLiveTrans] = useState('');
  const [turns, setTurns]         = useState([]);
  const [sockStatus, setSockStat] = useState('disconnected'); // connected|reconnecting|disconnected
  const [micLevel, setMicLevel]   = useState(0);

  // Refs — all mutable state used inside callbacks
  const activeRef      = useRef(false);
  const phaseRef       = useRef('idle');
  const lockedRef      = useRef(false); // true while TTS playing
  const recogRef       = useRef(null);
  const sockABRef      = useRef(null);
  const sockBARef      = useRef(null);
  const playerRef      = useRef(null);
  const analyserRef    = useRef(null);
  const micLevelTimer  = useRef(null);
  const lastLangRef    = useRef(null);
  const liveTextRef    = useRef('');   // ref copy of liveText to avoid stale closures
  const srcRef         = useRef(sourceLanguage);
  const tgtRef         = useRef(targetLanguage);
  const sessionRef     = useRef(sessionId);
  const deviceRef      = useRef(deviceId);
  const ttsTimerRef    = useRef(null);
  const ttsTimerBARef  = useRef(null);
  const utteranceIdRef = useRef(0); // incremented per utterance to invalidate stale handlers
  const utteranceTimeoutRef = useRef(null);
  const ttsChunksAB    = useRef([]);
  const ttsChunksBA    = useRef([]);
  const playingDirRef  = useRef(null); // which direction is currently playing TTS
  const micStreamRef   = useRef(null);
  const sttSockRef     = useRef(null);
  const sttRecorderRef = useRef(null);
  const backendSttActiveRef = useRef(false);

  useEffect(() => { srcRef.current = sourceLanguage; }, [sourceLanguage]);
  useEffect(() => { tgtRef.current = targetLanguage; }, [targetLanguage]);
  useEffect(() => { sessionRef.current = sessionId; }, [sessionId]);
  useEffect(() => { deviceRef.current = deviceId; }, [deviceId]);

  // Re-open sockets when languages or auth change (while active)
  useEffect(() => {
    if (activeRef.current) restartSockets();
  }, [sourceLanguage, targetLanguage, authToken]);

  function clearUtteranceTimeout() {
    if (utteranceTimeoutRef.current) {
      clearTimeout(utteranceTimeoutRef.current);
      utteranceTimeoutRef.current = null;
    }
  }

  function setPhaseR(p) { phaseRef.current = p; setPhase(p); }
  function buildUrl() {
    return typeof withAuthToken === 'function'
      ? withAuthToken(wsAudioUrl, authToken)
      : wsAudioUrl;
  }

  // ── Mic level polling ──────────────────────────────────────────────────
  function startMicLevelPoll(stream) {
    stopMicLevelPoll();
    analyserRef.current = createMicAnalyser(stream);
    micLevelTimer.current = setInterval(() => {
      if (analyserRef.current && phaseRef.current === 'listening') {
        setMicLevel(analyserRef.current.getLevel());
      } else {
        setMicLevel(0);
      }
    }, 80);
  }
  function stopMicLevelPoll() {
    clearInterval(micLevelTimer.current);
    analyserRef.current?.close();
    analyserRef.current = null;
    setMicLevel(0);
  }

  // ── After TTS: restart listening ──────────────────────────────────────
  function afterTts(sourceText, translatedText, speaker) {
    if (!activeRef.current) return;
    if (sourceText || translatedText) {
      setTurns(prev => [...prev, {
        speaker,
        speaker_label: speaker === 'A' ? 'Person 1' : 'Person 2',
        srcLang: speaker === 'A' ? srcRef.current : tgtRef.current,
        tgtLang: speaker === 'A' ? tgtRef.current : srcRef.current,
        source_text: sourceText,
        translated_text: translatedText,
        conversationSpeaker: speaker,
        timestamp: Date.now(),
      }]);
    }
    ttsChunksAB.current = [];
    ttsChunksBA.current = [];
    playingDirRef.current = null;
    setLiveTrans('');
    setLiveText('');
    liveTextRef.current = '';
    lockedRef.current = false;
    // Show "Ready" briefly so user knows system is about to listen again
    setPhaseR('ready');
    setTimeout(() => {
      if (activeRef.current && !lockedRef.current) {
        setPhaseR('listening');
        startRecognition();
      }
    }, 600);
  }

  // ── Open both translation sockets ────────────────────────────────────
  function openSockets() {
    const src = srcRef.current;
    const tgt = tgtRef.current;

    function makeTtsHandler(dir, outboundTargetLang) {
      const chunkBuf = dir === 'AB' ? ttsChunksAB : ttsChunksBA;
      const timerRef = dir === 'AB' ? ttsTimerRef : ttsTimerBARef;
      let finalTranslation = '';
      let finalSource = '';
      let receivedTtsChunks = 0;
      let ttsCompleted = false;
      let audioFallbackTimer = null;

      return {
        onTranslation(text, isFinal, frame = {}) {
          if (!activeRef.current) return;
          setLiveTrans(text);
          if (!isFinal) return;
          finalTranslation = text;
          clearTimeout(audioFallbackTimer);
          clearUtteranceTimeout();
          if (ttsCompleted) return;
          const activeTarget = frame.target_language || outboundTargetLang;
          const backendOwnsTts = frame.source === 'browser_live_text'
            && BACKEND_TTS_LANGS.has(activeTarget);
          if (backendOwnsTts) {
            receivedTtsChunks = 0;
            audioFallbackTimer = window.setTimeout(() => {
              if (!activeRef.current || receivedTtsChunks > 0 || ttsCompleted) return;
              onStatus?.('Voice playback timed out');
              afterTts(liveTextRef.current, text, dir === 'AB' ? 'A' : 'B');
            }, 12000);
            return;
          }
          if (text && !BACKEND_TTS_LANGS.has(activeTarget)) {
            clearTimeout(timerRef.current);
            clearTimeout(dir === 'AB' ? ttsTimerBARef.current : ttsTimerRef.current);
            setPhaseR('speaking');
            speakBrowser(text, activeTarget, {
              onEnd: () => afterTts(liveTextRef.current, text, dir === 'AB' ? 'A' : 'B'),
            });
          }
        },
        onTtsChunk(b64) {
          if (!activeRef.current) return;
          if (recogRef.current) {
            try { recogRef.current.abort(); } catch {}
            recogRef.current = null;
          }
          receivedTtsChunks += 1;
          clearTimeout(audioFallbackTimer);
          clearUtteranceTimeout();
          chunkBuf.current.push(b64);
          if (playingDirRef.current === null) {
            playingDirRef.current = dir;
            lockedRef.current = true;
            setPhaseR('speaking');
            drainChunks(chunkBuf, dir, finalTranslation, finalSource);
          }
        },
        onTtsEnd() {
          if (!activeRef.current) return;
          ttsCompleted = true;
          clearUtteranceTimeout();
          clearTimeout(audioFallbackTimer);
          clearTimeout(timerRef.current);
          timerRef.current = setTimeout(async () => {
            if (!activeRef.current) return;
            const player = playerRef.current;
            const remaining = player ? player.remainingMs() : 0;
            await new Promise(r => setTimeout(r, remaining + 300));
            const spk = dir === 'AB' ? 'A' : 'B';
            // For non-browser-TTS path: collect source from liveTextRef
            afterTts(liveTextRef.current, finalTranslation, spk);
          }, 150);
        },
        onFinal(data) {
          if (!activeRef.current || data?.source !== 'browser_live_text') return;
          if (data.translated_text) finalTranslation = data.translated_text;
        },
        onReady() { setSockStat('connected'); },
        onReconnecting(n) { setSockStat(n > 1 ? 'reconnecting' : 'connected'); },
        onError(err) {
          if (!activeRef.current) return;
          if (err?.warming) {
            onStatus?.('Models still loading — wait for LIVE');
            lockedRef.current = false;
            setPhaseR('idle');
            activeRef.current = false;
            setActive(false);
            setSockStat('disconnected');
            return;
          }
          const message = String(err?.message || '');
          if (message.includes('Too many active streams')) {
            onStatus?.('Stream limit — reconnecting conversation...');
            window.setTimeout(() => {
              if (activeRef.current) restartSockets();
            }, 800);
            return;
          }
          if (err?.source === 'browser_live_text' && err?.recoverable) {
            clearTimeout(audioFallbackTimer);
            ttsCompleted = true;
            const msg = String(err?.message || '');
            if (/translation failed/i.test(msg)) {
              onStatus?.(msg);
            }
            afterTts(liveTextRef.current, '', dir === 'AB' ? 'A' : 'B');
          }
        },
        setFinalSource(t) { finalSource = t; },
        getFinalTranslation() { return finalTranslation; },
        reset() {
          finalTranslation = '';
          finalSource = '';
          receivedTtsChunks = 0;
          ttsCompleted = false;
          clearTimeout(audioFallbackTimer);
        },
      };
    }

    const handlerAB = makeTtsHandler('AB', tgt);
    const handlerBA = makeTtsHandler('BA', src);
    const sessionKey = sessionRef.current;
    const baseDevice = deviceRef.current;

    sockABRef.current = createTranslationSocket(() => buildUrl(), src, tgt, handlerAB, {
      sessionId: sessionKey,
      deviceId: `${baseDevice}-conv-ab`,
      speaker: 'A',
      speakerLabel: 'Person 1',
    });
    sockBARef.current = createTranslationSocket(() => buildUrl(), tgt, src, handlerBA, {
      sessionId: sessionKey,
      deviceId: `${baseDevice}-conv-ba`,
      speaker: 'B',
      speakerLabel: 'Person 2',
    });

    // Store handlers for use in handleUtterance
    sockABRef.current._handler = handlerAB;
    sockBARef.current._handler = handlerBA;
  }

  async function drainChunks(chunkBuf, dir, finalTrans, finalSrc) {
    let stalls = 0;
    while (activeRef.current && playingDirRef.current === dir) {
      const player = playerRef.current;
      if (!player) break; // player closed (stop() called)
      const chunk = chunkBuf.current.shift();
      if (chunk) {
        stalls = 0;
        await player.playChunk(chunk).catch(() => {});
      } else {
        stalls++;
        if (stalls > 100) break; // 5s with no chunks - bail out
        await new Promise(r => setTimeout(r, 50));
      }
    }
  }

  function restartSockets() {
    clearUtteranceTimeout();
    clearTimeout(ttsTimerRef.current);
    clearTimeout(ttsTimerBARef.current);
    utteranceIdRef.current += 1;
    lockedRef.current = false;
    stopBackendStt();
    sockABRef.current?.destroy(); sockABRef.current = null;
    sockBARef.current?.destroy(); sockBARef.current = null;
    setSockStat('disconnected');
    window.setTimeout(() => {
      if (!activeRef.current) return;
      openSockets();
      if (languagePairNeedsBackendStt(srcRef.current, tgtRef.current)) {
        startBackendSttListening();
      } else {
        startRecognition();
      }
    }, 600);
  }

  function stopMicStream() {
    micStreamRef.current?.getTracks().forEach((track) => track.stop());
    micStreamRef.current = null;
  }

  function stopBackendStt() {
    backendSttActiveRef.current = false;
    if (sttRecorderRef.current?.state === 'recording') {
      try { sttRecorderRef.current.stop(); } catch {}
    }
    sttRecorderRef.current = null;
    if (sttSockRef.current) {
      sttSockRef.current.onclose = null;
      try { sttSockRef.current.close(); } catch {}
      sttSockRef.current = null;
    }
  }

  function openBackendSttSocket() {
    if (sttSockRef.current?.readyState === WebSocket.OPEN
      || sttSockRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }
    const ws = new WebSocket(buildUrl());
    sttSockRef.current = ws;
    ws.binaryType = 'arraybuffer';
    ws.onmessage = ({ data }) => {
      try {
        const d = JSON.parse(data);
        if (d.type === 'ready') {
          ws.send(JSON.stringify({
            type: 'start',
            source_language: srcRef.current,
            target_language: tgtRef.current,
            session_id: sessionRef.current,
            device_id: `${deviceRef.current}-conv-stt`,
            speaker_mode: 'auto',
            speaker: 'auto',
            stt_only: true,
            mime_type: preferredAudioMimeType(),
          }));
          return;
        }
        if (d.type === 'error') {
          if (d.warming) {
            onStatus?.('Models still loading — wait for LIVE');
            stop();
          }
          return;
        }
        if (d.type === 'partial_transcription' && !lockedRef.current && activeRef.current) {
          const visible = String(d.text || '').trim();
          if (visible) {
            setLiveText(visible);
            liveTextRef.current = visible;
          }
          return;
        }
        if (d.type === 'stt_only' && d.text && !lockedRef.current && activeRef.current) {
          handleUtterance(String(d.text).trim());
        }
      } catch {}
    };
    ws.onclose = () => {
      sttSockRef.current = null;
      if (activeRef.current && backendSttActiveRef.current) {
        window.setTimeout(() => {
          if (activeRef.current && backendSttActiveRef.current) openBackendSttSocket();
        }, 500);
      }
    };
  }

  function startBackendSttListening() {
    if (!activeRef.current || lockedRef.current || !micStreamRef.current) return;
    backendSttActiveRef.current = true;
    setPhaseR('listening');
    openBackendSttSocket();
    if (sttRecorderRef.current?.state === 'recording') return;
    try {
      const recorder = createAudioRecorder(micStreamRef.current);
      sttRecorderRef.current = recorder;
      recorder.ondataavailable = async (event) => {
        if (!backendSttActiveRef.current || lockedRef.current) return;
        const ws = sttSockRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN || event.data.size <= 0) return;
        const buffer = await event.data.arrayBuffer();
        ws.send(JSON.stringify({
          type: 'chunk_meta',
          sent_at_ms: Date.now(),
          bytes: buffer.byteLength,
          mime_type: recorder.mimeType || preferredAudioMimeType(),
          audio_level: analyserRef.current?.getLevel?.() || 0,
          voice_active: true,
        }));
        ws.send(buffer);
      };
      recorder.start(250);
    } catch {
      onStatus?.('Backend speech recognition unavailable');
      setPhaseR('idle');
    }
  }

  // ── Speech recognition ────────────────────────────────────────────────
  function startRecognition() {
    if (!activeRef.current || lockedRef.current) return;
    if (languagePairNeedsBackendStt(srcRef.current, tgtRef.current)) {
      startBackendSttListening();
      return;
    }
    if (recogRef.current) { try { recogRef.current.abort(); } catch {} recogRef.current = null; }

    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      onStatus?.('Speech recognition unavailable in this browser');
      setPhaseR('idle');
      return;
    }

    const rec = new Rec();
    // Alternate language hints to improve detection of both speakers
    const useAltLang = lastLangRef.current === srcRef.current;
    rec.lang = speechRecognitionLanguage(useAltLang ? tgtRef.current : srcRef.current);
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 3; // get alternatives for better detection
    recogRef.current = rec;
    setPhaseR('listening');

    rec.onresult = (ev) => {
      if (lockedRef.current || phaseRef.current === 'speaking' || phaseRef.current === 'processing') return;
      let final = '', interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        // Check all alternatives for language patterns
        const t = ev.results[i]?.[0]?.transcript || '';
        if (ev.results[i].isFinal) final += t;
        else interim += t;
      }
      const visible = (final || interim).trim();
      setLiveText(visible);
      liveTextRef.current = visible;
      if (final.trim()) handleUtterance(final.trim());
    };

    rec.onerror = (e) => {
      if (e.error === 'no-speech') {
        if (activeRef.current && !lockedRef.current) setTimeout(() => { if (activeRef.current && !lockedRef.current) startRecognition(); }, 100);
      } else if (e.error !== 'aborted') {
        if (activeRef.current && !lockedRef.current) setTimeout(() => { if (activeRef.current && !lockedRef.current) startRecognition(); }, 800);
      }
    };

    rec.onend = () => {
      if (recogRef.current === rec) recogRef.current = null;
      if (activeRef.current && phaseRef.current === 'listening' && !lockedRef.current) {
        setTimeout(() => { if (activeRef.current && !lockedRef.current) startRecognition(); }, 150);
      }
    };

    try { rec.start(); } catch {
      setTimeout(() => { if (activeRef.current) startRecognition(); }, 600);
    }
  }

  // ── Handle final utterance ─────────────────────────────────────────────
  function handleUtterance(text) {
    if (!activeRef.current || lockedRef.current) return;
    if (recogRef.current) { try { recogRef.current.stop(); } catch {} recogRef.current = null; }
    if (sttRecorderRef.current?.state === 'recording') {
      try { sttRecorderRef.current.stop(); } catch {}
    }

    const src = srcRef.current;
    const tgt = tgtRef.current;
    const detSrc = detectLanguage(text, src, tgt, lastLangRef.current);
    const detTgt = detSrc === src ? tgt : src;
    const speaker = detSrc === src ? 'A' : 'B';

    lastLangRef.current = detSrc;
    setDetLang(detSrc);
    setPhaseR('processing');
    lockedRef.current = true;

    ttsChunksAB.current = [];
    ttsChunksBA.current = [];
    playingDirRef.current = null;
    playerRef.current?.reset();

    // Store source text for the turn record
    liveTextRef.current = text;

    const sock = speaker === 'A' ? sockABRef.current : sockBARef.current;
    sock?._handler?.reset();

    // Timeout safety: restart if no response in 15s
    clearUtteranceTimeout();
    clearTimeout(ttsTimerRef.current);
    clearTimeout(ttsTimerBARef.current);
    const capturedUtteranceId = utteranceIdRef.current;
    utteranceTimeoutRef.current = setTimeout(() => {
      if (activeRef.current && utteranceIdRef.current === capturedUtteranceId &&
          (phaseRef.current === 'processing' || phaseRef.current === 'speaking')) {
        utteranceIdRef.current++;
        afterTts(text, '', speaker);
      }
    }, 15000);

    if (sock) {
      sock.send(text, true);
    } else {
      onStatus?.('Translation socket not ready');
      lockedRef.current = false;
      afterTts(text, '', speaker);
    }
  }

  // ── Public API ──────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    if (activeRef.current) return;
    if (!backendReady) {
      onStatus?.('Models still loading — wait for LIVE');
      return;
    }
    activeRef.current = true;
    lockedRef.current = false;
    setActive(true);
    setTurns([]);
    setLiveText(''); liveTextRef.current = '';
    setLiveTrans('');
    setDetLang(null);
    lastLangRef.current = null;
    ttsChunksAB.current = [];
    ttsChunksBA.current = [];
    playingDirRef.current = null;

    playerRef.current = createAudioPlayer();
    window.speechSynthesis?.getVoices(); // preload

    // Mic stream for level meter and optional backend STT
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      startMicLevelPoll(stream);
    } catch {
      onStatus?.('Microphone access denied');
      stop();
      return;
    }

    openSockets();
    setTimeout(() => { if (activeRef.current) startRecognition(); }, 500);
  }, [backendReady, onStatus]);

  const stop = useCallback(() => {
    activeRef.current = false;
    lockedRef.current = false;
    setActive(false);
    setPhaseR('idle');
    setDetLang(null);
    setMicLevel(0);
    clearUtteranceTimeout();
    clearTimeout(ttsTimerRef.current);
    clearTimeout(ttsTimerBARef.current);
    if (recogRef.current) { try { recogRef.current.abort(); } catch {} recogRef.current = null; }
    sockABRef.current?.destroy(); sockABRef.current = null;
    sockBARef.current?.destroy(); sockBARef.current = null;
    stopBackendStt();
    playerRef.current?.close(); playerRef.current = null;
    stopMicLevelPoll();
    stopMicStream();
    window.speechSynthesis?.cancel();
    setSockStat('disconnected');
  }, []);

  const clearTurns = useCallback(() => setTurns([]), []);

  useEffect(() => {
    if (activeRef.current && !backendReady) {
      onStatus?.('Models still loading — wait for LIVE');
      stop();
    }
  }, [backendReady, onStatus, stop]);

  useEffect(() => () => stop(), []);

  return {
    active, phase, detectedLang, turns,
    liveText, liveTranslation: liveTrans,
    sockStatus, micLevel,
    start, stop, clearTurns,
  };
}
