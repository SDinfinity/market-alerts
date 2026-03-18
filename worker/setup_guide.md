# Cloudflare Worker Setup Guide

This guide sets up a Cloudflare Worker that handles Telegram bot commands
instantly via webhook — instead of polling every 15 minutes.

**What changes:** Your bot will respond to `/add`, `/remove`, `/list`,
`/status`, and `/help` within 1-2 seconds instead of waiting up to 15 minutes.
The GitHub Actions schedule still runs for the daily opening/closing alerts.

**Time needed:** About 20 minutes.

---

## Prerequisites

- A Cloudflare account (free tier is enough)
- Node.js installed on your Mac (`node --version` to check; install from nodejs.org if missing)
- Your bot already works (Telegram token + chat ID set up)

---

## Step 1 — Install Wrangler (Cloudflare CLI)

```bash
npm install -g wrangler
```

Verify it works:
```bash
wrangler --version
```

---

## Step 2 — Log in to Cloudflare

```bash
wrangler login
```

This opens a browser window. Click **Allow** to grant Wrangler access to your
Cloudflare account. You only need to do this once.

---

## Step 3 — Edit wrangler.toml

Open `worker/wrangler.toml` and replace these two lines with your actual values:

```toml
GITHUB_OWNER = "your-github-username"   # e.g. "SDinfinity"
GITHUB_REPO  = "market-alerts"          # your repo name, probably already correct
```

---

## Step 4 — Create a GitHub Personal Access Token

The Worker needs to read and write `data/watchlist.json` in your repo.

1. Go to: https://github.com/settings/tokens/new
2. Fill in:
   - **Note:** `market-alerts-bot`
   - **Expiration:** 1 year (or "No expiration")
   - **Scopes:** tick only **`repo`** (the top-level checkbox)
3. Click **Generate token**
4. Copy the token — you won't see it again

---

## Step 5 — Deploy the Worker

From the `worker/` directory in your project:

```bash
cd /path/to/market-alerts/worker
wrangler deploy
```

You should see output like:
```
Deployed market-alerts-bot to https://market-alerts-bot.YOUR-SUBDOMAIN.workers.dev
```

Copy that URL — you'll need it in Step 7.

---

## Step 6 — Set the Secrets

Run each command below. Wrangler will prompt you to paste the value.

```bash
wrangler secret put TELEGRAM_BOT_TOKEN
```
Paste your Telegram bot token (from @BotFather), press Enter.

```bash
wrangler secret put TELEGRAM_CHAT_ID
```
Paste your Telegram chat ID (the number, e.g. `123456789`), press Enter.

```bash
wrangler secret put GITHUB_TOKEN
```
Paste the GitHub token you created in Step 4, press Enter.

---

## Step 7 — Register the Webhook with Telegram

Replace `<BOT_TOKEN>` and `<WORKER_URL>` with your actual values, then open
this URL in your browser (or run it with curl):

```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WORKER_URL>
```

Example:
```
https://api.telegram.org/bot123456:ABC-DEF/setWebhook?url=https://market-alerts-bot.myname.workers.dev
```

You should see:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

## Step 8 — Test It

Send `/help` to your Telegram bot. You should get a response within 2 seconds.

Try:
- `/list` — see your current watchlist
- `/add TCS` — add TCS
- `/add Infosys` — add by company name
- `/remove TCS` — remove TCS
- `/status` — see bot status

---

## Troubleshooting

**Worker not responding:**
- Check the webhook is set: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Check Worker logs: `wrangler tail` (shows live logs)

**"Error reading watchlist":**
- Your GitHub token may be wrong or expired
- Check GITHUB_OWNER and GITHUB_REPO in wrangler.toml match your actual repo

**Ticker not found:**
- The Worker checks Yahoo Finance to validate tickers
- Try the exact NSE ticker (e.g. `BAJAJ-AUTO`, not `BAJAJ AUTO`)
- Run `/add Bajaj Auto` to search by name

---

## Updating the Worker

After any code change to `worker/index.js`, just run:

```bash
wrangler deploy
```

---

## Removing the Webhook (to go back to polling)

```
https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook
```

After this, the GitHub Actions command-polling cron will handle commands again
(with up to 15-minute delay).
