# This file manages the list of stocks you want to track.
# The watchlist is saved in a JSON file so it persists between runs.
# You can add stocks by name (like "Infosys") or by ticker (like "INFY").
# The fuzzy search finds the best matching ticker from the NSE stock list.

import json
import os
from pathlib import Path
from rapidfuzz import process, fuzz
from config import WATCHLIST_FILE, NSE_SUFFIX, logger

# This is the path to the watchlist file, resolved from the project root
WATCHLIST_PATH = Path(WATCHLIST_FILE)


def load_watchlist() -> list[str]:
    """
    Reads the watchlist from the JSON file and returns a list of ticker symbols.
    If the file doesn't exist yet, returns an empty list (first-time setup).
    Example return: ["INFY", "HDFCBANK", "TCS"]
    """
    if not WATCHLIST_PATH.exists():
        logger.info("Watchlist file not found — starting with empty watchlist")
        return []

    try:
        with open(WATCHLIST_PATH, "r") as f:
            data = json.load(f)
        tickers = data.get("watchlist", [])
        logger.info(f"Loaded watchlist with {len(tickers)} stocks: {tickers}")
        return tickers
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read watchlist file: {e}")
        return []


def save_watchlist(tickers: list[str]) -> bool:
    """
    Saves the given list of ticker symbols to the watchlist JSON file.
    Creates the data/ directory if it doesn't exist yet.
    Returns True if saved successfully, False if something went wrong.
    """
    try:
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(WATCHLIST_PATH, "w") as f:
            json.dump({"watchlist": tickers}, f, indent=2)
        logger.info(f"Saved watchlist: {tickers}")
        return True
    except IOError as e:
        logger.error(f"Failed to save watchlist: {e}")
        return False


def add_stock(ticker: str) -> tuple[bool, str]:
    """
    Adds a stock ticker to the watchlist if it isn't already there.
    Returns (True, message) on success, (False, message) on failure or duplicate.
    The ticker should already be validated before calling this function.
    """
    tickers = load_watchlist()
    ticker = ticker.upper().strip()

    if ticker in tickers:
        return False, f"{ticker} is already in your watchlist."

    tickers.append(ticker)
    if save_watchlist(tickers):
        return True, f"Added {ticker} to your watchlist. Total: {len(tickers)} stocks."
    return False, "Failed to save the watchlist. Please try again."


def remove_stock(ticker: str) -> tuple[bool, str]:
    """
    Removes a stock ticker from the watchlist.
    Returns (True, message) on success, (False, message) if not found.
    """
    tickers = load_watchlist()
    ticker = ticker.upper().strip()

    if ticker not in tickers:
        return False, f"{ticker} is not in your watchlist."

    tickers.remove(ticker)
    if save_watchlist(tickers):
        return True, f"Removed {ticker} from your watchlist. Total: {len(tickers)} stocks."
    return False, "Failed to save the watchlist. Please try again."


