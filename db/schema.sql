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

CREATE TABLE IF NOT EXISTS live_events (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts REAL NOT NULL,
    value INTEGER NOT NULL,
    unit TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_vendor TEXT NOT NULL,
    device_id TEXT NOT NULL,
    source_device_name TEXT,
    received_at INTEGER NOT NULL,
    PRIMARY KEY(session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_quantity_user_type_ts ON quantity_samples(user_id, type, ts);
CREATE INDEX IF NOT EXISTS idx_category_user_type_start ON category_samples(user_id, type, start_ts);
CREATE INDEX IF NOT EXISTS idx_live_events_session_seq ON live_events(session_id, seq);

-- ─── Whoop tables ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS whoop_cycles (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER,
    strain REAL,
    kilojoule REAL,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    synced_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS whoop_recoveries (
    cycle_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    recovery_score INTEGER,
    resting_heart_rate REAL,
    hrv_rmssd_milli REAL,
    spo2_percentage REAL,
    skin_temp_celsius REAL,
    synced_at INTEGER NOT NULL
);

-- id is a UUID string in API v2
CREATE TABLE IF NOT EXISTS whoop_sleeps (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    nap INTEGER NOT NULL DEFAULT 0,
    performance_percentage REAL,
    respiratory_rate REAL,
    total_in_bed_minutes REAL,
    total_sleep_minutes REAL,
    stage_sws_minutes REAL,
    stage_rem_minutes REAL,
    stage_wake_minutes REAL,
    synced_at INTEGER NOT NULL
);

-- id is a UUID string in API v2
CREATE TABLE IF NOT EXISTS whoop_workouts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    sport_name TEXT,
    strain REAL,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    kilojoule REAL,
    zone_zero_minutes REAL,
    zone_one_minutes REAL,
    zone_two_minutes REAL,
    zone_three_minutes REAL,
    zone_four_minutes REAL,
    zone_five_minutes REAL,
    synced_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_whoop_cycles_user_ts ON whoop_cycles(user_id, start_ts);
CREATE INDEX IF NOT EXISTS idx_whoop_recoveries_user_ts ON whoop_recoveries(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_whoop_sleeps_user_ts ON whoop_sleeps(user_id, start_ts);
CREATE INDEX IF NOT EXISTS idx_whoop_workouts_user_ts ON whoop_workouts(user_id, start_ts);

-- ─── Garmin tables ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS garmin_daily_summaries (
    summary_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    calendar_date TEXT NOT NULL,
    start_ts INTEGER,
    steps INTEGER,
    distance_meters REAL,
    active_seconds INTEGER,
    active_kilocalories INTEGER,
    bmr_kilocalories INTEGER,
    avg_stress_level INTEGER,
    max_stress_level INTEGER,
    avg_heart_rate INTEGER,
    resting_heart_rate INTEGER,
    min_heart_rate INTEGER,
    max_heart_rate INTEGER,
    body_battery_charged INTEGER,
    body_battery_drained INTEGER,
    moderate_intensity_seconds INTEGER,
    vigorous_intensity_seconds INTEGER,
    floors_climbed INTEGER,
    avg_spo2 REAL,
    avg_respiration_rate REAL,
    synced_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS garmin_sleeps (
    summary_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    calendar_date TEXT NOT NULL,
    start_ts INTEGER,
    duration_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds INTEGER,
    awake_seconds INTEGER,
    avg_spo2 REAL,
    avg_respiration_rate REAL,
    resting_heart_rate INTEGER,
    synced_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS garmin_activities (
    summary_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    activity_type TEXT,
    duration_seconds INTEGER,
    distance_meters REAL,
    avg_heart_rate INTEGER,
    max_heart_rate INTEGER,
    active_kilocalories INTEGER,
    avg_speed REAL,
    avg_pace_min_per_km REAL,
    elevation_gain_meters REAL,
    synced_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_garmin_daily_user_date ON garmin_daily_summaries(user_id, calendar_date);
CREATE INDEX IF NOT EXISTS idx_garmin_sleeps_user_date ON garmin_sleeps(user_id, calendar_date);
CREATE INDEX IF NOT EXISTS idx_garmin_activities_user_ts ON garmin_activities(user_id, start_ts);
