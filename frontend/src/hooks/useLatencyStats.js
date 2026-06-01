import { useState } from 'react';
import useLatencyHistory from './useLatencyHistory';
import {
  blankLatencyStats,
  formatLatencyValue,
  LATENCY_HISTORY_LIMIT,
} from '../utils';

export function useLatencyStats() {
  const [latencyStats, setLatencyStats] = useState(() => blankLatencyStats());
  const [latencyHistory, setLatencyHistory, latencySummary] = useLatencyHistory();

  function updateLatency(metric, ms) {
    setLatencyStats((current) => ({ ...current, [metric]: formatLatencyValue(ms) }));
  }

  function recordLatencyTurn(entry) {
    if (!Number.isFinite(entry.total) || entry.total <= 0) return;
    setLatencyHistory((current) => [
      ...current,
      {
        total: Math.round(entry.total),
        backend: Number.isFinite(entry.backend) ? Math.round(entry.backend) : null,
        audio: Number.isFinite(entry.audio) ? Math.round(entry.audio) : null,
        created_at: Date.now(),
      },
    ].slice(-LATENCY_HISTORY_LIMIT));
  }

  return {
    latencyStats,
    setLatencyStats,
    latencyHistory,
    setLatencyHistory,
    latencySummary,
    updateLatency,
    recordLatencyTurn,
  };
}
