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

async def trade_chunk(chunk, chunk_index):
    uri = "wss://socket.polygon.io/stocks"
    held = set(get_positions())
    candles = {}

    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
            print(f"✅ Chunk {chunk_index} connected")

            param_str = ",".join([f"A.{sym}" for sym in chunk])
            await ws.send(json.dumps({"action": "subscribe", "params": param_str}))
            print(f"📡 Chunk {chunk_index} subscribed")

            async def keepalive():
                while True:
                    await ws.send(json.dumps({"action": "ping"}))
                    await asyncio.sleep(20)

            asyncio.create_task(keepalive())

            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    for ev in data:
                        if ev.get("ev") != "A":
                            continue
                        sym = ev["sym"]
                        price = ev["c"]
                        open_price = ev["o"]

                        if sym not in candles:
                            candles[sym] = []

                        # Track green candles
                        candles[sym].append(price > open_price)
                        if len(candles[sym]) > 3:
                            candles[sym].pop(0)

                        # Buy logic
                        if (candles[sym] == [True, True, True] and
                            should_buy(sym) and
                            sym not in held):
                            qty = calculate_qty(price)
                            place_order(sym, qty, price)
                            held.add(sym)
                except Exception as e:
                    print(f"⚠️ Error in chunk {chunk_index}: {e}")
                    await asyncio.sleep(2)
    except Exception as e:
        print(f"❌ Connection failed for chunk {chunk_index}: {e}")
        await asyncio.sleep(5)

async def main():
    chunks = load_watchlist_chunks()
    print(f"🚀 Launching {len(chunks)} WebSocket chunks")
    tasks = [trade_chunk(chunk, i + 1) for i, chunk in enumerate(chunks)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    print(f"🔁 Bot booting at {datetime.now()}")
    asyncio.run(main())
