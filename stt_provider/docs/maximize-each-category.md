# Maximizing latency, scaling, diarization, reliability, and accuracy

> **Scope.** You asked for the best-possible answer in each of five categories,
> independent of hosting model. This doc surveys the May-2026 state of the art,
> measures the current codebase against it, and lays out a prioritized roadmap.
>
> **The honest framing up front.** You will not max all five categories on a
> single-server FastAPI + faster-whisper stack. The best version of this
> product is one of two architectures:
>
> 1. **Thin proxy in front of a commercial provider** (Deepgram is the latency
>    and managed-scaling winner today). Lowest engineering cost, best out-of-
>    the-box experience, regulatory baseline included.
> 2. **Self-hosted NVIDIA Riva / NeMo stack on GPU Kubernetes**, with
>    Parakeet-TDT or FastConformer for streaming, Sortformer for diarization,
>    Triton for serving, and the operator-grade reliability work you'd expect
>    of any enterprise SaaS.
>
> A pragmatic shop ships option 1 first, then carves out option 2 for the
> tenants that demand on-prem / fine-tuning / data residency. The hybrid is
> what "max each category" actually looks like in production.

## Executive summary

| Category | "Max" today (May 2026) | Where you are | Closing the gap |
|---|---|---|---|
| Raw streaming latency | Deepgram Flux (sub-300 ms P50). Self-hosted: NVIDIA Parakeet streaming on Riva ~200–400 ms with GPU | Whisper buffer-replay: ~1–3 s, growing with utterance length | Swap engine (managed proxy or Riva); incremental decoding; in-memory float32 hand-off |
| Managed scaling | Cloud APIs auto-scale to thousands of concurrent streams. Self-hosted: Triton + KEDA on GPU K8s | Single-process FastAPI; in-memory connection counter; file-based usage store | Externalize state to Redis/Postgres; gRPC bidi + sticky LB; horizontal pod autoscaling on GPU node pool |
| Diarization | pyannoteAI Precision-2 (cloud, <150 ms). Self-hosted: NVIDIA Streaming Sortformer (frame-level, up to 4 speakers) | None | Add streaming diarizer; emit `transcript.speaker_attributed.*` events; word-level timestamp pipeline |
| Enterprise reliability | SOC 2 + HIPAA + ISO 27001, 99.9% SLA, multi-region, audit logs, RBAC, CMK | Single VPS, file logs, no draining, no isolation, dev-key default | Externalize state, OpenTelemetry, mTLS, K8s with PodDisruptionBudgets, compliance program |
| Accuracy tuning | Deepgram Keyterm Prompting (100 terms, 90% KRR, 6× lift) / AssemblyAI Universal-3 / NeMo fine-tuning | Hardcoded `beam_size=1`, no `initial_prompt`, no biasing, no per-tenant config | Expose Whisper knobs; per-tenant keyterm/vocab; eventually fine-tune Parakeet on customer corpora |

The rest of this document expands each row.

---

## 1. Raw streaming latency

### State of the art (May 2026)

The independent benchmark referenced in the 2026 Deepgram/Speechmatics/AssemblyAI
comparison treats **Deepgram Flux** as the latency baseline. Relative additions at P50:

| Provider / model | Δ vs Flux at P50 |
|---|---|
| Deepgram Flux | 0 (baseline; sub-300 ms end-to-end) |
| Deepgram Nova-3 | +459 ms |
| Deepgram Nova-2 | +467 ms |
| Speechmatics Default | +614 ms |
| Speechmatics Enhanced | +734 ms |
| AssemblyAI Universal Streaming | +761 ms |

At P75 the spread exceeds 1 second. Speechmatics itself recommends starting voice-
agent integrations at a 1.5 s budget unless aggressively tuned.

For self-hosted, the floor is set by NVIDIA's Riva ASR with Parakeet/FastConformer:

- **Parakeet-TDT-1.1B** (top of Open ASR leaderboard for speed; RTFx > 2,000 on
  H100). Streaming variant: ~200–400 ms time-to-first-partial on GPU.
- **multitalker-parakeet-streaming-0.6b-v1** — released by NVIDIA on Hugging
  Face for multi-speaker streaming.
