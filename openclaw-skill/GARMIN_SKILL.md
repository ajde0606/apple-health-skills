---
name: garmin-query
description: Use this skill when the user asks about Garmin data — daily steps, resting heart rate, stress levels, Body Battery, sleep quality, or workout analysis. Fetch fresh data from the local SQLite database (populated by the Garmin sync script) and give coaching-style guidance.
---

# Garmin Query Skill

Use this skill to analyze Garmin data synced from the Garmin Health API into the local SQLite database.

## Setup (one-time)

Before data is available, the user must:

1. Register as a Garmin Health API developer at https://developer.garmin.com/gc-developer-program/overview/ and create an application to obtain a consumer key and secret.
2. Add credentials to `.env`:
   ```
   GARMIN_CONSUMER_KEY=<consumer-key>
   GARMIN_CONSUMER_SECRET=<consumer-secret>
   ```
3. Authorize and store tokens:
   ```
   python scripts/setup_garmin.py
   ```
4. Run the initial sync:
   ```
   python scripts/sync_garmin.py --days 30
   ```

After setup, keep data fresh by running `sync_garmin.py` on a schedule (e.g. daily cron).

## Syncing fresh data

Before querying, optionally refresh the local database:

```
python scripts/sync_garmin.py --days 7
```

## Querying data

```
python scripts/query_garmin.py --window-days 7
```

Adjust `--window-days` to match the user's request (default: 7).

## Output fields

The query script returns JSON with:

### `features.daily`
- `avg_steps` — average daily step count
- `latest_steps` — most recent day's steps
- `total_steps` — total steps in window
- `avg_resting_hr` — average resting heart rate (bpm)
- `latest_resting_hr` — most recent resting HR
- `avg_stress_level` — average stress level (0–100)
- `latest_stress_level` — most recent stress level
- `avg_body_battery_charged` — average Body Battery charged per day
- `avg_body_battery_drained` — average Body Battery drained per day
- `avg_active_kilocalories` — average active calories burned per day
- `avg_spo2` — average blood oxygen saturation (%)
- `days` — number of daily records in window

### `features.sleep`
- `avg_duration_minutes` — average total sleep duration
- `latest_duration_minutes` — last night's sleep duration
- `avg_deep_sleep_minutes` — average deep (SWS) sleep
- `avg_rem_minutes` — average REM sleep
- `avg_respiration_rate` — average breaths per minute during sleep
- `avg_sleep_efficiency` — ratio of sleep time to time in bed (0–1)
- `nights` — number of nights in window

### `features.activity`
- `total_activities` — number of workouts recorded
- `avg_duration_minutes` — average workout duration
- `total_kilocalories` — total active calories across all activities
- `activity_types` — list of distinct activity types

### `daily_summaries[]` — individual daily records
Each entry has `calendar_date`, `steps`, `distance_meters`, `resting_heart_rate`, `avg_stress_level`, `body_battery_charged`, `body_battery_drained`, `active_kilocalories`, `avg_spo2`, `moderate_intensity_seconds`, `vigorous_intensity_seconds`, `floors_climbed`.

### `sleeps[]` — individual sleep records
Each entry has `calendar_date`, `start_date`, `duration_minutes`, `deep_sleep_minutes`, `light_sleep_minutes`, `rem_sleep_minutes`, `awake_minutes`, `sleep_efficiency`, `avg_spo2`, `avg_respiration_rate`, `resting_heart_rate`.

### `activities[]` — individual workout records
Each entry has `start_date`, `activity_type`, `duration_minutes`, `distance_meters`, `avg_heart_rate`, `max_heart_rate`, `active_kilocalories`, `avg_speed`, `avg_pace_min_per_km`, `elevation_gain_meters`.

## Workflow

1. **Sync recent data** (optional, if user wants latest):
   - `python scripts/sync_garmin.py --days 7`
2. **Query the database**:
   - `python scripts/query_garmin.py --window-days 7`
3. **Adjust window to user intent**:
   - "How was my activity this week?" → `--window-days 7`
   - "Show me last month's trends" → `--window-days 30`
   - "Just today's stats" → `--window-days 1`
4. **Summarize with numbers**, then give practical next steps.
5. **Always include safety framing**: informational only, not medical advice.

## Coaching guidance

### Steps and activity
- **10,000+ steps/day**: Generally associated with good cardiovascular health.
- **Consistent low steps (<5,000)**: Flag sedentary pattern; suggest light movement breaks.
- **Moderate + vigorous intensity**: WHO recommends 150+ min/week moderate or 75+ min/week vigorous.

### Stress level interpretation
- **0–25 (Rest)**: Relaxed state; good for recovery.
- **26–50 (Low stress)**: Normal daily activity level.
- **51–75 (Medium stress)**: Elevated; monitor for sustained patterns.
- **76–100 (High stress)**: High physiological stress; prioritize recovery.
- Chronic high stress (3+ days above 60) → recommend sleep focus, light activity, stress reduction.

### Body Battery
- **Body Battery charged vs. drained**: Net daily balance indicates recovery quality.
- Waking with Body Battery below 30 consistently → insufficient overnight recovery.
- Body Battery draining faster than charging → overreaching or poor sleep pattern.

### Resting heart rate
- Resting HR elevated 5+ bpm above personal baseline → possible fatigue, illness, or poor hydration.
- Gradually declining resting HR over weeks → improving cardiovascular fitness.

### Sleep analysis
- Deep sleep < 60 min/night consistently → flag for sleep quality issues.
- REM < 90 min/night → may affect cognitive recovery.
- Sleep efficiency below 85% → investigate sleep hygiene, timing, or environment.

### Workout analysis
- Balance activity types across the week (cardio, strength, flexibility).
- Elevated average HR during sleep nights following hard workouts → consider extra recovery day.

### SpO2 (blood oxygen)
- Normal range: 95–100%.
- Persistent readings below 94% → consult a healthcare provider.
- Drops during sleep may indicate sleep-disordered breathing.

## Response style guardrails

- Cite the exact window used (e.g., "last 7 days").
- Lead with the most actionable metrics: steps, resting HR, stress, Body Battery.
- Tie suggestions to actual values; avoid generic advice.
- Flag persistent patterns (3+ days) more assertively than single-day anomalies.
- Never hardcode user IDs or DB paths — scripts read `.env` automatically.
- Remind users that Garmin metrics are informational, not medical diagnoses.
