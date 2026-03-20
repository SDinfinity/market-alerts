# This is the main entry point for the market alerts bot.
# It is run by GitHub Actions on a schedule, or manually by you for testing.
#
# Usage:
#   python src/main.py              # Normal run (checks time, sends if appropriate)
#   python src/main.py --test       # Test mode: sends both alerts with current data
#   python src/main.py --dry-run    # Dry run: fetches data, prints messages, no Telegram send
#   python src/main.py --opening    # Force send the opening alert right now
#   python src/main.py --closing    # Force send the closing alert right now
#   python src/main.py --commands   # No-op (commands handled by Cloudflare Worker)

import sys
import json
import os
import time
import argparse
from datetime import datetime

from config import IST, OPENING_ALERT_TIME, CLOSING_ALERT_TIME, LAST_ALERT_FILE, logger
from market_data import fetch_all_quotes
from formatter import format_opening_alert, format_closing_alert, format_failure_alert
from telegram_bot import send_message
from scheduler import is_trading_day, get_alert_type
from watchlist import load_watchlist


def load_last_alert() -> dict:
    """Loads the deduplication state from data/last_alert.json."""
    try:
        with open(LAST_ALERT_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_last_alert(data: dict) -> None:
    """Writes the deduplication state to data/last_alert.json."""
    os.makedirs(os.path.dirname(LAST_ALERT_FILE), exist_ok=True)
    with open(LAST_ALERT_FILE, "w") as f:
        json.dump(data, f)


def already_sent_today(alert_type: str) -> bool:
    """Returns True if the given alert type was already sent today (dedup check)."""
    today = datetime.now(tz=IST).strftime("%Y-%m-%d")
    last = load_last_alert()
    return last.get("date") == today and last.get(alert_type, False)


def mark_sent_today(alert_type: str) -> None:
    """Records that the given alert type was sent today."""
    today = datetime.now(tz=IST).strftime("%Y-%m-%d")
    last = load_last_alert()
    if last.get("date") != today:
        last = {"date": today, "opening": False, "closing": False}
    last[alert_type] = True
    save_last_alert(last)


def send_alert(alert_type: str, dry_run: bool = False) -> bool:
    """
    Fetches market data and sends the appropriate alert (opening or closing).
    If dry_run is True, prints the message to console instead of sending to Telegram.
    Returns True if the alert was sent/printed successfully.
    """
    watchlist = load_watchlist()
    logger.info(
        f"Starting {alert_type} alert | "
        f"Watchlist: {len(watchlist)} stocks | "
        f"Dry run: {dry_run}"
    )

    # Fetch all prices (indices + watchlist)
    quotes, failed = fetch_all_quotes(watchlist)

    # If we got zero data, send a failure alert
    if not quotes:
        logger.error("All data fetches failed — sending failure alert")
        failure_msg = format_failure_alert()
        if dry_run:
            print("\n" + "=" * 50)
            print("FAILURE ALERT:")
            print("=" * 50)
            print(failure_msg)
            return True
        return send_message(failure_msg)

    # Format the message based on alert type
    if alert_type == "opening":
        message = format_opening_alert(quotes, failed)
    else:
        message = format_closing_alert(quotes, failed)

    if dry_run:
        print("\n" + "=" * 50)
        print(f"{alert_type.upper()} ALERT MESSAGE:")
        print("=" * 50)
        # Strip HTML tags for console readability
        import re
        clean = re.sub(r"<[^>]+>", "", message)
        print(clean)
        print("=" * 50)
        return True

    success = send_message(message)
    if success:
        logger.info(f"{alert_type.capitalize()} alert sent successfully")
    else:
        logger.error(f"Failed to send {alert_type} alert")
    return success


def sleep_until_opening() -> None:
    """
    Sleeps until exactly 9:17 AM IST before the opening alert is sent.
    If it is already past 9:17 AM, no sleep is needed — send immediately.
    """
    now = datetime.now(tz=IST)
    target = now.replace(
        hour=OPENING_ALERT_TIME.hour,
        minute=OPENING_ALERT_TIME.minute,
        second=0,
        microsecond=0,
    )
    wait_seconds = (target - now).total_seconds()
    if wait_seconds > 0:
        logger.info(
            f"Sleeping {wait_seconds:.0f}s until "
            f"{OPENING_ALERT_TIME.strftime('%I:%M %p')} IST..."
        )
        time.sleep(wait_seconds)
    else:
        logger.info(
            f"Already past {OPENING_ALERT_TIME.strftime('%I:%M %p')} IST "
            f"— sending immediately"
        )


def sleep_until_closing() -> None:
    """
    Sleeps until exactly 4:00 PM IST before the closing alert is sent.
    If it is already past 4:00 PM, no sleep is needed — send immediately.
    """
    now = datetime.now(tz=IST)
    target = now.replace(
        hour=CLOSING_ALERT_TIME.hour,
        minute=CLOSING_ALERT_TIME.minute,
        second=0,
        microsecond=0,
    )
    wait_seconds = (target - now).total_seconds()
    if wait_seconds > 0:
        logger.info(
            f"Sleeping {wait_seconds:.0f}s until "
            f"{CLOSING_ALERT_TIME.strftime('%I:%M %p')} IST..."
        )
        time.sleep(wait_seconds)
    else:
        logger.info(
            f"Already past {CLOSING_ALERT_TIME.strftime('%I:%M %p')} IST "
            f"— sending immediately"
        )


def run_normal() -> None:
    """
    The normal scheduled run. Checks if today is a trading day and
    determines which alert to send based on the current IST time.
    Deduplicates so only one alert per type is sent per day even when
    multiple crons fire in the same window.
    """
    now = datetime.now(tz=IST)
    logger.info(f"Normal run starting at {now.strftime('%Y-%m-%d %H:%M:%S IST')}")

    # Check if today is a trading day
    if not is_trading_day():
        logger.info("Today is not a trading day — no alert will be sent")
        return

    # Determine which alert to send based on current time
    alert_type = get_alert_type()
    if alert_type is None:
        logger.info("Current time doesn't match any alert window — nothing to send")
        return

    # Deduplication: if we already sent this alert today, skip
    if already_sent_today(alert_type):
        logger.info(
            f"{alert_type.capitalize()} alert already sent today — "
            f"skipping duplicate run"
        )
        return

    # Sleep until the exact target time if we're early
    if alert_type == "opening":
        sleep_until_opening()
    elif alert_type == "closing":
        sleep_until_closing()

    success = send_alert(alert_type)
    if success:
        mark_sent_today(alert_type)


def run_test() -> None:
    """
    Test mode: sends both the opening and closing alerts immediately
    with current market data, regardless of time or day.
    Use this to verify the bot is working correctly after setup.
    """
    logger.info("TEST MODE: Sending both opening and closing alerts now")
    print("\n🧪 TEST MODE — Sending both alerts with current data...\n")

    print("Sending OPENING alert...")
    success1 = send_alert("opening")
    print(f"Opening alert: {'✅ Sent' if success1 else '❌ Failed'}")

    print("\nSending CLOSING alert...")
    success2 = send_alert("closing")
    print(f"Closing alert: {'✅ Sent' if success2 else '❌ Failed'}")

    if success1 and success2:
        print("\n✅ Both alerts sent! Check your Telegram.")
    else:
        print("\n⚠️ One or more alerts failed. Check the logs above.")


def run_dry_run() -> None:
    """
    Dry run mode: fetches all data, formats both messages, and prints them
    to the console WITHOUT sending to Telegram. Good for testing formatting.
    """
    logger.info("DRY RUN MODE: Fetching data and printing messages (no Telegram)")
    print("\n🔍 DRY RUN — Fetching data and printing messages (not sending)...\n")

    send_alert("opening", dry_run=True)
    send_alert("closing", dry_run=True)

    print("\n✅ Dry run complete. Messages printed above (not sent to Telegram).")


def run_forced(alert_type: str) -> None:
    """
    Forced alert mode (--opening or --closing). Triggered by Cloudflare Worker crons.
    - Still checks if today is a trading day; skips if not.
    - Still deduplicates; skips if already sent today.
    - Sleeps until the target time if invoked early.
    - Does NOT check the time window (bypasses get_alert_type()).
    """
    now = datetime.now(tz=IST)
    logger.info(
        f"Forced {alert_type} mode starting at "
        f"{now.strftime('%Y-%m-%d %H:%M:%S IST')}"
    )

    if not is_trading_day():
        logger.info("Today is not a trading day — skipping forced alert")
        return

    if already_sent_today(alert_type):
        logger.info(
            f"{alert_type.capitalize()} alert already sent today — "
            f"skipping duplicate"
        )
        return

    if alert_type == "opening":
        sleep_until_opening()
    elif alert_type == "closing":
        sleep_until_closing()

    success = send_alert(alert_type)
    if success:
        mark_sent_today(alert_type)


def main() -> None:
    """
    Parses command-line arguments and runs the appropriate mode.
    """
    parser = argparse.ArgumentParser(
        description="Market Alerts Bot — sends NSE stock price alerts via Telegram"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send both opening and closing alerts immediately (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data and print messages to console without sending to Telegram",
    )
    parser.add_argument(
        "--opening",
        action="store_true",
        help="Force send the opening alert right now",
    )
    parser.add_argument(
        "--closing",
        action="store_true",
        help="Force send the closing alert right now",
    )
    parser.add_argument(
        "--commands",
        action="store_true",
        help="No-op: Telegram commands are now handled by the Cloudflare Worker",
    )

    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.dry_run:
        run_dry_run()
    elif args.opening:
        run_forced("opening")
    elif args.closing:
        run_forced("closing")
    elif args.commands:
        logger.info("--commands is a no-op: Telegram commands are handled by Cloudflare Worker")
    else:
        run_normal()


if __name__ == "__main__":
    main()
