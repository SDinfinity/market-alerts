/**
 * Cloudflare Worker — Market Alerts Bot
 *
 * Two responsibilities:
 *
 * 1. SCHEDULED ALERTS (cron triggers — primary alerting path):
 *    Fires at exact market times, fetches live data, formats and sends
 *    Telegram alerts directly — no GitHub Actions in the critical path.
 *      3:47 AM UTC  = 9:17 AM IST  → opening alert
 *      10:30 AM UTC = 4:00 PM IST  → closing alert
 *    Dedup state is stored in data/last_alert.json on GitHub.
 *
 * 2. TELEGRAM WEBHOOK (HTTP POST — command handling):
 *    Handles bot commands instantly:
 *      /add TICKER [, TICKER2, ...]   — add one or more stocks
 *      /remove [TICKER | NUMBER]      — remove by ticker or list position
 *      /list                          — show current watchlist
 *      /status                        — show bot status
 *      /help                          — show command reference
 *
 * Secrets (set via `wrangler secret put`):
 *   TELEGRAM_BOT_TOKEN  — from @BotFather
 *   TELEGRAM_CHAT_ID    — your personal chat ID (security filter)
 *   GITHUB_TOKEN        — Personal Access Token with repo write access
 *
 * Variables in wrangler.toml (not secrets):
 *   GITHUB_OWNER, GITHUB_REPO
 */

// ─────────────────────────────────────────────────────────────────────────────
// NSE company name → ticker map (used by /add command fuzzy search)
// ─────────────────────────────────────────────────────────────────────────────

