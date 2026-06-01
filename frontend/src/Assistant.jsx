/**
 * NAIA Voice Assistant -- speak to ask, hear the answer.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';

const REQUEST_TIMEOUT_MS = 30_000;

function buildAuthHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

function speechRecognitionConstructor() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function speakText(text, lang = 'en-US') {
  if (!window.speechSynthesis || !text) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = lang;
  utt.rate = 1.0;
  utt.pitch = 1.0;
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find((v) => v.lang.startsWith(lang.slice(0, 2)) && !v.localService)
    || voices.find((v) => v.lang.startsWith(lang.slice(0, 2)));
  if (preferred) utt.voice = preferred;
  window.speechSynthesis.speak(utt);
}

function toLangCode(tl) {
  const map = { es: 'es-MX', fr: 'fr-FR', de: 'de-DE', pt: 'pt-BR', it: 'it-IT', ht: 'ht-HT', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR', ar: 'ar-SA', hi: 'hi-IN' };
  return map[tl] || 'en-US';
}

export default function Assistant({
  apiUrl = '',
  authToken = '',
  getTranslationContext,
  position = 'bottom-right',
  targetLanguage = 'en',
}) {
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(null);
  const [unavailableReason, setUnavailableReason] = useState('');
  const [messages, setMessages] = useState([]);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState('Tap mic to speak');
  const sessionIdRef = useRef(null);
  const scrollerRef = useRef(null);
  const recognitionRef = useRef(null);

  if (!sessionIdRef.current) {
    sessionIdRef.current =
      (typeof crypto !== 'undefined' && crypto.randomUUID?.()) ||
      `assistant-${Math.random().toString(36).slice(2)}-${Date.now()}`;
  }

  const checkHealth = useCallback(() => {
    if (!apiUrl) return;
    setAvailable(null);
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/api/assistant/health`, { headers: buildAuthHeaders(authToken) });
        const body = await res.json().catch(() => ({}));
        setAvailable(Boolean(body.available));
        setUnavailableReason(body.error || '');
      } catch (err) {
        setAvailable(false);
        setUnavailableReason(err?.message || 'Could not reach assistant');
      }
    })();
  }, [apiUrl, authToken]);

  useEffect(() => { if (open && available === null) checkHealth(); }, [open, available, checkHealth]);
  useEffect(() => { if (scrollerRef.current) scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight; }, [messages, pending, transcript]);
  useEffect(() => { if (!open) stopListening(); }, [open]);

  async function sendToAssistant(text) {
    if (!text.trim() || pending) return;
    const userText = text.trim();
    setTranscript('');
    setMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setPending(true);
    setStatus('Thinking...');
    const ctx = typeof getTranslationContext === 'function' ? getTranslationContext() : null;
    try {
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      const response = await fetch(`${apiUrl}/api/assistant/chat`, {
        method: 'POST',
        headers: buildAuthHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message: userText, session_id: sessionIdRef.current, translation_context: ctx || undefined }),
        signal: controller.signal,
      });
      clearTimeout(tid);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = body?.detail || (response.status === 503 ? 'Assistant not available.' : `Error ${response.status}`);
        setMessages((prev) => [...prev, { role: 'system', text: detail }]);
      } else {
        const reply = body.response || '(no response)';
        setMessages((prev) => [...prev, { role: 'assistant', text: reply }]);
        setStatus('Speaking...');
        speakText(reply, toLangCode(targetLanguage));
        setTimeout(() => setStatus('Tap mic to speak'), 1500);
      }
    } catch (err) {
      const msg = err?.name === 'AbortError' ? 'Request timed out.' : `Error: ${err?.message || err}`;
      setMessages((prev) => [...prev, { role: 'system', text: msg }]);
    } finally {
      setPending(false);
      if (status === 'Thinking...') setStatus('Tap mic to speak');
    }
  }

  function startListening() {
    const Recognition = speechRecognitionConstructor();
    if (!Recognition) { setStatus('Speech not supported in this browser'); return; }
    window.speechSynthesis?.cancel();
    const rec = new Recognition();
    rec.lang = toLangCode('en'); // always listen in English for the assistant
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    rec.onresult = (event) => {
      let interim = '', final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i]?.[0]?.transcript || '';
        if (event.results[i].isFinal) final += t; else interim += t;
      }
      setTranscript(final || interim);
      if (final) { stopListening(); sendToAssistant(final); }
    };
    rec.onerror = (e) => { if (e.error !== 'no-speech') setStatus(`Mic error: ${e.error}`); stopListening(); };
    rec.onend = () => { if (recognitionRef.current === rec) { setListening(false); if (!pending) setStatus('Tap mic to speak'); } };
    recognitionRef.current = rec;
    rec.start();
    setListening(true);
    setStatus('Listening...');
  }

  function stopListening() {
    if (recognitionRef.current) { try { recognitionRef.current.stop(); } catch (_) {} recognitionRef.current = null; }
    setListening(false);
  }

  function toggleMic() { if (listening) stopListening(); else startListening(); }
  function handleClear() { setMessages([]); setTranscript(''); window.speechSynthesis?.cancel(); setStatus('Tap mic to speak'); }

  const posStyles = position === 'bottom-left' ? { left: 20, bottom: 80 } : { right: 20, bottom: 80 };

  return (
    <div style={{ position: 'fixed', zIndex: 9999, ...posStyles }}>
      {!open && (
        <button type="button" onClick={() => setOpen(true)} aria-label="Open voice assistant" title="Voice Assistant"
          style={{ ...btnBase, width: 52, height: 52, borderRadius: '50%', fontSize: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 6px 18px rgba(15,23,42,0.4)' }}>
          🎙
        </button>
      )}
      {open && (
        <div role="dialog" aria-label="Voice assistant" aria-modal="true"
          style={{ width: 340, maxWidth: 'calc(100vw - 32px)', height: 480, maxHeight: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column', background: '#0f172a', color: '#f1f5f9', border: '1px solid #1e293b', borderRadius: 16, overflow: 'hidden', boxShadow: '0 24px 48px rgba(15,23,42,0.5)', fontFamily: 'inherit' }}>
          <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: '#1e293b', borderBottom: '1px solid #334155' }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: 14 }}>Voice Assistant</strong>
              <span style={{ fontSize: 11, color: available === false ? '#fca5a5' : '#94a3b8' }}>
                {available === false ? 'Unavailable' : available === true ? 'Ready' : 'Connecting...'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button type="button" onClick={handleClear} style={btnGhost} aria-label="Clear">Clear</button>
              <button type="button" onClick={() => { setOpen(false); stopListening(); }} style={btnGhost} aria-label="Close">&times;</button>
            </div>
          </header>

          {available === false && (
            <div style={{ padding: '8px 12px', fontSize: 12, color: '#fca5a5', background: '#1f1212', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>Unavailable.{unavailableReason ? ` ${unavailableReason}` : ''}</span>
              <button type="button" onClick={checkHealth} style={{ ...btnGhost, color: '#fca5a5', borderColor: '#5f1d1d', marginLeft: 8, fontSize: 11 }}>Retry</button>
            </div>
          )}

          <div ref={scrollerRef} style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {messages.length === 0 && !transcript && (
              <div style={{ fontSize: 13, color: '#64748b', textAlign: 'center', marginTop: 32 }}>Tap the mic and speak your question.</div>
            )}
            {messages.map((msg, idx) => <MessageBubble key={idx} role={msg.role} text={msg.text} />)}
            {pending && <MessageBubble role="assistant" text="..." pending />}
            {transcript && !pending && (
              <div style={{ fontSize: 12, color: '#94a3b8', fontStyle: 'italic', textAlign: 'right' }}>&ldquo;{transcript}&rdquo;</div>
            )}
          </div>

          <div style={{ padding: '12px 16px', borderTop: '1px solid #1e293b', background: '#0b1220', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: listening ? '#34d399' : pending ? '#fbbf24' : '#64748b' }}>{status}</span>
            <button type="button" onClick={toggleMic} disabled={pending || available === false} aria-label={listening ? 'Stop' : 'Speak'}
              style={{
                width: 64, height: 64, borderRadius: '50%', border: 'none',
                cursor: pending || available === false ? 'not-allowed' : 'pointer',
                fontSize: 26, display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.2s',
                background: listening ? 'radial-gradient(circle,#ef4444,#b91c1c)' : 'radial-gradient(circle,#2563eb,#1d4ed8)',
                boxShadow: listening ? '0 0 0 8px rgba(239,68,68,0.2),0 6px 16px rgba(239,68,68,0.4)' : '0 4px 12px rgba(37,99,235,0.4)',
                opacity: pending || available === false ? 0.5 : 1,
                animation: listening ? 'pulse 1.2s ease-in-out infinite' : 'none',
              }}>
              {listening ? '⏹' : '🎤'}
            </button>
          </div>
        </div>
      )}
      <style>{`@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}`}</style>
    </div>
  );
}

function MessageBubble({ role, text, pending = false }) {
  const isUser = role === 'user', isSystem = role === 'system';
  return (
    <div style={{ alignSelf: isUser ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
      <div style={{ background: isUser ? '#2563eb' : isSystem ? '#3f1d1d' : '#1e293b', color: '#f8fafc', padding: '8px 11px', borderRadius: 10, fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word', opacity: pending ? 0.6 : 1 }}>
        {text}
      </div>
    </div>
  );
}

const btnBase = { background: '#2563eb', color: '#f8fafc', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit', fontSize: 13 };
const btnGhost = { background: 'transparent', color: '#cbd5e1', border: '1px solid #334155', borderRadius: 6, padding: '2px 8px', cursor: 'pointer', fontSize: 12 };
