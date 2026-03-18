# This file fetches live stock prices and index levels.
#
# DATA SOURCES (in priority order):
# 1. NSE India allIndices API  — used for all 5 indices (real index values, free, no auth)
#    URL: https://www.nseindia.com/api/allIndices
#    Returns actual index levels (e.g., Nifty 50 at 23,581) in one API call.
#
# 2. Yahoo Finance (yfinance + direct API fallback) — used for:
#    - Individual stocks in the watchlist (always)
#    - Indices if the NSE API is unavailable (partial fallback — only 3 of 5 available)
#
# If a single stock fails, it is skipped and the rest are still sent.
# A 2-second delay between each Yahoo Finance call prevents rate-limiting (HTTP 429).

import time
import requests
import yfinance as yf
from dataclasses import dataclass
from typing import Optional
from config import (
    NSE_SUFFIX,
    INDICES_CONFIG,
    DEFAULT_NSE_INDICES,
    NSE_INDEX_DISPLAY,
    YF_INDEX_DISPLAY,
    logger,
)

# Small delay between each Yahoo Finance call to avoid being rate-limited
FETCH_DELAY_SECONDS = 2.0

# NSE India API — returns all index values in one call, no authentication needed
NSE_ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"

# Yahoo Finance chart API — reliable direct HTTP fallback
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Browser-like headers for both NSE and Yahoo Finance requests
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",   # No brotli — not always available in Actions
    "Referer": "https://www.nseindia.com/",
}

YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://finance.yahoo.com",
}


@dataclass
class StockQuote:
    """
    Holds the price data for a single stock or index at a point in time.
    All price fields are in Indian Rupees (₹).
    """
    ticker: str           # Identifier used internally (NSE symbol or YF ticker)
    display_name: str     # Human-readable label shown in the Telegram message
    current_price: float  # Most recent trading price (or index level)
    prev_close: float     # Yesterday's closing price
    change: float         # Absolute change: current - prev_close
    change_pct: float     # Percentage change from prev_close
    is_index: bool = False  # True for indices (Nifty 50 etc.), False for stocks


# ─────────────────────────────────────────────────
# INDEX FETCHING — NSE API (primary)
# ─────────────────────────────────────────────────

