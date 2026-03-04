---
name: apple-health-query
description: Use this skill when the user asks for Apple Health summaries, trends, alerts, or check-ins from the local collector. Validate collector connectivity over HTTP and fetch fresh data with shell commands before giving coaching-style guidance.
---

# Apple Health Query Skill

Use this skill to analyze Apple Health data already synced into local SQLite by the collector.

## Tools to use

- **Shell tool**: run `scripts/query_health.py` to pull fresh JSON data.
- **HTTP tool**: optionally verify collector availability with `/healthz` before troubleshooting missing data.

## Workflow

1. **(Optional health check) Verify collector is reachable** when user reports stale/missing data:
   - `curl -fsS http://<collector-host>:8443/healthz`
   - if TLS is enabled: `curl -fsS https://<collector-host>:8443/healthz`
2. **Query the local database via shell** (preferred default):
   - `python scripts/query_health.py --window-hours 24 --sleep-nights 7 --types heart_rate,glucose,sleep_stage`
3. **Adjust parameters to user intent**:
   - Short check-in: `--window-hours 1`
   - Daily review: `--window-hours 24 --sleep-nights 7`
   - Alert follow-up: keep `--types` narrow to requested metrics.
4. **Summarize with numbers and timestamps**, then give practical next steps.
5. **Always include safety framing**: informational only, not medical advice; suggest clinician contact for extreme/persistent readings.

## Output expectations

Base your answer on the returned JSON fields:
- `generated_at`, `user_id`, `window_hours`
- `quantity.<metric>[]` entries with `{ts, value, unit, source, device}`
- `sleep[]` entries with `{start_ts, end_ts, category, source, device}`

## Response style guardrails

- Cite the exact time window used (for example: “last 24 hours” and “last 7 nights”).
- Highlight notable thresholds carefully (e.g., glucose outside typical 70–180 mg/dL range).
- Tie suggestions to observed values; avoid generic advice.
- Never hardcode user IDs or DB paths—`scripts/query_health.py` already reads `.env`.