- **Canary-Qwen 2.5B** (top of Open ASR leaderboard for *accuracy* at 5.63%
  WER; SALM architecture — FastConformer encoder + Qwen3-1.7B decoder). Not
  optimized for streaming.

### Where the current codebase is

`stt_server/streaming.py` accumulates speech frames into `speech_buffer`, then on
every ~35-frame partial trigger calls `transcribe_pcm16_file` on the **entire**
buffer. So:

- First partial: ≥ `8 × frame_ms` of speech + ~35 frames + decode time ≈ 1.5 s on CPU.
- Each subsequent partial: same as above plus growing utterance prefix → CPU
  cost is roughly O(N²) in utterance length.
- Every partial also writes a temp WAV file and re-opens it inside
  `faster-whisper` (~10–50 ms of pure I/O).

This is "near-real-time chunked transcription" not streaming.

### Options ranked

1. **Replace engine with Deepgram Flux via a thin proxy.** Sub-300 ms, zero ML
   ops, no GPU required. Pay per audio minute. *Highest latency win, lowest
   engineering cost, hands over your data.*

2. **NVIDIA Riva on GPU with Parakeet streaming.** ~200–400 ms, on-prem,
   fine-tunable. *Best self-hosted option; needs CUDA-capable nodes and
   Triton ops experience.*

3. **whisper-streaming / WhisperLive wrapper.** Keeps Whisper's accuracy, gets
   ~600 ms partials via LocalAgreement confirmation. *Stepping stone if you
   want to stay on Whisper.*

4. **Rolling-tail incremental decode** (Approach A in
   `streaming-design.md`). ~500–800 ms, no engine swap, but heuristic-heavy.

5. **In-memory float32 hand-off + GPU faster-whisper + `beam_size=1`.** Drop
   the temp-WAV round-trip, run on CUDA `float16`. ~30–40% per-partial win
   without architectural change.

### Bonus latency wins worth doing regardless

- **In-process audio:** `faster-whisper` accepts a NumPy `float32` array directly
  via `WhisperModel.transcribe(np_array)`. Today you write a temp WAV per partial.
- **Opus over WebRTC (or WebTransport) instead of raw PCM over WebSocket.**
  Opus at 24 kbps mono is roughly 7× less bandwidth than PCM-16LE at 16 kHz,
  and WebRTC's built-in jitter buffer and FEC reduce tail-latency variance.
  WebSocket as the framing protocol has no congestion control or FEC, so a
  packet loss spike turns into a transcript hang.
- **gRPC bidirectional streaming** for service-to-service paths (faster than
  WebSocket framing, better with HTTP/2 multiplexing, native to Riva).
- **Locality:** co-locate ingress and inference in the same AZ; the round-trip
  to a distant GPU pool routinely adds 30–100 ms to first-partial latency.
- **Pre-warmed model and GPU memory:** keep one decoder process per GPU pinned;
  use Triton's `instance_group` to maintain concurrency.
- **VAD tuning:** lower `min_speech_frames` to emit a first partial earlier;
  use `vad_mode=3` (most aggressive) once you trust the model to handle noise.

---

## 2. Managed scaling

### State of the art

The commercial APIs solve this for you. Concurrency limits at the largest
providers run into the thousands of simultaneous streams per account, with
linear scale-out on demand and no infrastructure surface area.

Self-hosted "max" looks like:

- **NVIDIA Triton Inference Server** to host the ASR model with dynamic
  batching across sessions. Triton's ASR examples ship with Parakeet/Conformer
  configurations.
- **GPU Kubernetes** with the NVIDIA device plugin and time-sliced GPUs on
  smaller workloads. EKS, GKE, AKS all have GPU node pools; Nebius / Lambda /
  CoreWeave offer dedicated GPU K8s.
- **KEDA** to autoscale on custom metrics (active WebSocket count, queue
  depth, GPU utilization), not just CPU.
- **Envoy / Linkerd / Istio** with sticky-session routing for WebSocket
  affinity, or hash-on-session-id to keep the same client on the same pod
  through reconnects.
