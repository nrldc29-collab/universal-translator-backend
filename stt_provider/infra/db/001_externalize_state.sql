CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT[] NOT NULL DEFAULT ARRAY['stt:stream', 'stt:transcribe'],
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS usage_counters (
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    audio_seconds BIGINT NOT NULL DEFAULT 0,
    stream_count BIGINT NOT NULL DEFAULT 0,
    transcription_count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, usage_date)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    actor_id TEXT,
    event_type TEXT NOT NULL,
    resource TEXT,
    trace_id TEXT,
    payload_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_id
    ON api_keys(tenant_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created_at
    ON audit_log(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_usage_counters_tenant_date
    ON usage_counters(tenant_id, usage_date DESC);
