# This file formats stock and index price data into Telegram messages.
# The entire message is wrapped in <pre> tags so all columns align in monospace.
# No emoji, no rupee symbol, no arrow characters — plain text only.
#
# Opening alert format: stocks sorted by gap% (open vs prev close), indices below
# Closing alert format: stocks sorted by change%, with day range column, indices below

from datetime import datetime
from typing import List
from market_data import StockQuote
from config import IST, DEFAULT_NSE_INDICES, logger

# Set of all NSE index symbols — used to filter them out of "failed" warnings
_INDEX_SYMBOLS = set(DEFAULT_NSE_INDICES)

# ─────────────────────────────────────────────────────────────────
# Number formatting helpers
# ─────────────────────────────────────────────────────────────────

def _fmt_price(value: float) -> str:
    """
    Formats a price or index level with commas and 2 decimal places.
    Examples: 1234.5 → "1,234.50",  23581.15 → "23,581.15"
    """
    return f"{value:,.2f}"


def _fmt_pct(pct: float) -> str:
    """
    Formats a percentage with sign and 1 decimal place.
    Examples: 2.137 → "+2.1%",  -0.3 → "-0.3%",  0.0 → "+0.0%"
    """
    return f"{pct:+.1f}%"


def _fmt_range_val(value: float) -> str:
    """
    Formats a range endpoint (day high or low) with appropriate precision.
    - Values below 100: 1 decimal place (e.g., 84.3)
    - Values 100 and above: rounded to nearest integer (e.g., 1,640)
    - Values 10,000 and above: rounded to nearest 10 (e.g., 23,380)
    """
    if value < 100:
        return f"{value:,.1f}"
    elif value < 10000:
        return f"{int(round(value)):,}"
    else:
        # Round to nearest 10 for large index values
        return f"{int(round(value / 10) * 10):,}"


def _fmt_range(low: float, high: float) -> str:
    """
    Formats the day's trading range as "low – high".
    Returns empty string if either value is zero (data not available).
    Examples: "1,640 – 1,658",  "238.9 – 246.1",  "23,380 – 23,470"
    """
    if low == 0 or high == 0:
        return ""
    return f"{_fmt_range_val(low)} \u2013 {_fmt_range_val(high)}"


# ─────────────────────────────────────────────────────────────────
# Opening alert
# ─────────────────────────────────────────────────────────────────

