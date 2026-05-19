# Monitoring Setup Guide for STT Platform

This guide covers setting up comprehensive monitoring for the STT Platform.

## Monitoring Stack Components

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Alertmanager**: Alert routing and notification
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing
- **OpenTelemetry Collector**: Telemetry collection

## Initial Setup

### 1. Deploy Monitoring Stack

The monitoring stack is deployed as part of the cluster setup:
```bash
./infra/k8s/setup-cluster.sh
```

### 2. Access Grafana

1. Port forward to access Grafana:
   ```bash
   kubectl port-forward svc/grafana 3000:3000 -n stt
   ```

2. Open http://localhost:3000

3. Login with credentials from secrets:
   ```bash
   kubectl get secret stt-platform-secrets -n stt -o jsonpath='{.data.GRAFANA_ADMIN_PASSWORD}' | base64 -d
   ```

### 3. Configure Data Sources

Grafana datasources are pre-configured via ConfigMap:
- Prometheus: http://prometheus:9090
- Loki: http://loki:3100
- Tempo: http://tempo:3100

## Dashboard Configuration

### Pre-configured Dashboards

The following dashboards are included:

1. **STT Gateway Metrics**
   - Active connections
   - Sessions started rate
   - Audio bytes received
   - Error rates

2. **Triton Backend Metrics**
   - Inference request duration
   - Queue duration
   - GPU utilization
   - Model performance

3. **System Overview**
   - Pod status
   - Resource utilization
   - Network traffic
   - Storage usage

### Import Custom Dashboards

1. Go to Grafana → Dashboards → Import
2. Upload dashboard JSON or paste Grafana.com ID
3. Select Prometheus datasource
4. Save dashboard

## Alert Configuration

### Alert Rules

Alert rules are defined in `infra/k8s/prometheus-rules.yaml`:

**Gateway Alerts**:
- High active connections (>80% capacity)
- Gateway down
- High error rate (>5%)

**Triton Alerts**:
- Triton down
- High inference latency (>5s)
- High queue duration (>1s)

**Database Alerts**:
- PostgreSQL down
- High connection count (>80%)
- Slow queries

**Redis Alerts**:
- Redis down
- High memory usage

### Configure Alertmanager

Edit `infra/k8s/alertmanager-config.yaml`:

**PagerDuty Integration**:
```yaml
receivers:
  - name: pagerduty
    pagerduty_configs:
      - service_key: 'your-pagerduty-integration-key'
```

**Email Integration**:
```yaml
receivers:
  - name: email
    email_configs:
      - to: 'oncall@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@example.com'
        auth_password: 'your-smtp-password'
```

Apply configuration:
```bash
kubectl apply -f infra/k8s/alertmanager-config.yaml
kubectl rollout restart deployment/alertmanager -n stt
```

## Log Aggregation with Loki

### View Logs in Grafana

1. Go to Grafana → Explore
2. Select Loki datasource
3. Enter query:
   ```
   {namespace="stt", app="stt-gateway"}
   ```
4. View logs in real-time

### Log Queries

**Filter by pod**:
```
{namespace="stt", pod="stt-gateway-xxx"}
```

**Filter by log level**:
```
{namespace="stt", level="error"}
```

**Search for specific text**:
```
{namespace="stt"} |= "error"
```

## Distributed Tracing with Tempo

### View Traces in Grafana

1. Go to Grafana → Explore
2. Select Tempo datasource
3. Enter trace ID or search by service
4. View trace timeline

### Instrument Application

Add OpenTelemetry to your application:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure tracing
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector.stt.svc.cluster.local:4317"
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Create spans
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("transcribe"):
    # Your code here
    pass
```

## Custom Metrics

### Add Application Metrics

```python
from prometheus_client import Counter, Histogram, start_http_server

# Define metrics
transcription_counter = Counter('stt_transcriptions_total', 'Total transcriptions')
transcription_duration = Histogram('stt_transcription_duration_seconds', 'Transcription duration')

