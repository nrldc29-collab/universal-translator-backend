/**
 * MicPanel -- single mic orb with live HUD, voice meter, and status.
 */
import React from 'react';
import { Activity, Clock3, Mic, UserRound, Zap } from 'lucide-react';

export default function MicPanel({
  micState, micLevel, perceivedListening, micLabel, micHint, micReady = true,
  handleMicClick, handleMicPointerDown, handleMicPointerUp,
  playing, processing, streaming, recording,
  liveHudMode, liveHudItems = [],
  statusTone, statusText, speakerSummary, timingLabel,
  audioReplayAvailable, autoPlayFailed, playTranslationAudio,
}) {
  return (
    <section className="mic-panel">
      {/* Main orb */}
      <button
        className={`mic-orb ${micState} ${perceivedListening ? 'listening-pulse' : ''}`}
        style={{ '--voice-level': Math.max(0.02, Math.min(1, micLevel || 0)) }}
        onClick={handleMicClick}
        onPointerDown={handleMicPointerDown}
        onPointerUp={handleMicPointerUp}
        onPointerCancel={handleMicPointerUp}
        onContextMenu={e => e.preventDefault()}
        disabled={!micReady || playing || (processing && !streaming)}
        aria-label={micLabel}
        aria-live="polite"
        type="button"
      >
        <span className="voice-field" aria-hidden="true" />
        <span className="energy-rim" aria-hidden="true" />
        <span className="orb-ring" />
        <span className="orb-spin" />
        <MicGrille micLevel={micLevel} />
        <Mic className="mic-icon" size={58} strokeWidth={2.2} aria-hidden="true" />
        {perceivedListening && (
          <span className="rec-led" aria-hidden="true">
            <svg width="26" height="26" viewBox="0 0 26 26">
              <circle cx="13" cy="13" r="11" fill="#ef4444" filter="drop-shadow(0 0 6px rgba(239,68,68,.8))" />
              <circle cx="13" cy="13" r="4.5" fill="#fff" opacity=".9" />
            </svg>
          </span>
        )}
      </button>

      {/* Label + hint */}
      <p className="mic-label">{micLabel}</p>
      <p className="mic-hint">{micHint}</p>

      {/* Live HUD */}
      <LiveHud mode={liveHudMode} items={liveHudItems} />

      {/* Voice meter */}
      {(streaming || recording) && <VoiceMeter micLevel={micLevel} />}

      {/* Status */}
      <StatusPanel tone={statusTone} text={statusText} speakerSummary={speakerSummary} timingLabel={timingLabel} />

      {/* Replay fallback */}
      {audioReplayAvailable && autoPlayFailed && (
        <button className="neo-play-btn" type="button" onClick={playTranslationAudio} disabled={playing}>
          <Zap size={13} /> Play Voice
        </button>
      )}
    </section>
  );
}

function MicGrille({ micLevel }) {
  return (
    <span className="mic-grille" aria-hidden="true">
      {[0,1,2,3,4,5,6,7,8].map(i => {
        const boost = 1 - Math.abs(4-i) * 0.1;
        const h = 22 + Math.max(0.02, micLevel||0) * 70 * boost;
        return <span key={i} style={{ height:`${Math.min(92,h)}%`, '--delay':`${i*38}ms` }} />;
      })}
    </span>
  );
}

function LiveHud({ mode, items }) {
  return (
    <div className="live-hud" data-mode={String(mode||'').toLowerCase()} aria-label="Live state">
      <span className="live-mode-chip">{mode}</span>
      <div className="live-flow" aria-hidden="true">
        {items.map(item => (
          <span key={item.key}
            className={`live-flow-step ${item.active ? 'active' : ''}`}
            style={item.key==='listen' ? { '--level': Math.max(0.08, Math.min(1, item.level||0)) } : undefined}
          >
            <item.Icon size={11} strokeWidth={2.6} aria-hidden="true" />
            <b>{item.label}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function VoiceMeter({ micLevel }) {
  return (
    <div className="voice-meter" aria-hidden="true">
      {[0,1,2,3,4,5,6].map(i => {
        const threshold = (i+1)/8;
        const active = micLevel >= threshold * 0.6;
        const h = Math.max(6, Math.min(28, 6 + micLevel*28*(i===3?1:0.65+Math.abs(3-i)*0.08)));
        return <span key={i} className={active?'active':''} style={{ height:h }} />;
      })}
    </div>
  );
}

function StatusPanel({ tone, text, speakerSummary, timingLabel }) {
  return (
    <div className="status-panel" data-tone={tone} aria-live="polite">
      <div className="status-primary">
        <Activity size={13} strokeWidth={2.6} aria-hidden="true" />
        <span>{text}</span>
      </div>
      {(speakerSummary || timingLabel) && (
        <div className="status-meta">
          {speakerSummary && <span><UserRound size={11} strokeWidth={2.5} />{speakerSummary}</span>}
          {timingLabel && <span><Clock3 size={11} strokeWidth={2.5} />{timingLabel}</span>}
        </div>
      )}
    </div>
  );
}
