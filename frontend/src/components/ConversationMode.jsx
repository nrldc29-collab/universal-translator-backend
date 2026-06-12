/**
 * ConversationMode — automatic bidirectional conversation bridge UI.
 */
import React, { useEffect, useRef, useCallback } from 'react';
import { Mic, Square } from 'lucide-react';
import { useAutoConversation } from '../hooks/useAutoConversation';

const LANG_FLAG = { en:'🇺🇸',es:'🇪🇸',fr:'🇫🇷',de:'🇩🇪',it:'🇮🇹',pt:'🇧🇷',zh:'🇨🇳',ja:'🇯🇵',ko:'🇰🇷',ar:'🇸🇦',ru:'🇷🇺',hi:'🇮🇳',ht:'🇭🇹',nl:'🇳🇱' };
const LANG_NAME = { en:'English',es:'Spanish',fr:'French',de:'German',it:'Italian',pt:'Portuguese',zh:'Chinese',ja:'Japanese',ko:'Korean',ar:'Arabic',ru:'Russian',hi:'Hindi',ht:'Haitian Creole',nl:'Dutch' };

// Real mic-level waveform using live data
function LiveWaveform({ level = 0, active = false }) {
  const bars = 7;
  return (
    <div className="conv-waveform">
      {Array.from({length:bars},(_,i)=>{
        const center = (bars-1)/2;
        const dist = Math.abs(i - center) / center;
        const base = 4;
        const amplitude = active ? Math.max(base, level * 28 * (1 - dist * 0.4) * (0.7 + Math.sin(Date.now()/200 + i)*0.3)) : base;
        return (
          <div
            key={i}
            className={`conv-waveform-bar live ${active ? 'active' : ''}`}
            style={{
              '--bar-h': `${amplitude}px`,
              '--bar-opacity': level,
            }}
          />
        );
      })}
    </div>
  );
}

// Animated waveform (CSS-only fallback when no mic level)
function CssWaveform({ active }) {
  return (
    <div className="conv-waveform">
      {Array.from({ length: 7 }, (_, i) => (
        <div
          key={i}
          className={`conv-waveform-bar css-wave ${active ? 'active' : ''}`}
        />
      ))}
    </div>
  );
}

// Language detection pill
function DetectedLang({ lang, phase }) {
  if (!lang) return null;
  const isActive = phase === 'listening';
  return (
    <div className={`conv-detected-lang ${isActive ? 'active' : ''}`}>
      <span className="conv-detected-flag">{LANG_FLAG[lang]||'🌐'}</span>
      {LANG_NAME[lang]||lang} detected
    </div>
  );
}

// Processing dots
function ThinkingDots() {
  return (
    <div className="conv-thinking-dots">
      {[0,1,2].map(i => (
        <div key={i} className="conv-thinking-dot" />
      ))}
    </div>
  );
}