# Use metrics
transcription_counter.inc()
with transcription_duration.time():
    # Transcription logic
    pass
```

### Expose Metrics Endpoint

The FastAPI gateway already exposes metrics at `/metrics`. To add custom metrics:

```python
from prometheus_client import make_asgi_app

# Add metrics endpoint to FastAPI
app.mount("/metrics", make_asgi_app())
```

## Health Checks

### Gateway Health Checks

**Liveness probe**: `/health/live`
- Returns 200 if gateway is running

**Readiness probe**: `/health/ready`
- Returns 200 if gateway is ready to accept connections

### Database Health Check

```bash
kubectl exec -n stt postgres-0 -- pg_isready
```

### Redis Health Check

```bash
kubectl exec -n stt redis-0 -- redis-cli PING
```

### Triton Health Check

```bash
kubectl run triton-check --rm -i --restart=Never --image=curlimages/curl:latest \
  -- curl -f http://triton-parakeet:8000/v2/health/ready
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

- **Latency**: P50, P95, P99 response times
- **Throughput**: Requests per second
- **Error Rate**: Percentage of failed requests
- **Resource Utilization**: CPU, memory, GPU
- **Queue Depth**: Number of pending requests

### SLA Monitoring

Define SLAs in Grafana:

1. Create new dashboard
2. Add SLI/SLO panel
3. Configure:
   - Error budget: 99.9% uptime
   - Alert threshold: 99.5%
   - Time window: 30 days

## Troubleshooting Monitoring

### Prometheus Not Scraping

Check Prometheus targets:
```bash
kubectl port-forward svc/prometheus 9090:9090 -n stt
```

Go to http://localhost:9090/targets

If targets are down:
1. Check service labels match pod labels
2. Check network policies
3. Check service is in correct namespace

### Alerts Not Firing

Check Alertmanager status:
```bash
kubectl port-forward svc/alertmanager 9093:9093 -n stt
```

Go to http://localhost:9093

If alerts not firing:
1. Check Prometheus rules are loaded
2. Check alert thresholds
3. Check Alertmanager configuration

### Logs Not Appearing in Loki

Check Loki is running:
```bash
kubectl get pods -n stt -l app=loki
```

Check Loki configuration:
```bash
kubectl get configmap loki-config -n stt -o yaml
```

Check application is sending logs to Loki:
- Verify OpenTelemetry Collector is running
- Check log shipping configuration

## Maintenance

### Retention Policy

Configure retention in component configs:

**Prometheus** (30 days):
```yaml
args:
  - '--storage.tsdb.retention.time=30d'
```

**Loki** (30 days):
```yaml
limits_config:
  reject_old_samples_max_age: 168h
```

### Backup Monitoring Data

**Prometheus data**:
```bash
kubectl cp stt/prometheus-0:/prometheus /backup/prometheus
```

**Grafana dashboards**:
```bash
kubectl get configmap grafana-dashboards -n stt -o yaml > grafana-dashboards-backup.yaml
```

### Upgrade Monitoring Stack

**Upgrade Prometheus**:
```bash
kubectl set image deployment/prometheus prometheus=prom/prometheus:v2.49.0 -n stt
```

**Upgrade Grafana**:
```bash
kubectl set image deployment/grafana grafana=grafana/grafana:10.3.0 -n stt
```

## Best Practices

1. **Set up alerting early** - Configure alerts before deploying to production
2. **Test alerts regularly** - Verify alerts fire as expected
3. **Document runbooks** - Create procedures for common issues
4. **Review dashboards weekly** - Ensure dashboards provide actionable insights
5. **Monitor monitoring** - Ensure monitoring stack itself is healthy
6. **Use consistent naming** - Standardize metric and label naming
7. **Set up SLIs/SLOs** - Define and track service level objectives
8. **Enable log correlation** - Link logs to traces and metrics
