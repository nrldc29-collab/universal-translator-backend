# Phase 3 Step 5: Multi-AZ Deployment

## Target

Run the STT platform across at least 2 availability zones so a single-AZ failure does not take down production.

## Gateway requirements

- Run at least 2 gateway replicas.
- Spread gateway pods across at least 2 availability zones.
- Use pod anti-affinity so gateway replicas avoid landing on the same node.
- Keep the gateway stateless.
- Store durable state in Postgres.
- Store ephemeral connection counters in Redis.

## Triton requirements

- Run at least 2 Triton replicas.
- Pin Triton replicas to GPU node groups in separate availability zones where GPU capacity allows.
- Use pod anti-affinity so Triton replicas avoid the same node.
- Keep `minAvailable: 2` in the Triton PodDisruptionBudget.
- Reserve GPU capacity before production launch.

## Postgres requirements

- Use managed multi-AZ Postgres.
- Enable automated failover.
- Enable point-in-time recovery.
- Target RPO: 5 minutes.
- Document expected RTO before enterprise launch.

## Redis requirements

- Use managed Redis with multi-AZ replication where available.
- Redis may lose ephemeral counters, but must not lose durable tenant or billing state.
- Gateway reconnect logic must recover cleanly after Redis failover.

## Acceptance checks

- Gateway pods are spread across at least 2 availability zones.
- Triton GPU pods are spread across separate nodes and preferably separate zones.
- Postgres failover has been tested.
- Redis failover has been tested.
- A single-zone failure does not fully stop transcription service.
- RPO and RTO are documented.

This implements Phase 3, Step 5: spread gateway and Triton across availability zones, use managed multi-AZ Postgres with PITR, document RTO/RPO, and chaos-test failover.