const NSE_COMPANY_MAP = {
  // Nifty 50
  "RELIANCE INDUSTRIES": "RELIANCE", "RELIANCE": "RELIANCE",
  "HDFC BANK": "HDFCBANK", "HDFCBANK": "HDFCBANK",
  "ICICI BANK": "ICICIBANK", "ICICIBANK": "ICICIBANK",
  "INFOSYS": "INFY", "INFY": "INFY",
  "TCS": "TCS", "TATA CONSULTANCY SERVICES": "TCS",
  "HINDUSTAN UNILEVER": "HINDUNILVR", "HUL": "HINDUNILVR", "HINDUNILVR": "HINDUNILVR",
  "ITC": "ITC",
  "KOTAK MAHINDRA BANK": "KOTAKBANK", "KOTAK BANK": "KOTAKBANK", "KOTAKBANK": "KOTAKBANK",
  "LARSEN & TOUBRO": "LT", "L&T": "LT", "LT": "LT",
  "AXIS BANK": "AXISBANK", "AXISBANK": "AXISBANK",
  "BAJAJ FINANCE": "BAJFINANCE", "BAJFINANCE": "BAJFINANCE",
  "BAJAJ FINSERV": "BAJAJFINSV", "BAJAJFINSV": "BAJAJFINSV",
  "ASIAN PAINTS": "ASIANPAINT", "ASIANPAINT": "ASIANPAINT",
  "HCL TECHNOLOGIES": "HCLTECH", "HCL TECH": "HCLTECH", "HCLTECH": "HCLTECH",
  "MARUTI SUZUKI": "MARUTI", "MARUTI": "MARUTI",
  "SUN PHARMACEUTICALS": "SUNPHARMA", "SUN PHARMA": "SUNPHARMA", "SUNPHARMA": "SUNPHARMA",
  "WIPRO": "WIPRO",
  "ULTRATECH CEMENT": "ULTRACEMCO", "ULTRACEMCO": "ULTRACEMCO",
  "TITAN COMPANY": "TITAN", "TITAN": "TITAN",
  "POWER GRID": "POWERGRID", "POWERGRID": "POWERGRID",
  "NTPC": "NTPC",
  "NESTLE INDIA": "NESTLEIND", "NESTLE": "NESTLEIND", "NESTLEIND": "NESTLEIND",
  "TECH MAHINDRA": "TECHM", "TECHM": "TECHM",
  "JSW STEEL": "JSWSTEEL", "JSWSTEEL": "JSWSTEEL",
  "TATA STEEL": "TATASTEEL", "TATASTEEL": "TATASTEEL",
  "TATA MOTORS": "TATAMOTORS", "TATAMOTORS": "TATAMOTORS",
  "TATA CONSUMER PRODUCTS": "TATACONSUM", "TATACONSUM": "TATACONSUM",
  "GRASIM INDUSTRIES": "GRASIM", "GRASIM": "GRASIM",
  "INDUSIND BANK": "INDUSINDBK", "INDUSINDBK": "INDUSINDBK",
  "ONGC": "ONGC", "OIL AND NATURAL GAS CORPORATION": "ONGC",
  "CIPLA": "CIPLA",
  "HINDALCO": "HINDALCO",
  "DR REDDYS": "DRREDDY", "DR. REDDY'S LABORATORIES": "DRREDDY", "DRREDDY": "DRREDDY",
  "ADANI ENTERPRISES": "ADANIENT", "ADANIENT": "ADANIENT",
  "ADANI PORTS": "ADANIPORTS", "ADANIPORTS": "ADANIPORTS",
  "ADANI GREEN": "ADANIGREEN", "ADANIGREEN": "ADANIGREEN",
  "ADANI POWER": "ADANIPOWER", "ADANIPOWER": "ADANIPOWER",
  "SBI": "SBIN", "STATE BANK OF INDIA": "SBIN", "SBIN": "SBIN",
  "SBI LIFE": "SBILIFE", "SBILIFE": "SBILIFE",
  "HDFC LIFE": "HDFCLIFE", "HDFCLIFE": "HDFCLIFE",
  "ICICI PRUDENTIAL": "ICICIPRULI", "ICICIPRULI": "ICICIPRULI",
  "ICICI LOMBARD": "ICICIGI", "ICICIGI": "ICICIGI",
  "BAJAJ AUTO": "BAJAJ-AUTO", "BAJAJ-AUTO": "BAJAJ-AUTO",
  "HERO MOTOCORP": "HEROMOTOCO", "HEROMOTOCO": "HEROMOTOCO",
  "EICHER MOTORS": "EICHERMOT", "EICHERMOT": "EICHERMOT",
  "MAHINDRA & MAHINDRA": "M&M", "M&M": "M&M",
  "BHARAT PETROLEUM": "BPCL", "BPCL": "BPCL",
  "INDIAN OIL": "IOC", "IOC": "IOC",
  "COAL INDIA": "COALINDIA", "COALINDIA": "COALINDIA",
  "VEDANTA": "VEDL", "VEDL": "VEDL",
  "SHREE CEMENT": "SHREECEM", "SHREECEM": "SHREECEM",
  "DIVI'S LABORATORIES": "DIVISLAB", "DIVISLAB": "DIVISLAB",
  "APOLLO HOSPITALS": "APOLLOHOSP", "APOLLOHOSP": "APOLLOHOSP",
  // Popular additional stocks
  "ZOMATO": "ZOMATO",
  "PAYTM": "PAYTM",
  "NYKAA": "NYKAA", "FSN E-COMMERCE": "NYKAA",
  "DELHIVERY": "DELHIVERY",
  "POLICYBAZAAR": "POLICYBZR", "PB FINTECH": "POLICYBZR", "POLICYBZR": "POLICYBZR",
  "HAL": "HAL", "HINDUSTAN AERONAUTICS": "HAL",
  "BEL": "BEL", "BHARAT ELECTRONICS": "BEL",
  "IRCTC": "IRCTC",
  "DIXON TECHNOLOGIES": "DIXON", "DIXON": "DIXON",
  "HAVELLS": "HAVELLS",
  "LIC": "LICI", "LIFE INSURANCE CORPORATION": "LICI", "LICI": "LICI",
  "BANK OF BARODA": "BANKBARODA", "BANKBARODA": "BANKBARODA",
  "CANARA BANK": "CANBK", "CANBK": "CANBK",
  "PUNJAB NATIONAL BANK": "PNB", "PNB": "PNB",
  "YES BANK": "YESBANK", "YESBANK": "YESBANK",
  "IDFC FIRST BANK": "IDFCFIRSTB", "IDFCFIRSTB": "IDFCFIRSTB",
  "AU SMALL FINANCE": "AUBANK", "AUBANK": "AUBANK",
  "BANDHAN BANK": "BANDHANBNK", "BANDHANBNK": "BANDHANBNK",
  "TATA POWER": "TATAPOWER", "TATAPOWER": "TATAPOWER",
  "JSW ENERGY": "JSWENERGY", "JSWENERGY": "JSWENERGY",
  "INTERGLOBE AVIATION": "INDIGO", "INDIGO": "INDIGO",
  "DLF": "DLF",
  "GODREJ PROPERTIES": "GODREJPROP", "GODREJPROP": "GODREJPROP",
  "MRF": "MRF",
  "PERSISTENT SYSTEMS": "PERSISTENT", "PERSISTENT": "PERSISTENT",
  "MPHASIS": "MPHASIS",
  "COFORGE": "COFORGE",
  "LTIMINDTREE": "LTIM", "LTI MINDTREE": "LTIM", "LTIM": "LTIM",
  "KPIT TECHNOLOGIES": "KPITTECH", "KPITTECH": "KPITTECH",
  "TATA ELXSI": "TATAELXSI", "TATAELXSI": "TATAELXSI",
  "POLYCAB": "POLYCAB",
  "VOLTAS": "VOLTAS",
  "JUBILANT FOODWORKS": "JUBLFOOD", "DOMINOS": "JUBLFOOD", "JUBLFOOD": "JUBLFOOD",
  "INFO EDGE": "NAUKRI", "NAUKRI": "NAUKRI",
  "ANGEL ONE": "ANGELONE", "ANGELONE": "ANGELONE",
  "CDSL": "CDSL",
  "BSE": "BSE",
  "MCX": "MCX",
  "CAMS": "CAMS", "COMPUTER AGE MANAGEMENT": "CAMS",
  "ASTRAL": "ASTRAL",
  "MARICO": "MARICO",
  "GODREJ CONSUMER": "GODREJCP", "GODREJCP": "GODREJCP",
  "DABUR": "DABUR",
  "PIDILITE": "PIDILITIND", "PIDILITIND": "PIDILITIND",
  "MUTHOOT FINANCE": "MUTHOOTFIN", "MUTHOOTFIN": "MUTHOOTFIN",
  "SHRIRAM FINANCE": "SHRIRAMFIN", "SHRIRAMFIN": "SHRIRAMFIN",
  "CHOLAMANDALAM": "CHOLAFIN", "CHOLAFIN": "CHOLAFIN",
  "BHARTI AIRTEL": "BHARTIARTL", "AIRTEL": "BHARTIARTL", "BHARTIARTL": "BHARTIARTL",
  "AVENUE SUPERMARTS": "DMART", "DMART": "DMART",
  "TRENT": "TRENT",
  "SAIL": "SAIL", "STEEL AUTHORITY": "SAIL",
  "NMDC": "NMDC",
  "JINDAL STEEL": "JINDALSTEL", "JINDALSTEL": "JINDALSTEL",
  "PVR INOX": "PVRINOX", "PVRINOX": "PVRINOX",
  "ZEE ENTERTAINMENT": "ZEEL", "ZEEL": "ZEEL",
  "SUN TV": "SUNTV", "SUNTV": "SUNTV",
  "IGL": "IGL", "INDRAPRASTHA GAS": "IGL",
  "MGL": "MGL", "MAHANAGAR GAS": "MGL",
  "PETRONET LNG": "PETRONET", "PETRONET": "PETRONET",
  "OBEROI REALTY": "OBEROIRLTY", "OBEROIRLTY": "OBEROIRLTY",
  "PRESTIGE ESTATES": "PRESTIGE", "PRESTIGE": "PRESTIGE",
  "BALKRISHNA INDUSTRIES": "BALKRISIND", "BALKRISIND": "BALKRISIND",
  "APOLLO TYRES": "APOLLOTYRE", "APOLLOTYRE": "APOLLOTYRE",
  "PAGE INDUSTRIES": "PAGEIND", "PAGEIND": "PAGEIND",
  "CROMPTON GREAVES": "CROMPTON", "CROMPTON": "CROMPTON",
  "BATA INDIA": "BATAIND", "BATAIND": "BATAIND",
  "MOTHERSON SUMI": "MOTHERSON", "MOTHERSON": "MOTHERSON",
  "BOSCH": "BOSCHLTD", "BOSCHLTD": "BOSCHLTD",
  "EDELWEISS": "EDELWEISS",
};

