# Bluetrak — Prompts Log

## Session 1: Technology Stack Decision (2026-03-19)

**Prompt:** Evaluate Python, Go, and TypeScript for building a headless USD/ARS exchange rate tracker. Consider data sources (Western Union POST API, DolarApp GET API, infodolar HTML scraping), scheduling, alerting, and deployment simplicity.

**Outcome:** Python selected. See `plans/01_PLAN.md` and `decisions/01_DECISIONS.md`.

## Session 3: CI docs-only skip (2026-03-19)

**Prompt:** Have GHA not run on branches/PRs only involving docs.

**Outcome:** Added `paths-ignore` for `docs/**`, `**.md`, `**.txt` to both `push` and `pull_request` triggers in `.github/workflows/ci.yml`.

## Session 2: Project Bootstrap & Implementation (2026-03-19)

**Prompt:** Implement the chosen Python stack: bootstrap project with `uv`, create project structure, implement data fetchers (DolarApp, Western Union, infodolar), SQLite storage, APScheduler, and alerting skeleton.

## Session 4: Intelligent Alert System (2026-03-19)

**Prompt:** Research and implement an intelligent alert system that detects local peaks in ARS/USD exchange rates, replacing the static threshold approach. Evaluated statistical (Bollinger, ARIMA, z-score), ML (Prophet, XGBoost), and heuristic (percentile, momentum) methods. Selected a 3-component ensemble: percentile rank, linear trend residual, and momentum plateau detection.

**Outcome:** Implemented ensemble alert engine with cold-start strategy, regime change detection, and structured AlertSignal model. See `plans/02_PLAN.md` and `decisions/03_DECISIONS.md`.

## Session 5: Per-source alert level control (2026-03-22)

**Prompt:** Add per-source alert level env vars (off/normal/high) to control which real-time notifications get dispatched. DolarApp was too noisy; Roberto primarily wants Western Union alerts. Data collection and summaries should remain unaffected.

**Outcome:** Added `BLUETRAK_ALERT_LEVEL_{SOURCE}` env vars with dispatch-level filtering. See `decisions/04_DECISIONS.md`.

## Session 6: Every-change alert level for Western Union (2026-04-06)

**Prompt:** I want to get alerts every time that Western Union changes, what would be the best way to achieve this with the current design?

**Outcome:** Added `EVERY_CHANGE` alert level that bypasses ensemble analysis and notifies on any sell_rate change. See `decisions/05_DECISIONS.md`.

## Session 7: DolarApp renamed to ARQ (2026-06-04)

**Prompt:** DolarApp is now named ARQ. Let's rename that everywhere.

**Outcome:** Renamed the source, config, tests, and user-facing docs to ARQ while
keeping legacy alert-env compatibility. See `plans/03_PLAN.md` and
`decisions/06_DECISIONS.md`.
