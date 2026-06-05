# Plan 03 — Rename DolarApp to ARQ

## Context

DolarApp is now named ARQ. The codebase still uses the old brand in source
classes, source identifiers, alert configuration, tests, and documentation.

## Steps

1. Rename the exchange-rate source module, class, constants, and canonical source
   name from DolarApp/dolarapp to ARQ/arq.
2. Update source registration, tests, alert examples, configuration names, and
   environment documentation.
3. Keep a compatibility path for the previous DolarApp alert env var so existing
   deployments do not silently change behavior.
4. Run unit and integration tests.

## Files to Modify

| File | Change |
|---|---|
| `src/bluetrak/sources/dolarapp.py` | Move to `arq.py`, rename class and source key |
| `src/bluetrak/sources/__init__.py` | Register `ArqSource` |
| `src/bluetrak/config.py` | Rename alert setting and add compatibility lookup |
| `tests/test_sources.py` | Update source tests |
| `tests/test_alerts.py` | Update alert source tests |
| `.env.example` | Update env var example |
| `README.md` | Update public docs and examples |
| `docs/*` | Update historical references where appropriate |
