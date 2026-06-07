/**
 * MicPanel -- single mic orb with live HUD, voice meter, and status.
 */
import React from 'react';
import { Activity, Clock3, Mic, UserRound, Zap } from 'lucide-react';
import ThinkingIndicator from './ThinkingIndicator';

export default function MicPanel({
  micState, micLevel, perceivedListening, micLabel, micHint, micReady = true,
  handleMicClick, onStopListening, handleMicPointerDown, handleMicPointerUp,
  playing, processing, streaming, recording,
  liveHudMode, liveHudItems = [],
  statusTone, statusText, statusDetail, speakerSummary, timingLabel,
  onStatusToggle, showFriendlyStatus = true,
  audioReplayAvailable, autoPlayFailed, playTranslationAudio,
}) {
  return (
    <section
      className="mic-panel"
      data-tour-target="mic"
      aria-busy={processing && !streaming ? 'true' : undefined}
    >
      {/* Main orb */}
      <button
        className={`mic-orb ${micState} ${perceivedListening ? 'listening-pulse' : ''} ${!micReady ? 'unavailable' : ''}`}
        style={{ '--voice-level': Math.max(0.02, Math.min(1, micLevel || 0)) }}
        onClick={handleMicClick}
        onPointerDown={handleMicPointerDown || undefined}
        onPointerUp={handleMicPointerUp || undefined}
        onPointerCancel={handleMicPointerUp || undefined}
        onContextMenu={e => e.preventDefault()}
        disabled={!micReady}
        aria-pressed={streaming || recording}
        aria-label={micLabel}
        aria-live="polite"
        type="button"
      >
        <span className="voice-field" aria-hidden="true" />
        <span className="energy-rim" aria-hidden="true" />
        <span className="orb-ring" />
        <span className="orb-spin" />
        <MicGrille />
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

      {processing && !streaming && !playing && (
        <ThinkingIndicator stage="translating" message="Working on your translation…" className="mic-thinking" />
      )}

      {!perceivedListening && (
        <LiveHud mode={liveHudMode} items={liveHudItems} />
      )}

      {!perceivedListening && (streaming || recording) && <VoiceMeter micLevel={micLevel} />}

      {!perceivedListening ? (
        <StatusPanel
          tone={statusTone}
          text={statusText}
          detail={statusDetail}
          speakerSummary={speakerSummary}
          timingLabel={timingLabel}
          onToggle={onStatusToggle}
          showFriendlyStatus={showFriendlyStatus}
        />
      ) : (
        <>
          <div className="status-panel status-panel-live" data-tone="listening" aria-live="polite">
            <div className="status-primary">
              <Activity size={13} strokeWidth={2.6} aria-hidden="true" />
              <span>Live — speak anytime</span>
            </div>
          </div>
          {onStopListening && (
            <button type="button" className="stop-listening-btn" onClick={onStopListening}>
              Stop listening
            </button>
          )}
        </>
      )}

      {/* Replay fallback */}
      {audioReplayAvailable && autoPlayFailed && (
        <button className="neo-play-btn" type="button" onClick={playTranslationAudio} disabled={playing}>
          <Zap size={13} /> Play Voice
        </button>
      )}
    </section>
  );
}

function MicGrille() {
  return (
    <span className="mic-grille" aria-hidden="true">
      {Array.from({ length: 9 }, (_, i) => (
        <span key={i} />
      ))}
    </span>
  );
}

function LiveHud({ mode, items }) {
  return (
    <div className="live-hud" data-mode={String(mode||'').toLowerCase()} aria-label="Live state">
      <span className="live-mode-chip">{mode}</span>
      <div className="live-flow" aria-hidden="true">
        {items.map(item => (
          <span
            key={item.key}
            className={`live-flow-step${item.active ? ' active' : ''}${item.key === 'listen' ? ' listen-step' : ''}`}
            style={item.key === 'listen' ? { '--level': Math.max(0.08, Math.min(1, item.level || 0)) } : undefined}
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
  const level = Math.max(0, Math.min(1, micLevel || 0));
  return (
    <div className="voice-meter" style={{ '--voice-level': level }} aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => {
        const threshold = (i + 1) / 8;
        const active = level >= threshold * 0.6;
        return <span key={i} className={active ? 'active' : ''} />;
      })}
    </div>
  );
}

function StatusPanel({
  tone, text, detail, speakerSummary, timingLabel, onToggle, showFriendlyStatus,
}) {
  const hasMeta = Boolean(detail || speakerSummary || timingLabel);

  return (
    <button
      type="button"
      className="status-panel status-panel-btn"
      data-tone={tone}
      aria-live="polite"
      onClick={onToggle}
      title={showFriendlyStatus ? 'Tap for technical details' : 'Tap for simple status'}
      aria-label={`Status: ${text}. ${showFriendlyStatus ? 'Show technical details' : 'Show simple status'}`}
    >
      <div className="status-primary">
        <Activity size={13} strokeWidth={2.6} aria-hidden="true" />
        <span>{text}</span>
      </div>
      {hasMeta && (
        <div className="status-meta">
          {detail ? (
            <span>{detail}</span>
          ) : (
            <>
              {speakerSummary && <span><UserRound size={11} strokeWidth={2.5} />{speakerSummary}</span>}
              {timingLabel && <span><Clock3 size={11} strokeWidth={2.5} />{timingLabel}</span>}
            </>
          )}
        </div>
      )}
    </button>
  );
}