// ─────────────────────────────────────────────────────────────────────────────
// Fuzzy search (no npm — pure string scoring)
// ─────────────────────────────────────────────────────────────────────────────

function fuzzyScore(query, candidate) {
  if (query === candidate) return 100;
  if (candidate.startsWith(query)) return 90;
  if (candidate.includes(query)) return Math.max(50, 80 - (candidate.length - query.length));

  const bigrams = (s) => {
    const b = new Set();
    for (let i = 0; i < s.length - 1; i++) b.add(s.slice(i, i + 2));
    return b;
  };
  const qBig = bigrams(query);
  const cBig = bigrams(candidate);
  if (qBig.size === 0 || cBig.size === 0) return 0;
  let intersection = 0;
  for (const b of qBig) if (cBig.has(b)) intersection++;
  return Math.round((2 * intersection / (qBig.size + cBig.size)) * 70);
}

function fuzzySearch(query, limit = 5) {
  const q = query.toUpperCase().trim();
  const seen = new Set();
  const results = [];

  for (const [name, ticker] of Object.entries(NSE_COMPANY_MAP)) {
    if (seen.has(ticker)) continue;
    const score = fuzzyScore(q, name);
    if (score >= 40) {
      seen.add(ticker);
      results.push({ ticker, label: name, score });
    }
  }

  results.sort((a, b) => b.score - a.score);
  return results.slice(0, limit);
}

// ─────────────────────────────────────────────────────────────────────────────
// Trading day logic
// ─────────────────────────────────────────────────────────────────────────────

// Official NSE trading holidays 2026 (from NSE circular NSE/CMTR/71775).
const NSE_HOLIDAYS_2026 = new Set([
  "2026-01-26", // Republic Day
  "2026-03-03", // Holi
  "2026-03-26", // Shri Ram Navami
  "2026-03-31", // Shri Mahavir Jayanti
  "2026-04-03", // Good Friday
  "2026-04-14", // Dr. Ambedkar Jayanti
  "2026-05-01", // Maharashtra Day
  "2026-05-28", // Bakri Id
  "2026-06-26", // Muharram
  "2026-08-19", // Ganesh Chaturthi
  "2026-10-01", // Mahatma Gandhi Jayanti / Dussehra
  "2026-10-02", // Dussehra
  "2026-10-22", // Diwali Laxmi Pujan
  "2026-10-23", // Diwali Balipratipada
  "2026-11-05", // Prakash Gurpurb Sri Guru Nanak Dev
  "2026-12-25", // Christmas
]);

