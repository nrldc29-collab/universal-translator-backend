/**
 * NAIA Voice Assistant -- speak to ask, hear the answer.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, Sparkles, Square, X } from 'lucide-react';

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
      setStatus((current) => (current === 'Thinking...' ? 'Tap mic to speak' : current));
    }
  }

  function startListening() {
    const Recognition = speechRecognitionConstructor();
    if (!Recognition) { setStatus('Speech not supported in this browser'); return; }
    window.speechSynthesis?.cancel();
    const rec = new Recognition();
    rec.lang = toLangCode('en');
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    rec.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i]?.[0]?.transcript || '';
        if (event.results[i].isFinal) final += t;
        else interim += t;
      }
      setTranscript(final || interim);
      if (final) { stopListening(); sendToAssistant(final); }
    };
    rec.onerror = (e) => { if (e.error !== 'no-speech') setStatus(`Mic error: ${e.error}`); stopListening(); };
    rec.onend = () => {
      if (recognitionRef.current === rec) {
        setListening(false);
        if (!pending) setStatus('Tap mic to speak');
      }
    };
    recognitionRef.current = rec;
    rec.start();
    setListening(true);
    setStatus('Listening...');
  }

  function stopListening() {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) { /* noop */ }
      recognitionRef.current = null;
    }
    setListening(false);
  }

  function toggleMic() { if (listening) stopListening(); else startListening(); }

  function handleClear() {
    setMessages([]);
    setTranscript('');
    window.speechSynthesis?.cancel();
    setStatus('Tap mic to speak');
  }

  const anchorClass = `assistant-anchor assistant-anchor--${position === 'bottom-left' ? 'left' : 'right'}`;
  const statusClass = listening ? 'listening' : pending ? 'thinking' : '';

  return (
    <div className={anchorClass}>
      {!open && (
        <button
          type="button"
          className="assistant-fab"
          onClick={() => setOpen(true)}
          aria-label="Open voice assistant"
          title="Voice Assistant"
        >
          <Mic size={22} strokeWidth={2.2} />
        </button>
      )}
      {open && (
        <div className="assistant-panel" role="dialog" aria-label="Voice assistant" aria-modal="true">
          <header className="assistant-header">
            <div className="assistant-header-text">
              <strong className="assistant-title">Voice Assistant</strong>
              <span className={`assistant-status${available === false ? ' unavailable' : available === true ? ' ready' : ''}`}>
                {available === false ? 'Unavailable' : available === true ? 'Ready' : 'Connecting…'}
              </span>
            </div>
            <div className="assistant-header-actions">
              <button type="button" className="assistant-ghost-btn" onClick={handleClear} aria-label="Clear conversation">
                Clear
              </button>
              <button
                type="button"
                className="assistant-ghost-btn assistant-close-btn"
                onClick={() => { setOpen(false); stopListening(); }}
                aria-label="Close assistant"
              >
                <X size={16} strokeWidth={2.5} />
              </button>
            </div>
          </header>

          {available === false && (
            <div className="assistant-unavailable" role="alert">
              <span>Unavailable.{unavailableReason ? ` ${unavailableReason}` : ''}</span>
              <button type="button" className="assistant-ghost-btn danger" onClick={checkHealth}>
                Retry
              </button>
            </div>
          )}

          <div ref={scrollerRef} className="assistant-messages">
            {messages.length === 0 && !transcript && (
              <div className="assistant-empty">
                <div className="assistant-empty-icon" aria-hidden="true">
                  <Sparkles size={22} strokeWidth={1.8} />
                </div>
                <p>Tap the mic and speak your question.</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} role={msg.role} text={msg.text} index={idx} />
            ))}
            {pending && (
              <div className="assistant-bubble-wrap assistant">
                <div className="assistant-bubble assistant pending" aria-busy="true">
                  <span className="assistant-thinking-dots" aria-hidden="true">
                    <span /><span /><span />
                  </span>
                  <span className="sr-only">Thinking</span>
                </div>
              </div>
            )}
            {transcript && !pending && (
              <p className="assistant-interim">&ldquo;{transcript}&rdquo;</p>
            )}
          </div>

          <footer className="assistant-footer">
            <span className={`assistant-footer-status ${statusClass}`}>{status}</span>
            <button
              type="button"
              className={`assistant-mic${listening ? ' listening' : ''}${pending || available === false ? ' disabled' : ''}`}
              onClick={toggleMic}
              disabled={pending || available === false}
              aria-label={listening ? 'Stop listening' : 'Start speaking'}
            >
              {listening ? <Square size={22} strokeWidth={2.4} /> : <Mic size={24} strokeWidth={2.2} />}
            </button>
          </footer>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ role, text, index = 0 }) {
  return (
    <div
      className={`assistant-bubble-wrap ${role}`}
      style={{ '--bubble-index': index }}
    >
      <div className={`assistant-bubble ${role}`}>
        {text}
      </div>
    </div>
  );
}
