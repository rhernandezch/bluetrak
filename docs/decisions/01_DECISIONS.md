# Decisions 01: Technology Stack

**Date:** 2026-03-19

## Decision: Use Python

**Context:** Greenfield personal project to track USD/ARS exchange rates from multiple sources.

**Decision:** Python with httpx + APScheduler + BeautifulSoup + SQLite + pydantic.

**Rationale:**
- Core challenge is data source integration (reverse-engineering APIs, handling HTML changes) — Python's REPL + httpx + BS4 is unmatched for this
- Strong proficiency = zero learning-curve tax
- Deployment size difference (80MB vs 15MB Docker image) is negligible for a personal service
- Data sources will change over time, requiring parser iteration — Python is fastest for this

**Rejected alternatives:**
- **Go**: Better deployment story but 2-3x more verbose for scraping. Would pick if "deploy and forget" mattered more.
- **TypeScript (Bun)**: No clear advantage over Python, less experience, ecosystem churn risk.

## Decision: Use `uv` as package manager

**Rationale:** Modern, fast, handles virtualenv + dependency resolution. Replaces pip, pip-tools, and virtualenv in one tool.

## Decision: SQLite for storage

**Rationale:** Single-file database, zero ops, perfect for personal service. stdlib support. No need for PostgreSQL complexity.

## Decision: Project structure with `src/` layout

**Rationale:** Standard Python packaging convention. Prevents import confusion between package and project root.
