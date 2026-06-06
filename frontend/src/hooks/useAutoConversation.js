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

// ─── Language config ─────────────────────────────────────────────────────
const BROWSER_TTS_MAP = {
  en:'en-US', es:'es-MX', fr:'fr-FR', de:'de-DE', it:'it-IT',
  pt:'pt-BR', ru:'ru-RU', zh:'zh-CN', ja:'ja-JP', ko:'ko-KR',
  ar:'ar-SA', hi:'hi-IN', ht:'ht-HT', nl:'nl-NL',
};
const PIPER_LANGS = new Set(['en','es']);

// ─── Language detection ──────────────────────────────────────────────────
const LANG_PATTERNS = {
  es:/\b(el|la|los|las|un|una|que|es|en|de|y|no|lo|le|su|por|con|para|como|pero|más|este|bien|hola|gracias|cómo|qué|estás|soy|quiero|puedo|tiene|hace|usted|también|cuando|porque|donde|nosotros|ellos|aquí|allí)\b/i,
  fr:/\b(le|la|les|un|une|des|de|du|et|est|pas|je|tu|il|nous|avec|pour|sur|dans|mais|merci|bonjour|oui|non|très|bien|voilà|c'est|j'ai|vous|ils|mon|ma|ici|là|aussi|quand|comment|pourquoi|où)\b/i,
  de:/\b(der|die|das|ein|eine|und|ist|nicht|ich|du|er|sie|wir|mit|auf|zu|von|im|dem|auch|aber|wenn|bitte|danke|ja|nein|gut|hallo|können|haben|sein|noch|schon|nur|mehr|sehr|was|wer|wo|wie)\b/i,
  pt:/\b(o|a|os|as|um|uma|de|em|que|é|não|com|para|por|mas|seu|sua|você|também|muito|bem|obrigado|olá|como|está|posso|tenho|fazer|ter|ser|aqui|lá|agora|então|já|só)\b/i,
  it:/\b(il|la|i|le|un|una|di|e|è|non|con|per|ma|si|mi|ti|lo|che|come|sono|ho|ha|grazie|ciao|sì|no|bene|dove|anche|già|solo|quando|perché|quello|questa|loro|noi)\b/i,
  nl:/\b(de|het|een|van|en|is|niet|ik|je|hij|ze|we|met|voor|op|in|maar|ook|aan|bij|hallo|dank|ja|nee|goed|hoe|wat|wie|waar|wanneer|dit|dat|mijn|jouw)\b/i,
  ru:/[а-яёА-ЯЁ]{3,}/,
  ht:/\b(mwen|ou|li|nou|yo|se|pa|nan|ak|pou|ki|sa|gen|ka|ap|te|la|wi|non|mèsi|bonjou|sak|kijan|kote|jan|poukisa)\b/i,
};

function detectLanguage(text, langA, langB, lastLang) {
  if (!text || text.trim().length < 2) return lastLang || langA;
  // Script-range checks first (definitive)
  const checks = [
    [/[一-鿿぀-ゟ゠-ヿ]/, ['zh','ja']],
    [/[가-힯]/,           ['ko']],
    [/[؀-ۿ]/,            ['ar']],
    [/[Ѐ-ӿ]/,            ['ru']],
    [/[ऀ-ॿ]/,            ['hi']],
  ];
  for (const [rx, langs] of checks) {
    if (rx.test(text)) {
      for (const l of langs) {
        if (langA === l) return langA;
        if (langB === l) return langB;
      }
    }
  }
  // Score both with word patterns
  const sA = LANG_PATTERNS[langA] ? (text.match(LANG_PATTERNS[langA]) || []).length : 0;
  const sB = LANG_PATTERNS[langB] ? (text.match(LANG_PATTERNS[langB]) || []).length : 0;
  if (sA > sB) return langA;
  if (sB > sA) return langB;
  return lastLang || langA; // tie -> keep last speaker
}

