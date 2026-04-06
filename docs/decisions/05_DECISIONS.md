# Session 05 — EVERY_CHANGE alert level

## Decision: New alert level vs. separate config flag

**Context:** Roberto wants to be notified every time Western Union's rate changes.
The existing ensemble system detects "good times to sell" via statistical analysis,
which is a fundamentally different alerting paradigm from "the number moved."

**Considered:**
1. New `EVERY_CHANGE` value in the existing `AlertLevel` enum
2. Separate boolean flag (`BLUETRAK_CHANGE_NOTIFY_WESTERN_UNION=true`)
3. Modifying the ensemble engine to always fire on rate changes

**Chosen:** Option 1 — extend the existing enum.

**Rationale:** Reuses the per-source alert level infrastructure without adding a
parallel config system. The enum values form a natural hierarchy:
`off → normal → high → every_change`. Pydantic handles the new value automatically.

## Decision: Change detection in scheduler, not in the alert engine

**Context:** Where should the "did the rate change?" logic live?

**Chosen:** In `scheduler.py:_handle_rate_change()`, before ensemble evaluation.

**Rationale:** Change detection is a simple comparison, not statistical analysis.
Putting it in the engine would conflate two unrelated concerns. Sources configured
as `EVERY_CHANGE` are partitioned out of the ensemble pipeline entirely — they
never reach `evaluate_alerts()`.

## Decision: Trigger on sell_rate only

**Context:** Should the change detection compare buy_rate, sell_rate, or both?

**Chosen:** Trigger on `sell_rate` changes only. Buy rate delta is shown in the
notification message when sell_rate changes and buy_rate also differs.

**Rationale:** The entire alerting system is oriented around sell_rate (the rate
you get when selling USD). For Western Union specifically, buy_rate == sell_rate
anyway. Keeping the trigger consistent avoids confusion.
