/**
 * Cloudflare Worker — Telegram webhook handler for Market Alerts Bot.
 *
 * Handles commands instantly via webhook (no polling delay):
 *   /add TICKER [, TICKER2, ...]   — add one or more stocks
 *   /remove [TICKER | NUMBER]      — remove by ticker or list position
 *   /list                          — show current watchlist
 *   /status                        — show bot status
 *   /help                          — show command reference
 *
 * Environment variables (set via `wrangler secret put`):
 *   TELEGRAM_BOT_TOKEN  — from @BotFather
 *   TELEGRAM_CHAT_ID    — your personal chat ID (security filter)
 *   GITHUB_TOKEN        — Personal Access Token with repo write access
 *
 * Variables in wrangler.toml (not secrets):
 *   GITHUB_OWNER        — your GitHub username
 *   GITHUB_REPO         — repository name (e.g. "market-alerts")
 */

// ─────────────────────────────────────────────────────────────
// NSE company name → ticker map (mirrors watchlist.py)
// ─────────────────────────────────────────────────────────────

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
  "INDIGO": "INDIGO",
  "MARICO": "MARICO",
  "GODREJ CONSUMER": "GODREJCP", "GODREJCP": "GODREJCP",
  "DABUR": "DABUR",
  "PIGEON": "TTKHLTCARE",
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
};

// ─────────────────────────────────────────────────────────────
// Fuzzy search (no npm — pure string scoring)
// ─────────────────────────────────────────────────────────────

/**
 * Scores how well `query` matches `candidate` (0–100).
 * Uses a combination of:
 *   - Exact match (100)
 *   - Prefix match (90)
 *   - Contains match (80 minus length penalty)
 *   - Bigram similarity (0–70)
 */
function fuzzyScore(query, candidate) {
  if (query === candidate) return 100;
  if (candidate.startsWith(query)) return 90;
  if (candidate.includes(query)) return Math.max(50, 80 - (candidate.length - query.length));

  // Bigram similarity
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

/**
 * Returns top matches for `query` from NSE_COMPANY_MAP.
 * Each result: { ticker, label, score }
 */
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

// ─────────────────────────────────────────────────────────────
// GitHub API helpers
// ─────────────────────────────────────────────────────────────

const WATCHLIST_PATH = "data/watchlist.json";

async function githubGet(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${WATCHLIST_PATH}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "market-alerts-bot",
    },
  });
  if (!res.ok) throw new Error(`GitHub GET failed: ${res.status}`);
  const data = await res.json();
  const content = JSON.parse(atob(data.content.replace(/\n/g, "")));
  return { watchlist: content.watchlist || [], sha: data.sha };
}

async function githubPut(env, watchlist, sha) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${WATCHLIST_PATH}`;
  const content = btoa(JSON.stringify({ watchlist }, null, 2) + "\n");
  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "market-alerts-bot",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: `Update watchlist via Telegram [skip ci]`,
      content,
      sha,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`GitHub PUT failed: ${res.status} ${err}`);
  }
}

// ─────────────────────────────────────────────────────────────
// NSE ticker validation
// ─────────────────────────────────────────────────────────────

/**
 * Checks if a ticker is valid on NSE by hitting Yahoo Finance chart API.
 * Returns true if Yahoo Finance returns price data for TICKER.NS.
 */
async function isValidNseTicker(ticker) {
  // Check static map first (instant)
  if (NSE_COMPANY_MAP[ticker.toUpperCase()]) return true;

  // Verify against Yahoo Finance
  try {
    const yf = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}.NS?interval=1d&range=1d`;
    const res = await fetch(yf, {
      headers: {
        "User-Agent": "Mozilla/5.0",
        Accept: "application/json",
      },
    });
    if (!res.ok) return false;
    const data = await res.json();
    const result = data?.chart?.result?.[0];
    return !!(result && result.meta && result.meta.regularMarketPrice > 0);
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────
// Telegram API helpers
// ─────────────────────────────────────────────────────────────

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: "HTML",
    }),
  });
}

