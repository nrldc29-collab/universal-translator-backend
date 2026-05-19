# STT Provider Capacity and Performance Sizing

This document provides guidance for sizing and scaling the streaming STT provider service in production environments.

## System Requirements

### Minimum (Development)
- CPU: 2 cores
- RAM: 4 GB
- Storage: 10 GB
- Network: 100 Mbps

### Recommended (Production)
- CPU: 4+ cores
- RAM: 8+ GB
- Storage: 50 GB SSD
- Network: 1 Gbps

## Model Performance Characteristics

### Whisper Model Sizes

| Model | Size (MB) | RAM (GB) | RTF (Real-Time Factor) | Use Case |
|-------|-----------|----------|------------------------|----------|
| tiny | 39 | ~1 GB | 0.3x | Ultra-low latency, lower accuracy |
| base | 74 | ~1.5 GB | 0.5x | Balanced latency and accuracy |
| small | 244 | ~2 GB | 0.8x | Higher accuracy |
| medium | 769 | ~5 GB | 1.2x | High accuracy, slower |

**RTF (Real-Time Factor)**: Time to process audio relative to audio duration. RTF < 1.0 means faster than real-time.

## Connection Limits

### Default Configuration
- `MAX_ACTIVE_CONNECTIONS`: 10 (total)
- `MAX_CONNECTIONS_PER_KEY`: 3 (per API key)
- `MAX_SESSION_SECONDS`: 1800 (30 minutes per session)
- `IDLE_TIMEOUT_SECONDS`: 60 (disconnect after 60s idle)

### Scaling Guidelines

**Per Core Capacity (CPU-based Whisper)**
- tiny model: 3-5 concurrent streams
- base model: 2-3 concurrent streams
- small model: 1-2 concurrent streams
- medium model: 1 concurrent stream

**Example Sizing**
- 4-core CPU with base model: 8-12 concurrent streams
- 8-core CPU with base model: 16-24 concurrent streams

## Network Bandwidth

### Audio Stream Requirements
- Sample rate: 16 kHz
- Channels: 1 (mono)
- Bit depth: 16-bit PCM
- Bandwidth per stream: ~256 kbps (32 KB/s)

**Total bandwidth calculation**:
```
bandwidth_kbps = concurrent_streams * 256
bandwidth_MBs = concurrent_streams * 0.032
```

For 10 concurrent streams: ~2.5 Mbps (0.32 MB/s)

## Latency Targets

### Target Latencies
- Audio frame processing: < 100ms
- Partial transcript emission: < 300ms
- Final transcript emission: < 1s
- WebSocket round-trip: < 50ms (local network)

### Factors Affecting Latency
- Model size (larger = slower)
- VAD aggressiveness (higher = fewer but longer segments)
- Frame size (30ms default, adjustable)
- Network latency (for remote provider)

## Deployment Recommendations

### Single Instance (Small Scale)
- Use base or tiny model
- MAX_ACTIVE_CONNECTIONS: 10-20
- Suitable for: Development, small teams (< 10 users)

### Horizontal Scaling (Production)
- Deploy multiple provider instances behind a load balancer
- Each instance handles 10-20 concurrent streams
- Use sticky sessions for WebSocket connections
- Consider Redis for shared rate limiting (optional)

### Docker Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

## Monitoring Metrics

### Key Metrics to Monitor
- Active connections: `active_connections`
- Connections per key: `active_connections_by_key_label`
- Transcription latency: Average time to emit final transcript
- Error rate: Failed transcriptions / total transcriptions
- Memory usage: Should stay below 80% of allocated RAM
- CPU usage: Should stay below 80% for sustained load

### Health Check Endpoints
- `/health`: Basic health and connection stats
- `/ready`: Readiness probe (includes model warmup status)
- `/metrics`: Prometheus metrics (if enabled)

## Cost Considerations

### CPU-Based (Default)
- No GPU required
- Lower infrastructure cost
- Slower transcription
- Suitable for: Low to medium volume

### GPU-Based (Optional)
- Requires NVIDIA GPU
- Higher infrastructure cost
- 2-5x faster transcription
- Suitable for: High volume, low latency requirements

## Troubleshooting

### High Latency
- Switch to smaller model (tiny/base)
- Reduce MAX_ACTIVE_CONNECTIONS
- Increase CPU allocation
- Check for network bottlenecks

### Memory Exhaustion
- Switch to smaller model
- Reduce MAX_ACTIVE_CONNECTIONS
- Increase RAM allocation
- Check for memory leaks

### Connection Refused
- Check MAX_ACTIVE_CONNECTIONS limit
- Verify API key authentication
- Check rate limiting settings
- Review server logs for errors
