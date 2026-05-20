/**
 * MicPanel — the central mic orb, live-state HUD, voice meter, status
 * card, and "Translating..." spinner.
 *
 * Pure presentation: all state and handlers come from the parent (App).
 * The component is split into small render helpers so the orb's 9-bar
 * grille and the voice meter don't clutter the main return.
 */

import React from 'react';
import { Activity, Clock3, Mic, UserRound } from 'lucide-react';

export default function MicPanel({
  // mic orb state
  micState,
  micLevel,
  perceivedListening,
  micLabel,
  micHint,
  // event handlers
  handleMicClick,
  handleMicPointerDown,
  handleMicPointerUp,
  // disabled flags
  playing,
  processing,
  streaming,
  recording,
  // live HUD
  liveHudMode,
  liveHudItems = [],
  // status row
  statusTone,
  statusText,
  speakerSummary,
  timingLabel,
  // play-voice fallback
  audioReplayAvailable,
  autoPlayFailed,
  playTranslationAudio,
}) {
  return (
    <section className="mic-panel">
      <button
        className={`mic-orb ${micState} ${perceivedListening ? 'listening-pulse' : ''}`}
        style={{ '--voice-level': Math.max(0.02, Math.min(1, micLevel || 0)) }}
        onClick={handleMicClick}
        onPointerDown={handleMicPointerDown}
        onPointerUp={handleMicPointerUp}
        onPointerCancel={handleMicPointerUp}
        onContextMenu={(event) => event.preventDefault()}
        disabled={playing || (processing && !streaming)}
        aria-label={micLabel}
        aria-live="polite"
      >
        <span className="voice-field" aria-hidden="true" />
        <span className="energy-rim" aria-hidden="true" />
        <span className="orb-ring" />
        <span className="orb-spin" />
        <MicGrille micLevel={micLevel} />
        <Mic className="mic-icon" size={62} strokeWidth={2.3} aria-hidden="true" />
        <span className="sr-only">{micLabel}</span>
        <span className="rec-led">
          <svg width="28" height="28" viewBox="0 0 28 28">
            <circle
              cx="14"
              cy="14"
              r="12"
              fill="#ef4444"
              filter="drop-shadow(0 0 6px rgba(239,68,68,.7))"
            />
            <circle cx="14" cy="14" r="5" fill="#ffffff" opacity="0.9" />
          </svg>
        </span>
      </button>
      <p className="mic-hint">{micHint}</p>
      <p className="mic-label">{micLabel}</p>
      <LiveHud mode={liveHudMode} items={liveHudItems} />
      {(streaming || recording) && <VoiceMeter micLevel={micLevel} />}
      <StatusPanel
        tone={statusTone}
        text={statusText}
        speakerSummary={speakerSummary}
        timingLabel={timingLabel}
      />
      {audioReplayAvailable && autoPlayFailed && (
        <button
          className="play-voice-button compact-voice-action"
          type="button"
          onClick={playTranslationAudio}
          disabled={playing}
        >
          Play Voice
        </button>
      )}
      {processing && !streaming && !playing && (
        <p className="thinking">Translating...</p>
      )}
    </section>
  );
}

function MicGrille({ micLevel }) {
  return (
    <span className="mic-grille" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => {
        const centerBoost = 1 - Math.abs(4 - i) * 0.1;
        const height = 22 + Math.max(0.02, micLevel || 0) * 70 * centerBoost;
        return (
          <span
            key={i}
            style={{ height: `${Math.min(92, height)}%`, '--delay': `${i * 38}ms` }}
          />
        );
      })}
    </span>
  );
}

function LiveHud({ mode, items }) {
  return (
    <div
      className="live-hud"
      data-mode={String(mode || '').toLowerCase()}
      aria-label="Live interpreter state"
    >
      <span className="live-mode-chip">{mode}</span>
      <div className="live-flow" aria-hidden="true">
        {items.map((item) => (
          <span
            key={item.key}
            className={`live-flow-step ${item.active ? 'active' : ''}`}
            style={
              item.key === 'listen'
                ? { '--level': Math.max(0.08, Math.min(1, item.level || 0)) }
                : undefined
            }
          >
            <item.Icon size={12} strokeWidth={2.6} aria-hidden="true" />
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
      {[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const threshold = (i + 1) / 8;
        const active = micLevel >= threshold * 0.6;
        const heightPx = Math.max(
          6,
          Math.min(28, 6 + micLevel * 28 * (i === 3 ? 1 : 0.65 + Math.abs(3 - i) * 0.08)),
        );
        return <span key={i} className={active ? 'active' : ''} style={{ height: heightPx }} />;
      })}
    </div>
  );
}

function StatusPanel({ tone, text, speakerSummary, timingLabel }) {
  return (
    <div className="status-panel" data-tone={tone} aria-live="polite">
      <div className="status-primary">
        <Activity size={14} strokeWidth={2.6} aria-hidden="true" />
        <span>{text}</span>
      </div>
      {(speakerSummary || timingLabel) && (
        <div className="status-meta" aria-label="Interpreter details">
          {speakerSummary && (
            <span>
              <UserRound size={12} strokeWidth={2.5} aria-hidden="true" />
              {speakerSummary}
            </span>
          )}
          {timingLabel && (
            <span>
              <Clock3 size={12} strokeWidth={2.5} aria-hidden="true" />
              {timingLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
