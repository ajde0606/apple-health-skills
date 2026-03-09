---
name: oura-ring-query
description: Use this skill when the user asks for Oura Ring health summaries, readiness scores, sleep analysis, HRV trends, or activity data. Sync fresh data from the Oura Cloud API first, then query the local SQLite database for coaching-style analysis.
---

# Oura Ring Query Skill

Use this skill to sync and analyze Oura Ring data stored in local SQLite by the Oura collector.

## Tools to use

- **Shell tool**: run `oura/collector.py` to pull fresh data from the Oura Cloud API, then `scripts/query_oura.py` to query it.

## Workflow

1. **Sync fresh data from Oura Cloud** (do this first, especially for recent readings):
   ```
   python oura/collector.py
   ```
   This incrementally fetches only data since the last sync. To force a full refresh:
   ```
   python oura/collector.py --full-refresh --lookback-days 14
   ```

2. **Query the local database**:
   ```
   python scripts/query_oura.py --window-hours 24 --sleep-nights 7
   ```

3. **Adjust parameters to user intent**:
   - Quick readiness check: `--window-hours 24 --types readiness_score,resting_heart_rate,hrv`
   - Sleep deep dive: `--window-hours 48 --sleep-nights 14 --types sleep_stage,hrv`
   - Activity overview: `--window-hours 168 --types step_count,energy_burned,active_energy_burned`
   - Full picture: `--window-hours 24 --sleep-nights 7` (default — all metrics)

4. **Summarize with numbers and timestamps**, then provide practical next steps.
5. **Always include safety framing**: informational only, not medical advice; suggest clinician contact for extreme or persistent readings.

## Environment requirements

The following must be set in `.env` or the environment:

| Variable | Purpose |
|----------|---------|
| `OURA_PAT` | Oura Personal Access Token (create at https://cloud.ouraring.com/personal-access-tokens) |
| `AHB_USER_ID` | User identifier for data namespacing |
| `AHB_DB_PATH` | Path to SQLite database (default: `db/health.db`) |

If `OURA_PAT` is missing, guide the user to create one at https://cloud.ouraring.com/personal-access-tokens and add it to `.env`.

## Output expectations

Base your answer on the returned JSON fields from `query_oura.py`:

- `generated_at`, `user_id`, `window_hours`
- `quantity.<metric>[]` — raw samples with `{ts, value, unit, source, device}`
- `sleep[]` — category samples with `{start_ts, end_ts, category, source, device}`
- `features.sleep` — per-night breakdown and rolling averages
- `features.heart` — median/avg HR, resting HR, HRV stats
- `features.readiness` — latest score, rolling average, top contributors
- `features.activity` — avg daily steps, active calories
- `sync_state` — last synced date per data type (useful for diagnosing stale data)

## Oura-specific metrics to highlight

### Readiness Score (0–100)
- ≥ 85: Optimal — ready for high-intensity training
- 70–84: Good — normal training load is fine
- 60–69: Fair — consider moderate or recovery activity
- < 60: Pay attention — rest, hydration, illness indicators

Key contributors to mention: `resting_heart_rate`, `hrv_balance`, `recovery_index`, `sleep`, `activity_balance`.

### HRV (ms)
- Day-to-day HRV variability is expected; compare against the user's personal baseline.
- A downward trend over 3+ days signals elevated physiological stress.

### Resting Heart Rate (bpm)
- Elevated RHR (> 5 bpm above personal baseline) often precedes illness or overtraining.
- Report the Oura-measured nightly lowest RHR, not spot readings.

### Sleep stages
- Adults: target ≥ 15% deep sleep, ≥ 20–25% REM sleep of total sleep time.
- Report in minutes and percentages; use `features.sleep.recent_nights` for per-night breakdown.

## Response style guardrails

- Always cite the time window and sync timestamp.
- Note if sync_state shows a stale last_date (> 1 day ago) — advise running the collector again.
- Tie suggestions to observed values; avoid generic advice.
- Flag: resting HR > 10 bpm above norm, HRV drop > 20%, readiness < 55, or sleep < 5 hours.
- Never hardcode user IDs or DB paths — `query_oura.py` reads `.env` automatically.

---

## Setup (first-time only)

If data is missing or `sync_state` is empty, guide the user through setup:

```bash
bash scripts/setup_oura.sh
```

Or manually:
1. Create a Personal Access Token at https://cloud.ouraring.com/personal-access-tokens
2. Add `OURA_PAT=<token>` to `.env`
3. Run the initial sync: `python oura/collector.py --lookback-days 30`

## Syncing specific data types

```
python oura/collector.py --types heartrate,sleep,readiness
```

Available types: `heartrate`, `hrv`, `readiness`, `activity`, `sleep`, `resting_hr`
