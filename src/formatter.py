# This file formats the stock price data into nicely aligned Telegram messages.
# Telegram supports HTML formatting — we use <pre> tags for monospace text
# so the columns line up perfectly on both mobile and desktop.
# All prices are in Indian Rupees (₹) with 2 decimal places.

from datetime import datetime
from market_data import StockQuote
from config import IST, MARKET_OPEN_TIME, MARKET_CLOSE_TIME, logger


def format_change_arrow(change_pct: float) -> str:
    """
    Returns a directional arrow emoji based on whether the stock went up or down.
    Green up arrow for gains, red down arrow for losses, dash for flat.
    """
    if change_pct > 0:
        return "▲"
    elif change_pct < 0:
        return "▼"
    return "─"


def format_price_row(quote: StockQuote, name_width: int = 14) -> str:
    """
    Formats a single stock or index as one row of the price table.
    Columns: Name | Price | Change% | Arrow
    The name_width parameter ensures all names are padded to the same length
    so the price column lines up correctly in monospace.

    Example output: "INFY          1,891.25   +1.23% ▲"
    """
    arrow = format_change_arrow(quote.change_pct)
    sign = "+" if quote.change_pct >= 0 else ""

    # Truncate long names to fit the column width
    name = quote.display_name[:name_width].ljust(name_width)
    price = f"₹{quote.current_price:>10,.2f}"
    change = f"{sign}{quote.change_pct:>6.2f}%"

    return f"{name} {price}  {change} {arrow}"


def format_opening_alert(
    quotes: list[StockQuote],
    failed_tickers: list[str],
) -> str:
    """
    Creates the morning opening alert message.
    Shows the previous day's closing prices and sets context for the trading day.
    This is sent around 9:00 AM IST, before the market opens at 9:15 AM.

    The message uses HTML formatting for Telegram with <pre> for alignment.
    """
    now = datetime.now(tz=IST)
    date_str = now.strftime("%d %b %Y")  # e.g., "17 Mar 2026"
    open_time = MARKET_OPEN_TIME.strftime("%I:%M %p")  # "09:15 AM"

    # Split quotes into indices and watchlist stocks
    indices = [q for q in quotes if q.is_index]
    stocks = [q for q in quotes if not q.is_index]

    # Find the longest name for alignment
    all_names = [q.display_name for q in quotes]
    name_width = max((len(n) for n in all_names), default=10)
    name_width = min(name_width, 16)  # Cap at 16 so it doesn't get too wide

    lines = [
        f"<b>🌅 Market Opening Alert — {date_str}</b>",
        f"Market opens at {open_time} IST",
        "",
        "<pre>",
        "── INDICES ─────────────────────────────",
    ]

    for q in indices:
        lines.append(format_price_row(q, name_width))

    if stocks:
        lines.append("")
        lines.append("── YOUR WATCHLIST ───────────────────────")
        for q in stocks:
            lines.append(format_price_row(q, name_width))

    lines.append("</pre>")

    if failed_tickers:
        clean_failed = [t for t in failed_tickers if not t.startswith("^")]
        if clean_failed:
            lines.append(f"\n⚠️ Could not fetch: {', '.join(clean_failed)}")

    if not stocks:
        lines.append(
            "\n💡 <i>Tip: Use /add TICKER to add stocks to your watchlist</i>"
        )

    return "\n".join(lines)


def format_closing_alert(
    quotes: list[StockQuote],
    failed_tickers: list[str],
) -> str:
    """
    Creates the evening closing alert message.
    Shows the final closing prices for the day with gains/losses.
    This is sent around 3:45 PM IST, after the market closes at 3:30 PM.
    """
    now = datetime.now(tz=IST)
    date_str = now.strftime("%d %b %Y")

    indices = [q for q in quotes if q.is_index]
    stocks = [q for q in quotes if not q.is_index]

    all_names = [q.display_name for q in quotes]
    name_width = max((len(n) for n in all_names), default=10)
    name_width = min(name_width, 16)

    # Compute overall market sentiment from Nifty 50
    nifty = next((q for q in indices if q.ticker == "^NSEI"), None)
    if nifty:
        if nifty.change_pct >= 1.0:
            sentiment = "📈 Strong day for the market!"
        elif nifty.change_pct >= 0:
            sentiment = "📊 Market closed slightly higher."
        elif nifty.change_pct >= -1.0:
            sentiment = "📉 Market closed slightly lower."
        else:
            sentiment = "📉 Rough day for the market."
    else:
        sentiment = "📊 Market has closed."

    lines = [
        f"<b>🔔 Market Closing Alert — {date_str}</b>",
        sentiment,
        "",
        "<pre>",
        "── INDICES ─────────────────────────────",
    ]

    for q in indices:
        lines.append(format_price_row(q, name_width))

    if stocks:
        lines.append("")
        lines.append("── YOUR WATCHLIST ───────────────────────")
        for q in stocks:
            lines.append(format_price_row(q, name_width))

        # Highlight the top gainer and loser in the watchlist
        if len(stocks) >= 2:
            top_gainer = max(stocks, key=lambda q: q.change_pct)
            top_loser = min(stocks, key=lambda q: q.change_pct)
            lines.append("")
            lines.append(
                f"🏆 Best:  {top_gainer.display_name} ({top_gainer.change_pct:+.2f}%)"
            )
            lines.append(
                f"💔 Worst: {top_loser.display_name} ({top_loser.change_pct:+.2f}%)"
            )

    lines.append("</pre>")

    if failed_tickers:
        clean_failed = [t for t in failed_tickers if not t.startswith("^")]
        if clean_failed:
            lines.append(f"\n⚠️ Could not fetch: {', '.join(clean_failed)}")

    if not stocks:
        lines.append(
            "\n💡 <i>Tip: Use /add TICKER to add stocks to your watchlist</i>"
        )

    return "\n".join(lines)


def format_failure_alert() -> str:
    """
    Creates an alert message to send when ALL stock fetches have failed.
    This lets you know the bot is running but can't get data.
    """
    now = datetime.now(tz=IST)
    return (
        f"⚠️ <b>Market Alert — Data Fetch Failed</b>\n\n"
        f"Could not fetch any market data at "
        f"{now.strftime('%I:%M %p IST on %d %b %Y')}.\n\n"
        f"This may be a temporary issue with Yahoo Finance. "
        f"Please check the market manually."
    )
