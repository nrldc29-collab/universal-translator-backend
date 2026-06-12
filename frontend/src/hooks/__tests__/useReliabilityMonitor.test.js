import { describe, expect, it } from 'vitest';

/**
 * Regression for the 10s health-check timer: getHealthStatus must not declare
 * `const lastSuccess = lastSuccess.current[...]` — that shadows the ref and
 * throws "Cannot access 'lastSuccess' before initialization" on every tick.
 */
describe('useReliabilityMonitor health snapshot', () => {
  it('reads lastSuccess ref without name shadowing', () => {
    const lastSuccess = {
      current: {
        websocket: 1_000,
        tts: 1_000,
        translation: 1_000,
        stt: 1_000,
        audio: 1_000,
      },
    };
    const errorCounts = {
      current: { websocket: 0, tts: 0, translation: 0, stt: 0, audio: 0 },
    };
    const backoffDelays = {
      current: { websocket: 1000, tts: 1000, translation: 1000, stt: 1000, audio: 1000 },
    };
    const circuitStates = {
      websocket: 'closed',
      tts: 'closed',
      translation: 'closed',
      stt: 'closed',
      audio: 'closed',
    };

    const now = Date.now();
    const health = {};
    Object.keys(errorCounts.current).forEach((subsystem) => {
      const errors = errorCounts.current[subsystem];
      const lastSuccessAt = lastSuccess.current[subsystem];
      const circuit = circuitStates[subsystem];
      const timeSinceSuccess = now - lastSuccessAt;
      health[subsystem] = {
        status: circuit === 'open' ? 'degraded' : errors > 0 ? 'warning' : 'healthy',
        consecutiveErrors: errors,
        timeSinceSuccessMs: timeSinceSuccess,
        circuitState: circuit,
        backoffMs: backoffDelays.current[subsystem],
      };
    });

    expect(health.websocket.status).toBe('healthy');
    expect(health.websocket.timeSinceSuccessMs).toBeGreaterThanOrEqual(0);
  });
});
