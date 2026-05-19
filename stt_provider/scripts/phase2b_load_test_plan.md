# Phase 2B Load Test and Cutover Plan

## Target

Validate the self-hosted streaming STT stack before production rollout.

## Load test

Run a 12-hour soak test with:

- 200 concurrent WebSocket streams
- Realistic PCM-16LE audio chunks
- Rolling gateway restarts during active sessions
- Rolling Triton pod restarts during active sessions
- Redis active-connection counters enabled
- Prometheus metrics enabled

## Metrics to capture

- P50 time-to-first-partial
- P95 time-to-first-partial
- P50 time-between-partials
- P95 time-between-partials
- Final transcript latency
- WebSocket disconnect rate
- Triton inference queue duration
- GPU utilization
- GPU memory utilization
- Redis counter accuracy
- Gateway restart recovery behavior

## Pass criteria

- 12-hour test completes without uncontrolled outage.
- Rolling gateway restarts do not drop active sessions.
- Triton remains available with at least 2 replicas.
- P95 time-to-first-partial stays under 700 ms.
- P95 time-between-partials stays under 700 ms.
- Disconnect rate stays below 1%.
- Redis active connection counters return to zero after test completion.

## Cutover plan

1. Keep the Whisper backend enabled as fallback.
2. Enable self-hosted Triton backend for internal test tenants.
3. Roll out to 10% of low-risk tenants.
4. Hold for 24 hours and compare against Phase 1 baseline.
5. Roll out to 25%.
6. Roll out to 50%.
7. Roll out to 100%.
8. Keep Whisper fallback live during the full ramp.
9. Remove fallback only after production metrics are stable.

This implements Phase 2B, Step 7: run a 200-stream, 12-hour soak test, validate rolling restarts, compare against the Phase 1 baseline, and roll out per tenant tier while keeping Whisper as fallback.
