# Market Alerts Bot — Complete Setup Guide

This guide walks you through setting up your personal NSE stock alert bot from scratch.
No coding knowledge required — just follow each step carefully.

---

## What You'll End Up With

- A Telegram bot that sends you NSE market alerts automatically
- **9:00 AM IST** — Opening alert with previous close prices
- **3:45 PM IST** — Closing alert with day's final prices
- Alerts include Nifty 50, Bank Nifty, Nifty IT, plus your personal watchlist
- Commands to add/remove stocks: `/add Infosys`, `/remove INFY`, `/list`
- Runs completely free on GitHub — no server needed, no monthly cost

---

## Part 1: Create a GitHub Account and Repository

### Step 1.1 — Create a GitHub Account (skip if you already have one)

1. Open your browser and go to **https://github.com**
2. Click **Sign up** in the top-right corner
3. Enter your email address and click **Continue**
4. Create a password and click **Continue**
5. Choose a username (e.g., `sanyam-alerts`) and click **Continue**
6. Complete the verification puzzle
7. Check your email and click the verification link GitHub sends you
8. You now have a GitHub account ✅

### Step 1.2 — Create a New Repository

1. After logging in, click the **+** button in the top-right corner
2. Select **New repository**
3. Fill in the form:
   - **Repository name**: `market-alerts` (or any name you like)
   - **Description**: `My NSE stock alert bot` (optional)
   - **Visibility**: Select **Private** (keeps your watchlist private)
   - **Initialize this repository**: Check the box ✅ "Add a README file"
4. Click **Create repository**
5. You'll see your new empty repository ✅

---

## Part 2: Upload the Code to GitHub

### Step 2.1 — Install Git on Your Mac (if not already installed)

1. Open **Terminal** on your Mac
   - Press `Command + Space`, type "Terminal", press Enter
2. Type this command and press Enter:
   ```
   git --version
   ```
3. If you see something like `git version 2.x.x` → Git is already installed ✅
4. If you see a prompt to install developer tools → click **Install** and wait

### Step 2.2 — Clone the Repository to Your Mac

1. Go to your GitHub repository page
2. Click the green **Code** button
3. Click **HTTPS** (should already be selected)
4. Click the copy icon next to the URL (it looks like two overlapping squares)
5. Open Terminal on your Mac
6. Navigate to where you want to put the project. For example, to put it on your Desktop:
   ```
   cd ~/Desktop
   ```
7. Type this command (replace `YOUR-URL` with what you copied):
   ```
   git clone YOUR-URL
   ```
   Example: `git clone https://github.com/sanyam-alerts/market-alerts.git`
8. A folder called `market-alerts` will appear on your Desktop ✅

### Step 2.3 — Copy the Bot Files Into the Repository

1. The bot files are in the folder Claude built for you (the `market-alerts` project folder)
2. Copy all the files from there into the `market-alerts` folder you just cloned:
   - The `src/` folder
   - The `data/` folder
   - The `.github/` folder
   - `requirements.txt`
   - `.env.example`
   - `.gitignore`
   - `setup_guide.md`

3. You can do this by opening Finder, navigating to the cloned folder, and dragging files in

### Step 2.4 — Push the Files to GitHub

1. In Terminal, navigate into the project folder:
   ```
   cd ~/Desktop/market-alerts
   ```
2. Tell Git who you are (use your GitHub email):
   ```
   git config user.email "your-email@example.com"
   git config user.name "Your Name"
   ```
3. Stage all the files:
   ```
   git add .
   ```
4. Create a commit:
   ```
   git commit -m "Initial bot setup"
   ```
5. Push to GitHub:
   ```
   git push origin main
   ```
6. GitHub may ask for your username and password — use your GitHub username and a **Personal Access Token** (not your regular password):
   - Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
   - Click **Generate new token (classic)**
   - Give it a name like "market-alerts"
   - Check the **repo** checkbox
   - Click **Generate token**
   - Copy the token and use it as your password in the Terminal prompt
7. Refresh your GitHub repository page — you should see all the files ✅

---

## Part 3: Create Your Telegram Bot

### Step 3.1 — Create a Bot via @BotFather

1. Open Telegram on your phone or desktop
2. In the search bar, type **@BotFather** and tap on it
3. Tap **Start** (or send `/start`)
4. Send the message: `/newbot`
5. BotFather will ask: **"Alright, a new bot. How are we going to call it?"**
   - Send a display name, like: `My Market Alerts`
