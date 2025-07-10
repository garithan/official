import asyncio
import json
import websockets
import os
from datetime import datetime
from utils import (
    load_watchlist_chunks,
    get_positions,
    calculate_qty,
    place_order,
    should_buy,
    send_discord_alert
)
from dotenv import load_dotenv

load_dotenv()
POLYGON_KEY = os.getenv("POLYGON_API_KEY")

async def trade_stream():
    uri = "wss://socket.polygon.io/stocks"
    all_chunks = load_watchlist_chunks()
    print(f"🔢 Loaded {sum(len(c) for c in all_chunks)} total tickers across {len(all_chunks)} chunks")

    held = set(get_positions())
    print(f"📦 Already holding: {held}")

    for chunk_index, chunk in enumerate(all_chunks):
        print(f"🔁 Starting chunk {chunk_index + 1}/{len(all_chunks)}")
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
                auth_msg = await ws.recv()
                print(f"🔐 Auth response: {auth_msg}")

                param_str = ",".join([f"A.{sym}" for sym in chunk])
                await ws.send(json.dumps({"action": "subscribe", "params": param_str}))
                print(f"📡 Subscribed to {len(chunk)} tickers")

                async def keepalive():
                    while True:
                        await ws.send(json.dumps({"action": "ping"}))
                        await asyncio.sleep(20)

                asyncio.create_task(keepalive())

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    for ev in data:
                        if ev.get("ev") != "A":
                            continue
                        symbol = ev["sym"]
                        price = ev["c"]
                        if should_buy(symbol, price) and symbol not in held:
                            qty = calculate_qty(price)
                            place_order(symbol, qty, price)
                            held.add(symbol)
                            send_discord_alert(f"✅ Bought {symbol} x{qty} @ ${price:.2f}")
        except Exception as e:
            print(f"❌ Error in chunk {chunk_index + 1}: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    print(f"🚀 Bot started at {datetime.now()}")
    asyncio.run(trade_stream())
