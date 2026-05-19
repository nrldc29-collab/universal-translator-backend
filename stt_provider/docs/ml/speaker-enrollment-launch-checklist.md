# Speaker Enrollment Launch Checklist

## Launch gate

Speaker enrollment cannot be enabled in production until every required control below is complete.

## Storage and encryption

- [ ] `speaker_profiles` table exists
- [ ] `encrypted_embedding` is never stored as plaintext
- [ ] `SPEAKER_EMBEDDING_ENCRYPTION_KEY` is configured
- [ ] Encryption tests pass
- [ ] Raw embeddings are never logged
- [ ] Raw embeddings are never returned by API responses

## Access control

- [ ] Speaker profile management endpoints require admin scope
- [ ] Delete-my-voiceprint endpoint requires authentication
- [ ] Speaker profiles are tenant-scoped
- [ ] Cross-tenant speaker profile access is blocked

## Auditability

- [ ] `speaker_profile.created` audit event exists
- [ ] `speaker_profile.deleted` audit event exists
- [ ] `speaker_identity.matched` audit event exists
- [ ] Audit events include tenant ID and trace ID
- [ ] Audit events never include raw or encrypted embeddings

## Privacy and deletion

- [ ] Delete-my-voiceprint endpoint exists
- [ ] Deleted profiles set `deleted_at` 
- [ ] Deleted profiles are excluded from matching
- [ ] Deleted profiles are excluded from active profile lists
- [ ] Deletion response does not include embedding data

## Matching safety

- [ ] Speaker identity matching is disabled by default
- [ ] Confidence threshold is enforced
- [ ] Matches below `0.85` remain as `spk_*` 
- [ ] Transcript events support optional `speaker_identity` 
- [ ] Low-confidence identity guesses are never emitted

## Documentation

- [ ] Speaker enrollment docs exist
- [ ] Privacy classification is documented
- [ ] Delete-my-voiceprint behavior is documented
- [ ] Launch rule is documented

## Production enablement rule

Enable speaker enrollment only after:

- All checklist items are complete
- Security review is approved
- Legal/privacy review is approved
- Production audit logging is verified
- Rollback plan is documented