- **Ray Serve** as an alternative for Python-native ML teams; gives you a
  single deployment description that scales heterogeneously across CPU/GPU.

### Where the current codebase is

- `active_connections` is a Python global — sums correctly within one process,
  but multiple replicas would each track their own and the cap would be
  silently violated.
- `usage_store` writes to `logs/usage-snapshot.json`. Two replicas writing to
  the same volume will clobber each other; two replicas with different volumes
  will diverge.
- `get_whisper_model()` is `lru_cache`d per process. Each new pod loads the
  full Whisper weights from disk on startup — slow, and you can't share GPU
  memory across pods on the same node.
- WebSocket origin and API-key checks happen inside the handler; no edge
  authentication. An L7 load balancer cannot reject a bad key before it costs
  you a pod-side TLS handshake.
- No graceful shutdown: a `SIGTERM` will sever in-flight sessions abruptly.

### Options ranked

1. **Proxy to a commercial API.** Pricing is per audio-minute, not per replica.
   *No scaling work at all.*

2. **Triton + Parakeet on GPU K8s with KEDA.** The textbook self-hosted answer.
   Triton handles dynamic batching across concurrent streams; KEDA scales on
   active streams or queue depth; an external Postgres/Redis holds counters
   and usage. *6–12 weeks of ML platform work.*

3. **Ray Serve on a GPU autoscaling cluster.** Less ops-heavy than Triton for
   Python shops. *3–6 weeks if your team already knows Ray.*

4. **Knative + scale-to-zero GPU pods.** Cold starts hurt for ASR (model load
   is heavy), but acceptable for low-traffic tenants. *Niche.*

5. **Vanilla K8s deployment with HPA.** Fine for the FastAPI tier; doesn't
   solve the GPU-aware scaling problem on its own.

### Concrete architectural changes required

- **Move state out of the process.** Postgres for `usage_store`, Redis (or
  Postgres advisory locks) for the global active-connection counter. The
  WebSocket handler `INCR` on connect, `DECR` on disconnect; counters survive
  pod restarts.
- **Centralize API key management.** A `keys` table with hashed values, key
  metadata, labels, and revocation. Edge auth at the load balancer if
  possible (Envoy ext_authz against a small auth service).
- **Connection draining.** On `SIGTERM`: stop accepting new WebSocket
  upgrades, set readiness false, wait up to `MAX_SESSION_SECONDS` for
  in-flight sessions to drain, then exit. Tie to `terminationGracePeriodSeconds`.
- **Session offload protocol.** For long-running sessions on a draining pod,
  send a `session.handoff` event so the client reconnects to a new pod. This
  is harder than it sounds — partial state would need to be transferred or
  the client retransmits the recent audio buffer.
- **WebSocket-aware load balancer.** Envoy with `consistent_hash` on a
  session cookie, or AWS ALB with sticky sessions; required for upgrades to
  land on the same pod across short reconnects.
- **Model server out of the API tier.** Today FastAPI hosts the model. Split
  into (a) thin FastAPI/gRPC gateway that does auth and protocol, and
  (b) Triton (or Riva) hosting the ASR model. The gateway scales on CPU; the
  inference tier scales on GPU. Independent failure domains.

---

## 3. Diarization

### State of the art

- **NVIDIA Streaming Sortformer** (`nvidia/diar_streaming_sortformer_4spk-v2`
  on Hugging Face). Frame-level streaming diarization, up to 4 speakers,
  works in Riva alongside Parakeet-CTC or Conformer-CTC. Emits `spk_0..spk_3`
  per word at end-of-utterance.
- **pyannoteAI Precision-2** (commercial). The April 2026 Precision-2 release
  reports 28% improvement over prior open-source state of the art; the
  pyannoteAI API claims <150 ms latency.
- **pyannote.audio 4.0 / community-1** (open source). The largest open-source
  diarization model release; not as accurate as Precision-2 but
  self-hostable. Streaming support has matured but the offline pipeline is
  still where most of the accuracy lives.
- **Diart** (open source). Online wrapper around pyannote that gives real-time
  diarization with incremental clustering; lower accuracy than offline
  pyannote but CPU-runnable.

