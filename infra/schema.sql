-- Talos — Metadata Catalog Schema
-- Tracks every digital asset that enters the system: what it is, where it lives, and its current state.

CREATE TABLE IF NOT EXISTS assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    asset_type      TEXT NOT NULL CHECK (asset_type IN ('image', 'video', 'document', 'model_3d', 'audio')),
    origin_project  TEXT NOT NULL,
    bucket          TEXT NOT NULL,
    object_key      TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'classified', 'stored', 'error')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Speeds up the worker's poll/filter for unprocessed assets
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets (status);

-- Speeds up lookups by type, used by the distribution/consumer layer
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets (asset_type);