def format_opening_alert(quotes: List[StockQuote], failed_tickers: list) -> str:
    """
    Formats the morning opening alert message.
    Stocks are sorted by gap% (open price vs prev close) from highest to lowest.
    Indices are shown below in fixed order (Nifty 50 first, Nifty 500 last).

    Sent around 9:30 AM IST — 15 minutes after market opens, so opening prices
    are available. If open_price is zero for a stock, falls back to prev_close.

    The entire message is wrapped in <pre> tags for monospace alignment.
    """
    now = datetime.now(tz=IST)
    # "Wednesday, 18 Mar 2026"
    date_str = now.strftime("%A, %d %b %Y")

    indices = [q for q in quotes if q.is_index]
    stocks = [q for q in quotes if not q.is_index]

    # Sort stocks by gap% descending (best gap at top)
    # Fall back to change_pct if open_price is not available
    stocks_sorted = sorted(
        stocks,
        key=lambda q: q.gap_pct if q.open_price > 0 else q.change_pct,
        reverse=True,
    )

    # Column widths for the stocks section
    # Name: left-aligned to 14 chars (BHARTIARTL = 10, plus buffer)
    # Open: right-aligned to 10 chars (handles "1,648.50" = 8 chars with padding)
    # Gap: right-aligned to 7 chars (handles "+10.5%" = 6 chars)
    NAME_W = 14
    PRICE_W = 10
    PCT_W = 7

    # Column widths for the indices section (longer names, larger numbers)
    # Name: left-aligned to 15 chars (NIFTY NEXT 50 = 13)
    # Level: right-aligned to 11 chars (handles "65,021.60" = 9 chars with padding)
    # Pct: right-aligned to 7 chars
    IDX_NAME_W = 15
    IDX_PRICE_W = 11
    IDX_PCT_W = 7

    stock_header = (
        f"{'Ticker':<{NAME_W}}"
        f"{'Open':>{PRICE_W}}"
        f"{'Gap':>{PCT_W + 4}}"
    )
    stock_divider = "\u2501" * (NAME_W + PRICE_W + PCT_W + 4)

    idx_header_line = "Indices"

    lines = ["<pre>"]
    lines.append(f"Market open \u2014 {date_str}")
    lines.append("Opening prices \u00b7 sorted by gap high \u2192 low")
    lines.append("")
    lines.append(stock_header)
    lines.append(stock_divider)

    for q in stocks_sorted:
        # Use opening price if available, otherwise prev_close
        display_price = q.open_price if q.open_price > 0 else q.prev_close
        gap = q.gap_pct if q.open_price > 0 else q.change_pct
        lines.append(
            f"{q.display_name:<{NAME_W}}"
            f"{_fmt_price(display_price):>{PRICE_W}}"
            f"    "
            f"{_fmt_pct(gap):>{PCT_W}}"
        )

    # Indices section (no gap column — just level and % change from prev close)
    if indices:
        lines.append("")
        lines.append(idx_header_line)
        for q in indices:
            lines.append(
                f"{q.display_name:<{IDX_NAME_W}}"
                f"{_fmt_price(q.current_price):>{IDX_PRICE_W}}"
                f"   "
                f"{_fmt_pct(q.change_pct):>{IDX_PCT_W}}"
            )

    lines.append("")
    lines.append("Open = 9:15 opening price \u00b7 Gap = open vs prev close")

    # Only warn about failed STOCKS — index failures are expected when NSE API is down
    stock_failed = [t for t in failed_tickers if t not in _INDEX_SYMBOLS]
    if stock_failed:
        lines.append(f"Could not fetch: {', '.join(stock_failed)}")

    lines.append("</pre>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Closing alert
# ─────────────────────────────────────────────────────────────────

def format_closing_alert(quotes: List[StockQuote], failed_tickers: list) -> str:
    """
    Formats the evening closing alert message.
    Stocks are sorted by change% (best performers at top).
    Each row shows close price, % change, and the day's trading range.
    Indices are shown below in fixed order with their range.

    Sent around 3:45 PM IST — 15 minutes after market closes.

    The entire message is wrapped in <pre> tags for monospace alignment.
    """
    now = datetime.now(tz=IST)
    date_str = now.strftime("%A, %d %b %Y")

    indices = [q for q in quotes if q.is_index]
    stocks = [q for q in quotes if not q.is_index]

    # Sort stocks by change% descending (best performers at top)
    stocks_sorted = sorted(stocks, key=lambda q: q.change_pct, reverse=True)

    # Column widths for stocks section
    NAME_W = 14
    CLOSE_W = 10
    CHG_W = 7

    # Column widths for indices section
    IDX_NAME_W = 15
    IDX_CLOSE_W = 11
    IDX_CHG_W = 7

    stock_header = (
        f"{'Ticker':<{NAME_W}}"
        f"{'Close':>{CLOSE_W}}"
        f"{'Chg':>{CHG_W + 4}}"
        f"   Range"
    )
    stock_divider = "\u2501" * (NAME_W + CLOSE_W + CHG_W + 4 + 3 + 15)

    lines = ["<pre>"]
    lines.append(f"Market close \u2014 {date_str}")
    lines.append("Sorted best \u2192 worst")
    lines.append("")
    lines.append(stock_header)
    lines.append(stock_divider)

    for q in stocks_sorted:
        rng = _fmt_range(q.day_low, q.day_high)
        range_str = f"   {rng}" if rng else ""
        lines.append(
            f"{q.display_name:<{NAME_W}}"
            f"{_fmt_price(q.current_price):>{CLOSE_W}}"
            f"    "
            f"{_fmt_pct(q.change_pct):>{CHG_W}}"
            f"{range_str}"
        )

    # Indices section with range
    if indices:
        lines.append("")
        lines.append("Indices")
        for q in indices:
            rng = _fmt_range(q.day_low, q.day_high)
            range_str = f"   {rng}" if rng else ""
            lines.append(
                f"{q.display_name:<{IDX_NAME_W}}"
                f"{_fmt_price(q.current_price):>{IDX_CLOSE_W}}"
                f"   "
                f"{_fmt_pct(q.change_pct):>{IDX_CHG_W}}"
                f"{range_str}"
            )

    lines.append("")
    lines.append(
        "Chg = vs prev session close \u00b7 Range = day low \u2013 high"
    )

    # Only warn about failed STOCKS — index failures are expected when NSE API is down
    stock_failed = [t for t in failed_tickers if t not in _INDEX_SYMBOLS]
    if stock_failed:
        lines.append(f"Could not fetch: {', '.join(stock_failed)}")

    lines.append("</pre>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Failure alert
# ─────────────────────────────────────────────────────────────────

def format_failure_alert() -> str:
    """
    Sent when ALL data fetches fail — lets you know the bot ran but got no data.
    """
    now = datetime.now(tz=IST)
    return (
        f"<pre>Market alert failed\n\n"
        f"Could not fetch any market data at "
        f"{now.strftime('%I:%M %p IST on %d %b %Y')}.\n\n"
        f"Possible cause: Yahoo Finance or NSE API is temporarily unavailable.\n"
        f"Please check the market manually.</pre>"
    )
