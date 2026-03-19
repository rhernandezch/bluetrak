# Bluetrak

USD/ARS exchange rate tracker. Fetches rates from multiple sources on a schedule and stores them in SQLite.

## Sources

- **DolarApp** — ARQ Finance API (GET + JSON)
- **Western Union** — Price catalog API (POST + JSON)
- **infodolar.com** — CCL rate (HTML scraping)

## Quick start

```bash
uv sync
uv run bluetrak
```

## Configuration

Environment variables (prefix `BLUETRAK_`):

| Variable | Default | Description |
|---|---|---|
| `BLUETRAK_DB_PATH` | `bluetrak.db` | SQLite database path |
| `BLUETRAK_FETCH_INTERVAL_MINUTES` | `15` | Polling interval |
| `BLUETRAK_SELL_RATE_ALERT_ABOVE` | `0` (disabled) | Alert threshold |
| `BLUETRAK_TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `BLUETRAK_TELEGRAM_CHAT_ID` | — | Telegram chat ID |
| `BLUETRAK_WEBHOOK_URL` | — | Generic webhook URL |

## Deployment (Oracle Cloud Free Tier)

Provision an Ampere A1 ARM instance (Ubuntu 22.04+), then:

```bash
# One-time setup on the VM
bash <(curl -s https://raw.githubusercontent.com/rhernandezch/bluetrak/main/deploy/setup.sh)

# Edit secrets
sudo nano /opt/bluetrak/.env

# Check it's running
sudo journalctl -u bluetrak -f
```

To deploy updates:

```bash
bash /opt/bluetrak/deploy/deploy.sh
```

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check src/ tests/
```
