import asyncio
import websockets
import json
import os
import requests
from datetime import datetime
from collections import deque, defaultdict
from dotenv import load_dotenv

load_dotenv()

# === ENV VARS ===
POLYGON_KEY = os.getenv("POLYGON_API_KEY")
ALPACA_KEY_ID = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# === INPUT TICKERS ===
with open("qualified_watchlist.txt", "r") as f:
    WATCHLIST = [line.strip() for line in f.readlines() if line.strip()]

# === DATA TRACKING ===
candles = {sym: deque(maxlen=20) for sym in WATCHLIST}
vwap_data = defaultdict(lambda: {"cum_vol": 0, "cum_dollar": 0})

# === ALPACA ===
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY_ID,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

def get_positions():
    url = f"{ALPACA_BASE}/v2/positions"
    r = requests.get(url, headers=HEADERS)
    return [pos['symbol'] for pos in r.json()]

def get_account():
    url = f"{ALPACA_BASE}/v2/account"
    r = requests.get(url, headers=HEADERS)
    return r.json()

def calculate_qty(price):
    account = get_account()
    equity = float(account["cash"])
    trade_amt = equity * (TRADE_PERCENT / 100)
    return max(1, int(trade_amt / price))

def send_discord_message(text):
    if not DISCORD_WEBHOOK:
        print("⚠️ No Discord webhook set")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text})
    except Exception as e:
        print("Discord error:", e)

def place_order(symbol, qty, price):
    url = f"{ALPACA_BASE}/v2/orders"
    stop_price = round(price * 0.95, 2)
    trail_pct = 5

    order = {
        "symbol": symbol,
        "qty": qty,
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc",
        "order_class": "bracket",
        "take_profit": {"limit_price": round(price * 1.2, 2)},
        "stop_loss": {
            "stop_price": stop_price,
            "trail_percent": trail_pct
        }
    }

    r = requests.post(url, headers=HEADERS, json=order)
    if r.status_code == 200:
        msg = f"🚀 BUY: {symbol} | Qty: {qty} | Entry: ${price:.2f} | SL: ${stop_price} | Trail: {trail_pct}%"
    else:
        msg = f"❌ ORDER FAIL: {symbol} | {r.status_code}: {r.text}"
    print(msg)
    send_discord_message(msg)

# === ENTRY LOGIC ===
def should_buy(symbol):
    if len(candles[symbol]) < 3:
        return False

    c1, c2, c3 = candles[symbol][-3:]
    if not all(c['c'] > c['o'] for c in [c1, c2, c3]):
        return False

    # VWAP check
    vwap = vwap_data[symbol]
    if vwap["cum_vol"] == 0:
        return False
    current_vwap = vwap["cum_dollar"] / vwap["cum_vol"]
    if c3['c'] < current_vwap:
        return False

    # RVOL check
    volumes = [c['v'] for c in candles[symbol][-10:] if 'v' in c]
    if len(volumes) < 5:
        return False
    avg_vol = sum(volumes) / len(volumes)
    if c3['v'] < 2 * avg_vol:
        return False

    return True

# === LIVE TRADING LOOP ===
async def trade