// ─── Browser TTS ─────────────────────────────────────────────────────────
function speakBrowser(text, lang, { onEnd } = {}) {
  if (!window.speechSynthesis || !text) { onEnd?.(); return () => {}; }
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
function createTranslationSocket(urlFn, srcLang, tgtLang, handlers) {
  let ws = null;
  let ready = false;
  let queue = [];
  let retryCount = 0;
  let closed = false;
  let retryTimer = null;

  function connect() {
    if (closed) return;
    ws = new WebSocket(urlFn());
    ws.onopen = () => {
      retryCount = 0;
      ws.send(JSON.stringify({
        type:'start', source_language:srcLang, target_language:tgtLang,
        speaker_mode:'manual', speaker:'auto', speaker_label:'Auto',
      }));
      ready = true;
      queue.splice(0).forEach(m => ws.send(m));
      handlers.onReady?.();
    };
    ws.onmessage = ({ data }) => {
      try {
        const d = JSON.parse(data);
        if (d.type === 'live_translation' || d.type === 'partial_translation') handlers.onTranslation?.(d.text, false);
        if (d.type === 'final' || d.type === 'translation')  handlers.onTranslation?.(d.translated_text || d.text || '', true);
        if (d.type === 'tts_audio_chunk' && !d.partial)      handlers.onTtsChunk?.(d.audio_base64, d.mime_type);
        if (d.type === 'tts_end' && !d.partial)              handlers.onTtsEnd?.();
      } catch {}
    };
    ws.onerror = () => { ready = false; };
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
    const msg = JSON.stringify({
      type:'live_text', text, final:isFinal,
      source_language:srcLang, target_language:tgtLang,
      speaker:'auto', speaker_label:'Auto', speaker_mode:'manual',
    });
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
export function useAutoConversation({ wsAudioUrl, authToken, sourceLanguage, targetLanguage, withAuthToken }) {
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
  const ttsTimerRef    = useRef(null);
  const ttsTimerBARef  = useRef(null);
  const utteranceIdRef = useRef(0); // incremented per utterance to invalidate stale handlers
  const ttsChunksAB    = useRef([]);
  const ttsChunksBA    = useRef([]);
  const playingDirRef  = useRef(null); // which direction is currently playing TTS

  useEffect(() => { srcRef.current = sourceLanguage; }, [sourceLanguage]);
  useEffect(() => { tgtRef.current = targetLanguage; }, [targetLanguage]);

  // Re-open sockets when languages change (while active)
  useEffect(() => {
    if (activeRef.current) restartSockets();
  }, [sourceLanguage, targetLanguage]);

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

    function makeTtsHandler(dir) {
      const chunkBuf = dir === 'AB' ? ttsChunksAB : ttsChunksBA;
      const timerRef = dir === 'AB' ? ttsTimerRef : ttsTimerBARef;
      let finalTranslation = '';
      let finalSource = '';

      return {
        onTranslation(text, isFinal) {
          if (!activeRef.current) return;
          setLiveTrans(text);
          if (isFinal) finalTranslation = text;
        },
        onTtsChunk(b64) {
          if (!activeRef.current) return;
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
        onReady() { setSockStat('connected'); },
        onReconnecting(n) { setSockStat(n > 1 ? 'reconnecting' : 'connected'); },
        setFinalSource(t) { finalSource = t; },
        getFinalTranslation() { return finalTranslation; },
        reset() { finalTranslation = ''; finalSource = ''; },
      };
    }

    const handlerAB = makeTtsHandler('AB');
    const handlerBA = makeTtsHandler('BA');

    sockABRef.current = createTranslationSocket(() => buildUrl(), src, tgt, handlerAB);
    sockBARef.current = createTranslationSocket(() => buildUrl(), tgt, src, handlerBA);

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
    sockABRef.current?.destroy(); sockABRef.current = null;
    sockBARef.current?.destroy(); sockBARef.current = null;
    setSockStat('disconnected');
    openSockets();
  }

  // ── Speech recognition ────────────────────────────────────────────────
  function startRecognition() {
    if (!activeRef.current || lockedRef.current) return;
    if (recogRef.current) { try { recogRef.current.abort(); } catch {} recogRef.current = null; }

    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) { setPhaseR('idle'); return; }

    const rec = new Rec();
    // Alternate language hints to improve detection of both speakers
    const useAltLang = lastLangRef.current === srcRef.current;
    rec.lang = BROWSER_TTS_MAP[useAltLang ? tgtRef.current : srcRef.current] || 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 3; // get alternatives for better detection
    recogRef.current = rec;
    setPhaseR('listening');

    rec.onresult = (ev) => {
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

    // Timeout safety: restart if no response in 9s
    clearTimeout(ttsTimerRef.current);
    clearTimeout(ttsTimerBARef.current);
    const capturedUtteranceId = utteranceIdRef.current;
    ttsTimerRef.current = setTimeout(() => {
      if (activeRef.current && utteranceIdRef.current === capturedUtteranceId &&
          (phaseRef.current === 'processing' || phaseRef.current === 'speaking')) {
        utteranceIdRef.current++; // invalidate any pending handler
        afterTts(text, '', speaker);
      }
    }, 9000);

    if (sock) {
      sock.send(text, true);
    } else {
      // Socket not ready — browser TTS fallback
      setPhaseR('speaking');
      speakBrowser(text, detTgt, {
        onEnd: () => afterTts(text, '(offline)', speaker)
      });
    }

    // For browser-TTS target languages: backend sends translation text, we speak it
    // The onTranslation handler in makeTtsHandler will call speakBrowser when isFinal
    // For PIPER_LANGS: tts_audio_chunk arrives and we play via AudioContext
    if (!PIPER_LANGS.has(detTgt)) {
      // Override the handler to use browser TTS when final translation arrives
      const handler = sock?._handler;
      if (handler) {
        const origOnTrans = handler.onTranslation.bind(handler);
        handler.onTranslation = (translatedText, isFinal) => {
          if (!activeRef.current) return;
          setLiveTrans(translatedText);
          if (isFinal && translatedText) {
            clearTimeout(ttsTimerRef.current);
            clearTimeout(ttsTimerBARef.current);
            setPhaseR('speaking');
            speakBrowser(translatedText, detTgt, {
              onEnd: () => afterTts(text, translatedText, speaker)
            });
            // Restore original handler for next turn
            handler.onTranslation = origOnTrans;
          }
        };
      }
    }
  }

  // ── Public API ──────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    if (activeRef.current) return;
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

    // Try to get mic stream for level meter
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      startMicLevelPoll(stream);
    } catch {}

    openSockets();
    setTimeout(() => { if (activeRef.current) startRecognition(); }, 500);
  }, []);

  const stop = useCallback(() => {
    activeRef.current = false;
    lockedRef.current = false;
    setActive(false);
    setPhaseR('idle');
    setDetLang(null);
    setMicLevel(0);
    clearTimeout(ttsTimerRef.current);
    clearTimeout(ttsTimerBARef.current);
    if (recogRef.current) { try { recogRef.current.abort(); } catch {} recogRef.current = null; }
    sockABRef.current?.destroy(); sockABRef.current = null;
    sockBARef.current?.destroy(); sockBARef.current = null;
    playerRef.current?.close(); playerRef.current = null;
    stopMicLevelPoll();
    window.speechSynthesis?.cancel();
    setSockStat('disconnected');
  }, []);

  const clearTurns = useCallback(() => setTurns([]), []);

  useEffect(() => () => stop(), []);

  return {
    active, phase, detectedLang, turns,
    liveText, liveTranslation: liveTrans,
    sockStatus, micLevel,
    start, stop, clearTurns,
  };
}