Streaming diarization is materially harder than offline because labels are
provisional — a third speaker appearing mid-utterance can cause earlier
speakers to be re-clustered. Production systems either accept eventual
relabeling (with a "revise" event) or constrain max speakers up front.

### Where the current codebase is

None. There's no diarization, no per-word timestamps, no speaker concept in
the WebSocket protocol.

### Options ranked

1. **Cloud diarization paired with cloud STT.** Deepgram and AssemblyAI both
   ship diarization with their main STT call. pyannoteAI offers a
   transcription-sync orchestration that pairs their diarization with the STT
   provider of your choice. *Best quality, minimal integration.*

2. **NVIDIA Riva Sortformer + Parakeet (self-hosted).** Frame-level streaming
   diarization, integrated with the STT path, GPU-served. *Best self-hosted
   answer; locked to Parakeet-CTC / Conformer-CTC.*

3. **pyannote.audio community-1 (self-hosted offline) for final-only
   diarization.** Run diarization only on `transcript.final` segments; emit a
   second event with speaker labels. Lower latency overhead, but no live
   speaker indication during partials. *Pragmatic if you don't need partial
   labels.*

4. **Diart (self-hosted online) for live speaker labels.** Accuracy gap vs
   Precision-2 / Sortformer, but Python-native and CPU-capable. *Stepping
   stone before committing to GPU.*

### Schema changes required

The current event schema is too thin for diarization. Suggested additions:

```json
{ "type": "transcript.partial", "text": "...",
  "words": [ { "word": "hello", "start": 0.21, "end": 0.43, "speaker": "spk_0",
               "speaker_confirmed": false } ] }

{ "type": "transcript.final", "text": "...",
  "words": [ { "word": "hello", "start": 0.21, "end": 0.43, "speaker": "spk_0",
               "speaker_confirmed": true } ] }

{ "type": "diarization.revise",
  "revisions": [ { "from": "spk_2", "to": "spk_0", "range": [3.41, 4.20] } ] }
```

The `revise` event is important: streaming diarization will occasionally
correct earlier labels. Without an explicit revision channel, the client has
to re-render the whole transcript.

Speaker IDs are stable within a session but not across sessions unless you
add voice-print enrollment (pyannoteAI offers identification; Sortformer
does not by default).

---

## 4. Enterprise reliability

### State of the art

The bar for "enterprise STT" in 2026:

- **SLA:** 99.9% uptime, sometimes 99.95% on premium tiers; published status
  page; public incident history.
- **Compliance:** SOC 2 Type II, HIPAA BAA on request, ISO 27001, GDPR / DPF
  for EU data, PCI for finance (rare).
- **Identity:** SSO/SAML/SCIM, RBAC with at minimum (admin / operator /
  read-only) roles, API keys scoped to operations and rotatable without
  downtime.
- **Data handling:** in-flight TLS 1.2+, at-rest AES-256, customer-managed
  keys (CMK / BYOK) on enterprise tiers, configurable data retention down to
  "do not store audio".
- **Network:** mTLS or IP allowlisting for VPC-style connectivity (PrivateLink,
  Private Service Connect).
- **Audit:** complete audit log of admin actions, key issuance/revocation,
  data access, exportable to customer-controlled storage or SIEM.
- **Operations:** multi-region active/active or active/passive with documented
  RPO/RTO; chaos-tested failover; on-call rotation with public runbooks.
- **Observability:** OpenTelemetry traces + metrics + logs with customer-side
  forwarding (e.g., to Datadog, Honeycomb).

### Where the current codebase is

- **Single VPS deployment model.** `MAX_ACTIVE_CONNECTIONS=10` and a single
  uvicorn process. No HA, no failover.
- **State on local disk:** `logs/*.jsonl` and `logs/usage-snapshot.json`. A
  pod restart on a stateless host loses everything.
- **API keys must stay explicit** (`config.py:9`). Shipping with placeholder or
  shared example keys is a vulnerability, not a quirk.
- **Audit log covers only `usage.reset`.** Key creation, login, data export
  are not audited.
- **No rate limiting** beyond the per-key connection cap. A single noisy
  client can hammer `/v1/audio/transcriptions` until the box is exhausted.
