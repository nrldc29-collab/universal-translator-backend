#!/usr/bin/env bash
set -euo pipefail

# Multi-Region Deployment Script for STT Platform
# Deploys STT Platform to multiple regions with regional routing

REGIONS=("us-east-1" "us-west-2" "eu-west-1")
PRIMARY_REGION="us-east-1"

echo "==> Deploying STT Platform to multiple regions"

# Deploy to each region
for region in "${REGIONS[@]}"; do
    echo "==> Deploying to region: $region"
    
    # Set kubectl context for region
    kubectl config use-context "k8s-$region"
    
    # Create namespace
    kubectl create namespace stt --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply regional deployment
    if [ "$region" == "us-west-2" ]; then
        kubectl apply -f infra/k8s/multi-region/us-west-2-deployment.yaml
    elif [ "$region" == "eu-west-1" ]; then
        kubectl apply -f infra/k8s/multi-region/eu-west-1-deployment.yaml
    else
        echo "Using existing deployment for $region"
    fi
    
    # Wait for pods to be ready
    echo "Waiting for pods to be ready in $region"
    kubectl wait --for=condition=ready --timeout=600s pod -l app=stt-gateway -n stt || true
    kubectl wait --for=condition=ready --timeout=600s pod -l app=triton-parakeet -n stt || true
    
    echo "==> Deployment to $region complete"
done

# Deploy global routing configuration
echo "==> Deploying global routing configuration"
kubectl config use-context "k8s-$PRIMARY_REGION"
kubectl apply -f infra/k8s/multi-region/global-routing.yaml

# Configure DNS for global routing
echo "==> Configure DNS for global routing"
echo "Add the following DNS records:"
echo "stt.example.com → Load Balancer IP for us-east-1"
echo "us-east-1.stt.example.com → Load Balancer IP for us-east-1"
echo "us-west-2.stt.example.com → Load Balancer IP for us-west-2"
echo "eu-west-1.stt.example.com → Load Balancer IP for eu-west-1"

# Test regional connectivity
echo "==> Testing regional connectivity"
for region in "${REGIONS[@]}"; do
    echo "Testing $region..."
    if [ "$region" == "us-east-1" ]; then
        HOST="stt.example.com"
    else
        HOST="${region}.stt.example.com"
    fi
    
    curl -f "https://$HOST/health" || echo "WARNING: Health check failed for $region"
done

echo "==> Multi-region deployment complete"
echo "Next steps:"
echo "1. Configure DNS records"
echo "2. Test regional routing"
echo "3. Configure failover testing"
echo "4. Update documentation"
