# Operational Runbooks for STT Platform

This document contains operational procedures for common incidents and maintenance tasks.

## Table of Contents

1. [Incident Response](#incident-response)
2. [Service Degradation](#service-degradation)
3. [Database Issues](#database-issues)
4. [High Latency](#high-latency)
5. [Scaling Events](#scaling-events)
6. [Security Incidents](#security-incidents)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Rollback Procedures](#rollback-procedures)

---

## Incident Response

### Severity Levels

- **P1 - Critical**: Service completely down, all users affected
- **P2 - High**: Significant degradation, most users affected
- **P3 - Medium**: Partial degradation, some users affected
- **P4 - Low**: Minor issues, few users affected

### Incident Response Process

1. **Acknowledge alert** in PagerDuty within 5 minutes
2. **Join incident bridge** (Slack/Teams call)
3. **Assess impact** - determine severity and affected users
4. **Identify root cause** - check logs, metrics, and recent changes
5. **Implement fix** - rollback, scale, or patch
6. **Verify recovery** - confirm service is healthy
7. **Post-incident review** - document what happened and prevent recurrence

### Communication Template

```
🚨 Incident: [Brief Description]
Severity: [P1/P2/P3/P4]
Impact: [Who is affected]
Status: [Investigating/Mitigated/Resolved]
Next Update: [Time]
```

---

## Service Degradation

### Symptoms

- High error rates (> 5%)
- Slow response times (> 5s)
- Increased latency
- Failed health checks

### Diagnosis Steps

1. Check Grafana dashboards for error rates
2. Review Prometheus metrics: `stt_errors_total`, `stt_requests_total`
3. Check application logs in Loki
4. Verify all pods are running: `kubectl get pods -n stt`
5. Check resource utilization

### Resolution Steps

1. **If pods are crashing**:
   ```bash
   kubectl logs -f deployment/stt-gateway -n stt
   kubectl describe pod <pod-name> -n stt
   ```

2. **If high error rate**:
   - Identify error type from logs
   - Check recent deployments
   - Consider rollback if recent change

3. **If resource exhaustion**:
   - Scale up: `kubectl scale deployment stt-gateway --replicas=10 -n stt`
   - Check node capacity
   - Review resource limits

4. **If database issues**:
   - See [Database Issues](#database-issues)

---

## Database Issues

### Symptoms

- Database connection errors
- Slow queries
- High CPU/memory on PostgreSQL pod
- Connection pool exhaustion

### Diagnosis Steps

1. Check PostgreSQL pod status:
   ```bash
   kubectl get pods -n stt -l app=postgres
   kubectl logs -f statefulset/postgres -n stt
   ```

2. Check database metrics in Grafana:
   - Connection count
   - Query duration
   - Cache hit ratio

3. Run database health check:
   ```bash
   kubectl exec -n stt postgres-0 -- pg_isready
   ```

4. Check slow queries:
   ```bash
   kubectl exec -n stt postgres-0 -- psql -U stt -d stt -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
   ```

### Resolution Steps

1. **Connection pool exhaustion**:
   - Increase connection pool size
   - Scale up PostgreSQL pod
   - Check for connection leaks in application

2. **Slow queries**:
   - Identify slow query from `pg_stat_statements`
   - Add appropriate indexes
   - Optimize query
   - Consider read replicas

3. **Pod resource exhaustion**:
   ```bash
   kubectl top pod -n stt postgres-0
   kubectl set resources statefulset/postgres --limits=cpu=4,memory=8Gi -n stt
   ```

4. **Database corruption**:
   - Restore from latest backup
   - Run: `bash scripts/restore-postgres.sh /backups/postgres/latest_backup.sql.gz`

---

## High Latency

### Symptoms

- P95 latency > 5s
- Slow transcription results
- High queue duration in Triton

### Diagnosis Steps

1. Check Triton metrics in Grafana:
   - `nv_inference_request_duration_us`
   - `nv_inference_queue_duration_us`

2. Check GPU utilization:
   ```bash
   kubectl describe node <gpu-node> | grep -A 10 nvidia.com/gpu
   ```

3. Check network latency between gateway and Triton:
   ```bash
   kubectl run latency-test --rm -i --restart=Never --image=curlimages/curl:latest \
     -- curl -w "@curl-format.txt" -o /dev/null -s http://triton-parakeet:8000/v2/health/ready
   ```

### Resolution Steps

1. **High Triton queue duration**:
   - Scale Triton replicas: `kubectl scale statefulset/triton-parakeet --replicas=4 -n stt`
   - Check if model is too large for GPU
   - Consider using smaller model

2. **High inference duration**:
   - Check GPU utilization
   - Optimize model (quantization, pruning)
   - Add more GPU nodes

3. **Network latency**:
   - Ensure gateway and Triton are in same availability zone
   - Check network policies
   - Consider service mesh for better routing

---

## Scaling Events

### Auto-scaling Triggers

KEDA scales based on:
- Active WebSocket connections (gateway)
- Inference queue duration (Triton)

### Manual Scaling

**Scale gateway**:
```bash
kubectl scale deployment stt-gateway --replicas=10 -n stt
```

**Scale Triton**:
```bash
kubectl scale statefulset/triton-parakeet --replicas=4 -n stt
```

### Scaling Down

Before scaling down:
1. Check current load
2. Ensure no active sessions will be disrupted
3. Use graceful termination

**Scale down gateway**:
```bash
kubectl scale deployment stt-gateway --replicas=2 -n stt
```

**Scale down Triton**:
```bash
kubectl scale statefulset/triton-parakeet --replicas=2 -n stt
```

---

## Security Incidents

### Types of Security Incidents

- Unauthorized access attempts
- API key compromise
- Data breach
- DDoS attack
- Vulnerability disclosure

### Immediate Response

1. **Contain the incident**:
   - Block malicious IPs
   - Rotate compromised API keys
   - Enable rate limiting
   - Isolate affected systems

2. **Preserve evidence**:
   - Capture logs
   - Take snapshots
   - Document timeline

3. **Notify stakeholders**:
   - Security team
   - Management
   - Affected users (if applicable)

### API Key Compromise

1. Identify compromised key from audit logs:
   ```bash
   kubectl logs -f deployment/stt-gateway -n stt | grep "invalid_api_key"
   ```

2. Rotate the key:
   ```bash
   bash deploy/scripts/rotate-api-key.sh
   ```

3. Revoke old key:
   ```bash
   bash deploy/scripts/revoke-api-key.sh /opt/true-streaming-stt-provider/.env compromised
   ```

4. Restart services:
   ```bash
   kubectl rollout restart deployment/stt-gateway -n stt
   ```

### DDoS Attack

1. Enable rate limiting at edge
2. Scale up gateway pods
3. Enable Cloudflare or similar DDoS protection
4. Block attacking IP ranges
5. Consider using AWS Shield or similar service

---

## Maintenance Procedures

### Rolling Updates

**Update gateway**:
```bash
kubectl set image deployment/stt-gateway \
  stt-gateway=ghcr.io/your-org/true-streaming-stt-provider:new-version \
  -n stt
kubectl rollout status deployment/stt-gateway -n stt
```

**Update Triton**:
```bash
kubectl set image statefulset/triton-parakeet \
  triton=nvcr.io/nvidia/tritonserver:24.05-py3 \
  -n stt
kubectl rollout status statefulset/triton-parakeet -n stt
```

### Database Maintenance

**Vacuum database**:
```bash
kubectl exec -n stt postgres-0 -- psql -U stt -d stt -c "VACUUM ANALYZE;"
```

**Reindex**:
```bash
kubectl exec -n stt postgres-0 -- psql -U stt -d stt -c "REINDEX DATABASE stt;"
```

### Certificate Renewal

Cert-Manager automatically renews certificates. Check status:
```bash
kubectl get certificate -n stt
kubectl describe certificate stt-gateway-tls -n stt
```

Manual renewal if needed:
```bash
kubectl delete certificate stt-gateway-tls -n stt
# Cert-Manager will automatically recreate and request new certificate
```

---

## Rollback Procedures

### Application Rollback

**Rollback to previous deployment**:
```bash
kubectl rollout undo deployment/stt-gateway -n stt
kubectl rollout status deployment/stt-gateway -n stt
```

**Rollback to specific revision**:
```bash
kubectl rollout history deployment/stt-gateway -n stt
kubectl rollout undo deployment/stt-gateway --to-revision=3 -n stt
```

### Database Rollback

**Restore from backup**:
```bash
bash scripts/restore-postgres.sh /backups/postgres/stt_backup_20240101_120000.sql.gz
```

### Full System Rollback

**Disaster recovery**:
```bash
bash scripts/disaster-recovery.sh
```

---

## Monitoring and Alerting

### Key Metrics to Monitor

- **Gateway**: `stt_active_connections`, `stt_sessions_started_total`, `stt_errors_total`
- **Triton**: `nv_inference_request_duration_us`, `nv_inference_queue_duration_us`
- **Database**: `pg_stat_activity_count`, `pg_stat_database_tup_returned`
- **Redis**: `redis_connected_clients`, `redis_used_memory`

### Alert Thresholds

- **Critical**: Gateway down, Triton down, Database down
- **Warning**: High error rate (>5%), High latency (>5s), High connections (>80%)

### Dashboard Access

- **Grafana**: https://grafana.example.com
- **Prometheus**: https://prometheus.example.com
- **Alertmanager**: https://alertmanager.example.com

---

## On-Call Procedures

### On-Call Rotation

- Primary on-call responds to all alerts
- Secondary on-call provides backup
- Handover includes incident status and ongoing issues

### Escalation Path

1. **Level 1**: On-call engineer
2. **Level 2**: Engineering lead
3. **Level 3**: CTO/VP Engineering
4. **Level 4**: CEO (for P1 incidents)

### Post-Incident Review

Within 48 hours of incident:
1. Schedule post-incident review meeting
2. Create incident report:
   - Timeline
   - Root cause
   - Impact
   - Resolution
   - Follow-up actions
3. Update runbooks based on lessons learned
4. Track follow-up actions to completion
