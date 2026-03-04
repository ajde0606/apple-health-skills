PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS quantity_samples (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    ts INTEGER NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    device TEXT,
    metadata_json TEXT,
    ingested_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS category_samples (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    device TEXT,
    metadata_json TEXT,
    ingested_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_batches (
    batch_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    received_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quantity_user_type_ts ON quantity_samples(user_id, type, ts);
CREATE INDEX IF NOT EXISTS idx_category_user_type_start ON category_samples(user_id, type, start_ts);