// Conversation bubble with copy button
function Bubble({ turn, isLatest }) {
  const isA = turn.conversationSpeaker === 'A';
  const time = turn.timestamp
    ? new Date(turn.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
    : '';

  const speaker = isA ? 'a' : 'b';
  return (
    <div className={`conv-bubble-wrap ${speaker} ${isLatest ? 'latest' : ''}`}>
      {/* Speaker row */}
      <div className={`conv-bubble-meta ${speaker}`}>
        <span className="conv-bubble-flag">{LANG_FLAG[isA?turn.srcLang:turn.tgtLang]||''}</span>
        <span className="conv-bubble-speaker">{turn.speaker_label||(isA?'Person 1':'Person 2')}</span>
        {time && <span className="conv-bubble-time">{time}</span>}
      </div>

      {/* Source bubble */}
      {turn.source_text && (
        <div className={`conv-bubble-source ${speaker}`}>
          {turn.source_text}
        </div>
      )}

      {/* Bridged meaning */}
      {turn.source_text && turn.translated_text && (
        <div className={`conv-bubble-bridge ${speaker}`} aria-hidden="true">
          <span className="conv-bubble-bridge-line" />
          <span className="conv-bubble-bridge-hub">⬡</span>
          <span className="conv-bubble-bridge-line" />
        </div>
      )}
      {turn.translated_text && (
        <div className={`conv-bubble-bridged ${speaker}`}>
          {turn.translated_text}
        </div>
      )}
    </div>
  );
}

// Conversation history panel
function ConversationHistory({ turns, onClear }) {
  const scrollRef = useRef(null);
  const prevLen = useRef(0);

  useEffect(() => {
    if (turns.length > prevLen.current && scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior:'smooth' });
    }
    prevLen.current = turns.length;
  }, [turns.length]);

  // Copy all turns to clipboard
  const copyAll = useCallback(() => {
    const text = turns.map(t =>
      `[${t.speaker_label||'?'}] ${t.source_text}\n  ⬡ ${t.translated_text}`
    ).join('\n\n');
    navigator.clipboard?.writeText(text).catch(()=>{});
  }, [turns]);

  if (!turns.length) return null;

  return (
    <div className="conv-history">
      <div className="conv-history-header">
        <span className="conv-history-count">
          {turns.length} bridge exchange{turns.length!==1?'s':''}
        </span>
        <div className="conv-history-actions">
          <button type="button" className="conv-ghost-btn" onClick={copyAll} title="Copy conversation">Copy</button>
          <button type="button" className="conv-ghost-btn" onClick={onClear}>Clear</button>
        </div>
      </div>
      <div ref={scrollRef} className="conv-history-scroll">
        {turns.map((t, i) => (
          <Bubble key={`${t.timestamp||i}-${i}`} turn={t} isLatest={i===turns.length-1} />
        ))}
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────
export default function ConversationMode({
  wsAudioUrl, authToken, withAuthToken,
  sourceLanguage, targetLanguage,
  sessionId, deviceId,
  sourceLanguageLabel, targetLanguageLabel,
  connectionStatus = 'checking',
  onStatus,
}) {
  const backendReady = connectionStatus === 'online';
  const {
    active, phase, detectedLang, turns,
    liveText, liveTranslation,
    sockStatus, micLevel,
    start, stop, clearTurns,
  } = useAutoConversation({
    wsAudioUrl,
    authToken,
    sourceLanguage,
    targetLanguage,
    sessionId,
    deviceId,
    withAuthToken,
    backendReady,
    onStatus,
  });

  useEffect(() => () => stop(), []);

  const srcFlag = LANG_FLAG[sourceLanguage]||'🌐';
  const tgtFlag = LANG_FLAG[targetLanguage]||'🌐';
  const isListening  = phase==='listening' || phase==='ready';
  const isProcessing = phase==='processing';
  const isSpeaking   = phase==='speaking';

  const statusCfg = {
    idle:       { text: !backendReady ? 'Link bridge to begin' : active ? 'Opening bridge…' : 'Tap to open bridge' },
    ready:      { text: 'Ready…' },
    listening:  { text: 'Listening — speak in your voice' },
    processing: { text: 'Understanding…' },
    speaking:   { text: 'Bridging out loud…' },
  }[phase] || { text: '' };

  return (
    <div className="conv-root" data-phase={phase}>

      {/* Language pair + socket status */}
      <div className="conv-lang-bar">
        {[
          [sourceLanguage, sourceLanguageLabel],
          null,
          [targetLanguage, targetLanguageLabel],
        ].map((item, i) => {
          if (!item) return <span key="sep" className="conv-lang-sep conv-lang-bridge">⬡</span>;
          const [code, label] = item;
          const isActive = active && detectedLang === code;
          return (
            <span key={code} className={`conv-lang-item ${isActive ? 'active' : ''}`}>
              {LANG_FLAG[code]||'🌐'} {label}
            </span>
          );
        })}
        {active && (
          <div
            className={`conv-sock-dot ${sockStatus}`}
            title={sockStatus}
          />
        )}
      </div>

      {/* Main panel */}
      <div className={`conv-main-panel ${active ? 'active' : ''}`}>
        {/* Ambient glow */}
        {active && (
          <div className="conv-ambient-glow" data-phase={phase} aria-hidden="true" />
        )}

        {/* Mic button */}
        <button
          type="button"
          className={`conv-mic-btn ${active ? 'active' : ''} ${isListening ? 'listening' : ''}`}
          onClick={active ? stop : start}
          disabled={!active && !backendReady}
          aria-label={active ? 'Pause conversation bridge' : 'Open conversation bridge'}
        >
          {active ? (
            <Square size={26} strokeWidth={2.4} fill="currentColor" aria-hidden="true" />
          ) : (
            <Mic size={30} strokeWidth={2.2} aria-hidden="true" />
          )}
        </button>

        {/* State area */}
        <div className="conv-state-area">
          {/* Status row */}
          <div className="conv-status-row">
            {isProcessing
              ? <ThinkingDots />
              : (
                <>
                  {micLevel > 0.05 && isListening
                    ? <LiveWaveform level={micLevel} active />
                    : <CssWaveform active={isListening} />
                  }
                  <span className="conv-status-text" data-phase={phase}>
                    {statusCfg.text}
                  </span>
                  {micLevel > 0.05 && isListening
                    ? <LiveWaveform level={micLevel} active />
                    : <CssWaveform active={isListening} />
                  }
                </>
              )
            }
          </div>

          {/* Detected language */}
          {active && detectedLang && (
            <DetectedLang lang={detectedLang} phase={phase} />
          )}

          {/* Live transcript */}
          {liveText && (
            <div className="conv-live-text">&ldquo;{liveText}&rdquo;</div>
          )}

          {/* Live bridged meaning */}
          {liveTranslation && (
            <div className={`conv-live-bridged ${isSpeaking ? 'speaking' : ''}`}>
              {isSpeaking && <span className="conv-note-icon">♪</span>}
              {liveTranslation}
            </div>
          )}

          {/* Idle hint */}
          {!active && (
            <p className="conv-idle-hint">
              One mic &mdash; speak naturally in <strong>{sourceLanguageLabel}</strong>{' '}
              or <strong>{targetLanguageLabel}</strong>.<br/>
              Anai hears, understands, and bridges meaning both ways.
            </p>
          )}
        </div>
      </div>

      {/* Conversation history */}
      <ConversationHistory turns={turns} onClear={clearTurns} />
    </div>
  );
}
