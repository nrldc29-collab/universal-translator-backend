/**
 * Map pipeline/debug status strings to user-friendly labels.
 * Product voice: Anai bridges real conversations — each person stays in their language.
 */

export function getFriendlyStatusLabel({
  statusText = '',
  connectionStatus = 'online',
  streaming = false,
  processing = false,
  playing = false,
  ttsPlaying = false,
}) {
  if (connectionStatus === 'checking') return 'Linking bridge…';
  if (connectionStatus === 'warming') return 'Opening the conversation bridge…';
  if (connectionStatus === 'offline') return 'Bridge offline';
  if (playing || ttsPlaying) return 'Bridging out loud';
  if (processing) return 'Understanding…';
  if (streaming) return 'Listening — speak in your voice';

  const raw = String(statusText || '').trim();
  if (!raw || raw === 'Idle') return 'Bridge ready';

  const lower = raw.toLowerCase();
  if (/listen|hear|record|vad|speech/.test(lower)) return 'Listening — speak in your voice';
  if (/translat|nmt|marian|llm|understand/.test(lower)) return 'Understanding…';
  if (/speak|play|tts|voice|audio|bridg/.test(lower)) return 'Bridging out loud';
  if (/connect|reconnect|websocket|ws|link/.test(lower)) return 'Linking bridge…';
  if (/process|queue|buffer/.test(lower)) return 'Working on meaning…';
  if (/offline|unreachable|failed/.test(lower)) return 'Bridge connection issue';
  if (/ready|idle|standby/.test(lower)) return 'Bridge ready';

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
    parts.push('Linking to your bridge server…');
  } else if (connectionStatus === 'warming') {
    parts.push('Warming up hear → understand → bridge…');
  } else if (connectionStatus !== 'online') {
    parts.push('Check bridge server in Settings');
  } else if (!streaming && !processing && !playing && !ttsPlaying) {
    parts.push('Tap the mic to open the bridge');
  }
  if (sourceLanguageLabel && targetLanguageLabel) {
    parts.push(`${sourceLanguageLabel} → ${targetLanguageLabel}`);
  }
  if (turnCount > 0) {
    parts.push(`${turnCount} exchange${turnCount === 1 ? '' : 's'}`);
  }
  if (timingLabel && !parts.some((p) => p.includes('ms'))) {
    parts.push(timingLabel);
  }
  return parts.join(' · ');
}
