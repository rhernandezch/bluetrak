# Bluetrak

USD/ARS exchange rate tracker. Fetches rates from multiple sources on a schedule, stores them in SQLite, and sends intelligent alerts via Telegram or webhook when favorable selling conditions are detected.

## Sources

- **DolarApp** — ARQ Finance API (GET + JSON)
- **Western Union** — Price catalog API (POST + JSON)
- **infodolar.com** — CCL rate (HTML scraping)

## Quick start

```bash
uv sync
cp .env.example .env   # edit to configure alerts
uv run bluetrak
```

## How alerting works

Every fetch cycle (15 min by default), each source rate is evaluated by an **adaptive ensemble engine** that adjusts its analysis strategy based on how much historical data is available.

### Data maturity tiers

The engine tracks how many distinct rate changes have been recorded to determine which analysis components to enable:

| Tier | Changes | ~Age | Analysis enabled |
|---|---|---|---|
| COLD | 0–3 | <1 day | Simple threshold fallback |
| PRELIMINARY | 4–9 | 1–3 days | Percentile rank |
| DEVELOPING | 10–19 | 3–7 days | + Trend residual |
| STABLE | 20–49 | 7–14 days | + All components |
| FULL | 50+ | 14+ days | + Urgency modulation |

### Analysis components

**Percentile rank** — Is the current sell rate in the top N% of the last 7 days? Configurable via `BLUETRAK_ALERT_PERCENTILE_THRESHOLD` (default: top 10%).

**Trend residual** — Fits a linear trend over the last 14 days and checks if the current rate is more than 1 standard deviation above expected. Detects spikes above underlying drift.

**Momentum plateau** — Checks whether earlier rate changes were positive but the latest readings are flat or negative. When this coincides with an alert trigger, urgency is elevated to **HIGH** — the rate may be peaking.

### Regime change detection

If any single rate change exceeds 5% (e.g. a currency devaluation), the engine discards pre-change history and resets its analysis windows. This prevents old "normal" rates from suppressing alerts during a crisis.

### Alert message example

```
*dolarapp* sell rate *1485.20* ARS/USD
• 94th percentile of the last 7 days (highest was 1491.00)
• 22.00 ARS above the 14-day trend
• Momentum is flattening — rate has stopped increasing

⚡ This may be a good time to sell.
```

The `⚡` line only appears when urgency is HIGH (alert triggered + momentum plateau detected simultaneously).

### Delivery channels

Both channels can be active at the same time. A failure on one does not block the other.

- **Telegram** — Markdown-formatted message via Bot API
- **Webhook** — HTTP POST with `{"text": "..."}` body

## Configuration

All settings are environment variables with the `BLUETRAK_` prefix. See `.env.example` for a ready-to-copy template.

| Variable | Default | Description |
|---|---|---|
| `BLUETRAK_DB_PATH` | `bluetrak.db` | SQLite database path |
| `BLUETRAK_FETCH_INTERVAL_MINUTES` | `15` | Polling interval (minutes) |
| `BLUETRAK_TELEGRAM_BOT_TOKEN` | — | Bot token from @BotFather |
| `BLUETRAK_TELEGRAM_CHAT_ID` | — | Target chat or group ID |
| `BLUETRAK_WEBHOOK_URL` | — | Generic webhook endpoint |
| `BLUETRAK_ALERT_PERCENTILE_THRESHOLD` | `90.0` | Percentile rank to trigger alert (0–100) |
| `BLUETRAK_ALERT_PERCENTILE_WINDOW_DAYS` | `7` | Lookback window for percentile (days) |
| `BLUETRAK_ALERT_TREND_WINDOW_DAYS` | `14` | Lookback window for trend fitting (days) |
| `BLUETRAK_SELL_RATE_ALERT_ABOVE` | `0` (disabled) | Legacy: simple rate threshold fallback |

Alerts are disabled when no delivery channel is configured (i.e. no Telegram token+chat or webhook URL).

#### Getting a Telegram bot token and chat ID

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`, follow the prompts to name your bot, and copy the token it returns — that is `BLUETRAK_TELEGRAM_BOT_TOKEN`. It looks like `123456789:AAFxxxxxxx`.
3. To get your chat ID, send any message to your new bot, then open this URL in a browser (replace `<TOKEN>` with your token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Look for `"chat":{"id": ...}` in the response. That number (positive for private chats, negative for groups) is `BLUETRAK_TELEGRAM_CHAT_ID`.

> **Tip:** If you want alerts sent to a group instead of a private chat, add the bot to the group and send a message in the group before calling `getUpdates`.

### Setting env vars for local development

```bash
cp .env.example .env
# Edit .env with your values, then run:
uv run bluetrak
```

`pydantic-settings` reads `.env` from the working directory (configured via `env_file` in `config.py`).

### Setting env vars for deployment (systemd)

The production service reads from `/opt/bluetrak/.env` via the `EnvironmentFile` directive in the systemd unit. Secrets never appear in shell history or the process table.

```bash
sudo nano /opt/bluetrak/.env
sudo systemctl restart bluetrak
```

The `.env` file should be readable only by the service user (`chmod 600`, owned by `bluetrak`). The setup script handles this automatically.

## Deployment (Google Cloud e2 + Docker Compose)

The app runs as a Docker container managed by Compose. SQLite data is persisted in a named volume (`bluetrak-data`), so it survives container rebuilds.

### 1. Provision the VM

```bash
gcloud compute instances create bluetrak \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --zone=us-central1-a
```

### 2. Run the setup script

SSH into the VM and run the setup script directly from the repo. Since the repo is private, authenticate first using a **GitHub Deploy Key** — the script generates one and pauses for you to add it:

```bash
# Download and run the setup script using your GitHub credentials (one-time)
curl -sH "Authorization: token YOUR_PAT" \
  https://raw.githubusercontent.com/rhernandezch/bluetrak/main/deploy/setup.sh | bash
```

> **Getting a PAT:** GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → New token. The `repo` scope (read-only) is enough for a private repo.

The script will:
1. Install Docker
2. Generate an SSH deploy key, print the public key, and **pause** — add it to GitHub at **Settings → Deploy keys** (read-only), then press Enter
3. Clone the repo via SSH
4. Copy `.env.example` to `.env`

### 3. Configure and start

```bash
nano ~/bluetrak/.env          # fill in Telegram credentials and review settings
cd ~/bluetrak
docker compose up -d --build  # build image and start
docker compose logs -f        # tail logs
```

### Deploying updates

```bash
bash ~/bluetrak/deploy/deploy.sh
```

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check src/ tests/
```
