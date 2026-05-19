# Production Deployment Guide for STT Platform

This guide covers deploying the True Streaming STT Provider to a GPU Kubernetes cluster with full production infrastructure.

## Prerequisites

- GPU Kubernetes cluster (GKE, EKS, AKS, or self-managed with NVIDIA GPU support)
- kubectl configured with cluster admin access
- Helm 3.x installed
- Domain name with DNS configured to point to cluster load balancer
- PagerDuty account (or alternative alerting service)

## Quick Start

### 1. Clone and Prepare

```bash
git clone <repository>
cd true-streaming-stt-provider
```

### 2. Configure Domain

Edit `infra/k8s/ingress-deployment.yaml` and replace `stt.example.com` with your domain.

### 3. Configure Secrets

Edit `infra/k8s/secrets-template.yaml` and replace all `replace-me` values:
- `STT_API_KEY`: Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `ADMIN_API_KEY`: Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `POSTGRES_PASSWORD`: Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- `API_KEY_HASH_SECRET`: Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ENCRYPTION_KEY`: Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `GRAFANA_ADMIN_PASSWORD`: Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(16))"`
- `PAGERDUTY_SERVICE_KEY`: Your PagerDuty integration key
- `ALLOWED_ORIGINS`: Your production HTTPS domains

### 4. Configure Alertmanager

Edit `infra/k8s/alertmanager-config.yaml`:
- Replace `alerts@example.com` with your email
- Replace `replace-me-pagerduty-key` with your PagerDuty service key
- Configure SMTP settings for your email provider

### 5. Run Setup Script

```bash
chmod +x infra/k8s/setup-cluster.sh
./infra/k8s/setup-cluster.sh
```

This script will:
- Create namespaces
- Install NVIDIA device plugin
- Install Cert-Manager
- Install Nginx Ingress Controller
- Install KEDA
- Deploy PostgreSQL, Redis, Prometheus, Alertmanager, Grafana, Loki, Tempo
- Deploy OpenTelemetry Collector
- Run database migrations
- Deploy Triton backend
- Deploy STT Gateway
- Configure autoscaling

### 6. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n stt

# Check services
kubectl get svc -n stt

# Check ingress
kubectl get ingress -n stt

# Run health check
kubectl run health-check --rm -i --restart=Never --image=curlimages/curl:latest -- curl -f http://stt-gateway/health
```

### 7. Access Services

- **Grafana**: `https://grafana.your-domain.com` (admin credentials from secrets)
- **Prometheus**: `https://prometheus.your-domain.com`
- **STT API**: `https://stt.your-domain.com`

## Detailed Component Configuration

### GPU Cluster Requirements

For production, use at least:
- 2 GPU nodes (NVIDIA T4 or better)
- 4 CPU nodes for gateway and infrastructure
- 100GB SSD storage per node
- 16GB RAM per GPU node
- 8GB RAM per CPU node

### PostgreSQL Configuration

The deployment uses:
- PostgreSQL 15
- 100GB persistent storage
- Automated backups (configure separately)
- Connection pooling (consider adding PgBouncer for high load)

### Redis Configuration

The deployment uses:
- Redis 7 with AOF persistence
- 10GB persistent storage
- Single instance (consider Redis Cluster for HA)

### Triton Backend Configuration

The deployment uses:
- NVIDIA Triton Inference Server 24.05
- Parakeet TDT streaming model
- Sortformer diarization model
- GPU scheduling with 1 GPU per replica
- 100GB model repository storage

### Monitoring Stack

- **Prometheus**: Metrics collection with 30-day retention
- **Grafana**: Visualization with pre-configured dashboards
- **Alertmanager**: Alert routing to PagerDuty and email
- **Loki**: Log aggregation with 30-day retention
- **Tempo**: Distributed tracing
- **OpenTelemetry Collector**: Trace/metric/log collection

### Autoscaling

