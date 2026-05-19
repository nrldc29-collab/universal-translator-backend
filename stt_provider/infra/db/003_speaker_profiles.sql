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

CREATE INDEX IF NOT EXISTS idx_speaker_profiles_active_tenant
    ON speaker_profiles(tenant_id)
    WHERE deleted_at IS NULL;

# Run:
#
# psql "$DATABASE_URL" -f infra/db/003_speaker_profiles.sql
#
# This adds the durable storage needed for speaker enrollment, including tenant ownership, encrypted voice embeddings, embedding model version, consent tracking, and soft deletion. Speaker enrollment is part of the guide's Phase 4 differentiation path, and the guide explicitly warns that voice embeddings are biometric data that must be encrypted and deletable.
