# This file holds all configuration settings for the market alerts bot.
# It reads secrets (like Telegram tokens) from environment variables,
# which are set in GitHub Secrets for production and in a .env file locally.

import os
import logging
from datetime import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load .env file if it exists (only used during local development on your Mac)
# In GitHub Actions, environment variables are set directly as secrets
load_dotenv()

# Indian Standard Time timezone — all times in this bot use IST
IST = ZoneInfo("Asia/Kolkata")

# --- Telegram Secrets ---
# These come from your GitHub Secrets (or .env file locally)
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Market Timing ---
# NSE opens at 9:15 AM IST and closes at 3:30 PM IST
MARKET_OPEN_TIME: time = time(9, 15)
MARKET_CLOSE_TIME: time = time(15, 30)

# How many minutes before open/after close we send the alert
# e.g. opening alert at 9:00 AM, closing alert at 3:45 PM
OPENING_ALERT_TIME: time = time(9, 0)
CLOSING_ALERT_TIME: time = time(15, 45)

# --- NSE Indices to always include in every alert ---
# These are shown at the top of every message regardless of your watchlist
DEFAULT_INDICES: list[str] = [
    "^NSEI",    # Nifty 50
    "^NSEBANK", # Bank Nifty
    "^CNXIT",   # Nifty IT
]

# Human-readable names for the indices above
INDEX_DISPLAY_NAMES: dict[str, str] = {
    "^NSEI":    "NIFTY 50",
    "^NSEBANK": "BANK NIFTY",
    "^CNXIT":   "NIFTY IT",
}

# --- Retry Settings for Telegram ---
# If sending a Telegram message fails, we retry this many times
TELEGRAM_RETRY_COUNT: int = 3
TELEGRAM_RETRY_DELAY_SECONDS: int = 10

# --- Data File ---
# Where the watchlist is stored (relative to the project root)
# In GitHub Actions, this file is part of the repo and committed back
WATCHLIST_FILE: str = "data/watchlist.json"

# --- yfinance suffix for NSE stocks ---
# NSE-listed stocks on Yahoo Finance need ".NS" appended (e.g., "INFY.NS")
NSE_SUFFIX: str = ".NS"

# --- Logging format ---
# All log lines include IST timestamp so you can read GitHub Actions logs easily
LOG_FORMAT: str = "[%(asctime)s IST] %(levelname)s: %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """
    Sets up the logger for the entire application.
    All log messages will print to the console with IST timestamps,
    which is what GitHub Actions captures and shows in the logs tab.
    """
    # Convert log times to IST by using a custom formatter
    class ISTFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            import datetime
            # Convert the log record's UTC timestamp to IST
            dt = datetime.datetime.fromtimestamp(record.created, tz=IST)
            if datefmt:
                return dt.strftime(datefmt)
            return dt.strftime(LOG_DATE_FORMAT)

    logger = logging.getLogger("market_alerts")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = ISTFormatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Create a single shared logger instance used across all modules
logger = setup_logging()
