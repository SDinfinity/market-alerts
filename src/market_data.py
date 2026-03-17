# This file fetches live stock prices and index levels from Yahoo Finance.
# We use two methods:
# 1. The yfinance library (fast, convenient)
# 2. Direct Yahoo Finance API calls (fallback if yfinance fails)
# NSE stocks need ".NS" added to the ticker (e.g., "INFY" → "INFY.NS").
# If a stock fails to fetch, we skip it and log a warning instead of crashing.

import time
import requests
import yfinance as yf
from dataclasses import dataclass
from typing import Optional
from config import NSE_SUFFIX, DEFAULT_INDICES, INDEX_DISPLAY_NAMES, logger

# Small delay between each stock fetch to avoid Yahoo Finance rate-limiting
FETCH_DELAY_SECONDS = 0.5

# Yahoo Finance chart API — this works reliably without rate-limit issues
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"

# Headers that mimic a real browser request — needed to avoid Yahoo blocking us
YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com",
}


@dataclass
class StockQuote:
    """
    Holds the price data for a single stock or index at a point in time.
    All price fields are in Indian Rupees (₹).
    """
    ticker: str          # The raw ticker symbol (e.g., "INFY" or "^NSEI")
    display_name: str    # Human-readable name (e.g., "INFY" or "NIFTY 50")
    current_price: float # The most recent trading price
    prev_close: float    # Yesterday's closing price
    change: float        # Absolute change: current - prev_close
    change_pct: float    # Percentage change from prev_close
    is_index: bool = False  # True if this is an index like Nifty, not a stock


def fetch_via_yahoo_api(yf_ticker: str) -> Optional[tuple[float, float]]:
    """
    Fetches current price and previous close directly from the Yahoo Finance
    chart API using a plain HTTP request. This is more reliable than the
    yfinance library when there are rate-limit or session issues.
    Returns (current_price, prev_close) or None if the fetch fails.
    """
    try:
        url = YAHOO_CHART_URL.format(symbol=yf_ticker)
        response = requests.get(url, headers=YAHOO_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(
                f"Yahoo Finance API returned HTTP {response.status_code} for {yf_ticker}"
            )
            return None

        data = response.json()
        result = data.get("chart", {}).get("result", [])

        if not result:
            logger.warning(f"No data in Yahoo Finance API response for {yf_ticker}")
            return None

        meta = result[0].get("meta", {})

        # Try regularMarketPrice first (most recent price), fall back to previousClose
        current_price = (
            meta.get("regularMarketPrice")
            or meta.get("chartPreviousClose")
        )
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

        if current_price is None or prev_close is None:
            logger.warning(f"Missing price fields in Yahoo API response for {yf_ticker}")
            return None

        return float(current_price), float(prev_close)

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning(f"Yahoo API direct fetch failed for {yf_ticker}: {e}")
        return None


def fetch_via_yfinance(yf_ticker: str) -> Optional[tuple[float, float]]:
    """
    Fetches price using the yfinance library.
    Returns (current_price, prev_close) or None if the fetch fails.
    This is tried first; if it fails, we fall back to fetch_via_yahoo_api.
    """
    try:
        stock = yf.Ticker(yf_ticker)
        info = stock.fast_info

        current_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        if current_price is not None and prev_close is not None:
            return float(current_price), float(prev_close)

        # fast_info didn't work — try history as last resort within yfinance
        hist = stock.history(period="2d", raise_errors=False)
        if hist is not None and not hist.empty and len(hist) >= 2:
            return float(hist["Close"].iloc[-1]), float(hist["Close"].iloc[-2])

        return None

    except Exception as e:
        logger.debug(f"yfinance fetch failed for {yf_ticker}: {e}")
        return None


def fetch_quote(ticker: str, is_index: bool = False) -> Optional[StockQuote]:
    """
    Fetches the current price and change for a single stock or index.
    For NSE stocks, adds ".NS" suffix automatically.
    Returns None if the fetch fails (so the caller can skip this stock).

    Tries yfinance first, then falls back to direct Yahoo Finance API.
    Example: fetch_quote("INFY") fetches INFY.NS from Yahoo Finance.
    """
    # Indices like ^NSEI don't need a suffix — they're already Yahoo Finance format
    yf_ticker = ticker if is_index else f"{ticker}{NSE_SUFFIX}"

    # Try yfinance first (usually faster)
    prices = fetch_via_yfinance(yf_ticker)

    # Fall back to direct API if yfinance failed
    if prices is None:
        logger.debug(f"yfinance failed for {yf_ticker}, trying direct API...")
        prices = fetch_via_yahoo_api(yf_ticker)

    if prices is None:
        logger.error(f"All fetch methods failed for {yf_ticker}")
        return None

    current_price, prev_close = prices
    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0
    display_name = INDEX_DISPLAY_NAMES.get(ticker, ticker)

    logger.info(
        f"Fetched {display_name}: ₹{current_price:,.2f} "
        f"({'+' if change >= 0 else ''}{change_pct:.2f}%)"
    )

    return StockQuote(
        ticker=ticker,
        display_name=display_name,
        current_price=current_price,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        is_index=is_index,
    )


def fetch_all_quotes(watchlist: list[str]) -> tuple[list[StockQuote], list[str]]:
    """
    Fetches price data for all indices and all stocks in your watchlist.
    Returns two things:
    1. A list of StockQuote objects for everything that succeeded
    2. A list of tickers that failed to fetch (so we can warn about them)

    The indices (Nifty 50, Bank Nifty, etc.) always come first in the results.
    """
    successful_quotes: list[StockQuote] = []
    failed_tickers: list[str] = []

    # First, fetch the default indices (Nifty 50, Bank Nifty, etc.)
    logger.info("Fetching index data...")
    for index_ticker in DEFAULT_INDICES:
        quote = fetch_quote(index_ticker, is_index=True)
        if quote:
            successful_quotes.append(quote)
        else:
            failed_tickers.append(index_ticker)
        time.sleep(FETCH_DELAY_SECONDS)

    # Then fetch each stock in the watchlist
    if watchlist:
        logger.info(f"Fetching {len(watchlist)} stocks from watchlist...")
        for ticker in watchlist:
            quote = fetch_quote(ticker, is_index=False)
            if quote:
                successful_quotes.append(quote)
            else:
                failed_tickers.append(ticker)
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
    quote = fetch_quote(ticker, is_index=False)
    if quote and quote.current_price > 0:
        return True, quote.current_price
    return False, None