- **No structured logging context.** Logs lack trace IDs, tenant IDs, or
  session IDs as first-class fields; you can grep, but you can't trace.
- **Graceful shutdown is minimal.** `SIGTERM` sets `usage_store.save()` and
  exits; in-flight WebSocket sessions get a hard close.
- **No tenant isolation.** All keys share the same model instance, same
  filesystem, same log file. Cross-tenant data leakage via shared logs would
  be a real audit finding.
- **Secrets in plain `.env`.** Acceptable on dev hardware; not acceptable for
  customer-managed-key promises.
- **No CI/CD or test suite visible.** Hard to claim change-management
  controls (SOC 2 CC8) without one.

### Options ranked (do in this order)

1. **Externalize state.** Postgres for usage, Redis for ephemeral counters.
   Atomic increments, durability, multi-replica safety.
2. **OpenTelemetry everywhere.** Every WebSocket session, every model call,
   every audit event gets a trace ID propagated through the response. Ship
   OTLP to a customer-controlled collector.
3. **Replace the dev API-key default with `RuntimeError` on startup.**
   `STT_API_KEY` should have no default in production builds — refuse to
   start without an explicit value.
4. **Hashed key storage + revocation API.** Move keys out of env into Postgres
   with `argon2id` hashes, last-used timestamps, scopes (`stt:stream`,
   `stt:transcribe`, `usage:read`, `admin:*`), and a revocation endpoint that
   audits.
5. **Per-tenant audit log table** covering: key issued/revoked, session
   started/closed, transcript exported, usage reset, admin login. Exportable
   per-tenant.
6. **Connection draining + PodDisruptionBudget.** SIGTERM → readiness false →
   wait for sessions → exit, with a budget that prevents rolling deploys from
   killing the last replica.
7. **mTLS + edge auth.** Terminate at an Envoy or NGINX ingress with mTLS for
   service-to-service paths, JWT validation for public API.
8. **Multi-AZ deployment + read replicas + cross-region backup.** Postgres
   point-in-time recovery; Redis with AOF + replication; object-store
   snapshots for log archive.
9. **Compliance program.** SOC 2 Type II is typically a 9–12 month effort if
   started from scratch; HIPAA BAA in parallel for healthcare leads; ISO 27001
   if European enterprise demand.
10. **Public status page + incident process.** Statuspage.io or equivalent;
    documented SEV taxonomy; postmortem template; on-call rotation in
    PagerDuty/Opsgenie.

### Two things to fix this week regardless

- **API key startup guard.** Keep `stt_api_key: str = ""` as the default and
  refuse to start if no valid API key is configured in non-dev mode.
- **Rate limiting on REST endpoints.** A `slowapi` or `fastapi-limiter`
  middleware keyed on API key would prevent a misbehaving tenant from
  starving others through the batch endpoint.

---

## 5. Out-of-the-box accuracy tuning

### State of the art

| Capability | Best-in-class today |
|---|---|
| Headline accuracy (English, May 2026) | NVIDIA Canary-Qwen 2.5B — 5.63% WER on Open ASR Leaderboard |
| Fastest with competitive accuracy | NVIDIA Parakeet-TDT-1.1B — top of speed leaderboard, 23rd on accuracy |
| Multilingual accuracy | Whisper-large-v3, AssemblyAI Universal-3, Canary-Qwen on supported languages |
| Custom vocabulary (commercial) | Deepgram Nova-3 Keyterm Prompting — up to 100 terms, 90% KRR, 6× lift, no retraining |
| Multilingual custom vocab | Deepgram Nova-3 Multilingual Keyterm Prompting — 500 tokens across mixed-language audio |
| Self-hosted fine-tuning | NeMo recipes for fine-tuning Parakeet / FastConformer on customer data |
| Prompt-based biasing | Whisper `initial_prompt` (modest effect, fragile), Canary-Qwen via LLM decoder context (stronger) |

The big change since 2024: top-tier providers offer **instant vocabulary
adaptation** without retraining. Deepgram's Keyterm Prompting is the cleanest
example — pass up to ~100 terms in the request, get a 6× recall lift on those
terms. AssemblyAI's Universal-3 ships a comparable "Word Boost" + "Custom
Vocabulary" pairing.

