# Skill publishing and setup

If you want to publish the `openclaw-skill` folder so others can install it, use this structure and release flow.

## 1. Keep a clean skill package layout

```text
openclaw-skill/
├── SKILL.md               # required metadata + workflow instructions
├── scripts/               # optional deterministic helpers
├── references/            # optional deep docs loaded only when needed
└── assets/                # optional templates or static files used in outputs
```

Only `SKILL.md` is required. Keep it concise and move long examples to `references/` so agents load details only when needed.

## 2. Treat the skill as a versioned artifact

- Use semantic version tags (for example `v0.1.0`, `v0.2.0`).
- Add a short release note for each tag describing behavior changes.
- Keep breaking changes explicit in `SKILL.md` (new required tools, changed output contract, etc.).

## 3. Publish from a dedicated folder or repo

Two common options:

1. **Monorepo (current setup):** keep `openclaw-skill/` in this repo and tag full-repo releases.
2. **Skill-only repo:** copy `openclaw-skill/` into its own repository for simpler discovery/versioning.

If users install directly from GitHub, a skill-only repository is usually easiest to communicate.

## 4. Add install instructions for users

Document one command path users can follow consistently, for example:

```bash
# Example (adjust to your Codex/OpenClaw installer tooling)
git clone https://github.com/<you>/<your-skill-repo>.git
```

Then show a minimal "verify install" step (for example, list installed skills and confirm `apple-health-query` appears).

## 5. Keep runtime dependencies separate from skill logic

- Skill instructions live in `openclaw-skill/SKILL.md`.
- Operational code for this project (collector, scripts, db) stays outside the skill package.
- Reference project scripts from the skill only when they are stable entry points (for example `scripts/query_health.py`).

This separation makes the published skill portable and easier to maintain.

## 6. Validate before each release

Run a smoke check locally before tagging:

```bash
python scripts/query_health.py --window-hours 24 --sleep-nights 7
```

If command names or output JSON changed, update `openclaw-skill/SKILL.md` in the same commit as the code change.
