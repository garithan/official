import asyncio
import json
import websockets
import os
from datetime import datetime
from utils import (
    load_watchlist,
    get_positions,
    calculate_qty,
    place_order,
    should_buy
)
from dotenv import load_dotenv

load_dotenv()
POLYGON_KEY = os.getenv("POLYGON_KEY")

async def send_keepalive(ws):
    while True:
        try:
            await ws.send(json.dumps({"action": "ping"}))
            await asyncio.sleep(15)
        except Exception as e:
            print("⚠️ Keepalive error:", e)
            break

async def subscribe_in_chunks(ws, watchlist, chunk_size=400):
    for i in range(0, len(watchlist), chunk_size):
        chunk = watchlist[i:i + chunk_size]
        sub_string = ",".join([f"AM.{sym}" for sym in chunk])
        await ws.send(json.dumps({"action": "subscribe", "params": sub_string}))
        await asyncio.sleep(0.5)  # avoid overload

async def run_bot():
    uri = "wss://socket.polygon.io/stocks"
    watchlist = load_watchlist()
    print(f"📊 Loaded {len(watchlist)} tickers")

    while True:
        try:
            async with websockets.connect(uri, ping_interval=None, ping_timeout=None) as ws:
                print("🟢 Connected to Polygon WebSocket")

                await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
                auth_response = await ws.recv()
                print("🔐 Auth response:", auth_response)

                await subscribe_in_chunks(ws, watchlist)

                held = set(get_positions())
                print(f"📦 Currently holding: {held}")

                asyncio.create_task(send_keepalive(ws))

                while True:
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        for ev in data:
                            if ev.get("ev") != "AM":
                                continue

                            sym = ev["sym"]
                            price = ev["c"]

                            if should_buy(sym, price) and sym not in held:
                                qty = calculate_qty(price)
                                place_order(sym, qty, price)
                                held.add(sym)
                                print(f"✅ BUY {sym} at ${price:.2f}")

                    except websockets.exceptions.ConnectionClosed:
                        print("🔌 WebSocket disconnected — restarting...")
                        break
                    except Exception as e:
                        print(f"❌ Inner loop error: {e}")
                        await asyncio.sleep(1)

        except Exception as outer_e:
            print(f"🔁 Reconnecting after error: {outer_e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    print(f"🚀 Starting bot at {datetime.now()}")
    asyncio.run(run_bot())
