/**
 * Shows whether lifelike Edge neural TTS is active or robotic fallback.
 */
import React from 'react';
import { Volume2, AlertTriangle } from 'lucide-react';

export default function NeuralVoiceBadge({ diagnostics, connectionStatus }) {
  const neural = diagnostics?.tts_neural;
  const ready = neural?.neural_ready === true;
  const offline = connectionStatus === 'offline';

  if (offline) {
    return (
      <div
        className="ailang-status-badge degraded"
        role="status"
        aria-label="Voice: offline"
        title="Bridge offline — start the server to hear neural voice"
      >
        <span className="ailang-status-icon"><AlertTriangle size={12} /></span>
        <span className="ailang-status-text">Voice: Offline</span>
      </div>
    );
  }

  if (!neural) {
    return (
      <div className="ailang-status-badge loading" role="status" aria-label="Voice: checking">
        <span className="ailang-status-icon"><Volume2 size={12} /></span>
        <span className="ailang-status-text">Voice</span>
      </div>
    );
  }

  if (ready) {
    return (
      <div
        className="ailang-status-badge active"
        role="status"
        aria-label="Neural voice ready"
        title="Microsoft Edge neural TTS — lifelike bridged speech"
      >
        <span className="ailang-status-icon"><Volume2 size={12} /></span>
        <span className="ailang-status-text">Neural Voice</span>
      </div>
    );
  }

  return (
    <div
      className="ailang-status-badge degraded"
      role="status"
      aria-label="Robotic voice fallback"
      title={(neural.issues || []).join(' ') || 'Install edge-tts and restart'}
    >
      <span className="ailang-status-icon"><AlertTriangle size={12} /></span>
      <span className="ailang-status-text">Robotic Voice</span>
    </div>
  );
}
