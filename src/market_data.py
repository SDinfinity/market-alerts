# This file fetches live stock prices and index levels.
#
# DATA SOURCES (in priority order):
#
# For INDICES (Nifty 50, Next 50, Midcap 150, Smallcap 250, Nifty 500):
#   Primary:  NSE India allIndices API — https://www.nseindia.com/api/allIndices
#             Returns official index levels (open, high, low, last, prev_close)
#             in a single API call. No auth needed.
#   Fallback: Yahoo Finance direct API (only works for 3 of 5 indices)
#
# For STOCKS (watchlist):
#   Primary:  NSE India quote-equity API — https://www.nseindia.com/api/quote-equity?symbol=INFY
#             Returns open, high, low, last, prev_close for each stock.
#   Fallback: Yahoo Finance (yfinance library + direct chart API)
#
# A 2-second pause between each stock fetch prevents Yahoo rate-limiting.
# If a single stock fails, it is skipped and the rest are still sent.

import time
import requests
import yfinance as yf
from dataclasses import dataclass, field
from typing import Optional
from config import (
    NSE_SUFFIX,
    INDICES_CONFIG,
    DEFAULT_NSE_INDICES,
    NSE_INDEX_DISPLAY,
    YF_INDEX_DISPLAY,
    logger,
)

# 2-second delay between Yahoo Finance calls to avoid HTTP 429 rate-limiting
FETCH_DELAY_SECONDS = 2.0

# API URLs
NSE_ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"
NSE_EQUITY_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Browser-like headers required for NSE India API
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # No brotli — not always available in GitHub Actions
    "Referer": "https://www.nseindia.com/",
}

# Browser-like headers for Yahoo Finance
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
    Holds all price data for a single stock or index for one trading day.
    Used by both the opening alert (shows open + gap) and closing alert
    (shows close + change + day range).
    """
    ticker: str           # Internal identifier (e.g., "INFY" or "NIFTY 50")
    display_name: str     # Label shown in the Telegram message
    current_price: float  # Last traded price — used as "Close" in closing alert
    prev_close: float     # Previous session's closing price
    open_price: float     # Day's opening price at 9:15 AM — used in opening alert
    day_high: float       # Highest price traded today
    day_low: float        # Lowest price traded today
    change: float         # Absolute change vs prev_close
    change_pct: float     # Percentage change vs prev_close
    is_index: bool = False

    @property
    def gap_pct(self) -> float:
        """
        Gap percentage = how much the stock opened above/below yesterday's close.
        Used in the morning opening alert to show overnight sentiment.
        Returns 0 if opening price is not available yet (pre-market).
        """
        if self.prev_close == 0 or self.open_price == 0:
            return 0.0
        return (self.open_price - self.prev_close) / self.prev_close * 100


# ─────────────────────────────────────────────────────────────────
# INDEX FETCHING — NSE India allIndices API (primary source)
# ─────────────────────────────────────────────────────────────────

def fetch_indices_from_nse() -> dict:
    """
    Fetches all index values from NSE India's allIndices API in one HTTP call.
    Returns a dict mapping NSE index symbol → StockQuote.
    Example key: "NIFTY 50", "NIFTY MIDCAP 150", "NIFTY SMLCAP 250"

    The allIndices API returns: last, open, high, low, previousClose, percentChange.
    This is the only source for Midcap 150 and Smallcap 250 index values.
    Returns empty dict if the API fails (caller will try yfinance fallback).
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
            logger.warning("NSE allIndices API returned empty data")
            return {}

        # Build lookup: indexSymbol → row data
        nse_lookup = {row["indexSymbol"]: row for row in all_indices}

        results = {}
        for nse_symbol in DEFAULT_NSE_INDICES:
            row = nse_lookup.get(nse_symbol)
            if row is None:
                logger.warning(f"NSE API: '{nse_symbol}' not in response")
                continue

            current_price = float(row.get("last") or 0)
            prev_close = float(row.get("previousClose") or 0)
            open_price = float(row.get("open") or 0)
            day_high = float(row.get("high") or 0)
            day_low = float(row.get("low") or 0)

            if current_price == 0:
                logger.warning(f"NSE API: zero price for '{nse_symbol}'")
                continue

            change = current_price - prev_close
            change_pct = float(row.get("percentChange") or 0)
            display_name = NSE_INDEX_DISPLAY.get(nse_symbol, nse_symbol)

            logger.info(
                f"NSE index {display_name}: {current_price:,.2f} "
                f"({change_pct:+.2f}%)"
            )

            results[nse_symbol] = StockQuote(
                ticker=nse_symbol,
                display_name=display_name,
                current_price=current_price,
                prev_close=prev_close,
                open_price=open_price,
                day_high=day_high,
                day_low=day_low,
                change=change,
                change_pct=change_pct,
                is_index=True,
            )

        logger.info(f"NSE API: fetched {len(results)}/{len(DEFAULT_NSE_INDICES)} indices")
        return results

    except Exception as e:
        logger.warning(f"NSE allIndices API failed (will try yfinance fallback): {e}")
        return {}


