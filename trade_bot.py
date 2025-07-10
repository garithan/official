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

    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
            auth_resp = await ws.recv()
            print(f"✅ Chunk {chunk_index} auth: {auth_resp}")

            param_str = ",".join([f"A.{sym}" for sym in chunk])
            await ws.send(json.dumps({"action": "subscribe", "params": param_str}))
            print(f"📡 Chunk {chunk_index} subscribed to {len(chunk)} tickers")

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
                        symbol = ev["sym"]
                        price = ev["c"]
                        if should_buy(symbol, price) and symbol not in held:
                            qty = calculate_qty(price)
                            place_order(symbol, qty, price)
                            held.add(symbol)
                            notify = (
                                f"✅ Bought {symbol} @ ${price:.2f} (qty: {qty})\n"
                                f"🎯 Sell 50% @ ${price * 1.05:.2f} (+5%)\n"
                                f"🎯 Sell 25% @ ${price * 1.10:.2f} (+10%)\n"
                                f"🟠 Trail stop 25% @ 3%\n"
                                f"🛑 Stop loss @ ${price * 0.92:.2f} (-8%)\n"
                                f"🕒 Sell remainder 5 min before close\n"
                                f"📅 Executed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            send_discord_alert(notify)
                except Exception as e:
                    print(f"⚠️ Chunk {chunk_index} error: {e}")
                    await asyncio.sleep(2)
    except Exception as e:
        print(f"❌ Connection failed for chunk {chunk_index}: {e}")
        await asyncio.sleep(5)

async def main():
    chunks = load_watchlist_chunks()
    print(f"🚀 Starting {len(chunks)} WebSocket connections")

    tasks = [
        trade_chunk(chunk, i + 1)
        for i, chunk in enumerate(chunks)
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    print(f"🔁 Bot booting at {datetime.now()}")
    asyncio.run(main())
