# This is the main entry point for the market alerts bot.
# It is run by GitHub Actions on a schedule, or manually by you for testing.
#
# Usage:
#   python src/main.py              # Normal run (checks time, sends if appropriate)
#   python src/main.py --test       # Test mode: sends both alerts with current data
#   python src/main.py --dry-run    # Dry run: fetches data, prints messages, no Telegram send
#   python src/main.py --opening    # Force send the opening alert right now
#   python src/main.py --closing    # Force send the closing alert right now
#   python src/main.py --commands   # Only process pending Telegram commands

import sys
import argparse
from datetime import datetime

from config import IST, logger
from market_data import fetch_all_quotes
from formatter import format_opening_alert, format_closing_alert, format_failure_alert
from telegram_bot import send_message, process_pending_commands
from scheduler import is_trading_day, get_alert_type
from watchlist import load_watchlist


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


def run_normal() -> None:
    """
    The normal scheduled run. Checks if today is a trading day and
    determines which alert to send based on the current IST time.
    Also processes any pending Telegram commands from users.
    """
    now = datetime.now(tz=IST)
    logger.info(f"Normal run starting at {now.strftime('%Y-%m-%d %H:%M:%S IST')}")

    # First, always check for pending commands (so /add /remove work daily)
    logger.info("Checking for pending Telegram commands...")
    cmd_count = process_pending_commands()
    logger.info(f"Processed {cmd_count} pending command(s)")

    # Check if today is a trading day
    if not is_trading_day():
        logger.info("Today is not a trading day — no alert will be sent")
        return

    # Determine which alert to send based on current time
    alert_type = get_alert_type()
    if alert_type is None:
        logger.info("Current time doesn't match any alert window — nothing to send")
        return

    send_alert(alert_type)


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


def run_commands_only() -> None:
    """
    Command-only mode: only processes pending Telegram commands.
    Useful if you want to handle commands without sending a market alert.
    """
    logger.info("COMMAND MODE: Processing pending Telegram commands only")
    count = process_pending_commands()
    logger.info(f"Done. Processed {count} command(s).")


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
        help="Only process pending Telegram commands, no alerts",
    )

    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.dry_run:
        run_dry_run()
    elif args.opening:
        logger.info("Forced opening alert mode")
        send_alert("opening")
    elif args.closing:
        logger.info("Forced closing alert mode")
        send_alert("closing")
    elif args.commands:
        run_commands_only()
    else:
        run_normal()


if __name__ == "__main__":
    main()
