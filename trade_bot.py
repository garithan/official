
import os
import json
import requests
import asyncio
import websockets
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")
ALPACA_BASE = "https://paper-api.alpaca.markets"
POLYGON_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

print("🔑 POLYGON_KEY Loaded:", POLYGON_KEY[:5], flush=True)

with open("qualified_watchlist.txt", "r") as f:
    WATCHLIST = [line.strip() for line in f if line.strip()]
print("📄 Loaded", len(WATCHLIST), "tickers", flush=True)

candles = {}  # Symbol: list of 1-min AM bars
vwap_data = {}  # Symbol: cumulative VWAP

def send_discord_message(msg):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    except:
        pass

def get_positions():
    r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=HEADERS)
    if r.status_code == 200:
        return [pos['symbol'] for pos in r.json()]
    return []

def calculate_qty(price):
    capital = float(os.getenv("TOTAL_CAPITAL", "10000"))
    risk_per_trade = capital * 0.02
    qty = int(risk_per_trade // price)
    return max(qty, 1)

def should_buy(symbol):
    c = candles.get(symbol, [])
    if len(c) < 3:
        return False
    rvol = vwap_data[symbol]["cum_vol"] / (sum([x['v'] for x in c]) / len(c))
    green_candles = sum([1 for x in c[-3:] if x['c'] > x['o']])
    if green_candles >= 3 and rvol >= 1 and vwap_data[symbol]["cum_vol"] > 1000000:
        return True
    return False

def place_order(symbol, qty, price):
    url = f"{ALPACA_BASE}/v2/orders"
    stop_trail_pct = 5
    take_profit_pct = 15

    buy_order = {
        "symbol": symbol,
        "qty": qty,
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc"
    }
    r = requests.post(url, headers=HEADERS, json=buy_order)
    if r.status_code != 200:
        msg = f"❌ BUY FAILED: {symbol} | {r.status_code}: {r.text}"
        print(msg)
        send_discord_message(msg)
        return

    limit_qty = qty // 2
    limit_price = round(price * (1 + take_profit_pct / 100), 2)
    limit_order = {
        "symbol": symbol,
        "qty": limit_qty,
        "side": "sell",
        "type": "limit",
        "limit_price": limit_price,
        "time_in_force": "gtc"
    }
    requests.post(url, headers=HEADERS, json=limit_order)

    trail_order = {
        "symbol": symbol,
        "qty": qty - limit_qty,
        "side": "sell",
        "type": "trailing_stop",
        "trail_percent": stop_trail_pct,
        "time_in_force": "gtc"
    }
    requests.post(url, headers=HEADERS, json=trail_order)

    msg = (
        f"🚀 BUY {symbol} | Qty: {qty} @ ${price:.2f}\n"
        f"💰 SELL 50% @ +{take_profit_pct}% = ${limit_price}\n"
        f"📉 TRAIL 50% with {stop_trail_pct}% stop"
    )
    print(msg, flush=True)
    send_discord_message(msg)

async def trade_stream():
    print("🚀 Starting trade_stream()", flush=True)
    uri = "wss://socket.polygon.io/stocks"
    async with websockets.connect(uri) as ws:
        print("🟢 Connected to Polygon", flush=True)
        await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
        auth_resp = await ws.recv()
        print("🔐 Auth:", auth_resp, flush=True)

        tickers = [f"AM.{sym}" for sym in WATCHLIST]
        chunk_size = 100
        for i in range(0, len(tickers), chunk_size):
            chunk = ",".join(tickers[i:i + chunk_size])
            await ws.send(json.dumps({"action": "subscribe", "params": chunk}))
            await asyncio.sleep(0.5)

        print("✅ Subscribed to", len(WATCHLIST), "symbols.", flush=True)

        held = set(get_positions())
        print("🎒 Currently holding:", held, flush=True)

        while True:
            try:
                print("⏳ Waiting for WebSocket message at", datetime.now(), flush=True)
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
                print(f"❌ WebSocket Error: {e}", flush=True)
                await asyncio.sleep(1)

if __name__ == "__main__":
    print(f"🚀 Starting bot at {datetime.now()}", flush=True)
    asyncio.run(trade_stream())
