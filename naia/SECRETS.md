# Secrets Management for NAIA

## Overview

NAIA requires secure management of sensitive configuration including API keys and database credentials. This document outlines the recommended approach for secrets management across different deployment scenarios.

## Environment Variables

NAIA uses the following environment variables for configuration:

### Required
- `ANTHROPIC_API_KEY`: Anthropic API key for Claude model access
- `NAIA_API_KEYS`: Comma-separated list of API key:permission_level mappings (e.g., `key1:ADMIN,key2:LIMITED_WRITE`)

### Optional
- `POSTGRES_PASSWORD`: PostgreSQL database password (if using PostgreSQL)
- `REDIS_PASSWORD`: Redis password (if using Redis)

## Local Development

For local development, use a `.env` file:

```bash
# .env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
NAIA_API_KEYS=dev_key:LIMITED_WRITE
```

Add `.env` to `.gitignore` to prevent accidental commits.

## Docker Deployment

### Using Environment Variables

Pass secrets via environment variables in `docker-compose.yml`:

```yaml
services:
  naia:
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - NAIA_API_KEYS=${NAIA_API_KEYS}
```

Create a `.env` file and source it:

```bash
docker-compose up
```

### Using Docker Secrets (Swarm/Kubernetes)

For production deployments, use Docker secrets:

```yaml
services:
  naia:
    secrets:
      - anthropic_api_key
      - naia_api_keys

secrets:
  anthropic_api_key:
    file: ./secrets/anthropic_api_key.txt
  naia_api_keys:
    file: ./secrets/naia_api_keys.txt
```

## Kubernetes Deployment

### Using Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: naia-secrets
type: Opaque
stringData:
  anthropic-api-key: "your_api_key_here"
  naia-api-keys: "key1:ADMIN,key2:LIMITED_WRITE"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: naia
spec:
  template:
    spec:
      containers:
      - name: naia
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: naia-secrets
              key: anthropic-api-key
        - name: NAIA_API_KEYS
          valueFrom:
            secretKeyRef:
              name: naia-secrets
              key: naia-api-keys
```

### Using External Secret Management

For enhanced security, integrate with external secret managers:

- **AWS Secrets Manager**: Use AWS EKS integration
- **HashiCorp Vault**: Use Vault Agent Sidecar

## Cloud-Native Secret Managers

### AWS Secrets Manager

```python
import boto3

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']
```

### HashiCorp Vault

```python
import hvac

client = hvac.Client(url='https://vault.example.com')
client.auth.approle.login(role_id='naia', secret_id='secret_id')
secret = client.secrets.kv.v2.read_secret_version(path='naia/anthropic')
```

## Security Best Practices

1. **Never commit secrets to version control**
   - Add `.env` to `.gitignore`
   - Use git-secrets or similar tools to prevent accidental commits

2. **Rotate secrets regularly**
   - Implement automated secret rotation
   - Monitor for secret exposure

3. **Use least privilege**
   - Grant minimum required permissions to API keys
   - Use scoped API keys where possible

4. **Encrypt secrets at rest**
   - Use encrypted storage for secrets
   - Enable encryption for secret managers

5. **Audit secret access**
   - Log all secret access attempts
   - Monitor for unusual access patterns

## Secret Rotation

Implement automated secret rotation for:

- Anthropic API keys (rotate monthly)
- Database credentials (rotate quarterly)
- Internal API keys (rotate quarterly)

## Current Limitations

- Current implementation uses environment variables
- No automatic secret rotation
- No secret versioning
- No audit logging for secret access

## Migration Path

1. **Short-term**: Continue using environment variables with `.env` files
2. **Medium-term**: Integrate with cloud secret manager (AWS Secrets Manager or similar)
3. **Long-term**: Implement automated secret rotation and audit logging
