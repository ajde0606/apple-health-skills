# Apple Health Query Skill

Use this skill to fetch recent health data from the local SQLite store populated
by the collector and provide real-time monitoring, pattern detection, and advice.

## Prerequisites

The user must have run `bash scripts/setup.sh` and have the collector running
(`bash scripts/start.sh`). `.env` in the repo root provides `AHB_USER_ID` and
`AHB_DB_PATH` automatically.

## Command

```bash
python scripts/query_health.py --window-hours 24 --sleep-nights 7 --types heart_rate,glucose,sleep_stage
```

> `--user-id` and `--db` are read from `.env` automatically; no need to
> hard-code any user-specific values.

## Output contract

JSON object with:
- `generated_at` — ISO-8601 timestamp of query
- `user_id` — whose data this is
- `window_hours` — quantity sample lookback window
- `quantity` — map of metric type → array of `{ts, value, unit, source, device}`
- `sleep` — array of `{start_ts, end_ts, category, source, device}` segments

## What the agent should do

1. **Run the command** to fetch fresh data.
2. **Summarise** key metrics: resting heart rate trend, glucose levels, sleep
   duration and quality (deep/REM breakdown).
3. **Detect patterns** worth flagging:
   - Heart rate sustained above 100 bpm at rest → suggest checking in.
   - Glucose above 180 mg/dL or below 70 mg/dL → flag immediately.
   - Less than 6 hours total sleep or <10% deep sleep → recovery advice.
   - Sudden resting HR spike vs 7-day baseline → note it.
4. **Give actionable advice** tied to the specific numbers (e.g. "Your glucose
   peaked at 142 mg/dL two hours after dinner — that's within range, but worth
   watching if it happens again").
5. **Offer to re-check** on a cadence the user requests ("Check again in 30
   minutes and alert me if HR goes above 90").
6. **Always cite** the time window used ("based on the last 24 hours / 7 nights").

## Important notes

- Informational only — not medical advice.
- For extreme or persistent values recommend the user consult a clinician.
- Never hardcode a user ID; always rely on the `AHB_USER_ID` env variable
  loaded from `.env`.
