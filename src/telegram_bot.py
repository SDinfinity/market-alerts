# This file handles all Telegram communication:
# 1. Sending alert messages to your chat
# 2. Listening for commands like /add, /remove, /list, /status, /help
#
# The bot uses long-polling to check for new commands.
# In GitHub Actions, command handling runs once per scheduled job
# (not continuously). For real-time command response, you'd need a server —
# but this "poll on each run" approach works fine for a scheduled bot.

import time
import requests
from typing import Optional
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_RETRY_COUNT,
    TELEGRAM_RETRY_DELAY_SECONDS,
    logger,
)
from watchlist import (
    load_watchlist,
    add_stock,
    remove_stock,
    fuzzy_search_ticker,
)
from market_data import validate_ticker

# Base URL for all Telegram Bot API calls
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, chat_id: Optional[str] = None) -> bool:
    """
    Sends a Telegram message to your chat.
    Uses HTML parse mode so formatting tags like <b> and <pre> work.
    Retries up to 3 times if the send fails (network issues, etc.).
    Returns True if the message was sent successfully.
    """
    target_chat = chat_id or TELEGRAM_CHAT_ID

    if not TELEGRAM_BOT_TOKEN or not target_chat:
        logger.error(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set — "
            "check your GitHub Secrets or .env file"
        )
        return False

    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, TELEGRAM_RETRY_COUNT + 1):
        try:
            response = requests.post(
                f"{TELEGRAM_API_BASE}/sendMessage",
                json=payload,
                timeout=30,
            )
            data = response.json()

            if data.get("ok"):
                logger.info(f"Telegram message sent successfully (attempt {attempt})")
                return True
            else:
                error_desc = data.get("description", "Unknown error")
                logger.warning(
                    f"Telegram API error on attempt {attempt}: {error_desc}"
                )

        except requests.RequestException as e:
            logger.warning(f"Network error sending Telegram message (attempt {attempt}): {e}")

        if attempt < TELEGRAM_RETRY_COUNT:
            logger.info(f"Retrying in {TELEGRAM_RETRY_DELAY_SECONDS} seconds...")
            time.sleep(TELEGRAM_RETRY_DELAY_SECONDS)

    logger.error("All Telegram send attempts failed")
    return False


def get_updates(offset: Optional[int] = None) -> list[dict]:
    """
    Fetches new messages/commands sent to the bot since the last check.
    The offset parameter tells Telegram which messages we've already processed.
    Returns a list of update objects from the Telegram API.
    """
    params = {"timeout": 1, "limit": 100}
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(
            f"{TELEGRAM_API_BASE}/getUpdates",
            params=params,
            timeout=15,
        )
        data = response.json()
        if data.get("ok"):
            return data.get("result", [])
        else:
            logger.warning(f"getUpdates error: {data.get('description')}")
            return []
    except requests.RequestException as e:
        logger.warning(f"Failed to get Telegram updates: {e}")
        return []


def handle_command(text: str, chat_id: str) -> None:
    """
    Parses a command message (like "/add INFY") and performs the right action.
    Supported commands:
    - /add <name or ticker>   — search for and add a stock
    - /remove <ticker>        — remove a stock from the watchlist
    - /list                   — show current watchlist
    - /status                 — show bot status and next alert time
    - /help                   — show available commands
    """
    text = text.strip()
    parts = text.split(maxsplit=1)
    command = parts[0].lower().split("@")[0]  # Handle "/add@BotName" format
    args = parts[1].strip() if len(parts) > 1 else ""

    logger.info(f"Handling command: {command} with args: '{args}'")

    if command == "/add":
        _handle_add(args, chat_id)
    elif command == "/remove":
        _handle_remove(args, chat_id)
    elif command == "/list":
        _handle_list(chat_id)
    elif command == "/status":
        _handle_status(chat_id)
    elif command == "/help" or command == "/start":
        _handle_help(chat_id)
    else:
        send_message(
            f"Unknown command: <code>{command}</code>\n"
            "Type /help to see available commands.",
            chat_id,
        )


def _handle_add(query: str, chat_id: str) -> None:
    """
    Handles the /add command. Searches for the stock by name or ticker,
    validates it exists on NSE, then adds it to the watchlist.
    If multiple matches are found, shows the top 5 and asks the user to be specific.
    """
    if not query:
        send_message(
            "Please provide a stock name or ticker.\n"
            "Example: <code>/add Infosys</code> or <code>/add INFY</code>",
            chat_id,
        )
        return

    # Try exact ticker match first (user typed "INFY" directly)
    query_upper = query.upper().strip()
    is_valid, price = validate_ticker(query_upper)

    if is_valid:
        # Direct ticker match — add it straight away
        success, message = add_stock(query_upper)
        send_message(f"{'✅' if success else '⚠️'} {message}", chat_id)
        return

    # Ticker not valid directly — try fuzzy search by company name
    matches = fuzzy_search_ticker(query, top_n=5)

    if not matches:
        send_message(
            f"❌ Could not find any NSE stock matching <b>{query}</b>.\n\n"
            "Try using the exact NSE ticker symbol (e.g., INFY, HDFCBANK, TCS).\n"
            "You can find NSE tickers at <a href='https://www.nseindia.com'>nseindia.com</a>",
            chat_id,
        )
        return

    if len(matches) == 1 or matches[0][2] >= 90:
        # High confidence single match — add it automatically
        best_ticker, best_name, score = matches[0]
        is_valid, price = validate_ticker(best_ticker)
        if is_valid:
            success, message = add_stock(best_ticker)
            send_message(
                f"{'✅' if success else '⚠️'} Found <b>{best_name}</b> → "
                f"<code>{best_ticker}</code> (₹{price:,.2f})\n{message}",
                chat_id,
            )
        else:
            send_message(
                f"⚠️ Found ticker <code>{best_ticker}</code> in our list "
                f"but couldn't verify it on NSE right now. "
                f"Try <code>/add {best_ticker}</code> directly later.",
                chat_id,
            )
        return

    # Multiple possible matches — show them and ask user to pick
    lines = [f"🔍 Found multiple matches for <b>{query}</b>. Did you mean:\n"]
    for ticker, name, score in matches:
        lines.append(f"• <code>/add {ticker}</code> — {name}")
    lines.append("\nType the exact command to add the stock you want.")
    send_message("\n".join(lines), chat_id)


