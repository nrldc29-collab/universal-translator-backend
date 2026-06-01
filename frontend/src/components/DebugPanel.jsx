/**
 * DebugPanel -- collapsible diagnostics view (connection, mic permission,
 * audio context, TTS state, CIP brain health, last error, build info).
 *
 * Currently rendered behind a `false &&` guard in main.jsx, but kept as
 * a real component so a future debug toggle can re-enable it without
 * resurrecting 120 lines of inline JSX. All readouts are pulled via
 * props from the App component.
 */

import React from 'react';

import { EXPERIMENTAL_IOS_STREAMING, isIosOrSafariRecorder } from '../utils';

export default function DebugPanel({
  onClose,
  loadDiagnostics,
  connectionStatus,
  micPermission,
  audioContextState,
  mobileAudioUnlocked,
  audioReplayAvailable,
  ttsQueueLength,
  ttsPlaying,
  pipelineStage,
  status,
  diagnosticsStatus,
  diagnostics,
  result,
  lastAudioError,
}) {
  const cip = diagnostics?.cip;
  const ailang = diagnostics?.ailang;
  const ailangConfig = ailang?.config;
  return (
    <section className="debug-panel">
      <div className="debug-header">
        <h3>Debug Panel</h3>
        <div className="debug-header-actions">
          <button type="button" className="debug-btn" onClick={loadDiagnostics}>Refresh</button>
          <button type="button" className="debug-btn close" onClick={onClose}>×</button>
        </div>
      </div>
      <div className="debug-grid">
        <DebugItem label="Connection:" value={connectionStatus} />
        <DebugItem label="Mic Permission:" value={micPermission} />
        <DebugItem label="Audio Context:" value={audioContextState} />
        <DebugItem label="Audio Unlocked:" value={mobileAudioUnlocked ? 'Yes' : 'No'} />
        <DebugItem label="Audio Replay:" value={audioReplayAvailable ? 'Yes' : 'No'} />
        <DebugItem label="TTS Queue:" value={ttsQueueLength} />
        <DebugItem label="TTS Playing:" value={ttsPlaying ? 'Yes' : 'No'} />
        <DebugItem label="Pipeline Stage:" value={pipelineStage} />
        <DebugItem label="Status:" value={status} />
        <DebugItem label="Backend Diagnostics:" value={diagnosticsStatus} />
        <DebugItem label="CIP Mode:" value={cip?.mode || '-'} />
        <DebugItem
          label="CIP Reachable:"
          value={cip ? (cip.reachable ? 'Yes' : 'No') : '-'}
          color={cip?.reachable ? '#86efac' : '#fca5a5'}
        />
        <DebugItem
          label="CIP Latency:"
          value={`${cip?.latency_ms ?? '-'}${cip?.latency_ms != null ? ' ms' : ''}`}
        />
        <DebugItem
          label="CIP OpenAI:"
          value={cip?.openai?.translator ? (cip.openai.translator.configured ? 'Configured' : 'Not configured') : '-'}
          color={cip?.openai?.translator?.configured ? '#86efac' : '#fca5a5'}
        />
        <DebugItem
          label="CIP Translator:"
          value={cip?.openai?.translator?.last || cip?.openai?.error || '-'}
        />
        <DebugItem
          label="CIP URL:"
          value={cip?.process_url || '-'}
          span
          color={cip?.process_url ? '#93c5fd' : undefined}
        />
        {cip?.error && (
          <DebugItem label="CIP Error:" value={cip.error} span color="#fca5a5" />
        )}
        <DebugItem
          label="AILang Enabled:"
          value={ailangConfig?.enabled ? 'Yes' : 'No'}
          color={ailangConfig?.enabled ? '#86efac' : '#fca5a5'}
        />
        <DebugItem
          label="AILang Sessions:"
          value={ailang?.active_sessions ?? '-'}
        />
        <DebugItem
          label="AILang Timeout:"
          value={`${ailangConfig?.agent_timeout ?? '-'}${ailangConfig?.agent_timeout != null ? 's' : ''}`}
        />
        <DebugItem
          label="AILang Cache TTL:"
          value={`${ailangConfig?.cache_ttl ?? '-'}${ailangConfig?.cache_ttl != null ? 's' : ''}`}
        />
        <DebugItem
          label="AILang Circuit Threshold:"
          value={ailangConfig?.circuit_failure_threshold ?? '-'}
        />
        <DebugItem
          label="AILang Bridge:"
          value={ailang?.bridge_stats ? 'Loaded' : 'Not loaded'}
          color={ailang?.bridge_stats ? '#86efac' : '#fca5a5'}
        />
        {result?.translated_by && (
          <DebugItem label="Translated by:" value={result.translated_by} />
        )}
        {result?.cip_decision && (
          <DebugItem
            label="CIP Decision:"
            value={JSON.stringify(result.cip_decision)}
            span
            color="#93c5fd"
          />
        )}
        {result?.ailang_metadata && (
          <DebugItem
            label="AILang Metadata:"
            value={JSON.stringify(result.ailang_metadata)}
            span
            color="#93c5fd"
          />
        )}
        {lastAudioError && (
          <DebugItem
            label="Last Error:"
            value={`${lastAudioError.type}: ${lastAudioError.name || ''} ${lastAudioError.message || ''}`}
            span
            color="#fca5a5"
          />
        )}
        <DebugItem label="Build:" value="ios-audio-fix-v3" span color="#86efac" />
        <DebugItem
          label="iOS path:"
          value={
            isIosOrSafariRecorder()
              ? EXPERIMENTAL_IOS_STREAMING
                ? 'WebSocket streaming (experimental)'
                : 'HTTP record-and-upload (no chunked WS)'
              : 'WebSocket streaming'
          }
          span
        />
      </div>
    </section>
  );
}

function DebugItem({ label, value, span = false, color }) {
  return (
    <div className={`debug-item${span ? ' span' : ''}`} data-color={color || undefined}>
      <span className="debug-label">{label}</span>
      <span className="debug-value">{value}</span>
    </div>
  );
}
