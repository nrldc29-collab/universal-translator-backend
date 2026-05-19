# GPU Kubernetes Provisioning Notes

## Phase 2B Step 1: Provision GPU Kubernetes

Target platform: managed Kubernetes with NVIDIA GPU nodes.

Approved options:

- EKS with NVIDIA GPU node group
- GKE with NVIDIA GPU node pool
- AKS with NVIDIA GPU node pool

Initial GPU choice:

- L4 for cost-sensitive development and staging
- A10G for balanced production latency and cost
- H100 only for premium low-latency production workloads

Minimum production capacity:

- At least 2 GPU nodes for high availability
- Reserved GPU capacity required before production launch
- Autoscaling enabled, but minimum GPU node count must stay at 2

Required cluster add-ons:

- NVIDIA device plugin
- DCGM exporter for GPU metrics
- Cluster autoscaler or managed node-pool autoscaler
- Metrics server
- Ingress controller
- cert-manager

Scheduling requirements:

- ASR and diarization workloads must be pinned to GPU nodes.
- GPU nodes should use taints so non-GPU workloads do not consume GPU capacity.
- Gateway pods should run separately from Triton GPU workloads.
- Production GPU workloads must not rely on spot/preemptible capacity.

Availability requirements:

- GPU nodes must be distributed across at least 2 availability zones when the cloud provider supports it.
- Triton replicas should not be scheduled onto the same physical node when avoidable.
- Capacity must be reserved because streaming ASR cannot tolerate eviction during active sessions.

Deliverable:

A managed Kubernetes cluster with a dedicated NVIDIA GPU node pool, NVIDIA runtime support, GPU metrics, and enough reserved capacity to support the first self-hosted Triton deployment.

This starts Phase 2B with GPU Kubernetes, including an NVIDIA GPU node pool, NVIDIA device plugin, DCGM exporter, reserved capacity, and a minimum of 2 GPU nodes for high availability.