def _handle_remove(ticker: str, chat_id: str) -> None:
    """
    Handles the /remove command. Removes a stock ticker from the watchlist.
    The user must provide the exact ticker symbol (e.g., /remove INFY).
    """
    if not ticker:
        send_message(
            "Please provide the ticker to remove.\n"
            "Example: <code>/remove INFY</code>\n\n"
            "Use <code>/list</code> to see your current watchlist.",
            chat_id,
        )
        return

    success, message = remove_stock(ticker.upper().strip())
    send_message(f"{'✅' if success else '⚠️'} {message}", chat_id)


def _handle_list(chat_id: str) -> None:
    """
    Handles the /list command. Shows all stocks currently in the watchlist.
    """
    watchlist = load_watchlist()

    if not watchlist:
        send_message(
            "📋 Your watchlist is empty.\n\n"
            "Add stocks with: <code>/add Infosys</code> or <code>/add INFY</code>",
            chat_id,
        )
        return

    lines = [f"📋 <b>Your Watchlist ({len(watchlist)} stocks):</b>\n"]
    for i, ticker in enumerate(watchlist, 1):
        lines.append(f"{i}. <code>{ticker}</code>")
    lines.append(f"\nRemove with: <code>/remove TICKER</code>")
    send_message("\n".join(lines), chat_id)


def _handle_status(chat_id: str) -> None:
    """
    Handles the /status command. Shows bot health info:
    current time, trading day status, watchlist count, next alert time.
    """
    from datetime import datetime
    from config import IST, OPENING_ALERT_TIME, CLOSING_ALERT_TIME
    from scheduler import is_trading_day

    now = datetime.now(tz=IST)
    watchlist = load_watchlist()
    trading_today = is_trading_day()

    next_alert = "N/A (not a trading day today)"
    if trading_today:
        if now.time() < OPENING_ALERT_TIME:
            next_alert = f"Opening alert at {OPENING_ALERT_TIME.strftime('%I:%M %p')} IST"
        elif now.time() < CLOSING_ALERT_TIME:
            next_alert = f"Closing alert at {CLOSING_ALERT_TIME.strftime('%I:%M %p')} IST"
        else:
            next_alert = "All alerts done for today"

    status_text = (
        f"<b>🤖 Market Alerts Bot — Status</b>\n\n"
        f"🕐 Current time: {now.strftime('%I:%M %p IST, %d %b %Y')}\n"
        f"📅 Trading day: {'Yes ✅' if trading_today else 'No ❌'}\n"
        f"📋 Watchlist: {len(watchlist)} stocks\n"
        f"⏭ Next alert: {next_alert}"
    )
    send_message(status_text, chat_id)


def _handle_help(chat_id: str) -> None:
    """
    Handles the /help and /start commands. Shows all available commands.
    """
    help_text = (
        "<b>🤖 Market Alerts Bot — Commands</b>\n\n"
        "<code>/add &lt;name or ticker&gt;</code>\n"
        "Add a stock to your watchlist\n"
        "<i>e.g. /add Infosys or /add INFY</i>\n\n"
        "<code>/remove &lt;ticker&gt;</code>\n"
        "Remove a stock from your watchlist\n"
        "<i>e.g. /remove INFY</i>\n\n"
        "<code>/list</code>\n"
        "Show all stocks in your watchlist\n\n"
        "<code>/status</code>\n"
        "Show bot status and next alert time\n\n"
        "<code>/help</code>\n"
        "Show this help message\n\n"
        "<b>Alerts are sent automatically:</b>\n"
        "• 🌅 9:00 AM IST — Opening alert\n"
        "• 🔔 3:45 PM IST — Closing alert\n"
        "• Only on NSE trading days (Mon-Fri, no holidays)"
    )
    send_message(help_text, chat_id)


def process_pending_commands() -> int:
    """
    Checks for any commands sent to the bot since the last run and handles them.
    This is called once per GitHub Actions job run.
    Returns the number of commands processed.

    We use a simple approach: fetch all unread updates, process each one,
    then acknowledge them so they don't repeat next time.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No Telegram token — skipping command processing")
        return 0

    updates = get_updates()
    if not updates:
        logger.info("No pending Telegram commands")
        return 0

    count = 0
    last_update_id = None

    for update in updates:
        last_update_id = update.get("update_id")
        message = update.get("message") or update.get("edited_message")

        if not message:
            continue

        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))

        # Only process messages from your own chat (security check)
        if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
            logger.warning(f"Ignoring message from unknown chat_id: {chat_id}")
            continue

        if text.startswith("/"):
            handle_command(text, chat_id)
            count += 1

    # Acknowledge all processed updates so Telegram doesn't resend them
    if last_update_id is not None:
        get_updates(offset=last_update_id + 1)
        logger.info(f"Processed {count} command(s), acknowledged up to update {last_update_id}")

    return count
