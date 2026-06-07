/**
 * Map pipeline/debug status strings to user-friendly labels.
 */

export function getFriendlyStatusLabel({
  statusText = '',
  connectionStatus = 'online',
  streaming = false,
  processing = false,
  playing = false,
  ttsPlaying = false,
}) {
  if (connectionStatus === 'checking') return 'Connecting to server…';
  if (connectionStatus === 'warming') return 'Starting translation engine…';
  if (connectionStatus === 'offline') return 'Server offline';
  if (playing || ttsPlaying) return 'Speaking translation';
  if (processing) return 'Translating…';
  if (streaming) return 'Listening';

  const raw = String(statusText || '').trim();
  if (!raw || raw === 'Idle') return 'Ready';

  const lower = raw.toLowerCase();
  if (/listen|hear|record|vad|speech/.test(lower)) return 'Listening';
  if (/translat|nmt|marian|llm/.test(lower)) return 'Translating…';
  if (/speak|play|tts|voice|audio/.test(lower)) return 'Speaking';
  if (/connect|reconnect|websocket|ws/.test(lower)) return 'Connecting…';
  if (/process|queue|buffer/.test(lower)) return 'Processing…';
  if (/offline|unreachable|failed/.test(lower)) return 'Connection issue';
  if (/ready|idle|standby/.test(lower)) return 'Ready';

  return raw.length > 42 ? `${raw.slice(0, 39)}…` : raw;
}

export function getFriendlyStatusDetail({
  connectionStatus,
  streaming,
  processing,
  playing,
  ttsPlaying,
  sourceLanguageLabel,
  targetLanguageLabel,
  turnCount = 0,
  timingLabel = '',
}) {
  const parts = [];
  if (connectionStatus === 'checking') {
    parts.push('Connecting to your translator server…');
  } else if (connectionStatus === 'warming') {
    parts.push('Warming up speech and translation models…');
  } else if (connectionStatus !== 'online') {
    parts.push('Check server connection in Settings');
  } else if (!streaming && !processing && !playing && !ttsPlaying) {
    parts.push('Tap the mic to begin');
  }
  if (sourceLanguageLabel && targetLanguageLabel) {
    parts.push(`${sourceLanguageLabel} → ${targetLanguageLabel}`);
  }
  if (turnCount > 0) {
    parts.push(`${turnCount} phrase${turnCount === 1 ? '' : 's'} translated`);
  }
  if (timingLabel && !parts.some((p) => p.includes('ms'))) {
    parts.push(timingLabel);
  }
  return parts.join(' · ');
}