def fetch_index_via_yfinance_fallback(nse_symbol: str) -> Optional[StockQuote]:
    """
    Fallback for a single index when the NSE allIndices API is down.
    Uses the mapped yfinance ticker if one exists for this index.
    Nifty Midcap 150 and Smallcap 250 have no yfinance ticker — they return None.
    """
    yf_ticker = None
    for _, nse, yf_t in INDICES_CONFIG:
        if nse == nse_symbol:
            yf_ticker = yf_t
            break

    if yf_ticker is None:
        logger.warning(
            f"No yfinance fallback for '{nse_symbol}' — NSE API is the only source"
        )
        return None

    price_data = _fetch_via_yahoo_api(yf_ticker)
    if price_data is None:
        price_data = _fetch_via_yfinance_lib(yf_ticker)
    if price_data is None:
        return None

    display_name = YF_INDEX_DISPLAY.get(yf_ticker, nse_symbol)
    return _build_quote(nse_symbol, display_name, price_data, is_index=True)


# ─────────────────────────────────────────────────────────────────
# STOCK FETCHING — NSE equity API (primary) + Yahoo Finance (fallback)
# ─────────────────────────────────────────────────────────────────

def fetch_stock_from_nse(ticker: str) -> Optional[StockQuote]:
    """
    Fetches price data for a single NSE-listed stock using the NSE India
    quote-equity API. Returns None if the API fails (will fall back to yfinance).

    The API returns: priceInfo with lastPrice, open, previousClose,
    intraDayHighLow.min/max, pChange.
    """
    try:
        url = NSE_EQUITY_URL.format(symbol=ticker)
        session = requests.Session()
        response = session.get(url, headers=NSE_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(
                f"NSE equity API returned HTTP {response.status_code} for {ticker}"
            )
            return None

        data = response.json()
        pi = data.get("priceInfo", {})

        current_price = float(pi.get("lastPrice") or pi.get("close") or 0)
        prev_close = float(pi.get("previousClose") or pi.get("basePrice") or 0)
        open_price = float(pi.get("open") or 0)
        intraday = pi.get("intraDayHighLow", {}) or {}
        day_high = float(intraday.get("max") or 0)
        day_low = float(intraday.get("min") or 0)
        change_pct = float(pi.get("pChange") or 0)

        if current_price == 0:
            logger.warning(f"NSE equity API: zero price for {ticker}")
            return None

        change = current_price - prev_close

        logger.info(
            f"NSE stock {ticker}: {current_price:,.2f} "
            f"({change_pct:+.2f}%)"
        )

        return StockQuote(
            ticker=ticker,
            display_name=ticker,
            current_price=current_price,
            prev_close=prev_close,
            open_price=open_price,
            day_high=day_high,
            day_low=day_low,
            change=change,
            change_pct=change_pct,
            is_index=False,
        )

    except Exception as e:
        logger.warning(f"NSE equity API failed for {ticker}: {e}")
        return None


def fetch_stock_quote(ticker: str) -> Optional[StockQuote]:
    """
    Fetches the current price for a single NSE-listed stock (e.g., "INFY").
    Tries NSE equity API first, then falls back to Yahoo Finance.
    Returns None if all methods fail — the stock is skipped, not a crash.
    """
    # Try NSE equity API first (has open, high, low — full data)
    quote = fetch_stock_from_nse(ticker)
    if quote:
        return quote

    logger.warning(f"NSE equity API failed for {ticker} — trying Yahoo Finance fallback")

    # Yahoo Finance needs ".NS" suffix for NSE stocks
    yf_ticker = f"{ticker}{NSE_SUFFIX}"

    price_data = _fetch_via_yahoo_api(yf_ticker)
    if price_data is None:
        price_data = _fetch_via_yfinance_lib(yf_ticker)

    if price_data is None:
        logger.error(f"All fetch methods failed for {ticker}")
        return None

    return _build_quote(ticker, ticker, price_data, is_index=False)


# ─────────────────────────────────────────────────────────────────
# YAHOO FINANCE HELPERS (used as fallback for both stocks and indices)
# ─────────────────────────────────────────────────────────────────

def _fetch_via_yahoo_api(yf_ticker: str) -> Optional[dict]:
    """
    Fetches price data via a direct HTTP GET to the Yahoo Finance chart API.
    Returns a dict with current_price, prev_close, open_price, day_high, day_low.
    Returns None if the fetch fails.
    This is more reliable than the yfinance library when there are 429 errors.
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
            return None

        meta = result[0].get("meta", {})
        current_price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

        if current_price is None or prev_close is None:
            return None

        return {
            "current_price": float(current_price),
            "prev_close": float(prev_close),
            "open_price": float(meta.get("regularMarketOpen") or 0),
            "day_high": float(meta.get("regularMarketDayHigh") or 0),
            "day_low": float(meta.get("regularMarketDayLow") or 0),
        }

    except Exception as e:
        logger.debug(f"Yahoo direct API failed for {yf_ticker}: {e}")
        return None


def _fetch_via_yfinance_lib(yf_ticker: str) -> Optional[dict]:
    """
    Fetches price data using the yfinance Python library.
    Returns a dict with current_price, prev_close, open_price, day_high, day_low.
    Returns None if the fetch fails.
    """
    try:
        stock = yf.Ticker(yf_ticker)
        fi = stock.fast_info

        current_price = getattr(fi, "last_price", None)
        prev_close = getattr(fi, "previous_close", None)

        if current_price is None or prev_close is None:
            return None

        return {
            "current_price": float(current_price),
            "prev_close": float(prev_close),
            "open_price": float(getattr(fi, "open", None) or 0),
            "day_high": float(getattr(fi, "day_high", None) or 0),
            "day_low": float(getattr(fi, "day_low", None) or 0),
        }

    except Exception as e:
        logger.debug(f"yfinance lib failed for {yf_ticker}: {e}")
        return None


def _build_quote(
    ticker: str, display_name: str, price_data: dict, is_index: bool
) -> StockQuote:
    """
    Builds a StockQuote from a price data dict returned by Yahoo Finance helpers.
    """
    current_price = price_data["current_price"]
    prev_close = price_data["prev_close"]
    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0

    logger.info(
        f"YF {'index' if is_index else 'stock'} {display_name}: "
        f"{current_price:,.2f} ({change_pct:+.2f}%)"
    )

    return StockQuote(
        ticker=ticker,
        display_name=display_name,
        current_price=current_price,
        prev_close=prev_close,
        open_price=price_data.get("open_price", 0.0),
        day_high=price_data.get("day_high", 0.0),
        day_low=price_data.get("day_low", 0.0),
        change=change,
        change_pct=change_pct,
        is_index=is_index,
    )


# ─────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def fetch_all_quotes(watchlist: list) -> tuple:
    """
    Fetches price data for all 5 indices and all stocks in the watchlist.

    Indices:  NSE allIndices API (one call) → yfinance per-index fallback
    Stocks:   NSE equity API → Yahoo Finance fallback, with 2s delay between calls

    Returns:
      - List of StockQuote objects (indices first, then watchlist stocks in order)
      - List of tickers that completely failed to fetch
    """
    successful_quotes = []
    failed_tickers = []

    # ── Step 1: Fetch all 5 indices from NSE in one call ──
    logger.info("Fetching indices from NSE India allIndices API...")
    nse_index_results = fetch_indices_from_nse()

    for _, nse_symbol, _ in INDICES_CONFIG:
        if nse_symbol in nse_index_results:
            successful_quotes.append(nse_index_results[nse_symbol])
        else:
            logger.warning(f"Trying yfinance fallback for index '{nse_symbol}'...")
            fallback = fetch_index_via_yfinance_fallback(nse_symbol)
            if fallback:
                successful_quotes.append(fallback)
            else:
                failed_tickers.append(nse_symbol)

    # ── Step 2: Fetch each watchlist stock ──
    if watchlist:
        logger.info(f"Fetching {len(watchlist)} watchlist stocks...")
        for ticker in watchlist:
            quote = fetch_stock_quote(ticker)
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


def validate_ticker(ticker: str) -> tuple:
    """
    Checks if a ticker symbol is valid by fetching its current price.
    Returns (True, price) if valid, (False, None) if not found.
    Used by /add command to verify a ticker before saving it.
    """
    quote = fetch_stock_quote(ticker)
    if quote and quote.current_price > 0:
        return True, quote.current_price
    return False, None
