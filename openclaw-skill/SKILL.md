# Apple Health Query Skill (Milestone 1)

Use this skill to fetch recent health data from the local SQLite store populated by the collector.

## Command

```bash
python scripts/query_health.py --db db/health.db --user-id dad --window-hours 24 --sleep-nights 7 --types heart_rate,glucose
```

## Output contract

JSON object with:
- `generated_at`
- `window_hours`
- `quantity`: map of metric type -> recent quantity samples
- `sleep`: recent sleep stage segments

## Notes

- This skill is informational only and not medical advice.
- Mention windows used in responses (e.g. "last 24 hours", "last 7 nights").
