# Plan 01: Technology Stack Selection

**Date:** 2026-03-19
**Status:** Complete

## Goal

Choose the language and framework for Bluetrak, a headless USD/ARS exchange rate tracker.

## Alternatives Evaluated

1. **Python** (FastAPI + APScheduler + httpx + BeautifulSoup)
2. **Go** (stdlib + robfig/cron + goquery)
3. **TypeScript** (Bun + croner + cheerio)

## Decision

**Python** — best DX for HTTP/scraping iteration, strong proficiency, negligible deployment disadvantage for a personal service.

## Implementation Steps

1. Bootstrap project with `uv init`
2. Implement DolarApp fetcher first (simplest — GET + JSON)
3. Verify SQLite storage
4. Add Western Union fetcher (POST + JSON)
5. Add infodolar scraper (HTML)
6. Wire up APScheduler
7. Add alerting (stretch goal)
