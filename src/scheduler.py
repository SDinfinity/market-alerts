# This file handles market hours and trading day logic.
# It tells the bot whether today is a trading day and which alert to send.
# NSE holidays are fetched from the NSE website; if that fails, we
# fall back to simple weekday checking (Mon-Fri).

import requests
from datetime import date, datetime
from typing import Optional
from config import IST, OPENING_ALERT_TIME, CLOSING_ALERT_TIME, logger


# Known NSE market holidays for the current year (2026)
# These are the official NSE holidays. We keep a local copy as a fallback
# in case the NSE website is unavailable.
# Source: NSE India equity market holiday list
HARDCODED_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 2, 19),  # Chhatrapati Shivaji Maharaj Jayanti
    date(2026, 3, 20),  # Holi
    date(2026, 4, 2),   # Ram Navami (Good Friday falls on 3rd)
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti / Mahavir Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 6, 8),   # Bakri Id
    date(2026, 8, 15),  # Independence Day
    date(2026, 8, 27),  # Ganesh Chaturthi
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    date(2026, 10, 20), # Diwali Laxmi Pujan (tentative)
    date(2026, 10, 21), # Diwali Balipratipada (tentative)
    date(2026, 11, 4),  # Guru Nanak Jayanti (tentative)
    date(2026, 12, 25), # Christmas
}

# Known NSE market holidays for 2025 (useful if run retroactively)
HARDCODED_HOLIDAYS_2025: set[date] = {
    date(2025, 1, 26),  # Republic Day
    date(2025, 3, 14),  # Holi
    date(2025, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Maharashtra Day
    date(2025, 8, 15),  # Independence Day
    date(2025, 8, 27),  # Ganesh Chaturthi
    date(2025, 10, 2),  # Gandhi Jayanti
    date(2025, 10, 20), # Diwali Laxmi Pujan
    date(2025, 10, 21), # Diwali Balipratipada
    date(2025, 11, 5),  # Prakash Gurpurab
    date(2025, 12, 25), # Christmas
}

ALL_HARDCODED_HOLIDAYS = HARDCODED_HOLIDAYS_2025 | HARDCODED_HOLIDAYS_2026


def get_nse_holidays_from_web() -> Optional[set[date]]:
    """
    Tries to fetch the official NSE holiday list from the NSE website API.
    Returns a set of holiday dates if successful, or None if the fetch fails.
    This is best-effort — if it fails, we use the hardcoded list above.
    """
    try:
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/",
        }
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.warning(f"NSE holiday API returned status {response.status_code}")
            return None

        data = response.json()
        # NSE API returns dates in "DD-Mon-YYYY" format like "26-Jan-2026"
        holidays = set()
        for category in data.values():
            if isinstance(category, list):
                for entry in category:
                    date_str = entry.get("tradingDate", "")
                    try:
                        holidays.add(datetime.strptime(date_str, "%d-%b-%Y").date())
                    except ValueError:
                        pass

        logger.info(f"Fetched {len(holidays)} NSE holidays from web")
        return holidays if holidays else None

    except Exception as e:
        logger.warning(f"NSE holiday fetch failed (will use hardcoded list): {e}")
        return None


def get_holidays() -> set[date]:
    """
    Returns the set of NSE market holidays to use.
    First tries the live NSE website; falls back to the hardcoded list.
    """
    web_holidays = get_nse_holidays_from_web()
    if web_holidays:
        return web_holidays
    logger.info("Using hardcoded holiday list as fallback")
    return ALL_HARDCODED_HOLIDAYS


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """
    Returns True if the given date (or today, if not specified) is a trading day.
    A trading day is: Monday to Friday, AND not an NSE market holiday.
    """
    if check_date is None:
        check_date = datetime.now(tz=IST).date()

    # Saturday = 5, Sunday = 6 in Python's weekday() system
    if check_date.weekday() >= 5:
        logger.info(f"{check_date} is a weekend — not a trading day")
        return False

    holidays = get_holidays()
    if check_date in holidays:
        logger.info(f"{check_date} is an NSE holiday — not a trading day")
        return False

    return True


def get_alert_type() -> Optional[str]:
    """
    Looks at the current IST time and decides which alert to send.
    Returns "opening" if it's time for the morning alert,
    "closing" if it's time for the evening alert,
    or None if we're not in any alert window right now.

    The GitHub Actions workflow is scheduled to run at both alert times,
    so this function just confirms which one we're currently doing.
    """
    now = datetime.now(tz=IST)
    current_time = now.time()

    # Opening window: 8:45 AM – 9:45 AM IST
    # Matches crons "15-59/3 3 * * 1-5" and "0-3 4 * * 1-5"
    from datetime import time as time_
    opening_start = time_(8, 45)
    opening_end   = time_(9, 45)

    # Closing window: 3:15 PM – 4:16 PM IST
    # Matches crons "45-59/3 9 * * 1-5" and "0-45/3 10 * * 1-5"
    closing_start = time_(15, 15)
    closing_end   = time_(16, 16)

    if opening_start <= current_time <= opening_end:
        return "opening"
    elif closing_start <= current_time <= closing_end:
        return "closing"
    else:
        logger.info(f"Current time {current_time} is not in any alert window")
        return None
