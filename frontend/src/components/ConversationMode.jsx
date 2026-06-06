/**
 * ConversationMode -- 10/10 automatic bidirectional live translation UI.
 */
import React, { useEffect, useRef, useCallback } from 'react';
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
          <div key={i}
            className={`conv-waveform-bar ${active ? 'active' : ''}`}
            style={{
              height: amplitude,
              background: active ? `rgba(99,102,241,${0.5 + level*0.5})` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}

// Animated waveform (CSS-only fallback when no mic level)
function CssWaveform({ active, color='#6366f1' }) {
  const speeds = [0.9,1.4,0.7,1.6,1.1,0.8,1.3];
  return (
    <div className="conv-waveform">
      {speeds.map((s,i)=>(
        <div key={i}
          className={`conv-waveform-bar ${active ? 'active' : ''}`}
          style={{
            background: active ? color : undefined,
            animation: active ? `wv${i%5} ${s}s ease-in-out infinite alternate` : 'none',
          }}
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
        <div key={i} className="conv-thinking-dot" style={{ animationDelay:`${i*0.15}s` }} />
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

      {/* Translation bubble */}
      {turn.translated_text && (
        <div className={`conv-bubble-translation ${speaker}`}>
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
      `[${t.speaker_label||'?'}] ${t.source_text}\n  → ${t.translated_text}`
    ).join('\n\n');
    navigator.clipboard?.writeText(text).catch(()=>{});
  }, [turns]);

  if (!turns.length) return null;

  return (
    <div className="conv-history">
      <div className="conv-history-header">
        <span className="conv-history-count">
          {turns.length} exchange{turns.length!==1?'s':''}
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
    idle:       { text: !backendReady ? 'Wait for LIVE' : active ? 'Starting…' : 'Tap to start', color:'#475569' },
    ready:      { text: 'Ready…',         color:'#34d399' },
    listening:  { text: 'Listening…',    color:'#34d399' },
    processing: { text: 'Translating…',  color:'#fbbf24' },
    speaking:   { text: 'Speaking…',     color:'#a78bfa' },
  }[phase] || { text:'', color:'#475569' };

  const glowColor = isSpeaking ? 'rgba(167,139,250,.08)'
                  : isListening ? 'rgba(52,211,153,.06)'
                  : 'transparent';

  return (
    <div className="conv-root">

      {/* Language pair + socket status */}
      <div className="conv-lang-bar">
        {[
          [sourceLanguage, sourceLanguageLabel],
          null,
          [targetLanguage, targetLanguageLabel],
        ].map((item, i) => {
          if (!item) return <span key="sep" className="conv-lang-sep">⇄</span>;
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
          <div
            className="conv-ambient-glow"
            style={{ background:`radial-gradient(ellipse 80% 60% at 50% 100%, ${glowColor}, transparent)` }}
          />
        )}

        {/* Mic button */}
        <button
          type="button"
          className={`conv-mic-btn ${active ? 'active' : ''} ${isListening ? 'listening' : ''}`}
          onClick={active ? stop : start}
          disabled={!active && !backendReady}
          aria-label={active ? 'Stop conversation' : 'Start auto conversation'}
        >
          {active ? '⏹' : '🎤'}
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
                    : <CssWaveform active={isListening} color={statusCfg.color} />
                  }
                  <span className="conv-status-text" style={{ color:statusCfg.color }}>
                    {statusCfg.text}
                  </span>
                  {micLevel > 0.05 && isListening
                    ? <LiveWaveform level={micLevel} active />
                    : <CssWaveform active={isListening} color={statusCfg.color} />
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

          {/* Live translation */}
          {liveTranslation && (
            <div className={`conv-live-translation ${isSpeaking ? 'speaking' : ''}`}>
              {isSpeaking && <span className="conv-note-icon">♪</span>}
              {liveTranslation}
            </div>
          )}

          {/* Idle hint */}
          {!active && (
            <p className="conv-idle-hint">
              One mic &mdash; speak naturally in <strong>{sourceLanguageLabel}</strong>{' '}
              or <strong>{targetLanguageLabel}</strong>.<br/>
              Auto-detects, translates, and speaks back.
            </p>
          )}
        </div>
      </div>

      {/* Conversation history */}
      <ConversationHistory turns={turns} onClear={clearTurns} />
    </div>
  );
}
