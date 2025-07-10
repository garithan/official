import asyncio
import json
import os
import websockets
from datetime import datetime
from dotenv import load_dotenv
from utils import load_watchlist, get_positions, calculate_qty, place_order, should_buy

load_dotenv()
POLYGON_KEY = os.getenv("POLYGON_KEY")

async def subscribe_to_tickers(ws, tickers, chunk_size=400):
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        param_str = ",".join([f"A.{sym}" for sym in chunk])
        await ws.send(json.dumps({"action": "subscribe", "params": param_str}))
        await asyncio.sleep(1.0)

async def send_keepalive(ws):
    while True:
        try:
            await ws.ping()
            await asyncio.sleep(15)
        except Exception:
            break

async def trade_stream():
    uri = "wss://socket.polygon.io/stocks"
    tickers = load_watchlist()
    print(f"📄 Loaded {len(tickers)} tickers")

    async with websockets.connect(uri, ping_interval=None) as ws:
        print("🟢 Connected to Polygon")
        await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
        print("🔐 Auth sent")

        await subscribe_to_tickers(ws, tickers)

        held = set(get_positions())
        print(f"📦 Already holding: {held}")

        asyncio.create_task(send_keepalive(ws))

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                for ev in data:
                    if ev.get("ev") != "A":
                        continue
                    symbol = ev["sym"]
                    price = ev["c"]
                    if should_buy(symbol) and symbol not in held:
                        qty = calculate_qty(price)
                        place_order(symbol, qty, price)
                        held.add(symbol)
            except Exception as e:
                print(f"❌ WebSocket Error: {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    print(f"🚀 Starting bot at {datetime.now()}")
    asyncio.run(trade_stream())
