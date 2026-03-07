---
layout: default
title: Apple Health Skills
---

# Apple Health Skills

Stream your iPhone's Apple Health data to your Mac in real time — **no Tailscale required on the iPhone**.

Apple Health Bridge syncs health metrics from **Apple Health / HealthKit** to a local Mac server, where an AI agent (OpenClaw) can analyze trends, detect patterns, and provide proactive health insights — **all locally, with no cloud services or external servers.**

```
iPhone ──HealthKit──► IOS Health Bridge app
                              │  (HTTPS — public internet via Tailscale Funnel)
                              ▼
                     Mac collector (FastAPI)  ← token auth required
                              │
                              ▼
                       SQLite (local only)
                              │
                              ▼
               OpenClaw agent  →  alerts & advice
```

View the full documentation on [GitHub](https://github.com/ajde0606/apple-health-skills).