### Where the current codebase is

In `stt_server/model.py`:

```python
segments, _info = model.transcribe(
    path,
    beam_size=1,
    vad_filter=False,
    language=language,
    condition_on_previous_text=False,
)
```

- `beam_size=1` (greedy decoding — fast, slightly less accurate than `beam_size=5`).
- `condition_on_previous_text=False` (good for streaming, prevents hallucination drift).
- No `initial_prompt`, no `word_timestamps`, no `hotwords` (faster-whisper does
  support a `hotwords` param since 1.0.0), no `temperature`, no
  `compression_ratio_threshold`.
- No per-request override path. `language` is the only knob that reaches the
  decoder from the client.
- Single model instance per process — no per-tenant model choice.

### Options ranked

1. **Proxy to Deepgram Nova-3 with Keyterm Prompting.** 90% KRR on customer
   terms, no fine-tuning infrastructure. *Highest accuracy gain for the
   lowest effort.*

2. **Expose `hotwords` / `initial_prompt` per request and store a per-tenant
   default.** `faster-whisper` supports `hotwords` since 1.0; this is a small
   change in `model.py` and a new column in the (eventually-real) tenants
   table. Effect is more modest than commercial Keyterm Prompting but it's
   free.

3. **Switch to NeMo Parakeet + word-boosting.** NeMo's transducer decoders
   support shallow-fusion with an external word boost list; integrated with
   Riva. Combines top-tier streaming accuracy with custom vocab.

4. **Fine-tune Parakeet/FastConformer on customer data.** NeMo ships recipes
   for this. Offer it as a managed flow per enterprise tenant. *Highest
   ceiling, real ML ops cost.*

5. **Ensemble:** Parakeet for partials (low latency), Whisper-large-v3 or
   Canary-Qwen for finals (higher accuracy). Final replaces partial. Doubles
   model footprint; pays off for high-stakes domains.

6. **Domain post-processing.** A trivial dictionary substitution pass on the
   final transcript catches the long tail your decoder gets wrong. Costs
   nothing, helps surprisingly often, never close-the-loop on its own.

7. **Language auto-detect with confidence.** `faster-whisper` returns
   `info.language_probability`; expose it and let clients fall back to
   English on low-confidence detection.

### What to expose on the WebSocket today

Even before swapping engines, the protocol should accept (and ignore where
unsupported):

```
?api_key=...
&language=auto
&hotwords=acme,kubernetes,LangChain
&initial_prompt=Medical consultation about cardiology and pulmonology.
&beam_size=5
&word_timestamps=true
```

These flow into the decoder call in `model.py`. The accuracy delta from
`beam_size=1` to `beam_size=5` alone is typically 0.5–1.5 WER absolute on
hard audio.

---

## Cross-cutting: the "max each" architecture

The honest answer to "max all five" is a layered architecture:

```
┌────────────────────────────────────────────────────────────────────┐
│                    Customer (browser / agent / app)                │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket / WebRTC (Opus 16 kHz mono)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Edge: TLS termination, mTLS optional, JWT validation, rate limit  │
│  (Envoy or AWS ALB + Lambda authorizer)                            │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ gRPC bidi (audio + control)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Gateway (Python or Go): protocol, auth, per-tenant routing,       │
│  per-tenant biasing config, OpenTelemetry context propagation      │
└────────────────────────────────────────────────────────────────────┘
       │                                       │
       │ (default tenant: cloud path)          │ (enterprise tenant: on-prem)
       ▼                                       ▼
┌────────────────────────┐         ┌────────────────────────────────────────┐
│  Deepgram Nova-3 +     │         │  Triton / Riva on GPU K8s              │
│  pyannoteAI Precision-2│         │  Parakeet streaming + Sortformer       │
│  proxy                 │         │  Fine-tuned per-tenant adapters        │
│                        │         │  Postgres usage, Redis counters        │
│  Sub-300ms latency,    │         │  ~300–500ms latency, full residency    │
│  managed scaling, SOC2 │         │  + fine-tuning + on-prem isolation     │
└────────────────────────┘         └────────────────────────────────────────┘
```

