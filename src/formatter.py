# This file formats stock and index data into Telegram messages.
# The entire message is inside <pre> tags for monospace alignment.
# No emoji, no rupee symbol, no arrow characters — plain text only.
#
# Every row is exactly 31 characters wide:
#   Stocks:  name.ljust(15) + price.rjust(8) + "   " + pct.rjust(5)  = 31
#   Indices: name.ljust(15) + price.rjust(9) + "  "  + pct.rjust(5)  = 31
#   Divider: "━" * 31
#
# Name column is 15 so "NIFTY NEXT 50" (13 chars) has 2 spaces before price.

from datetime import datetime
from typing import List
from market_data import StockQuote
from config import IST, DEFAULT_NSE_INDICES, logger

# Column widths — all rows sum to ROW_WIDTH characters
STOCK_NAME_W  = 15   # fits "BHARTIARTL" (10) and "NIFTY NEXT 50" (13) + 2 gap
STOCK_PRICE_W = 8    # "1,797.00" — max 4-digit price with comma and 2 decimals
STOCK_SEP     = "   "
IDX_NAME_W    = 15   # "NIFTY NEXT 50  " — 13 chars + 2 spaces before price
IDX_PRICE_W   = 9    # "65,021.60" — 5-digit index level with comma and 2 decimals
IDX_SEP       = "  "
PCT_W         = 5    # "+0.8%" — sign + up to 2 digits + dot + 1 digit + %
ROW_WIDTH     = STOCK_NAME_W + STOCK_PRICE_W + len(STOCK_SEP) + PCT_W  # = 31

# NSE index symbols — used to exclude them from the "failed stocks" warning
_INDEX_SYMBOLS = set(DEFAULT_NSE_INDICES)


# ─────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────

def _price(value: float) -> str:
    """Formats a price or index level: 1234.5 → '1,234.50'"""
    return f"{value:,.2f}"


def _pct(value: float) -> str:
    """Formats a percentage with sign and 1 decimal: 2.137 → '+2.1%'"""
    return f"{value:+.1f}%"


def _stock_row(name: str, price: float, pct: float) -> str:
    """
    Formats one stock data row. Total width = 31 characters.
    Example: "BHARTIARTL    1,797.00    +0.5%"
    """
    return (
        f"{name:<{STOCK_NAME_W}}"
        f"{_price(price):>{STOCK_PRICE_W}}"
        f"{STOCK_SEP}"
        f"{_pct(pct):>{PCT_W}}"
    )


def _index_row(name: str, price: float, pct: float) -> str:
    """
    Formats one index data row. Total width = 31 characters.
    Example: "NIFTY NEXT 50 65,021.60   +0.9%"
    """
    return (
        f"{name:<{IDX_NAME_W}}"
        f"{_price(price):>{IDX_PRICE_W}}"
        f"{IDX_SEP}"
        f"{_pct(pct):>{PCT_W}}"
    )


# ─────────────────────────────────────────────────────────────
# Opening alert
# ─────────────────────────────────────────────────────────────