// Special sessions on otherwise non-trading days (e.g. Muhurat Trading).
const NSE_SPECIAL_TRADING_DAYS_2026 = new Set([
  "2026-11-08", // Muhurat Trading (Sunday)
]);

/** Returns today's date string in IST (e.g. "2026-03-23"). */
function getISTDateString() {
  const ist = new Date(Date.now() + (5 * 60 + 30) * 60 * 1000);
  return ist.toISOString().slice(0, 10);
}

/** Returns true if today (IST) is an NSE trading day. */
function isTradingDay() {
  const dateStr = getISTDateString();
  if (NSE_SPECIAL_TRADING_DAYS_2026.has(dateStr)) return true;

  const ist = new Date(Date.now() + (5 * 60 + 30) * 60 * 1000);
  const dow = ist.getUTCDay(); // 0 = Sunday, 6 = Saturday
  if (dow === 0 || dow === 6) return false;
  if (NSE_HOLIDAYS_2026.has(dateStr)) return false;
  return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Market data — index config + fetching
// ─────────────────────────────────────────────────────────────────────────────

const INDICES_CONFIG = [
  { display: "NIFTY 50",      nse: "NIFTY 50",          yf: "^NSEI"    },
  { display: "NIFTY NEXT 50", nse: "NIFTY NEXT 50",     yf: "^NSMIDCP" },
  { display: "MIDCAP 150",    nse: "NIFTY MIDCAP 150",  yf: null       },
  { display: "SMALLCAP 250",  nse: "NIFTY SMLCAP 250",  yf: null       },
  { display: "NIFTY 500",     nse: "NIFTY 500",         yf: "^CRSLDX"  },
];

const NSE_INDEX_DISPLAY = Object.fromEntries(
  INDICES_CONFIG.map(({ display, nse }) => [nse, display])
);

const NSE_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "application/json, text/plain, */*",
  "Accept-Language": "en-US,en;q=0.9",
  "Referer": "https://www.nseindia.com/",
};

const YAHOO_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "application/json",
};

/**
 * Fetches all 5 index values from NSE India's allIndices API in one call.
 * Returns a map of nse_symbol → quote object, or {} on failure.
 */
async function fetchIndicesFromNSE() {
  try {
    const res = await fetch("https://www.nseindia.com/api/allIndices", {
      headers: NSE_HEADERS,
    });
    if (!res.ok) return {};

    const data = await res.json();
    const rows = data?.data;
    if (!Array.isArray(rows) || rows.length === 0) return {};

    const lookup = Object.fromEntries(rows.map((r) => [r.indexSymbol, r]));
    const results = {};

    for (const { display, nse } of INDICES_CONFIG) {
      const r = lookup[nse];
      if (!r) continue;
      const currentPrice = parseFloat(r.last) || 0;
      if (currentPrice === 0) continue;
      const prevClose = parseFloat(r.previousClose) || 0;
      results[nse] = {
        ticker: nse,
        displayName: display,
        currentPrice,
        prevClose,
        openPrice: parseFloat(r.open) || 0,
        dayHigh: parseFloat(r.high) || 0,
        dayLow: parseFloat(r.low) || 0,
        change: currentPrice - prevClose,
        changePct: parseFloat(r.percentChange) || 0,
        isIndex: true,
      };
    }
    return results;
  } catch {
    return {};
  }
}

/**
 * Fetches a single quote from Yahoo Finance chart API.
 * Used as fallback for both indices (with ^NSEI etc.) and stocks (with .NS suffix).
 * Returns a quote object, or null on failure.
 */
async function fetchViaYahoo(symbol, displayName, isIndex) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
    const res = await fetch(url, { headers: YAHOO_HEADERS });
    if (!res.ok) return null;

    const data = await res.json();
    const result = data?.chart?.result?.[0];
    if (!result) return null;

    const meta = result.meta;
    const currentPrice = meta?.regularMarketPrice;
    const prevClose = meta?.chartPreviousClose ?? meta?.previousClose;
    if (!currentPrice || !prevClose) return null;

    const cp = parseFloat(currentPrice);
    const pc = parseFloat(prevClose);
    const change = cp - pc;
    const changePct = pc !== 0 ? (change / pc) * 100 : 0;

    return {
      ticker: symbol,
      displayName,
      currentPrice: cp,
      prevClose: pc,
      openPrice: parseFloat(meta?.regularMarketOpen) || 0,
      dayHigh: parseFloat(meta?.regularMarketDayHigh) || 0,
      dayLow: parseFloat(meta?.regularMarketDayLow) || 0,
      change,
      changePct,
      isIndex,
    };
  } catch {
    return null;
  }
}

/**
 * Fetches a single NSE stock from NSE's equity API.
 * Returns a quote object, or null on failure (caller falls back to Yahoo).
 */
