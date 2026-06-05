# Session 06 — DolarApp renamed to ARQ

## Decision: Use `arq` as the canonical source key

**Context:** The code uses `dolarapp` as both a user-facing label and a stable
source identifier in alert configuration, tests, and stored `Rate.source` values.

**Chosen:** Rename the canonical source key to `arq`.

**Rationale:** The user asked to rename DolarApp everywhere. Keeping `dolarapp`
as the source key would leave the old name visible in alerts and persisted rows.

## Decision: Keep backward compatibility for the old alert env var

**Context:** Existing deployments may already set
`BLUETRAK_ALERT_LEVEL_DOLARAPP`, especially because DolarApp alerts were
previously considered noisy.

**Chosen:** Prefer `BLUETRAK_ALERT_LEVEL_ARQ`, but accept the legacy
`BLUETRAK_ALERT_LEVEL_DOLARAPP` value when the new setting is not provided.

**Rationale:** This completes the rename for the primary interface while avoiding
a silent behavior change for deployed `.env` files.

## Decision: Keep the existing API hostname

**Context:** The live API endpoint in the repo is
`https://api.dolarapp.com/v1/tickers?currencies=ARS`.

**Chosen:** Rename our local constant to `ARQ_URL`, but keep the endpoint URL
unchanged until a verified replacement endpoint exists.

**Rationale:** A brand rename does not necessarily imply an API hostname change.
Changing the hostname without confirmation would risk breaking rate collection.
