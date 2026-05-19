# ADR 0001: Streaming STT Platform Architecture

## Step 1: Target Customer Profile

Primary customer profile: voice agents.

Initial launch assumptions:

- Peak concurrent streams: 100
- P50 latency target: under 300 ms
- P95 latency target: under 700 ms
- Max session duration: 60 minutes
- Average audio minutes per tenant per month: 50,000

Reasoning:

Voice agents need very low latency because transcripts feed directly into real-time responses. This makes time-to-first-partial and time-between-partials more important than batch throughput. Diarization is useful but not the first launch blocker unless the customer is meeting transcription, healthcare scribing, or contact center analytics.

This matches Phase 0, Step 1 of the guide: define the customer type, concurrency, latency targets, max session duration, and monthly audio volume before writing code.

## Step 2: Compliance Ceiling

Compliance ceiling for the first 18 months: SOC 2 Type II.

Initial launch assumptions:

- Primary market: general SaaS voice-agent teams
- Required at launch: strong API-key handling, HTTPS/WSS, audit logs for admin actions, operational metrics, and documented incident response
- Required within 18 months: SOC 2 Type II audit readiness, access reviews, change management, vendor risk documentation, backup/restore procedures, and retention/deletion policies
- Deferred unless a specific customer deal requires it: HIPAA BAA, ISO 27001, and FedRAMP Moderate

Reasoning:

Voice-agent customers need a credible enterprise security posture, but the initial profile does not require healthcare, public-sector, or high-regulation certification as a launch blocker. SOC 2 Type II is the most practical compliance ceiling for the first enterprise-ready version because it supports SaaS procurement without forcing the platform into a slower regulated-industry build from day one.

This decision keeps Phase 3 enterprise hardening important, but not a blocker for the first launch. The platform should avoid storing raw audio or transcript content by default, keep secrets out of source control, hash or fingerprint sensitive key material in logs, and preserve enough audit data to support future SOC 2 evidence collection.

## Decision

We will use a self-hosted architecture.

The public API will remain our FastAPI gateway, including the existing WebSocket streaming endpoint. Internally, the gateway will become a thin gRPC client to NVIDIA Triton serving Parakeet streaming ASR and Sortformer streaming diarization.

The current Whisper backend will remain available as a fallback during migration and rollout.

We will not implement the cloud-first Deepgram + pyannoteAI path in Phase 2.

## Accepted Trade-offs

- Slower launch in exchange for stronger control over infrastructure and data residency.
- Higher platform complexity in exchange for lower vendor lock-in.
- GPU capacity planning in exchange for avoiding per-minute STT provider costs at scale.
- More ML platform work in exchange for future fine-tuning and domain-model control.

## Alternatives Considered

### Cloud-first

Rejected for now.

A cloud-first path using Deepgram and pyannoteAI would be faster to ship, but it adds vendor lock-in, external data-processing dependencies, and less control over residency and fine-tuning.

### Hybrid first

Rejected for now.

Hybrid is still a possible long-term architecture, but it adds routing, testing, operational, and support complexity before we have the self-hosted backend stable.

The guide defines Phase 2B as the self-hosted path using GPU Kubernetes, NVIDIA Triton, Parakeet streaming ASR, and Sortformer diarization, so we'll continue only on that track.