async function fetchStockFromNSE(ticker) {
  try {
    const url = `https://www.nseindia.com/api/quote-equity?symbol=${encodeURIComponent(ticker)}`;
    const res = await fetch(url, { headers: NSE_HEADERS });
    if (!res.ok) return null;

    const data = await res.json();
    const pi = data?.priceInfo;
    if (!pi) return null;

    const currentPrice = parseFloat(pi.lastPrice ?? pi.close) || 0;
    if (currentPrice === 0) return null;

    const prevClose = parseFloat(pi.previousClose ?? pi.basePrice) || 0;
    const intraday = pi.intraDayHighLow || {};
    const change = currentPrice - prevClose;
    const changePct = parseFloat(pi.pChange) || 0;

    return {
      ticker,
      displayName: ticker,
      currentPrice,
      prevClose,
      openPrice: parseFloat(pi.open) || 0,
      dayHigh: parseFloat(intraday.max) || 0,
      dayLow: parseFloat(intraday.min) || 0,
      change,
      changePct,
      isIndex: false,
    };
  } catch {
    return null;
  }
}

/**
 * Fetches a single stock quote: NSE equity API first, Yahoo Finance fallback.
 */
async function fetchStockQuote(ticker) {
  const nseQuote = await fetchStockFromNSE(ticker);
  if (nseQuote) return nseQuote;
  return fetchViaYahoo(`${ticker}.NS`, ticker, false);
}

/**
 * Fetches all quotes: 5 indices + every stock in the watchlist.
 * Returns { quotes: [...], failed: [...] }.
 * Indices and stocks are fetched in parallel for speed.
 */
async function fetchAllQuotes(watchlist) {
  // Fetch indices (one NSE call, with per-index Yahoo fallback)
  const nseIndices = await fetchIndicesFromNSE();

  const indexPromises = INDICES_CONFIG.map(async ({ display, nse, yf }) => {
    if (nseIndices[nse]) return { quote: nseIndices[nse], ticker: nse };
    if (yf) {
      const q = await fetchViaYahoo(yf, display, true);
      return { quote: q, ticker: nse };
    }
    return { quote: null, ticker: nse };
  });

  // Fetch watchlist stocks in parallel
  const stockPromises = watchlist.map(async (ticker) => {
    const q = await fetchStockQuote(ticker);
    return { quote: q, ticker };
  });

  const [indexResults, stockResults] = await Promise.all([
    Promise.all(indexPromises),
    Promise.all(stockPromises),
  ]);

  const quotes = [];
  const failed = [];

  for (const { quote, ticker } of indexResults) {
    if (quote) quotes.push(quote);
    else failed.push(ticker);
  }
  for (const { quote, ticker } of stockResults) {
    if (quote) quotes.push(quote);
    else failed.push(ticker);
  }

  return { quotes, failed };
}

// ─────────────────────────────────────────────────────────────────────────────
// Message formatting
// ─────────────────────────────────────────────────────────────────────────────

// Column layout matching the Python formatter (31 chars wide per row):
//   Stocks:  name.padEnd(15) + price.padStart(8) + "   " + pct.padStart(5)
//   Indices: name.padEnd(15) + price.padStart(9) + "  "  + pct.padStart(5)
const DIVIDER = "━".repeat(31);

const NSE_INDEX_SYMBOLS = new Set(INDICES_CONFIG.map((i) => i.nse));

/** Formats a price with commas and 2 decimals: 1234.5 → "1,234.50" */
function fmtPrice(v) {
  const parts = v.toFixed(2).split(".");
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return parts.join(".");
}

