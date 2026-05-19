# Phase 4 Step 2: Domain Models

## Target

Offer pre-tuned domain model options so tenants can improve accuracy without needing a custom fine-tuning project.

## Initial domains

Support these named domains first:

- medical
- legal
- finance
- contact_center
- general

## API behavior

Expose available models through:

```text
GET /v1/models
```

Example response:

```json
{
  "models": [
    {
      "id": "parakeet-general",
      "domain": "general",
      "default": true
    },
    {
      "id": "parakeet-medical",
      "domain": "medical",
      "default": false
    },
    {
      "id": "parakeet-legal",
      "domain": "legal",
      "default": false
    },
    {
      "id": "parakeet-finance",
      "domain": "finance",
      "default": false
    },
    {
      "id": "parakeet-contact-center",
      "domain": "contact_center",
      "default": false
    }
  ]
}
```

## Tenant settings

Add a tenant-level default model setting:

```sql
ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS default_model_id TEXT NOT NULL DEFAULT 'parakeet-general';
```

## Routing behavior

When a stream starts:

- Load the tenant's `default_model_id`.
- Allow an explicit request-level model override if the API key scope permits it.
- Route the request to the matching Triton model.
- Fall back to `parakeet-general` only if the tenant allows fallback.

## Acceptance checks

- GET /v1/models returns available domain models.
- Tenant can set a default model.
- Streaming requests use the tenant default model.
- Request-level model override is supported.
- Unknown model IDs are rejected.
- Fallback behavior is explicit and logged.
