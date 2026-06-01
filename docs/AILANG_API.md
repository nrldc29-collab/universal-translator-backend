# AILang API Documentation

The AILang (AI Language) pipeline provides advanced translation features through intelligent agents. This document describes the available API endpoints for configuring and monitoring the AILang pipeline.

## Overview

The AILang pipeline consists of 9 intelligent agents that enhance translation quality:

- **TranslationBrain**: Analyzes text for domain, formality, urgency, and model selection
- **ContextMemoryAgent**: Tracks speaker identity and pronouns across conversation turns
- **SpeakerProfilerAgent**: Learns each speaker's vocabulary level and speaking style
- **DialectAdapterAgent**: Adapts translations for regional language variants
- **GlossaryInjectorAgent**: Injects custom terminology from domain glossaries
- **AmbiguityResolverAgent**: Detects and resolves ambiguous phrases
- **ConfidenceFallbackAgent**: Escalates low-confidence translations to stronger models
- **BackTranslatorAgent**: Verifies translations through back-translation
- **EmotionTTS**: Preserves emotional tone in text-to-speech synthesis

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AILANG_ENABLED` | `true` | Enable/disable the entire AILang pipeline |
| `AILANG_AGENT_TIMEOUT` | `10.0` | Timeout in seconds for agent calls (1-60) |
| `AILANG_CACHE_TTL` | `300.0` | Cache TTL in seconds for agent responses (0-3600) |
| `AILANG_CIRCUIT_FAILURE_THRESHOLD` | `5` | Failures before circuit breaker opens (1-20) |
| `AILANG_CIRCUIT_RECOVERY_TIMEOUT` | `60.0` | Circuit breaker recovery timeout in seconds (10-600) |
| `AILANG_MAX_RETRIES` | `2` | Maximum retry attempts for failed agent calls (0-5) |
| `AILANG_ENABLED_AGENTS` | `""` | Comma-separated whitelist of enabled agents (empty = all) |
| `AILANG_DISABLED_AGENTS` | `""` | Comma-separated blacklist of disabled agents (empty = none) |

## API Endpoints

All AILang endpoints require authentication via API key or JWT token.

### Health & Statistics

#### GET `/ailang/health`

Returns the health status of the AILang bridge and pipeline.

**Response:**
```json
{
  "status": "healthy" | "unavailable" | "error",
  "bridge_loaded": true,
  "bridge_stats": { ... },
  "pipeline_enabled": true
}
```

#### GET `/ailang/stats`

Returns comprehensive statistics about the AILang pipeline including circuit breaker metrics.

**Response:**
```json
{
  "enabled": true,
  "active_sessions": 5,
  "bridge_stats": { ... },
  "circuit_breakers": {
    "TranslationBrain": {
      "state": "closed",
      "total_calls": 150,
      "success_rate": 0.95,
      "avg_latency_ms": 250.5
    },
    ...
  }
}
```

### Agent Configuration

#### GET `/ailang/agents`

Returns the enable/disable status of all AILang agents.

**Response:**
```json
{
  "TranslationBrain": true,
  "ContextMemoryAgent": true,
  "SpeakerProfilerAgent": true,
  "DialectAdapterAgent": true,
  "GlossaryInjectorAgent": true,
  "AmbiguityResolverAgent": true,
  "ConfidenceFallbackAgent": true,
  "BackTranslatorAgent": true,
  "EmotionTTS": true
}
```

#### POST `/ailang/agent/{agent_name}/enable`

Enables a specific AILang agent.

**Parameters:**
- `agent_name`: Name of the agent to enable (one of the 9 agent names)

**Response:**
```json
{
  "status": "ok",
  "agent": "SpeakerProfilerAgent",
  "enabled": true
}
```

**Rate Limit:** 20 requests per minute

#### POST `/ailang/agent/{agent_name}/disable`

Disables a specific AILang agent.

**Parameters:**
- `agent_name`: Name of the agent to disable

**Response:**
```json
{
  "status": "ok",
  "agent": "SpeakerProfilerAgent",
  "enabled": false
}
```

**Rate Limit:** 20 requests per minute

### Session Configuration

#### POST `/ailang/glossary`

Sets a custom glossary for terminology injection.

**Request Body:**
```json
{
  "glossary": [
    {"term": "myocardial infarction", "translation": "heart attack"},
    {"term": "hypertension", "translation": "high blood pressure"}
  ],
  "session_id": "default"
}
```

**Response:**
```json
{
  "status": "ok",
  "session_id": "default",
  "glossary_terms": 2
}
```

**Rate Limit:** 10 requests per minute

#### POST `/ailang/dialect`

Sets dialect preference for regional language adaptation.

**Request Body:**
```json
{
  "dialect": "es-MX",
  "session_id": "default"
}
```

**Response:**
```json
{
  "status": "ok",
  "session_id": "default",
  "dialect": "es-MX"
}
```

**Rate Limit:** 10 requests per minute

#### POST `/ailang/speaker`

Sets the current speaker for context tracking.

**Request Body:**
```json
{
  "speaker": "Doctor",
  "session_id": "default"
}
```

**Response:**
```json
{
  "status": "ok",
  "session_id": "default",
  "speaker": "Doctor"
}
```

**Rate Limit:** 10 requests per minute

## Circuit Breaker Pattern

The AILang pipeline uses a circuit breaker pattern to prevent cascading failures:

- **CLOSED**: Normal operation, all requests allowed
- **OPEN**: Circuit is open after failure threshold, requests rejected
- **HALF_OPEN**: Testing if service has recovered, allows limited requests

When an agent fails repeatedly (default: 5 failures), the circuit breaker opens and rejects calls for the recovery timeout (default: 60 seconds). This prevents cascading failures and allows the service to recover.

## Response Caching

Expensive agent calls (e.g., SpeakerProfilerAgent) are cached with a configurable TTL (default: 5 minutes). Cache keys are generated based on agent name and input parameters. The cache automatically cleans up old entries when it exceeds 1000 entries.

## Retry Logic

Failed agent calls are automatically retried with exponential backoff:
- Attempt 1: Immediate
- Attempt 2: 100ms delay
- Attempt 3: 200ms delay
- Attempt 4: 400ms delay

The maximum number of retries is configurable (default: 2).

## Timeout Configuration

All agent calls have a configurable timeout (default: 10 seconds). If an agent call exceeds the timeout, it's cancelled and treated as a failure, triggering the retry logic and circuit breaker.

## Diagnostics

AILang status is included in the `/diagnostics` endpoint under the `ailang` key:

```json
{
  "ailang": {
    "enabled": true,
    "active_sessions": 5,
    "bridge_stats": { ... },
    "circuit_breakers": { ... },
    "config": {
      "enabled": true,
      "agent_timeout": 10.0,
      "cache_ttl": 300.0,
      "circuit_failure_threshold": 5,
      "circuit_recovery_timeout": 60.0,
      "max_retries": 2,
      "enabled_agents": "",
      "disabled_agents": ""
    }
  }
}
```

## Frontend Debug Panel

The frontend Debug Panel displays AILang status when debug mode is enabled:
- AILang Enabled status
- Active session count
- Agent timeout
- Cache TTL
- Circuit breaker threshold
- Bridge loaded status
- AILang metadata from translation results

## Error Handling

All AILang endpoints return standard error responses:

```json
{
  "status": "error",
  "message": "AILang pipeline not available"
}
```

Rate limit errors return HTTP 429 with:
```json
{
  "detail": "Rate limit exceeded: 10 per 1 minute"
}
```