def fetch_indices_from_nse() -> dict[str, StockQuote]:
    """
    Fetches ALL index values from the NSE India allIndices API in a single call.
    Returns a dict mapping NSE index symbol → StockQuote.
    Example key: "NIFTY 50", "NIFTY MIDCAP 150", "NIFTY SMLCAP 250".

    This is the primary and preferred source for index data because:
    - It gives the actual official NSE index values (not ETF prices)
    - One API call returns everything (efficient)
    - Free and publicly accessible
    Returns an empty dict if the API fails, so callers can fall back to yfinance.
    """
    try:
        session = requests.Session()
        response = session.get(NSE_ALL_INDICES_URL, headers=NSE_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(f"NSE allIndices API returned HTTP {response.status_code}")
            return {}

        data = response.json()
        all_indices = data.get("data", [])

        if not all_indices:
            logger.warning("NSE allIndices API returned empty data list")
            return {}

        # Build a lookup: indexSymbol → row  (e.g., "NIFTY 50" → {...})
        nse_lookup = {row["indexSymbol"]: row for row in all_indices}

        results: dict[str, StockQuote] = {}
        for nse_symbol in DEFAULT_NSE_INDICES:
            row = nse_lookup.get(nse_symbol)
            if row is None:
                logger.warning(f"NSE API: '{nse_symbol}' not found in response")
                continue

            current_price = float(row.get("last", 0))
            prev_close = float(row.get("previousClose", 0))

            if current_price == 0:
                logger.warning(f"NSE API: zero price returned for '{nse_symbol}'")
                continue

            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0
            display_name = NSE_INDEX_DISPLAY.get(nse_symbol, nse_symbol)

            logger.info(
                f"NSE: {display_name}: ₹{current_price:,.2f} "
                f"({'+' if change >= 0 else ''}{change_pct:.2f}%)"
            )

            results[nse_symbol] = StockQuote(
                ticker=nse_symbol,
                display_name=display_name,
                current_price=current_price,
                prev_close=prev_close,
                change=change,
                change_pct=change_pct,
                is_index=True,
            )

        logger.info(f"NSE API: fetched {len(results)}/{len(DEFAULT_NSE_INDICES)} indices")
        return results

    except Exception as e:
        logger.warning(f"NSE allIndices API failed (will fall back to yfinance): {e}")
        return {}


# ─────────────────────────────────────────────────
# INDIVIDUAL QUOTE FETCHING — Yahoo Finance (primary for stocks, fallback for indices)
# ─────────────────────────────────────────────────

def fetch_via_yahoo_api(yf_ticker: str) -> Optional[tuple[float, float]]:
    """
    Fetches current price and previous close directly from the Yahoo Finance
    chart API using a plain HTTP GET request.
    Returns (current_price, prev_close) or None if the fetch fails.
    This is more reliable than the yfinance library when there are rate-limit issues.
    """
    try:
        url = YAHOO_CHART_URL.format(symbol=yf_ticker)
        response = requests.get(url, headers=YAHOO_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(f"Yahoo API HTTP {response.status_code} for {yf_ticker}")
            return None

        data = response.json()
        result = data.get("chart", {}).get("result", [])

        if not result:
            logger.warning(f"Yahoo API: no data in response for {yf_ticker}")
            return None

        meta = result[0].get("meta", {})
        current_price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

        if current_price is None or prev_close is None:
            logger.warning(f"Yahoo API: missing price fields for {yf_ticker}")
            return None

        return float(current_price), float(prev_close)

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning(f"Yahoo API direct fetch failed for {yf_ticker}: {e}")
        return None


def fetch_via_yfinance(yf_ticker: str) -> Optional[tuple[float, float]]:
    """
    Fetches price using the yfinance library (tried first before direct API).
    Returns (current_price, prev_close) or None if the fetch fails.
    """
    try:
        stock = yf.Ticker(yf_ticker)
        info = stock.fast_info

        current_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        if current_price is not None and prev_close is not None:
            return float(current_price), float(prev_close)

        return None

    except Exception as e:
        logger.debug(f"yfinance failed for {yf_ticker}: {e}")
        return None


def fetch_stock_quote(ticker: str) -> Optional[StockQuote]:
    """
    Fetches the current price for a single NSE-listed stock (e.g., "INFY").
    Adds ".NS" to the ticker for Yahoo Finance (e.g., "INFY.NS").
    Tries yfinance first, then falls back to the direct Yahoo Finance chart API.
    Returns None if all methods fail (stock is skipped, not a crash).
    """
    yf_ticker = f"{ticker}{NSE_SUFFIX}"

    # Try yfinance first (usually faster when not rate-limited)
    prices = fetch_via_yfinance(yf_ticker)

    # Fall back to direct API call
    if prices is None:
        logger.debug(f"yfinance failed for {yf_ticker}, trying direct API...")
        prices = fetch_via_yahoo_api(yf_ticker)

    if prices is None:
        logger.error(f"All fetch methods failed for {ticker} ({yf_ticker})")
        return None

    current_price, prev_close = prices
    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0

    logger.info(
        f"Fetched {ticker}: ₹{current_price:,.2f} "
        f"({'+' if change >= 0 else ''}{change_pct:.2f}%)"
    )

    return StockQuote(
        ticker=ticker,
        display_name=ticker,
        current_price=current_price,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        is_index=False,
    )


def fetch_index_via_yfinance_fallback(nse_symbol: str) -> Optional[StockQuote]:
    """
    Fallback for a single index when the NSE API is down.
    Uses the yfinance ticker mapped to this NSE index symbol (if one exists).
    Nifty Midcap 150 and Smallcap 250 have no yfinance ticker, so they return None.
    """
    # Find the yfinance ticker for this NSE index symbol
    yf_ticker = None
    for _, nse, yf in INDICES_CONFIG:
        if nse == nse_symbol:
            yf_ticker = yf
            break

    if yf_ticker is None:
        logger.warning(
            f"No yfinance fallback ticker for '{nse_symbol}' — "
            f"this index is NSE API only"
        )
        return None

    prices = fetch_via_yfinance(yf_ticker)
    if prices is None:
        prices = fetch_via_yahoo_api(yf_ticker)
    if prices is None:
        return None

    current_price, prev_close = prices
    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0
    display_name = YF_INDEX_DISPLAY.get(yf_ticker, nse_symbol)

    logger.info(
        f"YF fallback {display_name}: ₹{current_price:,.2f} "
        f"({'+' if change >= 0 else ''}{change_pct:.2f}%)"
    )

    return StockQuote(
        ticker=nse_symbol,
        display_name=display_name,
        current_price=current_price,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        is_index=True,
    )


# ─────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────

def fetch_all_quotes(watchlist: list[str]) -> tuple[list[StockQuote], list[str]]:
    """
    Fetches price data for all 5 indices and all stocks in your watchlist.

    For indices:  NSE allIndices API (one call) → yfinance per-index fallback
    For stocks:   yfinance → direct Yahoo API fallback

    Returns:
    - List of StockQuote objects (indices first, then watchlist stocks)
    - List of tickers that completely failed (for warning in the alert message)
    """
    successful_quotes: list[StockQuote] = []
    failed_tickers: list[str] = []

    # ── Step 1: Fetch all indices from NSE in one shot ──
    logger.info("Fetching indices from NSE India API...")
    nse_results = fetch_indices_from_nse()

    # For each required index, use NSE result or fall back to yfinance
    for _, nse_symbol, _ in INDICES_CONFIG:
        if nse_symbol in nse_results:
            successful_quotes.append(nse_results[nse_symbol])
        else:
            logger.warning(
                f"NSE API missed '{nse_symbol}' — trying yfinance fallback..."
            )
            fallback = fetch_index_via_yfinance_fallback(nse_symbol)
            if fallback:
                successful_quotes.append(fallback)
            else:
                failed_tickers.append(nse_symbol)

    # ── Step 2: Fetch each watchlist stock from Yahoo Finance ──
    if watchlist:
        logger.info(f"Fetching {len(watchlist)} stocks from watchlist...")
        for ticker in watchlist:
            quote = fetch_stock_quote(ticker)
            if quote:
                successful_quotes.append(quote)
            else:
                failed_tickers.append(ticker)
            # 2-second pause to avoid Yahoo Finance rate-limiting (HTTP 429)
            time.sleep(FETCH_DELAY_SECONDS)
    else:
        logger.info("Watchlist is empty — only sending index data")

    logger.info(
        f"Fetch complete: {len(successful_quotes)} succeeded, "
        f"{len(failed_tickers)} failed"
    )
    return successful_quotes, failed_tickers


def validate_ticker(ticker: str) -> tuple[bool, Optional[float]]:
    """
    Checks if a ticker symbol is valid by trying to fetch its current price.
    Returns (True, price) if valid, (False, None) if the ticker doesn't exist.
    Used when someone types /add SOMESTOCK to verify it before saving.
    """
    quote = fetch_stock_quote(ticker)
    if quote and quote.current_price > 0:
        return True, quote.current_price
    return False, None