- The **gateway** is the only thing customers see. Same protocol regardless of
  which backend serves them.
- **Per-tenant routing** decides whether a request goes to the cloud path or
  the self-hosted path, based on tenant settings (data residency, fine-tuning
  needs, compliance class).
- **State is shared** between the two backends through Postgres/Redis for
  counters, usage, and audit.
- Diarization is symmetric: pyannoteAI on the cloud path, Sortformer on the
  self-hosted path. Same `transcript.*` event schema either way.

This is the design that gives you Deepgram's latency *and* on-prem
fine-tuning *and* SOC 2 reliability without compromise. It's also six to
twelve months of work if you start today and have a small team.

---

## Prioritized roadmap

This is the order I'd execute. Each phase is roughly a "release" — ship,
measure, then continue. Numbers in parentheses are rough team-week estimates
for a 2–3 engineer team.

### Phase 0 — Strategic decision (1 week)

Before anything else, decide:

- Is "self-hosted" a marketing constraint or a real customer requirement?
- Which categories must you own end-to-end vs. proxy?
- What's the compliance ceiling you're aiming for (SOC 2? HIPAA? FedRAMP?)?

The rest of the roadmap branches based on the answer. The two main paths are
"cloud-first with on-prem option" or "self-hosted only".

### Phase 1 — Quick wins on current stack (1–2 weeks)

These help no matter which path you choose.

- Replace dev API-key default with hard failure on empty.
- In-process float32 audio: skip the temp WAV in `streaming.py`/`model.py`.
- Expose `hotwords`, `initial_prompt`, `beam_size`, `word_timestamps`,
  `temperature` on `/v1/audio/transcriptions` and `/stt/stream`.
- Move CORS / counter fixes already landed into a tagged release.
- Add `slowapi` rate limits on REST endpoints, keyed on API key.
- Add structured logging context (session_id, tenant_id, trace_id) and
  emit OpenTelemetry spans.

Latency improvement: ~30%. Accuracy improvement on hard domains: meaningful
once `hotwords` is wired up. Reliability: small but real.

### Phase 2A — Cloud path (3–6 weeks)

If you chose cloud-first:

- Build the proxy: same WebSocket protocol, transform-to-Deepgram on the way
  in, transform-from-Deepgram on the way out.
- Add pyannoteAI orchestration for diarized output.
- Pass tenant-configured keyterms through to Deepgram.
- All five categories are now at "max" instantly, with the trade-off being
  data residency and fine-tuning.

### Phase 2B — Self-hosted path (8–12 weeks)

If you chose self-hosted:

- Stand up Triton serving Parakeet-streaming on a GPU node pool.
- Replace `model.py` with a Triton client; the gateway becomes a thin shell.
- Add Sortformer streaming diarization in parallel.
- Externalize usage and counters to Postgres + Redis.
- Implement connection draining and PodDisruptionBudgets.
- KEDA autoscaling on active streams.

Latency target: ~300–500 ms P50. Scaling target: 100+ concurrent streams per
GPU node. Diarization: 2–4 speakers, frame-level labels.

### Phase 3 — Enterprise hardening (6–10 weeks)

Whichever backend(s) you ended up with:

- mTLS at the edge, SSO/SAML/SCIM for tenant admins, RBAC scopes on API keys.
- Per-tenant audit log table + export.
- Multi-AZ deployment with documented RPO/RTO. Cross-region backups.
- Public status page and incident process.
- Begin SOC 2 Type II evidence collection.

### Phase 4 — Differentiation (ongoing)

- NeMo fine-tuning recipes packaged as a tenant-facing flow.
- Domain models (medical, legal, finance) trained on tenant corpora.
- Speaker enrollment (cross-session speaker identity).
- Co-located GPU regions for sub-300 ms self-hosted latency.

---

## Decision matrix