// ─────────────────────────────────────────────────────────────
// Command handlers
// ─────────────────────────────────────────────────────────────

async function handleAdd(args, env) {
  if (!args) {
    return "Usage: /add TICKER\nExample: /add INFY\nExample: /add INFY, TCS, WIPRO\n\nYou can search by company name:\n/add Infosys";
  }

  // Split by comma for bulk add
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

    // Check static map first (handles company names too)
    const mapped = NSE_COMPANY_MAP[upper];
    const ticker = mapped || upper;

    // Check if already in watchlist
    if (watchlist.includes(ticker)) {
      results.push(`${ticker} — already in watchlist`);
      continue;
    }

    // Validate ticker
    const valid = await isValidNseTicker(ticker);
    if (!valid) {
      // Try fuzzy search for suggestions
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

  const summary = results.join("\n");
  return `<pre>${summary}\n\nTotal: ${watchlist.length} stocks</pre>`;
}

async function handleRemove(args, env) {
  let watchlistData;
  try {
    watchlistData = await githubGet(env);
  } catch (e) {
    return `Error reading watchlist: ${e.message}`;
  }

  let { watchlist, sha } = watchlistData;

  // No args → show numbered list
  if (!args) {
    if (watchlist.length === 0) return "Your watchlist is empty.";
    const numbered = watchlist.map((t, i) => `${i + 1}. ${t}`).join("\n");
    return `<pre>Your watchlist:\n${numbered}\n\nUse /remove TICKER or /remove 1,3 to remove by number.</pre>`;
  }

  // Parse args: could be "TICKER", "1", "1,3", or "1, 3"
  const parts = args.split(",").map((s) => s.trim()).filter(Boolean);
  const toRemove = new Set();
  const errors = [];

  for (const part of parts) {
    const n = parseInt(part, 10);
    if (!isNaN(n)) {
      // Number-based removal (1-indexed)
      if (n < 1 || n > watchlist.length) {
        errors.push(`${n} — invalid position (list has ${watchlist.length} stocks)`);
      } else {
        toRemove.add(watchlist[n - 1]);
      }
    } else {
      // Ticker-based removal
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
  const now = new Date();
  // Convert to IST (UTC+5:30)
  const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
  const timeStr = ist.toISOString().replace("T", " ").slice(0, 19) + " IST";

  return (
    `<pre>Market Alerts Bot — Status\n\n` +
    `Status:    Running\n` +
    `Time (IST): ${timeStr}\n` +
    `Data:      NSE India API + Yahoo Finance\n` +
    `Alerts:    9:17 AM IST (opening)\n` +
    `           3:45 PM IST (closing)</pre>`
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
    `Opening: 9:17 AM IST  Closing: 3:45 PM IST</pre>`
  );
}

// ─────────────────────────────────────────────────────────────
// Main handler
// ─────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    // Only accept POST requests (Telegram webhook sends POST)
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

    // Parse command and args
    const text = message.text.trim();
    const spaceIdx = text.indexOf(" ");
    const rawCmd = spaceIdx === -1 ? text : text.slice(0, spaceIdx);
    const args = spaceIdx === -1 ? "" : text.slice(spaceIdx + 1).trim();

    // Strip bot username suffix (e.g. /add@MyBot → /add)
    const cmd = rawCmd.split("@")[0].toLowerCase();

    let reply;
    try {
      switch (cmd) {
        case "/add":
          reply = await handleAdd(args || null, env);
          break;
        case "/remove":
          reply = await handleRemove(args || null, env);
          break;
        case "/list":
          reply = await handleList(env);
          break;
        case "/status":
          reply = handleStatus();
          break;
        case "/help":
        case "/start":
          reply = handleHelp();
          break;
        default:
          // Ignore unknown commands silently
          return new Response("OK", { status: 200 });
      }
    } catch (e) {
      reply = `Error: ${e.message}`;
    }

    await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, reply);
    return new Response("OK", { status: 200 });
  },
};
