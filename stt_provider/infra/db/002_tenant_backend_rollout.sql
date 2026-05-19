ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS backend TEXT NOT NULL DEFAULT 'triton';

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS allow_backend_fallback BOOLEAN NOT NULL DEFAULT true;

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS max_concurrent_streams INTEGER NOT NULL DEFAULT 100;

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS default_model_id TEXT NOT NULL DEFAULT 'parakeet-general';

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS home_region TEXT NOT NULL DEFAULT 'us-east-1';

CREATE INDEX IF NOT EXISTS idx_tenants_backend
    ON tenants(backend);

CREATE INDEX IF NOT EXISTS idx_tenants_home_region
    ON tenants(home_region);

CREATE INDEX IF NOT EXISTS idx_tenants_default_model_id
    ON tenants(default_model_id);

-- Run it against your production-like database before rollout:
--
-- psql "$DATABASE_URL" -f infra/db/002_tenant_backend_rollout.sql
--
-- This consolidates the tenant-level rollout fields needed for self-hosted Triton routing, Whisper fallback, stream limits, domain model selection, and regional GPU routing. The guide's self-hosted rollout depends on per-tenant ramping while keeping Whisper available as fallback.
