# Phase 4 Step 1: NeMo Fine-Tuning for Self-Hosted Tenants

## Target

Offer tenant-specific ASR fine-tuning for regulated or domain-heavy customers using NVIDIA NeMo and the self-hosted Parakeet backend.

## Scope

This applies only to the self-hosted path.

The fine-tuning flow should support:

- Tenant upload of labeled audio
- Dataset validation
- Training job creation
- Parakeet adapter fine-tuning
- Evaluation against a fixed test set
- Model approval
- Automated deployment to Triton
- Rollback to the previous model version

## Tenant-facing workflow

1. Tenant uploads labeled audio and transcripts.
2. System validates format, duration, sample rate, and transcript quality.
3. System creates a fine-tuning job.
4. NeMo trains a tenant-specific adapter.
5. Evaluation runs against baseline and tenant test data.
6. Admin approves the model.
7. Approved model is deployed to Triton.
8. Tenant default model is updated after rollout.

## Required dataset format

```text
tenant-dataset/
  train/
    audio/
    manifest.jsonl
  validation/
    audio/
    manifest.jsonl
  test/
    audio/
    manifest.jsonl
```

Each manifest row:

```json
{
  "audio_filepath": "audio/example.wav",
  "text": "expected transcript text",
  "duration": 12.4
}
```

## Model registry fields

Track each fine-tuned model version with:

- tenant_id
- base_model
- adapter_version
- training_dataset_id
- wer_baseline
- wer_fine_tuned
- status
- approved_by
- approved_at
- deployed_at
- rollback_model_version

## Acceptance checks

- Tenant can upload a labeled dataset.
- Dataset validation rejects bad audio or missing transcripts.
- Fine-tuning job produces a versioned adapter.
- Evaluation compares baseline WER against fine-tuned WER.
- Approved model deploys to Triton.
- Rollback restores the previous model version.
