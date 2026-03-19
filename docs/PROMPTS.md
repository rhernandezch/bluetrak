# Bluetrak — Prompts Log

## Session 1: Technology Stack Decision (2026-03-19)

**Prompt:** Evaluate Python, Go, and TypeScript for building a headless USD/ARS exchange rate tracker. Consider data sources (Western Union POST API, DolarApp GET API, infodolar HTML scraping), scheduling, alerting, and deployment simplicity.

**Outcome:** Python selected. See `plans/01_PLAN.md` and `decisions/01_DECISIONS.md`.

## Session 2: Project Bootstrap & Implementation (2026-03-19)

**Prompt:** Implement the chosen Python stack: bootstrap project with `uv`, create project structure, implement data fetchers (DolarApp, Western Union, infodolar), SQLite storage, APScheduler, and alerting skeleton.