KEDA is configured to:
- Scale gateway based on active WebSocket connections
- Scale Triton based on inference queue duration
- Minimum 2 replicas, maximum 20 replicas

## Security Configuration

### TLS Certificates

Cert-Manager automatically provisions Let's Encrypt certificates for:
- `stt.your-domain.com`
- `grafana.your-domain.com`
- `prometheus.your-domain.com`

Certificates auto-renew 30 days before expiration.

### Secrets Management

Secrets are stored as Kubernetes secrets. For enhanced security:
- Consider external secrets operator (AWS Secrets Manager, HashiCorp Vault)
- Rotate secrets regularly using provided scripts
- Enable RBAC to restrict secret access

### Network Policies

Consider adding network policies to restrict:
- Inter-pod communication
- External egress
- Database access

## Backup and Disaster Recovery

### Database Backups

Configure automated PostgreSQL backups:
```bash
# Create backup
kubectl exec -n stt postgres-0 -- pg_dump -U stt stt > backup.sql

# Restore backup
kubectl exec -i -n stt postgres-0 -- psql -U stt stt < backup.sql
```

### Persistent Volume Backups

Use your cloud provider's snapshot feature for:
- PostgreSQL PVC
- Redis PVC
- Triton model repository PVC
- Prometheus, Loki, Tempo PVCs

### Disaster Recovery Procedure

1. Restore from latest database backup
2. Restore persistent volume snapshots
3. Run setup script to redeploy
4. Verify all services are healthy
5. Run smoke tests

## Operational Procedures

### Scaling

Manual scaling:
```bash
# Scale gateway
kubectl scale deployment stt-gateway -n stt --replicas=5

# Scale Triton
kubectl scale statefulset triton-parakeet -n stt --replicas=3
```

### Rolling Updates

```bash
# Update gateway image
kubectl set image deployment/stt-gateway stt-gateway=ghcr.io/your-org/true-streaming-stt-provider:new-version -n stt

# Update Triton image
kubectl set image statefulset/triton-parakeet triton=nvcr.io/nvidia/tritonserver:24.05-py3 -n stt
```

### Logs

View logs:
```bash
# Gateway logs
kubectl logs -f deployment/stt-gateway -n stt

# Triton logs
kubectl logs -f statefulset/triton-parakeet -n stt

# All logs in namespace
kubectl logs -f -n stt --all-containers=true
```

### Metrics

Access Prometheus metrics:
```bash
# Port forward to access locally
kubectl port-forward svc/prometheus 9090:9090 -n stt

# Query metrics
curl http://localhost:9090/api/v1/query?query=stt_active_connections
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n stt

# Check events
kubectl get events -n stt --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n stt
```

### High Latency

1. Check Triton queue duration in Grafana
2. Scale Triton replicas
3. Check GPU utilization
4. Check network latency between gateway and Triton

### Database Connection Issues

1. Check PostgreSQL pod is healthy
2. Verify database URL in secrets
3. Check network policies
4. Review connection pool settings

## Cost Optimization

- Use spot/preemptible instances for GPU nodes when possible
- Scale down Triton during low-traffic periods
- Use smaller Whisper models if accuracy allows
- Configure appropriate retention periods for logs/metrics
- Use regional storage classes

## Support and Maintenance

### Regular Tasks

- Daily: Review alert notifications
- Weekly: Review Grafana dashboards
- Monthly: Rotate secrets, review costs
- Quarterly: Disaster recovery testing, security audit

### Monitoring Checklist

- [ ] All pods running and healthy
- [ ] No critical alerts firing
- [ ] Disk usage < 80%
- [ ] CPU utilization < 70%
- [ ] Memory utilization < 80%
- [ ] TLS certificates valid
- [ ] Backups completing successfully

## Appendix: Additional Resources

- [SECURITY_HARDENING.md](../SECURITY_HARDENING.md) - Security checklist
- [PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md) - Operational runbook
- [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) - Release checklist
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Troubleshooting guide
