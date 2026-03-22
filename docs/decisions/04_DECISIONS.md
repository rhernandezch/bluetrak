# Session 04 — Per-source alert level control

## Decision: Per-source env vars over single comma-separated var

**Context:** DolarApp alerts were too noisy. Roberto wanted per-source control
over real-time alert notifications.

**Considered:**
1. One env var per source (`BLUETRAK_ALERT_LEVEL_DOLARAPP`, etc.)
2. Single comma-separated env var (`BLUETRAK_ALERT_SOURCES=western_union:high,...`)

**Chosen:** Option 1 — individual env vars.

**Rationale:** No plans to add more sources. Individual env vars are simpler,
self-documenting, and work natively with pydantic-settings `StrEnum` parsing
without custom validators.

## Decision: Filter at dispatch, not in the engine

**Context:** Should the per-source level suppress alert evaluation or only
suppress notification dispatch?

**Chosen:** Filter at the dispatch point in `scheduler.py`.

**Rationale:** Summaries should still report all alerts that *would have* fired,
regardless of per-source level. Filtering in the engine would lose this
visibility. The `state.add(signals)` call runs before the level check, so
12h summaries remain complete.

## Decision: AlertLevel values — off / normal / high

- `off` — no real-time alerts (data still collected and shown in summaries)
- `normal` — receive all alerts, both NORMAL and HIGH urgency (default)
- `high` — only receive HIGH urgency alerts (momentum fading near peak)

Default for unconfigured or unknown sources: `normal`.
