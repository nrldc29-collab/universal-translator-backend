#!/usr/bin/env bash
set -euo pipefail

# GPU Kubernetes Cluster Setup Script for STT Platform
# This script sets up a complete GPU Kubernetes cluster with all required components

echo "==> Setting up GPU Kubernetes cluster for STT Platform"

# Create namespaces
echo "==> Creating namespaces"
kubectl create namespace stt --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace keda --dry-run=client -o yaml | kubectl apply -f -

# Install NVIDIA device plugin
echo "==> Installing NVIDIA device plugin"
kubectl apply -f infra/k8s/nvidia-device-plugin.yaml

# Install Cert-Manager
echo "==> Installing Cert-Manager"
kubectl apply -f infra/k8s/cert-manager-deployment.yaml

# Wait for Cert-Manager to be ready
echo "==> Waiting for Cert-Manager to be ready"
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager -n cert-manager
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager-webhook -n cert-manager
kubectl wait --for=condition=available --timeout=300s deployment/cert-manager-cainjector -n cert-manager

# Install Nginx Ingress Controller
echo "==> Installing Nginx Ingress Controller"
kubectl apply -f infra/k8s/ingress-deployment.yaml

# Wait for Ingress Controller to be ready
echo "==> Waiting for Ingress Controller to be ready"
kubectl wait --for=condition=available --timeout=300s deployment/ingress-nginx-controller -n ingress-nginx

# Install KEDA
echo "==> Installing KEDA"
kubectl apply -f infra/k8s/keda-install.yaml

# Wait for KEDA to be ready
echo "==> Waiting for KEDA to be ready"
kubectl wait --for=condition=available --timeout=300s deployment/keda-operator -n keda

# Deploy core infrastructure
echo "==> Deploying PostgreSQL"
kubectl apply -f infra/k8s/postgres-deployment.yaml

echo "==> Deploying Redis"
kubectl apply -f infra/k8s/redis-deployment.yaml

echo "==> Deploying Prometheus"
kubectl apply -f infra/k8s/prometheus-config.yaml
kubectl apply -f infra/k8s/prometheus-rules.yaml
kubectl apply -f infra/k8s/prometheus-deployment.yaml

echo "==> Deploying Alertmanager"
kubectl apply -f infra/k8s/alertmanager-config.yaml
kubectl apply -f infra/k8s/alertmanager-deployment.yaml

echo "==> Deploying Grafana"
kubectl apply -f infra/k8s/grafana-datasources.yaml
kubectl apply -f infra/k8s/grafana-dashboards.yaml
kubectl apply -f infra/k8s/grafana-deployment.yaml

echo "==> Deploying Loki"
kubectl apply -f infra/k8s/loki-config.yaml
kubectl apply -f infra/k8s/loki-deployment.yaml

echo "==> Deploying Tempo"
kubectl apply -f infra/k8s/tempo-config.yaml
kubectl apply -f infra/k8s/tempo-deployment.yaml

echo "==> Deploying OpenTelemetry Collector"
kubectl apply -f infra/k8s/otel-collector-config.yaml
kubectl apply -f infra/k8s/otel-collector-deployment.yaml

# Wait for databases to be ready
echo "==> Waiting for databases to be ready"
kubectl wait --for=condition=ready --timeout=300s pod -l app=postgres -n stt
kubectl wait --for=condition=ready --timeout=300s pod -l app=redis -n stt

# Run database migrations
echo "==> Running database migrations"
kubectl run migration-job --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --namespace=stt \
  --env="PGPASSWORD=$(kubectl get secret stt-platform-secrets -n stt -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
  -- psql -h postgres.stt.svc.cluster.local -U stt -d stt -f /migrations/001_externalize_state.sql

kubectl run migration-job --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --namespace=stt \
  --env="PGPASSWORD=$(kubectl get secret stt-platform-secrets -n stt -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
  -- psql -h postgres.stt.svc.cluster.local -U stt -d stt -f /migrations/002_tenant_backend_rollout.sql

kubectl run migration-job --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --namespace=stt \
  --env="PGPASSWORD=$(kubectl get secret stt-platform-secrets -n stt -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
  -- psql -h postgres.stt.svc.cluster.local -U stt -d stt -f /migrations/003_speaker_profiles.sql

# Generate secrets
echo "==> Generating secrets"
kubectl apply -f infra/k8s/secrets-generator.yaml

# Deploy application components
echo "==> Deploying Triton backend"
kubectl apply -f infra/k8s/triton-parakeet-statefulset.yaml
kubectl apply -f infra/k8s/triton-parakeet-service.yaml

echo "==> Deploying STT Gateway"
kubectl apply -f infra/k8s/gateway-draining-and-pdb.yaml
kubectl apply -f infra/k8s/gateway-deployment.yaml

echo "==> Deploying KEDA autoscaling"
kubectl apply -f infra/k8s/keda-scaledobjects.yaml

echo "==> Waiting for application to be ready"
kubectl wait --for=condition=ready --timeout=600s pod -l app=triton-parakeet -n stt
kubectl wait --for=condition=ready --timeout=300s pod -l app=stt-gateway -n stt

echo "==> Cluster setup complete"
echo "==> Next steps:"
echo "1. Update infra/k8s/secrets-template.yaml with your PagerDuty integration key"
echo "2. Update infra/k8s/ingress-deployment.yaml with your domain"
echo "3. Generate secrets: kubectl run secrets-generator --rm -i --restart=Never --image=python:3.11 -- bash -c \"\$(kubectl get configmap secrets-generator -n stt -o jsonpath='{.data.generate-secrets\.sh}')\""
echo "4. Apply secrets: kubectl apply -f infra/k8s/secrets-template.yaml"
