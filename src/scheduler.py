# This file handles market hours and trading day logic.
# It tells the bot whether today is a trading day and which alert to send.
#
# Holiday source: NSE_HOLIDAYS_2026 in config.py (hardcoded from NSE circular
# NSE/CMTR/71775). The NSE web API is NOT used — it returns clearing/settlement
# holidays (e.g. Gudi Padwa) which are NOT trading holidays.

from datetime import date, datetime
from typing import Optional
from config import (
    IST, OPENING_ALERT_TIME, CLOSING_ALERT_TIME, logger,
    NSE_HOLIDAYS_2026, NSE_SPECIAL_TRADING_DAYS_2026,
)


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """
    Returns True if the given date (or today, if not specified) is a trading day.
    Logic:
      1. Special trading sessions (e.g. Muhurat Trading) → always True
      2. Weekends (Sat/Sun) → False
      3. NSE_HOLIDAYS_2026 → False
      4. Otherwise → True
    """
    if check_date is None:
        check_date = datetime.now(tz=IST).date()

    # Special trading day overrides everything
    if check_date in NSE_SPECIAL_TRADING_DAYS_2026:
        logger.info(f"{check_date} is a special trading session — trading day")
        return True

    # Saturday = 5, Sunday = 6
    if check_date.weekday() >= 5:
        logger.info(f"{check_date} is a weekend — not a trading day")
        return False

    if check_date in NSE_HOLIDAYS_2026:
        logger.info(f"{check_date} is an NSE trading holiday — not a trading day")
        return False

    return True


def get_alert_type() -> Optional[str]:
    """
    Looks at the current IST time and decides which alert to send.
    Returns "opening" if it's time for the morning alert,
    "closing" if it's time for the evening alert,
    or None if we're not in any alert window right now.
    """
    now = datetime.now(tz=IST)
    current_time = now.time()

    from datetime import time as time_

    # Opening window: 8:45 AM – 9:45 AM IST
    opening_start = time_(8, 45)
    opening_end   = time_(9, 45)

    # Closing window: 3:15 PM – 4:16 PM IST
    closing_start = time_(15, 15)
    closing_end   = time_(16, 16)

    if opening_start <= current_time <= opening_end:
        return "opening"
    elif closing_start <= current_time <= closing_end:
        return "closing"
    else:
        logger.info(f"Current time {current_time} is not in any alert window")
        return None