def get_nse_ticker_map() -> dict[str, str]:
    """
    Returns a dictionary mapping company names and ticker symbols to NSE tickers.
    This is used for fuzzy search — so you can type "Infosys" and find "INFY".

    We build this map from a curated list of the most commonly traded NSE stocks.
    The keys are searchable terms (company name + ticker), the values are tickers.
    """
    # A comprehensive map of NSE stocks: display name → ticker symbol
    # Format: "Company Name": "TICKER"
    nse_stocks = {
        # Nifty 50 stocks
        "Reliance Industries": "RELIANCE",
        "HDFC Bank": "HDFCBANK",
        "ICICI Bank": "ICICIBANK",
        "Infosys": "INFY",
        "TCS": "TCS",
        "Tata Consultancy Services": "TCS",
        "Hindustan Unilever": "HINDUNILVR",
        "HUL": "HINDUNILVR",
        "ITC": "ITC",
        "Kotak Mahindra Bank": "KOTAKBANK",
        "Kotak Bank": "KOTAKBANK",
        "Larsen & Toubro": "LT",
        "L&T": "LT",
        "Axis Bank": "AXISBANK",
        "Bajaj Finance": "BAJFINANCE",
        "Bajaj Finserv": "BAJAJFINSV",
        "Asian Paints": "ASIANPAINT",
        "HCL Technologies": "HCLTECH",
        "HCL Tech": "HCLTECH",
        "Maruti Suzuki": "MARUTI",
        "Maruti": "MARUTI",
        "Sun Pharmaceuticals": "SUNPHARMA",
        "Sun Pharma": "SUNPHARMA",
        "Wipro": "WIPRO",
        "UltraTech Cement": "ULTRACEMCO",
        "Titan Company": "TITAN",
        "Titan": "TITAN",
        "Power Grid": "POWERGRID",
        "NTPC": "NTPC",
        "Nestle India": "NESTLEIND",
        "Nestle": "NESTLEIND",
        "Tech Mahindra": "TECHM",
        "JSW Steel": "JSWSTEEL",
        "Tata Steel": "TATASTEEL",
        "Tata Motors": "TATAMOTORS",
        "Tata Consumer Products": "TATACONSUM",
        "Grasim Industries": "GRASIM",
        "IndusInd Bank": "INDUSINDBK",
        "ONGC": "ONGC",
        "Oil and Natural Gas Corporation": "ONGC",
        "Cipla": "CIPLA",
        "Hindalco": "HINDALCO",
        "Dr Reddys": "DRREDDY",
        "Dr. Reddy's Laboratories": "DRREDDY",
        "Adani Enterprises": "ADANIENT",
        "Adani Ports": "ADANIPORTS",
        "Adani Green": "ADANIGREEN",
        "Adani Power": "ADANIPOWER",
        "SBI": "SBIN",
        "State Bank of India": "SBIN",
        "SBI Life": "SBILIFE",
        "HDFC Life": "HDFCLIFE",
        "ICICI Prudential": "ICICIPRULI",
        "ICICI Lombard": "ICICIGI",
        "Bajaj Auto": "BAJAJ-AUTO",
        "Hero MotoCorp": "HEROMOTOCO",
        "Eicher Motors": "EICHERMOT",
        "Mahindra & Mahindra": "M&M",
        "M&M": "M&M",
        "Bharat Petroleum": "BPCL",
        "BPCL": "BPCL",
        "Indian Oil": "IOC",
        "IOC": "IOC",
        "Coal India": "COALINDIA",
        "Vedanta": "VEDL",
        "Shree Cement": "SHREECEM",
        "Divi's Laboratories": "DIVISLAB",
        "Apollo Hospitals": "APOLLOHOSP",
        # Additional popular stocks
        "Zomato": "ZOMATO",
        "Paytm": "PAYTM",
        "Nykaa": "NYKAA",
        "FSN E-Commerce": "NYKAA",
        "Delhivery": "DELHIVERY",
        "PB Fintech": "POLICYBZR",
        "PolicyBazaar": "POLICYBZR",
        "Hindustan Aeronautics": "HAL",
        "HAL": "HAL",
        "BEL": "BEL",
        "Bharat Electronics": "BEL",
        "IRCTC": "IRCTC",
        "Indian Railway Catering": "IRCTC",
        "Dixon Technologies": "DIXON",
        "Havells": "HAVELLS",
        "Page Industries": "PAGEIND",
        "Pidilite": "PIDILITIND",
        "Marico": "MARICO",
        "Godrej Consumer": "GODREJCP",
        "Dabur": "DABUR",
        "Emami": "EMAMILTD",
        "Trent": "TRENT",
        "Avenue Supermarts": "DMART",
        "DMart": "DMART",
        "Motherson Sumi": "MOTHERSON",
        "Bosch": "BOSCHLTD",
        "Muthoot Finance": "MUTHOOTFIN",
        "Cholamandalam": "CHOLAFIN",
        "Shriram Finance": "SHRIRAMFIN",
        "LIC": "LICI",
        "Life Insurance Corporation": "LICI",
        "Bank of Baroda": "BANKBARODA",
        "Canara Bank": "CANBK",
        "Punjab National Bank": "PNB",
        "Union Bank": "UNIONBANK",
        "Federal Bank": "FEDERALBNK",
        "Karnataka Bank": "KTKBANK",
        "Yes Bank": "YESBANK",
        "IDFC First Bank": "IDFCFIRSTB",
        "AU Small Finance": "AUBANK",
        "Bandhan Bank": "BANDHANBNK",
        "RBL Bank": "RBLBANK",
        "SAIL": "SAIL",
        "Steel Authority": "SAIL",
        "NMDC": "NMDC",
        "Jindal Steel": "JINDALSTEL",
        "JSW Energy": "JSWENERGY",
        "Tata Power": "TATAPOWER",
        "Adani Total Gas": "ATGL",
        "Gujarat Gas": "GUJGASLTD",
        "IGL": "IGL",
        "Indraprastha Gas": "IGL",
        "MGL": "MGL",
        "Mahanagar Gas": "MGL",
        "Petronet LNG": "PETRONET",
        "Interglobe Aviation": "INDIGO",
        "IndiGo": "INDIGO",
        "SpiceJet": "SPICEJET",
        "Oberoi Realty": "OBEROIRLTY",
        "DLF": "DLF",
        "Godrej Properties": "GODREJPROP",
        "Prestige Estates": "PRESTIGE",
        "Phoenix Mills": "PHOENIXLTD",
        "Balkrishna Industries": "BALKRISIND",
        "MRF": "MRF",
        "Apollo Tyres": "APOLLOTYRE",
        "CEAT": "CEATLTD",
        "Jubilant FoodWorks": "JUBLFOOD",
        "Dominos": "JUBLFOOD",
        "Burger King India": "RBA",
        "Westlife": "WESTLIFE",
        "Info Edge": "NAUKRI",
        "Naukri": "NAUKRI",
        "Just Dial": "JUSTDIAL",
        "Indiamart": "INDIAMART",
        "Angel One": "ANGELONE",
        "Zerodha": "ZERODHA",
        "CDSL": "CDSL",
        "BSE": "BSE",
        "MCX": "MCX",
        "Computer Age Management": "CAMS",
        "CAMS": "CAMS",
        "Persistent Systems": "PERSISTENT",
        "Mphasis": "MPHASIS",
        "Coforge": "COFORGE",
        "LTIMindtree": "LTIM",
        "Mindtree": "LTIM",
        "Hexaware": "HEXAWARE",
        "Mastek": "MASTEK",
        "Birlasoft": "BSOFT",
        "Zensar": "ZENSARTECH",
        "KPIT Technologies": "KPITTECH",
        "Tata Elxsi": "TATAELXSI",
        "Cyient": "CYIENT",
        "Firstsource": "FSL",
        "Happiest Minds": "HAPPSTMNDS",
        "Tanla Platforms": "TANLA",
        "Astral": "ASTRAL",
        "Polycab": "POLYCAB",
        "KEI Industries": "KEI",
        "V-Guard": "VGUARD",
        "Finolex Cables": "FINCABLES",
        "Crompton Greaves": "CROMPTON",
        "Voltas": "VOLTAS",
        "Blue Star": "BLUESTAR",
        "Symphony": "SYMPHONY",
        "Whirlpool": "WHIRLPOOL",
        "Relaxo Footwear": "RELAXO",
        "Bata India": "BATAIND",
        "Campus Activewear": "CAMPUS",
        "PVR INOX": "PVRINOX",
        "Inox Leisure": "PVRINOX",
        "Netflix India": "NETFINDLTD",
        "Zee Entertainment": "ZEEL",
        "Sun TV": "SUNTV",
        "Dish TV": "DISHTV",
    }

    # Build the search map: both "Company Name" and "TICKER" map to the ticker
    search_map = {}
    for name, ticker in nse_stocks.items():
        search_map[name.upper()] = ticker
        search_map[ticker.upper()] = ticker

    return search_map


def fuzzy_search_ticker(query: str, top_n: int = 5) -> list[tuple[str, str, int]]:
    """
    Searches for a stock by company name or ticker using fuzzy matching.
    For example, searching "Infosys" returns [("INFY", "Infosys", 95), ...]

    Returns a list of (ticker, display_name, confidence_score) tuples,
    sorted by best match first. The confidence score is 0-100.
    """
    search_map = get_nse_ticker_map()
    query_upper = query.upper().strip()

    # Use rapidfuzz to find the closest matches among all searchable names
    matches = process.extract(
        query_upper,
        list(search_map.keys()),
        scorer=fuzz.WRatio,
        limit=top_n * 2  # Get more than needed so we can deduplicate
    )

    # Deduplicate by ticker (multiple names can map to same ticker)
    seen_tickers = set()
    results = []
    for match_name, score, _ in matches:
        ticker = search_map[match_name]
        if ticker not in seen_tickers and score >= 50:  # Minimum 50% confidence
            seen_tickers.add(ticker)
            results.append((ticker, match_name.title(), score))
        if len(results) >= top_n:
            break

    return results
