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

# === LOAD TICKERS ===
with open("qualified_watchlist.txt", "r") as f:
    WATCHLIST = [line.strip() for line in f if line.strip()]

candles = {sym: deque(maxlen=20) for sym in WATCHLIST}
vwap_data = defaultdict(lambda: {"cum_vol": 0, "cum_dollar": 0})

# === ALPACA AUTH ===
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY_ID,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

def get_positions():
    r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=HEADERS)
    if r.status_code != 200:
        return []
    return [pos['symbol'] for pos in r.json()]

def get_account():
    r = requests.get(f"{ALPACA_BASE}/v2/account", headers=HEADERS)
    return r.json()

def calculate_qty(price):
    account = get_account()
    equity = float(account["cash"])
    trade_amt = equity * (TRADE_PERCENT / 100)
    return max(1, int(trade_amt / price))

def send_discord_message(text):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text})
    except:
        pass

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
        msg = f"🚀 BUY {symbol} | Qty: {qty} | Entry: ${price:.2f} | SL: ${stop_price} | Trail: {trail_pct}%"
    else:
        msg = f"❌ ORDER FAIL {symbol} | {r.status_code}: {r.text}"
    print(msg)
    send_discord_message(msg)

# === ENTRY LOGIC ===
def should_buy(symbol):
    if len(candles[symbol]) < 3:
        return False

    c1, c2, c3 = candles[symbol][-3:]
    if not all(c['c'] > c['o'] for c in [c1, c2, c3]):
        return False

    vwap = vwap_data[symbol]
    if vwap["cum_vol"] == 0:
        return False
    current_vwap = vwap["cum_dollar"] / vwap["cum_vol"]
    if c3['c'] < current_vwap:
        return False

    volumes = [c['v'] for c in candles[symbol][-10:] if 'v' in c]
    if len(volumes) < 5:
        return False
    avg_vol = sum(volumes) / len(volumes)
    if c3['v'] < 2 * avg_vol:
        return False

    return True

# === MAIN LOOP ===
async def trade_stream():
    uri = "wss://socket.polygon.io/stocks"
    async with websockets.connect(uri) as ws:
        print("🟢 Connected to Polygon")
        await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
        auth_resp = await ws.recv()
        print("🔐 Auth:", auth_resp)

        # Chunk subscriptions to avoid disconnects
        tickers = [f"AM.{sym}" for sym in WATCHLIST]
        chunk_size = 100
        for i in range(0, len(tickers), chunk_size):
            chunk = ",".join(tickers[i:i + chunk_size])
            await ws.send(json.dumps({"action": "subscribe", "params": chunk}))
            await asyncio.sleep(0.5)
        print(f"✅ Subscribed to {len(WATCHLIST)} symbols.")

        held = set(get_positions())
        print(f"🎒 Currently holding: {held}")

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                if isinstance(data, list):
                    for ev in data:
                        if ev.get('ev') != 'AM':
                            continue
                        symbol = ev['sym']
                        candles[symbol].append(ev)
                        vwap_data[symbol]["cum_vol"] += ev['v']
                        vwap_data[symbol]["cum_dollar"] += ev['v'] * ((ev['h'] + ev['l'] + ev['c']) / 3)

                        if should_buy(symbol) and symbol not in held:
                            price = ev['c']
                            qty = calculate_qty(price)
                            place_order(symbol, qty, price)
                            held.add(symbol)
            except Exception as e:
                print(f"❌ WebSocket Error: {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    print(f"🚀 Starting bot at {datetime.now()}")
    asyncio.run(trade_stream())
