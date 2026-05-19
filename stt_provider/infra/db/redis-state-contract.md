# Redis State Contract

Redis stores ephemeral runtime state only.

## Keys

### Active WebSocket connections per pod

```text
pod:{pod_name}:active_connections
```

Increment on WebSocket connect.
Decrement on WebSocket disconnect.
Set an expiry as a safety net.

### Active WebSocket connections per tenant

```text
tenant:{tenant_id}:active_connections
```

Increment on WebSocket connect.
Decrement on WebSocket disconnect.
Used for per-tenant limits and autoscaling signals.

### Per-tenant rate limits

```text
tenant:{tenant_id}:rate:{operation}:{window}
```

Increment per operation.
Expire at the end of the rate-limit window.
Operations include `stt_stream`, `stt_transcribe`, and `admin`.
