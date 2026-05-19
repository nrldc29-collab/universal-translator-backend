# Streaming STT Alert Rules Spec

## Goal

Define the production alerts required to operate the self-hosted streaming STT platform safely.

## Critical alerts

### High streaming latency

Trigger when:

```text
p95_time_to_first_partial_ms > 700 for 30 minutes
```

Severity:

SEV-2

Action:

- Check gateway latency.
- Check Triton inference queue duration.
- Check GPU utilization.
- Roll back affected tenants to Whisper if latency does not recover.

### High WebSocket disconnect rate

Trigger when:

```text
websocket_disconnect_rate > 1% for 15 minutes
```

Severity:

SEV-2

Action:

- Check gateway restarts.
- Check ingress errors.
- Check connection draining behavior.
- Check Redis active connection counters.

### Triton inference queue elevated

Trigger when:

```text
avg(nv_inference_queue_duration_us) > 5000 for 15 minutes
```

Severity:

SEV-2

Action:

- Check Triton pod health.
- Check GPU saturation.
- Check KEDA scaling.
- Add GPU capacity or roll back affected tenants.

### Triton pod crash loop

Trigger when:

```text
kube_pod_container_status_restarts_total increases repeatedly for triton-parakeet
```

Severity:

SEV-1

Action:

- Stop rollout.
- Route affected tenants to Whisper fallback.
- Check model repository, GPU availability, and Triton logs.

### GPU saturation

Trigger when:

```text
gpu_utilization > 95% for 20 minutes
```

Severity:

SEV-2

Action:

- Check active streams.
- Check Triton queue duration.
- Confirm autoscaling has headroom.
- Add capacity or roll back affected tenants.

### Redis unavailable

Trigger when:

```text
redis_up == 0 for 5 minutes
```

Severity:

SEV-2

Action:

- Check managed Redis failover.
- Confirm active connection counters recover.
- Confirm rate limiting fails safely.

### Postgres unavailable

Trigger when:

```text
postgres_up == 0 for 5 minutes
```

Severity:

SEV-1

Action:

- Stop rollout.
- Check managed Postgres failover.
- Confirm usage counters and audit logs resume.
- Update status page if customer-visible.

### Audit-log writes failing

Trigger when:

```text
audit_log_write_failures > 0 for 10 minutes
```

Severity:

SEV-2

Action:

- Check Postgres write path.
- Check schema migrations.
- Pause admin actions if auditability is compromised.

### Usage-counter writes failing

Trigger when:

```text
usage_counter_write_failures > 0 for 10 minutes
```

Severity:

SEV-3

Action:

- Check Postgres write path.
- Check usage-counter queue or retry logic.
- Reconcile usage after recovery.

## Acceptance checks

- All critical alerts exist in the observability tool.
- SEV-1 and SEV-2 alerts page on-call.
- SEV-3 alerts create tickets or lower-priority notifications.
- Alert descriptions include rollback guidance.
- Alerts distinguish gateway, Triton, Redis, Postgres, and GPU failures.
