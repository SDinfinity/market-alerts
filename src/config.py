# This file holds all configuration settings for the market alerts bot.
# It reads secrets (like Telegram tokens) from environment variables,
# which are set in GitHub Secrets for production and in a .env file locally.

import os
import logging
from datetime import time
from typing import Optional
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
# Each entry is (display_name, nse_api_symbol, yfinance_ticker_fallback)
#
# nse_api_symbol: exact name as returned by NSE India's allIndices API
#   Source: https://www.nseindia.com/api/allIndices
#   This is the PRIMARY data source — gives real index values, not ETF prices.
#
# yfinance_ticker_fallback: used only if the NSE API is unavailable.
#   Verified working tickers (tested 2026-03-18):
#     ^NSEI    = Nifty 50        (confirmed: ₹23,581)
#     ^NSMIDCP = Nifty Next 50  (Yahoo names it "NIFTY NEXT 50", confirmed: ₹65,021)
#     ^CRSLDX  = Nifty 500      (confirmed: ₹21,669)
#   Nifty Midcap 150 and Smallcap 250 have NO direct Yahoo Finance index tickers,
#   so those two fall back to None (NSE API only).
INDICES_CONFIG: list[tuple[str, str, Optional[str]]] = [
    ("NIFTY 50",      "NIFTY 50",          "^NSEI"),
    ("NIFTY NEXT 50", "NIFTY NEXT 50",     "^NSMIDCP"),
    ("MIDCAP 150",    "NIFTY MIDCAP 150",  None),
    ("SMALLCAP 250",  "NIFTY SMLCAP 250",  None),
    ("NIFTY 500",     "NIFTY 500",         "^CRSLDX"),
]

# Convenience lookups derived from INDICES_CONFIG
# nse_symbol → display_name  (used when parsing NSE API response)
NSE_INDEX_DISPLAY: dict[str, str] = {nse: display for display, nse, _ in INDICES_CONFIG}
# yfinance_ticker → display_name  (used when falling back to yfinance)
YF_INDEX_DISPLAY: dict[str, str] = {
    yf: display for display, _, yf in INDICES_CONFIG if yf is not None
}

# The ordered list of NSE API symbols we want to fetch
DEFAULT_NSE_INDICES: list[str] = [nse for _, nse, _ in INDICES_CONFIG]

# Legacy alias kept so formatter.py and other modules that reference
# INDEX_DISPLAY_NAMES don't break (maps both NSE symbols and YF tickers)
INDEX_DISPLAY_NAMES: dict[str, str] = {**NSE_INDEX_DISPLAY, **YF_INDEX_DISPLAY}

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
