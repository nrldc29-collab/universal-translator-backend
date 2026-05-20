/**
 * useLatencyHistory — keep a rolling list of recent round-trip latency
 * measurements, persist it to `localStorage`, and expose the summary
 * (average / best).
 *
 * Returns `[latencyHistory, setLatencyHistory, summary]`:
 *  - `latencyHistory`: array of `{ total, backend, audio, created_at }`.
 *  - `setLatencyHistory`: setter (use a functional updater that appends
 *    a new entry and slices to `LATENCY_HISTORY_LIMIT`).
 *  - `summary`: `{ average, best }` recomputed from the current history.
 */

import { useEffect, useMemo, useState } from 'react';

import {
  LATENCY_HISTORY_KEY,
  LATENCY_HISTORY_LIMIT,
  readLatencyHistory,
  summarizeLatencyHistory,
} from '../utils';

export default function useLatencyHistory() {
  const [latencyHistory, setLatencyHistory] = useState(() => readLatencyHistory());

  useEffect(() => {
    try {
      localStorage.setItem(
        LATENCY_HISTORY_KEY,
        JSON.stringify(latencyHistory.slice(-LATENCY_HISTORY_LIMIT)),
      );
    } catch {
      /* ignore quota errors */
    }
  }, [latencyHistory]);

  const summary = useMemo(
    () => summarizeLatencyHistory(latencyHistory),
    [latencyHistory],
  );

  return [latencyHistory, setLatencyHistory, summary];
}
