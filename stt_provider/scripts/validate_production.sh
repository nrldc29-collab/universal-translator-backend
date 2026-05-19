#!/usr/bin/env bash
set -euo pipefail

echo "==> Checking Kubernetes namespace"
kubectl get namespace stt

echo "==> Checking gateway deployment"
kubectl -n stt rollout status deployment/stt-gateway

echo "==> Checking Triton StatefulSet"
kubectl -n stt rollout status statefulset/triton-parakeet

echo "==> Checking services"
kubectl -n stt get service stt-gateway
kubectl -n stt get service triton-parakeet

echo "==> Checking PodDisruptionBudgets"
kubectl -n stt get pdb stt-gateway-pdb
kubectl -n stt get pdb triton-parakeet-pdb

echo "==> Checking KEDA ScaledObjects"
kubectl -n stt get scaledobject stt-gateway-active-websockets
kubectl -n stt get scaledobject triton-queue-duration

echo "==> Checking GPU pods"
kubectl -n stt get pods -l app=triton-parakeet -o wide

echo "==> Checking gateway pods"
kubectl -n stt get pods -l app=stt-gateway -o wide

echo "==> Checking required secrets exist"
kubectl -n stt get secret stt-platform-secrets

echo "==> Checking gateway readiness endpoint"
kubectl -n stt run stt-readiness-check \
  --rm \
  -i \
  --restart=Never \
  --image=curlimages/curl:latest \
  -- curl -fsS http://stt-gateway/health/ready

echo "==> Checking gateway liveness endpoint"
kubectl -n stt run stt-liveness-check \
  --rm \
  -i \
  --restart=Never \
  --image=curlimages/curl:latest \
  -- curl -fsS http://stt-gateway/health/live

echo "==> Checking Triton health endpoint"
kubectl -n stt run triton-health-check \
  --rm \
  -i \
  --restart=Never \
  --image=curlimages/curl:latest \
  -- curl -fsS http://triton-parakeet:8000/v2/health/ready

echo "==> Production validation passed"
