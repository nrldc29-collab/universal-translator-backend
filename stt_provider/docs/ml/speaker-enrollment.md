# Speaker Enrollment

## Goal

Speaker enrollment lets a tenant map generic diarization labels like `spk_0` to known speaker identities when confidence is high enough.

## Privacy classification

Voice embeddings are biometric data.

They must be:

- Encrypted before storage
- Scoped to one tenant
- Hidden from API responses
- Excluded from logs
- Deletable through the delete-my-voiceprint endpoint
- Audited when created, matched, or deleted

## Enrollment flow

1. Admin uploads a labeled speaker audio sample.
2. System validates the audio file.
3. System generates a speaker embedding.
4. System encrypts the embedding with `SPEAKER_EMBEDDING_ENCRYPTION_KEY`.
5. System stores the encrypted embedding in `speaker_profiles`.
6. System writes `speaker_profile.created` to the audit log.

## Matching flow

1. Sortformer emits session-level speaker labels like `spk_0`.
2. The platform compares live speaker embeddings against enrolled profiles.
3. A resolved identity is attached only when confidence is at least `0.85`.
4. Low-confidence matches remain as generic `spk_*` labels.
5. Emitted identity matches write `speaker_identity.matched` to the audit log.

## Delete-my-voiceprint flow

Users can delete their enrolled voiceprint through:

```text
DELETE /v1/me/speaker-profiles/{speaker_id}
```

Deletion must:

- Set deleted_at
- Stop future identity matching
- Preserve an audit event
- Never return raw or encrypted embedding data

## Transcript event shape

```json
{
  "type": "transcript.final",
  "text": "thanks for joining",
  "words": [
    {
      "word": "thanks",
      "start": 0.1,
      "end": 0.42,
      "speaker": "spk_0",
      "confidence": 0.94,
      "speaker_identity": {
        "speaker_profile_id": "00000000-0000-0000-0000-000000000456",
        "display_name": "Alex",
        "confidence": 0.91
      }
    }
  ]
}
```

## Launch rule

Speaker identity must stay disabled until encryption, deletion, audit logging, and confidence-threshold enforcement are all tested.
