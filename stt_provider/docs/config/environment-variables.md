# Environment Variable Reference

## Core app

| Variable | Required | Example | Description |
|---|---|---|---|
| `ENV` | Yes | `production` | Runtime environment. Use `dev`, `staging`, or `production`. |
| `STT_API_KEY` | Yes outside dev | `replace-me` | Legacy single API key. Must not default to `dev-secret-key`. |
| `STT_BACKEND` | Yes | `triton` | Active backend. Use `triton` for self-hosted or `whisper` for fallback. |
| `LOG_LEVEL` | No | `INFO` | Application log level. |
| `REGION` | Yes in production | `us-east-1` | Region where this gateway instance is running. Used for tenant home-region enforcement. |

## Triton backend

| Variable | Required | Example | Description |
|---|---|---|---|
| `TRITON_GRPC_URL` | Yes | `triton-parakeet.stt.svc.cluster.local:8001` | Internal Triton gRPC endpoint. |
| `TRITON_ASR_MODEL` | Yes | `parakeet-tdt-streaming` | ASR model name loaded in Triton. |
| `TRITON_DIARIZATION_MODEL` | Yes | `diar_streaming_sortformer_4spk-v2` | Streaming diarization model name loaded in Triton. |
| `TRITON_REQUEST_TIMEOUT_MS` | No | `5000` | Gateway timeout for Triton requests. |

## Postgres

| Variable | Required | Example | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://user:pass@host:5432/stt` | Durable state database for tenants, API keys, usage, and audit logs. |
| `DATABASE_POOL_MIN_SIZE` | No | `2` | Minimum DB connections. |
| `DATABASE_POOL_MAX_SIZE` | No | `20` | Maximum DB connections. |

## Redis

| Variable | Required | Example | Description |
|---|---|---|---|
| `REDIS_URL` | Yes | `redis://redis.stt.svc.cluster.local:6379/0` | Ephemeral counters and rate-limit state. |
| `REDIS_KEY_PREFIX` | No | `stt:` | Prefix for runtime Redis keys. |

## Observability

| Variable | Required | Example | Description |
|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Yes in production | `https://otel-collector.example.com` | OpenTelemetry collector endpoint. |
| `TRACE_ID_HEADER` | No | `X-Trace-Id` | Response/request trace header name. |
| `METRICS_ENABLED` | No | `true` | Enables Prometheus metrics endpoint. |

## Security

| Variable | Required | Example | Description |
|---|---|---|---|
| `REQUIRE_TLS` | Yes in production | `true` | Production must require TLS at ingress. |
| `REQUIRE_MTLS` | No | `false` | Enable for enterprise/private connectivity. |
| `API_KEY_HASH_SECRET` | Yes in production | `replace-me` | Secret used when hashing or verifying API keys. |
| `SPEAKER_EMBEDDING_ENCRYPTION_KEY` | Yes for speaker enrollment | `generated-fernet-key` | Key used to encrypt speaker voice embeddings before storage. |

## Session limits

| Variable | Required | Example | Description |
|---|---|---|---|
| `MAX_SESSION_SECONDS` | Yes | `3600` | Maximum WebSocket session duration. |
| `MAX_CONCURRENT_STREAMS_PER_TENANT` | Yes | `100` | Default active-stream limit per tenant. |
| `TRANSCRIPTION_RATE_LIMIT_PER_MINUTE` | Yes | `30` | REST transcription rate limit per API key. |
| `ADMIN_RATE_LIMIT_PER_MINUTE` | Yes | `5` | Admin route rate limit per API key. |

This consolidates the configuration needed for the self-hosted path: explicit API keys, Triton routing, Postgres state, Redis counters, observability, TLS/mTLS, and session limits.