6. BotFather will ask: **"Good. Now let's choose a username for your bot."**
   - Send a username ending in `bot`, like: `sanyam_market_alerts_bot`
   - If taken, try variations until you find an available one
7. BotFather will send you a message like:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/sanyam_market_alerts_bot.
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
8. **Copy that token** — it's your `TELEGRAM_BOT_TOKEN` ✅

   > ⚠️ Keep this token secret! Anyone with this token can control your bot.

### Step 3.2 — Get Your Telegram Chat ID

1. In Telegram, search for **@userinfobot**
2. Tap **Start** (or send `/start`)
3. The bot will reply with your information, including:
   ```
   Id: 123456789
   ```
4. **Copy that number** — it's your `TELEGRAM_CHAT_ID` ✅

### Step 3.3 — Start a Chat With Your Bot

1. In Telegram, search for your bot's username (e.g., `@sanyam_market_alerts_bot`)
2. Tap **Start**
3. This is important — the bot can only send you messages if you've started a chat with it first

---

## Part 4: Add Secrets to GitHub

GitHub Secrets store your sensitive information (bot token, chat ID) securely.
The bot reads them automatically when it runs on GitHub.

### Step 4.1 — Navigate to Secrets Settings

1. Go to your GitHub repository (e.g., `https://github.com/YOUR-USERNAME/market-alerts`)
2. Click **Settings** (the gear icon in the top tabs)
3. In the left sidebar, click **Secrets and variables**
4. Click **Actions**

### Step 4.2 — Add TELEGRAM_BOT_TOKEN

1. Click the green **New repository secret** button
2. Fill in:
   - **Name**: `TELEGRAM_BOT_TOKEN`
   - **Secret**: Paste the token from @BotFather (e.g., `1234567890:ABCdef...`)
3. Click **Add secret** ✅

### Step 4.3 — Add TELEGRAM_CHAT_ID

1. Click **New repository secret** again
2. Fill in:
   - **Name**: `TELEGRAM_CHAT_ID`
   - **Secret**: Paste your chat ID from @userinfobot (e.g., `123456789`)
3. Click **Add secret** ✅

You should now see two secrets listed under "Repository secrets" ✅

---

## Part 5: Enable GitHub Actions

### Step 5.1 — Enable Actions for Your Repository

1. In your repository, click the **Actions** tab (in the top navigation)
2. If you see a yellow warning saying "Workflows aren't being run on this forked repository" — click **I understand my workflows, go ahead and enable them**
3. If you see your workflow listed → it's already enabled ✅

### Step 5.2 — Allow the Bot to Commit Back to the Repo

The bot needs to save watchlist changes back to GitHub when you use `/add` or `/remove`.

1. Go to **Settings → Actions → General**
2. Scroll down to **Workflow permissions**
3. Select **Read and write permissions**
4. Check **Allow GitHub Actions to create and approve pull requests**
5. Click **Save** ✅

---

## Part 6: Test the Bot

### Step 6.1 — Trigger a Test Run Manually

1. Go to the **Actions** tab in your GitHub repository
2. In the left sidebar, click **Market Alerts**
3. You'll see a message saying "This workflow has a workflow_dispatch event trigger"
4. Click the **Run workflow** dropdown button on the right
5. In the **Run mode** dropdown, select **test**
6. Click **Run workflow** (green button)
7. A new job will appear — click on it to watch it run
8. Wait about 30-60 seconds for it to complete

### Step 6.2 — Verify You Received the Alerts

1. Open Telegram
2. Check your chat with the bot
3. You should have received **two messages** — one opening alert and one closing alert
4. The messages should show Nifty 50, Bank Nifty, Nifty IT prices ✅

If you received the messages → your bot is working! 🎉

---

## Part 7: Using Bot Commands

Once the bot is running, you can send commands to it in Telegram:

### /add — Add a Stock to Your Watchlist

You can add stocks by company name or NSE ticker symbol:

```
/add Infosys
/add INFY
/add HDFC Bank
/add Reliance
/add TCS
```

The bot uses smart search — typing "Infosys" will find the ticker INFY automatically.
If multiple matches are found, it will show you options to pick from.

### /remove — Remove a Stock

```
/remove INFY
/remove TCS
```

You must use the exact ticker symbol (use /list to see your current tickers).

### /list — See Your Watchlist

```
/list
```

Shows all stocks currently in your watchlist.

### /status — Check Bot Health

```
/status
```

Shows current time, whether today is a trading day, and when the next alert is.

### /help — See All Commands

```
/help
```

