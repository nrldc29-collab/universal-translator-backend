/**
 * NAIA Assistant — conversational helper alongside the translator.
 *
 * Renders a floating button in the corner; clicking it opens a chat
 * panel that talks to POST /api/assistant/chat on the backend.  If a
 * `getTranslationContext` callback is provided, the most recent
 * translation is attached to every outgoing message so the assistant
 * can answer follow-up questions like "make that more formal" or
 * "what does that idiom mean?".
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

const REQUEST_TIMEOUT_MS = 30_000;

function buildAuthHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

export default function Assistant({
  apiUrl = '',
  authToken = '',
  getTranslationContext,
  position = 'bottom-right',
}) {
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(null); // null = unknown, true/false after probe
  const [unavailableReason, setUnavailableReason] = useState('');
  const [messages, setMessages] = useState([]); // { role: 'user'|'assistant'|'system', text }
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const sessionIdRef = useRef(null);
  const scrollerRef = useRef(null);
  const textareaRef = useRef(null);

  if (!sessionIdRef.current) {
    sessionIdRef.current =
      (typeof crypto !== 'undefined' && crypto.randomUUID && crypto.randomUUID()) ||
      `assistant-${Math.random().toString(36).slice(2)}-${Date.now()}`;
  }

  const checkHealth = useCallback(() => {
    if (!apiUrl) return;
    setAvailable(null);
    setUnavailableReason('');
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/api/assistant/health`, {
          headers: buildAuthHeaders(authToken),
        });
        const body = await res.json().catch(() => ({}));
        setAvailable(Boolean(body.available));
        setUnavailableReason(body.error || '');
      } catch (err) {
        setAvailable(false);
        setUnavailableReason(err?.message || 'Could not reach assistant');
      }
    })();
  }, [apiUrl, authToken]);

  // Probe /api/assistant/health on first open so we can tell the user
  // up-front if the bundled naia kernel didn't load.
  useEffect(() => {
    if (open && available === null) checkHealth();
  }, [open, available, checkHealth]);

  // Autoscroll to the newest message.
  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [messages, pending]);

  // Focus textarea when panel opens.
  useEffect(() => {
    if (open && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  async function handleSend() {
    const text = draft.trim();
    if (!text || pending) return;
    setDraft('');
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setPending(true);

    const ctx = typeof getTranslationContext === 'function' ? getTranslationContext() : null;

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      const response = await fetch(`${apiUrl}/api/assistant/chat`, {
        method: 'POST',
        headers: buildAuthHeaders(authToken, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          message: text,
          session_id: sessionIdRef.current,
          translation_context: ctx || undefined,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail =
          body?.detail ||
          (response.status === 503
            ? 'Assistant is not available right now.'
            : response.status === 429
            ? 'Too many requests. Please wait a moment.'
            : response.status === 413
            ? 'Message too long.'
            : `Request failed (HTTP ${response.status}).`);
        setMessages((prev) => [...prev, { role: 'system', text: detail }]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: body.response || '(no response)' },
        ]);
      }
    } catch (err) {
      const msg =
        err?.name === 'AbortError'
          ? 'Request timed out. Try again.'
          : `Network error: ${err?.message || err}`;
      setMessages((prev) => [...prev, { role: 'system', text: msg }]);
    } finally {
      setPending(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  function handleClear() {
    setMessages([]);
  }

  const posStyles =
    position === 'bottom-left'
      ? { left: 20, bottom: 20 }
      : { right: 20, bottom: 20 };

  return (
    <div style={{ position: 'fixed', zIndex: 9999, ...posStyles }} aria-live="polite">
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open NAIA assistant"
          style={{
            ...buttonBase,
            padding: '12px 18px',
            borderRadius: 999,
            fontWeight: 600,
            boxShadow: '0 8px 20px rgba(15, 23, 42, 0.35)',
          }}
        >
          Ask NAIA
        </button>
      )}

      {open && (
        <div
          role="dialog"
          aria-label="NAIA assistant"
          aria-modal="true"
          style={{
            width: 360,
            maxWidth: 'calc(100vw - 32px)',
            height: 520,
            maxHeight: 'calc(100vh - 32px)',
            display: 'flex',
            flexDirection: 'column',
            background: '#0f172a',
            color: '#f1f5f9',
            border: '1px solid #1e293b',
            borderRadius: 14,
            overflow: 'hidden',
            boxShadow: '0 24px 48px rgba(15, 23, 42, 0.45)',
            fontFamily: 'inherit',
          }}
        >
          <header
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              background: '#1e293b',
              borderBottom: '1px solid #334155',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: 14 }}>NAIA Assistant</strong>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                {available === false
                  ? 'Unavailable'
                  : available === true
                  ? 'Ready'
                  : 'Connecting\u2026'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button type="button" onClick={handleClear} style={buttonGhost} title="Clear chat" aria-label="Clear chat history">
                Clear
              </button>
              <button type="button" onClick={() => setOpen(false)} style={buttonGhost} title="Close" aria-label="Close assistant">
                &times;
              </button>
            </div>
          </header>

          {available === false && (
            <div
              style={{
                padding: '10px 12px',
                fontSize: 12,
                color: '#fca5a5',
                background: '#1f1212',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>
                Assistant is unavailable.{unavailableReason ? ` ${unavailableReason}` : ''}
              </span>
              <button
                type="button"
                onClick={checkHealth}
                style={{
                  ...buttonGhost,
                  color: '#fca5a5',
                  borderColor: '#5f1d1d',
                  marginLeft: 8,
                  fontSize: 11,
                }}
                aria-label="Retry connection"
              >
                Retry
              </button>
            </div>
          )}

          <div
            ref={scrollerRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {messages.length === 0 && (
              <div style={{ fontSize: 13, color: '#94a3b8' }}>
                Ask a question about your translation, request a rephrase, or get a language tip.
              </div>
            )}
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} role={msg.role} text={msg.text} />
            ))}
            {pending && (
              <MessageBubble role="assistant" text="\u2026" pending />
            )}
          </div>

          <div
            style={{
              padding: 10,
              borderTop: '1px solid #1e293b',
              background: '#0b1220',
              display: 'flex',
              gap: 8,
            }}
          >
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask the assistant\u2026"
              rows={2}
              disabled={available === false || pending}
              aria-label="Type a message to the assistant"
              style={{
                flex: 1,
                resize: 'none',
                background: '#0f172a',
                color: '#f1f5f9',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: 8,
                fontFamily: 'inherit',
                fontSize: 13,
              }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={pending || available === false || !draft.trim()}
              aria-label="Send message"
              style={{
                ...buttonBase,
                padding: '0 14px',
                opacity: pending || available === false || !draft.trim() ? 0.5 : 1,
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ role, text, pending = false }) {
  const isUser = role === 'user';
  const isSystem = role === 'system';
  const bg = isUser ? '#2563eb' : isSystem ? '#3f1d1d' : '#1e293b';
  const align = isUser ? 'flex-end' : 'flex-start';
  return (
    <div style={{ alignSelf: align, maxWidth: '85%' }} role="log" aria-label={`${isUser ? 'You' : isSystem ? 'System' : 'NAIA'}: ${text}`}>
      <div
        style={{
          background: bg,
          color: '#f8fafc',
          padding: '8px 10px',
          borderRadius: 10,
          fontSize: 13,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          opacity: pending ? 0.7 : 1,
        }}
      >
        {text}
      </div>
    </div>
  );
}

const buttonBase = {
  background: '#2563eb',
  color: '#f8fafc',
  border: 'none',
  borderRadius: 8,
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 13,
};

const buttonGhost = {
  background: 'transparent',
  color: '#cbd5e1',
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '2px 8px',
  cursor: 'pointer',
  fontSize: 12,
};