| | Cloud-first (Deepgram + pyannoteAI proxy) | Self-hosted (Riva + Sortformer) | Hybrid |
|---|---|---|---|
| Time to "max each" | 6–10 weeks | 6–9 months | 9–12 months |
| Engineering cost | Low (1–2 engineers) | High (3–5 engineers + ML platform) | High |
| Per-minute cost | $0.005–0.02 (cloud margin to manage) | GPU rental + amortized eng | Mixed |
| Data residency | Limited (US-EU regions, no on-prem) | Full | Full |
| Fine-tuning | Limited (Keyterm Prompting only) | Full (NeMo) | Full |
| Compliance baseline | SOC 2 / HIPAA inherited | Your responsibility | Your responsibility |
| Lock-in | High (Deepgram + pyannoteAI APIs) | Low | Medium |
| Failure modes | Vendor outage = your outage | Your outage = your outage | Smaller blast radius |

If forced to pick one row: most teams should start with **cloud-first**, then
add the self-hosted lane only when a specific deal demands it. That's the
shortest path to "max each category" with the lowest engineering bet.

---

## Open questions for you

1. **Who is the customer?** Voice agents, meeting transcription, contact
   center, healthcare? Latency budget and diarization requirements differ
   dramatically.
2. **What's the compliance ceiling?** SOC 2 only, or HIPAA / GDPR / FedRAMP?
   This decides how much of the enterprise-reliability phase you actually
   need.
3. **Languages?** English-only changes the model choice; multilingual
   strongly favors Whisper-large-v3 or AssemblyAI Universal-3 over Parakeet.
4. **Budget for cloud egress?** Deepgram Nova-3 is roughly $0.0043–0.0058 per
   audio minute streaming; at 1,000 concurrent streams for 8 hours/day that's
   $80–100k/month. Self-hosted GPU is a fixed cost regardless of utilization.
5. **GPU availability?** Self-hosted requires sustained access to H100/H200/
   A100 inventory; if you can't reserve capacity, cloud is a less risky bet.

Answers to these reshape the roadmap. Happy to redo Phase 2 once you point me
at a target customer profile.

---

## Sources (May 2026)

- [Best Speech-to-Text APIs in 2026 — Deepgram](https://deepgram.com/learn/best-speech-to-text-apis-2026)
- [Deepgram vs Speechmatics vs AssemblyAI: 2026 Guide](https://deepgram.com/learn/deepgram-vs-speechmatics-vs-assemblyai)
- [Best Speech-to-Text Providers in 2026 (Coval independent benchmarks)](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose)
- [Speech Recognition in 2026: Whisper vs Gemini vs AssemblyAI vs Deepgram (CodeSOTA)](https://www.codesota.com/guides/speech-recognition)
- [Open ASR Leaderboard — Hugging Face](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard)
- [Open ASR Leaderboard blog post — Trends and Insights](https://huggingface.co/blog/open-asr-leaderboard)
- [Best open-source STT in 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [NVIDIA Riva ASR Overview](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/asr/asr-overview.html)
- [NVIDIA Riva ASR Models Reference](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/models/asr.html)
- [NVIDIA Streaming Sortformer — Identify Speakers in Real-Time (NVIDIA blog)](https://developer.nvidia.com/blog/identify-speakers-in-meetings-calls-and-voice-apps-in-real-time-with-nvidia-streaming-sortformer/)
- [nvidia/diar_streaming_sortformer_4spk-v2 — Hugging Face](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2)
- [nvidia/multitalker-parakeet-streaming-0.6b-v1 — Hugging Face](https://huggingface.co/nvidia/multitalker-parakeet-streaming-0.6b-v1)
- [pyannoteAI — Speaker Diarization & Conversation Intelligence](https://www.pyannote.ai/)
- [pyannoteAI Precision-2 release](https://www.pyannote.ai/blog/precision-2)
- [pyannote.audio community-1 — Hugging Face](https://huggingface.co/pyannote/speaker-diarization-community-1)
- [Deepgram Nova-3 launch announcement](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api)
- [Deepgram Keyterm Prompting docs](https://developers.deepgram.com/docs/keyterm)
- [Deepgram Nova-3 multilingual + keyterm prompting expansion](https://deepgram.com/learn/deepgram-expands-nova-3-with-10-new-languages-and-multilingual-keyterm-prompting)