/** Formats a percentage with sign and 1 decimal: 2.137 → "+2.1%" */
function fmtPct(v) {
  return (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
}

function stockRow(name, price, pct) {
  return name.padEnd(15) + fmtPrice(price).padStart(8) + "   " + fmtPct(pct).padStart(5);
}

function indexRow(name, price, pct) {
  return name.padEnd(15) + fmtPrice(price).padStart(9) + "  " + fmtPct(pct).padStart(5);
}

/** Returns a human-readable IST date string, e.g. "Mon, 23 Mar 2026". */
function getISTDateStr() {
  const ist = new Date(Date.now() + (5 * 60 + 30) * 60 * 1000);
  const days   = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const d = String(ist.getUTCDate()).padStart(2, "0");
  return `${days[ist.getUTCDay()]}, ${d} ${months[ist.getUTCMonth()]} ${ist.getUTCFullYear()}`;
}

/**
 * Opening alert: stocks sorted by gap% (open vs prev close) high → low.
 * Indices follow in fixed order.
 */
function formatOpeningAlert(quotes, failed) {
  const dateStr = getISTDateStr();
  const indices = quotes.filter((q) => q.isIndex);
  const stocks  = quotes.filter((q) => !q.isIndex);

  stocks.sort((a, b) => {
    const gapA = a.openPrice > 0 ? (a.openPrice - a.prevClose) / a.prevClose * 100 : a.changePct;
    const gapB = b.openPrice > 0 ? (b.openPrice - b.prevClose) / b.prevClose * 100 : b.changePct;
    return gapB - gapA;
  });

  const header = "Ticker".padEnd(15) + "Open".padStart(8) + "   " + "Gap".padStart(5);
  const lines = ["<pre>"];
  lines.push(`Market open \u2014 ${dateStr}`);
  lines.push("Sorted by gap high \u2192 low");
  lines.push("");
  lines.push(header);
  lines.push(DIVIDER);

  for (const q of stocks) {
    const price = q.openPrice > 0 ? q.openPrice : q.prevClose;
    const gap   = q.openPrice > 0
      ? (q.openPrice - q.prevClose) / q.prevClose * 100
      : q.changePct;
    lines.push(stockRow(q.displayName, price, gap));
  }

  lines.push("");
  lines.push("Indices");
  for (const q of indices) {
    lines.push(indexRow(q.displayName, q.currentPrice, q.changePct));
  }

  lines.push("");
  lines.push("Gap = open vs prev close");

  const stockFailed = failed.filter((t) => !NSE_INDEX_SYMBOLS.has(t));
  if (stockFailed.length > 0) {
    lines.push(`Could not fetch: ${stockFailed.join(", ")}`);
  }

  lines.push("</pre>");
  return lines.join("\n");
}

/**
 * Closing alert: stocks sorted by change% (best performers first).
 * Indices follow in fixed order.
 */
function formatClosingAlert(quotes, failed) {
  const dateStr = getISTDateStr();
  const indices = quotes.filter((q) => q.isIndex);
  const stocks  = quotes.filter((q) => !q.isIndex);

  stocks.sort((a, b) => b.changePct - a.changePct);

  const header = "Ticker".padEnd(15) + "Close".padStart(8) + "   " + "Chg".padStart(5);
  const lines = ["<pre>"];
  lines.push(`Market close \u2014 ${dateStr}`);
  lines.push("Sorted best \u2192 worst");
  lines.push("");
  lines.push(header);
  lines.push(DIVIDER);

  for (const q of stocks) {
    lines.push(stockRow(q.displayName, q.currentPrice, q.changePct));
  }

  lines.push("");
  lines.push("Indices");
  for (const q of indices) {
    lines.push(indexRow(q.displayName, q.currentPrice, q.changePct));
  }

  lines.push("");
  lines.push("Chg = close vs prev close");

  const stockFailed = failed.filter((t) => !NSE_INDEX_SYMBOLS.has(t));
  if (stockFailed.length > 0) {
    lines.push(`Could not fetch: ${stockFailed.join(", ")}`);
  }

  lines.push("</pre>");
  return lines.join("\n");
}

/** Sent when ALL data fetches fail. */
function formatFailureAlert() {
  const ist = new Date(Date.now() + (5 * 60 + 30) * 60 * 1000);
  const timeStr = ist.toISOString().replace("T", " ").slice(0, 16) + " IST";
  return (
    `<pre>Market alert failed\n\n` +
    `Could not fetch any market data at ${timeStr}.\n\n` +
    `Possible cause: Yahoo Finance or NSE API temporarily unavailable.\n` +
    `Please check the market manually.</pre>`
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GitHub API helpers
// ─────────────────────────────────────────────────────────────────────────────

const WATCHLIST_PATH   = "data/watchlist.json";
const LAST_ALERT_PATH  = "data/last_alert.json";

function githubHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "market-alerts-bot",
  };
}

/** Reads data/watchlist.json from GitHub. Returns { watchlist, sha }. */
async function githubGet(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${WATCHLIST_PATH}`;
  const res = await fetch(url, { headers: githubHeaders(env) });
  if (!res.ok) throw new Error(`GitHub GET failed: ${res.status}`);
  const data = await res.json();
  const content = JSON.parse(atob(data.content.replace(/\n/g, "")));
  return { watchlist: content.watchlist || [], sha: data.sha };
}

/** Writes data/watchlist.json to GitHub. */
async function githubPut(env, watchlist, sha) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${WATCHLIST_PATH}`;
  const content = btoa(JSON.stringify({ watchlist }, null, 2) + "\n");
  const res = await fetch(url, {
    method: "PUT",
    headers: { ...githubHeaders(env), "Content-Type": "application/json" },
    body: JSON.stringify({
      message: "Update watchlist via Telegram [skip ci]",
      content,
      sha,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`GitHub PUT failed: ${res.status} ${err}`);
  }
}

/**
 * Reads data/last_alert.json from GitHub for dedup checking.
 * Returns { state, sha } — state is {} if the file doesn't exist yet.
 */
async function githubGetLastAlert(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${LAST_ALERT_PATH}`;
  const res = await fetch(url, { headers: githubHeaders(env) });
  if (!res.ok) return { state: {}, sha: null };
  const data = await res.json();
  const state = JSON.parse(atob(data.content.replace(/\n/g, "")));
  return { state, sha: data.sha };
}

/**
 * Writes data/last_alert.json to GitHub to record that an alert was sent.
 * Uses [skip ci] so this commit doesn't re-trigger GitHub Actions.
 */
async function githubPutLastAlert(env, state, sha) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${LAST_ALERT_PATH}`;
  const body = {
    message: "Update bot data [skip ci]",
    content: btoa(JSON.stringify(state, null, 2) + "\n"),
  };
  if (sha) body.sha = sha;

  const res = await fetch(url, {
    method: "PUT",
    headers: { ...githubHeaders(env), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error(`Failed to update last_alert.json: ${res.status} ${err}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// NSE ticker validation (used by /add command)
// ─────────────────────────────────────────────────────────────────────────────

async function isValidNseTicker(ticker) {
  if (NSE_COMPANY_MAP[ticker.toUpperCase()]) return true;

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}.NS?interval=1d&range=1d`;
    const res = await fetch(url, { headers: YAHOO_HEADERS });
    if (!res.ok) return false;
    const data = await res.json();
    const result = data?.chart?.result?.[0];
    return !!(result?.meta?.regularMarketPrice > 0);
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Telegram API helper
// ─────────────────────────────────────────────────────────────────────────────

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML" }),
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Telegram command handlers
// ─────────────────────────────────────────────────────────────────────────────

async function handleAdd(args, env) {
  if (!args) {
    return "Usage: /add TICKER\nExample: /add INFY\nExample: /add INFY, TCS, WIPRO\n\nYou can search by company name:\n/add Infosys";
  }

  const inputs = args.split(",").map((s) => s.trim()).filter(Boolean);
  const results = [];

  let watchlistData;
  try {
    watchlistData = await githubGet(env);
  } catch (e) {
    return `Error reading watchlist: ${e.message}`;
  }

  let { watchlist, sha } = watchlistData;
  let changed = false;

  for (const input of inputs) {
    const upper = input.toUpperCase();
    const mapped = NSE_COMPANY_MAP[upper];
    const ticker = mapped || upper;

    if (watchlist.includes(ticker)) {
      results.push(`${ticker} — already in watchlist`);
      continue;
    }

    const valid = await isValidNseTicker(ticker);
    if (!valid) {
      const suggestions = fuzzySearch(input, 3);
      if (suggestions.length > 0) {
        const opts = suggestions.map((s) => s.ticker).join(", ");
        results.push(`${input} — not found. Did you mean: ${opts}?`);
      } else {
        results.push(`${input} — not found on NSE`);
      }
      continue;
    }

    watchlist.push(ticker);
    changed = true;
    results.push(`${ticker} — added`);
  }

  if (changed) {
    try {
      await githubPut(env, watchlist, sha);
    } catch (e) {
      return `Error saving watchlist: ${e.message}`;
    }
  }

  return `<pre>${results.join("\n")}\n\nTotal: ${watchlist.length} stocks</pre>`;
}

async function handleRemove(args, env) {
  let watchlistData;
  try {
    watchlistData = await githubGet(env);
  } catch (e) {
    return `Error reading watchlist: ${e.message}`;
  }

  let { watchlist, sha } = watchlistData;

  if (!args) {
    if (watchlist.length === 0) return "Your watchlist is empty.";
    const numbered = watchlist.map((t, i) => `${i + 1}. ${t}`).join("\n");
    return `<pre>Your watchlist:\n${numbered}\n\nUse /remove TICKER or /remove 1,3 to remove by number.</pre>`;
  }

  const parts = args.split(",").map((s) => s.trim()).filter(Boolean);
  const toRemove = new Set();
  const errors = [];

  for (const part of parts) {
    const n = parseInt(part, 10);
    if (!isNaN(n)) {
      if (n < 1 || n > watchlist.length) {
        errors.push(`${n} — invalid position (list has ${watchlist.length} stocks)`);
      } else {
        toRemove.add(watchlist[n - 1]);
      }
    } else {
      const upper = part.toUpperCase();
      if (!watchlist.includes(upper)) {
        errors.push(`${upper} — not in watchlist`);
      } else {
        toRemove.add(upper);
      }
    }
  }

  const removed = [...toRemove];
  const newList = watchlist.filter((t) => !toRemove.has(t));

  if (removed.length > 0) {
    try {
      await githubPut(env, newList, sha);
    } catch (e) {
      return `Error saving watchlist: ${e.message}`;
    }
  }

  const lines = [];
  for (const t of removed) lines.push(`${t} — removed`);
  for (const e of errors) lines.push(e);
  lines.push(`\nTotal: ${newList.length} stocks`);

  return `<pre>${lines.join("\n")}</pre>`;
}

async function handleList(env) {
  let watchlistData;
  try {
    watchlistData = await githubGet(env);
  } catch (e) {
    return `Error reading watchlist: ${e.message}`;
  }

  const { watchlist } = watchlistData;
  if (watchlist.length === 0) {
    return "Your watchlist is empty.\n\nUse /add TICKER to add stocks.";
  }

  const numbered = watchlist.map((t, i) => `${String(i + 1).padStart(2)}. ${t}`).join("\n");
  return `<pre>Watchlist (${watchlist.length} stocks):\n\n${numbered}</pre>`;
}

function handleStatus() {
  const ist = new Date(Date.now() + (5 * 60 + 30) * 60 * 1000);
  const timeStr = ist.toISOString().replace("T", " ").slice(0, 19) + " IST";
  const trading = isTradingDay();

  return (
    `<pre>Market Alerts Bot — Status\n\n` +
    `Status:     Running\n` +
    `Time (IST): ${timeStr}\n` +
    `Today:      ${trading ? "Trading day" : "Non-trading day"}\n` +
    `Data:       NSE India API + Yahoo Finance\n` +
    `Alerts:     9:17 AM IST (opening)\n` +
    `            4:00 PM IST (closing)\n` +
    `Engine:     Cloudflare Worker (direct)</pre>`
  );
}

function handleHelp() {
  return (
    `<pre>Market Alerts Bot — Commands\n\n` +
    `/add TICKER     Add a stock (e.g. /add INFY)\n` +
    `/add A, B, C    Add multiple stocks at once\n` +
    `/add Infosys    Search by company name\n` +
    `/remove         Show numbered list\n` +
    `/remove TICKER  Remove by ticker name\n` +
    `/remove 1,3     Remove by list position\n` +
    `/list           Show current watchlist\n` +
    `/status         Show bot status\n` +
    `/help           Show this help\n\n` +
    `Alerts run Mon-Fri on trading days.\n` +
    `Opening: 9:17 AM IST  Closing: 4:00 PM IST</pre>`
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main export
// ─────────────────────────────────────────────────────────────────────────────

export default {
  /**
   * Cron handler — the primary alerting path.
   *
   * Fires at exact alert times (set in wrangler.toml):
   *   3:47 AM UTC  = 9:17 AM IST → opening alert
   *   10:30 AM UTC = 4:00 PM IST → closing alert
   *
   * Steps:
   *   1. Skip if today is not a trading day.
   *   2. Read last_alert.json from GitHub — skip if already sent today.
   *   3. Read watchlist from GitHub.
   *   4. Fetch market data (NSE primary, Yahoo Finance fallback).
   *   5. Format and send Telegram message.
   *   6. Write last_alert.json back to GitHub to mark as sent.
   */
  async scheduled(event, env) {
    const utcHour = new Date(event.scheduledTime).getUTCHours();
    const alertType = utcHour < 9 ? "opening" : "closing";

    // Step 1: trading day check
    if (!isTradingDay()) {
      console.log(`${alertType}: not a trading day — skipping`);
      return;
    }

    // Step 2: dedup check via GitHub last_alert.json
    const today = getISTDateString();
    let lastAlertState, lastAlertSha;
    try {
      const { state, sha } = await githubGetLastAlert(env);
      lastAlertState = state;
      lastAlertSha = sha;
    } catch (e) {
      console.error(`Failed to read last_alert.json: ${e.message}`);
      lastAlertState = {};
      lastAlertSha = null;
    }

    if (lastAlertState.date === today && lastAlertState[alertType]) {
      console.log(`${alertType}: already sent today — skipping`);
      return;
    }

    // Step 3: read watchlist
    let watchlist = [];
    try {
      const { watchlist: wl } = await githubGet(env);
      watchlist = wl;
    } catch (e) {
      console.error(`Failed to read watchlist: ${e.message} — continuing with indices only`);
    }

    // Step 4: fetch market data
    console.log(`Fetching market data for ${alertType} alert (${watchlist.length} stocks)...`);
    const { quotes, failed } = await fetchAllQuotes(watchlist);
    console.log(`Fetched ${quotes.length} quotes, ${failed.length} failed: ${failed.join(", ") || "none"}`);

    // Step 5: format and send
    let message;
    if (quotes.length === 0) {
      console.error("All data fetches failed — sending failure alert");
      message = formatFailureAlert();
    } else if (alertType === "opening") {
      message = formatOpeningAlert(quotes, failed);
    } else {
      message = formatClosingAlert(quotes, failed);
    }

    await sendTelegram(env.TELEGRAM_BOT_TOKEN, env.TELEGRAM_CHAT_ID, message);
    console.log(`${alertType} alert sent`);

    // Step 6: mark as sent in last_alert.json
    const newState = lastAlertState.date === today
      ? { ...lastAlertState, [alertType]: true }
      : { date: today, opening: false, closing: false, [alertType]: true };

    await githubPutLastAlert(env, newState, lastAlertSha);
  },

  /**
   * HTTP handler — Telegram webhook for bot commands.
   * Unchanged from the original implementation.
   */
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    const message = update?.message;
    if (!message || !message.text) {
      return new Response("OK", { status: 200 });
    }

    // Security: only respond to your own chat
    const chatId = String(message.chat.id);
    if (chatId !== String(env.TELEGRAM_CHAT_ID)) {
      return new Response("OK", { status: 200 });
    }

    const text = message.text.trim();
    const spaceIdx = text.indexOf(" ");
    const rawCmd = spaceIdx === -1 ? text : text.slice(0, spaceIdx);
    const args   = spaceIdx === -1 ? "" : text.slice(spaceIdx + 1).trim();
    const cmd    = rawCmd.split("@")[0].toLowerCase();

    let reply;
    try {
      switch (cmd) {
        case "/add":    reply = await handleAdd(args || null, env); break;
        case "/remove": reply = await handleRemove(args || null, env); break;
        case "/list":   reply = await handleList(env); break;
        case "/status": reply = handleStatus(); break;
        case "/help":
        case "/start":  reply = handleHelp(); break;
        default: return new Response("OK", { status: 200 });
      }
    } catch (e) {
      reply = `Error: ${e.message}`;
    }

    await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, reply);
    return new Response("OK", { status: 200 });
  },
};
