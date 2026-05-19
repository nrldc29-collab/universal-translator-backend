# Merge Checklist: Self-Hosted Streaming STT

## Required before merge

- [ ] PR description is complete
- [ ] Reviewer checklist is complete
- [ ] Architecture decision record is included
- [ ] Phase 2B self-hosted path is clearly selected
- [ ] Phase 2A cloud-first path is not introduced
- [ ] Whisper fallback remains available
- [ ] Tests pass locally
- [ ] Local validation script passes
- [ ] Database migrations are reviewed
- [ ] Kubernetes manifests are reviewed
- [ ] Security-sensitive endpoints require proper scopes
- [ ] Audit events are written for sensitive changes
- [ ] Speaker embeddings are encrypted before storage
- [ ] Regional routing blocks cross-region traffic by default
- [ ] Production launch decision remains marked `Not approved` 

## Commands to run before merge

```bash
./scripts/validate_local.sh
pytest
python -m compileall stt_server tests
```

## Merge rule

Do not merge if any required launch gate is accidentally marked production-ready without validation evidence.

## Post-merge actions

After merge:

- Create release tag
- Apply migrations in staging
- Deploy to staging Kubernetes
- Run production validation script against staging
- Run regional smoke tests against staging
- Schedule 12-hour, 200-stream soak test
- Confirm Whisper fallback is enabled before tenant rollout