def format_opening_alert(quotes: List[StockQuote], failed_tickers: list) -> str:
    """
    Formats the morning opening alert (sent at 9:30 AM IST).
    Stocks are sorted by gap% (open price vs prev close), highest gap first.
    Indices follow in fixed order with their % change from yesterday's close.

    Structure:
      Market open — Wed, 18 Mar 2026
      Sorted by gap high → low

      Ticker            Open      Gap
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      [stocks sorted by gap desc]

      Indices
      [indices in fixed order]

      Open = 9:15 price · Gap = vs prev close
    """
    now = datetime.now(tz=IST)
    date_str = now.strftime("%a, %d %b %Y")  # "Wed, 18 Mar 2026"

    indices = [q for q in quotes if q.is_index]
    stocks  = [q for q in quotes if not q.is_index]

    # Sort stocks by gap% descending (best gap at top).
    # Fall back to change_pct if the market hasn't opened yet (open_price = 0).
    stocks_sorted = sorted(
        stocks,
        key=lambda q: q.gap_pct if q.open_price > 0 else q.change_pct,
        reverse=True,
    )

    header  = (
        f"{'Ticker':<{STOCK_NAME_W}}"
        f"{'Open':>{STOCK_PRICE_W}}"
        f"{STOCK_SEP}"
        f"{'Gap':>{PCT_W}}"
    )
    divider = "\u2501" * ROW_WIDTH  # ━━━━━ (31 wide)

    lines = ["<pre>"]
    lines.append(f"Market open \u2014 {date_str}")
    lines.append("Sorted by gap high \u2192 low")
    lines.append("")
    lines.append(header)
    lines.append(divider)

    for q in stocks_sorted:
        price = q.open_price if q.open_price > 0 else q.prev_close
        gap   = q.gap_pct   if q.open_price > 0 else q.change_pct
        lines.append(_stock_row(q.display_name, price, gap))

    # Blank line before indices, NO blank line between "Indices" label and data
    lines.append("")
    lines.append("Indices")
    for q in indices:
        lines.append(_index_row(q.display_name, q.current_price, q.change_pct))

    lines.append("")
    lines.append("Gap = open vs prev close")

    stock_failed = [t for t in failed_tickers if t not in _INDEX_SYMBOLS]
    if stock_failed:
        lines.append(f"Could not fetch: {', '.join(stock_failed)}")

    lines.append("</pre>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Closing alert
# ─────────────────────────────────────────────────────────────

def format_closing_alert(quotes: List[StockQuote], failed_tickers: list) -> str:
    """
    Formats the evening closing alert (sent at 3:45 PM IST).
    Stocks are sorted by change% (best performers at top).
    Three columns only: Ticker, Close, Chg. No range column.

    Structure:
      Market close — Wed, 18 Mar 2026
      Sorted best → worst

      Ticker            Close      Chg
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      [stocks sorted by change_pct desc]

      Indices
      [indices in fixed order]

      Chg = vs prev close
    """
    now = datetime.now(tz=IST)
    date_str = now.strftime("%a, %d %b %Y")

    indices = [q for q in quotes if q.is_index]
    stocks  = [q for q in quotes if not q.is_index]

    stocks_sorted = sorted(stocks, key=lambda q: q.change_pct, reverse=True)

    header  = (
        f"{'Ticker':<{STOCK_NAME_W}}"
        f"{'Close':>{STOCK_PRICE_W}}"
        f"{STOCK_SEP}"
        f"{'Chg':>{PCT_W}}"
    )
    divider = "\u2501" * ROW_WIDTH

    lines = ["<pre>"]
    lines.append(f"Market close \u2014 {date_str}")
    lines.append("Sorted best \u2192 worst")
    lines.append("")
    lines.append(header)
    lines.append(divider)

    for q in stocks_sorted:
        lines.append(_stock_row(q.display_name, q.current_price, q.change_pct))

    lines.append("")
    lines.append("Indices")
    for q in indices:
        lines.append(_index_row(q.display_name, q.current_price, q.change_pct))

    lines.append("")
    lines.append("Chg = close vs prev close")

    stock_failed = [t for t in failed_tickers if t not in _INDEX_SYMBOLS]
    if stock_failed:
        lines.append(f"Could not fetch: {', '.join(stock_failed)}")

    lines.append("</pre>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Failure alert
# ─────────────────────────────────────────────────────────────

def format_failure_alert() -> str:
    """Sent when ALL data fetches fail — bot ran but couldn't get any data."""
    now = datetime.now(tz=IST)
    return (
        f"<pre>Market alert failed\n\n"
        f"Could not fetch any market data at "
        f"{now.strftime('%I:%M %p IST on %d %b %Y')}.\n\n"
        f"Possible cause: Yahoo Finance or NSE API temporarily unavailable.\n"
        f"Please check the market manually.</pre>"
    )
