# Phase 4 Step 3: Speaker Enrollment

## Target

Allow tenants to enroll known speakers so future sessions can resolve generic speaker labels like `spk_0` into real speaker identities.

## Scope

Speaker enrollment applies to self-hosted deployments, but it requires special privacy handling because voice embeddings are biometric data.

## Enrollment workflow

1. Tenant admin uploads a labeled voice sample.
2. System validates audio quality and minimum duration.
3. System generates a speaker embedding.
4. Embedding is encrypted at rest using a customer-managed key where available.
5. Speaker profile is stored under the tenant.
6. Future diarized sessions compare `spk_*` embeddings against enrolled speakers.
7. Transcript events include both generic and resolved speaker labels when confidence is high.

## Database table

```sql
CREATE TABLE IF NOT EXISTS speaker_profiles (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    encrypted_embedding BYTEA NOT NULL,
    embedding_model TEXT NOT NULL,
    consent_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_speaker_profiles_tenant_id
    ON speaker_profiles(tenant_id);
```

## Transcript event shape

```json
{
  "type": "transcript.final",
  "text": "thanks for joining today",
  "words": [
    {
      "word": "thanks",
      "start": 0.10,
      "end": 0.42,
      "speaker": "spk_0",
      "speaker_identity": {
        "id": "speaker_123",
        "display_name": "Alex",
        "confidence": 0.91
      }
    }
  ]
}
```

## Privacy requirements

- Treat voice embeddings as biometric data.
- Encrypt embeddings at rest.
- Restrict access by tenant.
- Log enrollment, update, match, export, and deletion events.
- Provide a delete-my-voiceprint API.
- Do not expose speaker identity unless confidence exceeds the configured threshold.

## Delete-my-voiceprint behavior

Users can request deletion of their enrolled voiceprint through:

DELETE /v1/me/speaker-profiles/{speaker_id}

Deletion must:

- Soft-delete the speaker profile by setting `deleted_at`
- Stop future identity matching for that speaker
- Preserve an audit event proving deletion occurred
- Never return the encrypted embedding in the response

## Acceptance checks

- Tenant can enroll a labeled speaker sample.
- Speaker embeddings are encrypted at rest.
- Future sessions can resolve known speakers.
- Low-confidence matches stay as `spk_*`.
- Speaker deletion removes or tombstones the profile.
- Audit log records enrollment and deletion events.