Shows a summary of all available commands.

> **Note about command timing:** The bot checks for your commands every 15 minutes
> during market hours. So after you send a command, it may take up to 15 minutes
> for the bot to respond. This is normal for a scheduled bot (as opposed to one
> running on a dedicated server).

---

## Part 8: Reading GitHub Actions Logs

If something seems wrong, here's how to see exactly what happened:

1. Go to your GitHub repository → **Actions** tab
2. Click on the most recent workflow run
3. Click on the **run-alerts** job
4. You'll see a list of steps — click any step to expand it
5. Look for lines starting with `[2026-03-17 09:12:34 IST]` — these are the bot's logs
6. Common things to look for:
   - `INFO: Fetched HDFCBANK: ₹1,648.50` — price fetched successfully
   - `ERROR: Failed to fetch SOMESTOCK.NS` — that stock had an issue
   - `INFO: Telegram message sent successfully` — message delivered
   - `ERROR: TELEGRAM_BOT_TOKEN is not set` — secret not configured

### Common Log Messages Explained

| Log Message | What It Means |
|-------------|---------------|
| `Today is not a trading day — no alert will be sent` | Correctly skipped a holiday or weekend |
| `Watchlist is empty — only sending index data` | You haven't added any stocks yet |
| `No pending Telegram commands` | Nobody sent a command since last run |
| `Fetch complete: 3 succeeded, 1 failed` | 1 stock couldn't be fetched (skip, others sent) |
| `All Telegram send attempts failed` | Network/token issue — check your secrets |

---

## Part 9: Common Issues and Fixes

### "I didn't receive any Telegram messages"

1. Make sure you started a chat with your bot (sent `/start` to it)
2. Check GitHub Secrets — are both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set?
3. Run a manual test run with mode = **test** and check the Actions logs
4. In the logs, look for any `ERROR` lines

### "The bot says my ticker is invalid"

- NSE tickers don't always match common abbreviations
- Use the exact NSE ticker from https://www.nseindia.com
- Try the company name instead: `/add Infosys` (the bot will search for you)

### "The bot stopped responding to commands"

- Commands are processed every 15 minutes — just wait
- Check that the scheduled workflows are still enabled in the Actions tab
- Look at recent workflow runs to see if they're failing

### "GitHub Actions workflow is not running automatically"

- GitHub sometimes disables scheduled workflows if the repo has no activity for 60 days
- To fix: go to Actions tab and click "Enable workflow"
- Or: make a small change to a file and push it to restart the schedule

### "I'm getting a 'permission denied' error when pushing code"

- Make sure you're using a Personal Access Token as your password, not your GitHub password
- Create a new token at: GitHub → Settings → Developer settings → Personal access tokens

### "The prices look wrong or delayed"

- Yahoo Finance data can have a 15-20 minute delay for NSE stocks — this is normal
- The closing alert is sent at 3:45 PM IST, 15 minutes after close, to allow prices to settle

---

## Part 10: Updating the Code in the Future

If you want to make changes (new features, bug fixes, etc.):

1. Open Terminal on your Mac
2. Navigate to your project folder:
   ```
   cd ~/Desktop/market-alerts
   ```
3. Pull the latest code (in case GitHub has newer changes):
   ```
   git pull origin main
   ```
4. Ask Claude Code to make your changes (just describe what you want)
5. After Claude makes the changes, push them to GitHub:
   ```
   git add .
   git commit -m "Describe what you changed"
   git push origin main
   ```
6. GitHub Actions will automatically use the new code on the next run

---

## Appendix: NSE Ticker Reference

Here are some commonly used NSE tickers for the `/add` command:

| Company | Ticker |
|---------|--------|
| Reliance Industries | RELIANCE |
| HDFC Bank | HDFCBANK |
| ICICI Bank | ICICIBANK |
| Infosys | INFY |
| TCS | TCS |
| Wipro | WIPRO |
| HCL Technologies | HCLTECH |
| Bajaj Finance | BAJFINANCE |
| Kotak Mahindra Bank | KOTAKBANK |
| Axis Bank | AXISBANK |
| State Bank of India | SBIN |
| Maruti Suzuki | MARUTI |
| Tata Motors | TATAMOTORS |
| Sun Pharma | SUNPHARMA |
| Zomato | ZOMATO |
| IRCTC | IRCTC |
| LTIMindtree | LTIM |
| Tech Mahindra | TECHM |

For the full list of NSE-listed stocks, visit: https://www.nseindia.com/market-data/securities-available-for-trading
