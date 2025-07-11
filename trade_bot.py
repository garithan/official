
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
    send_discord_alert,
    should_buy,
    should_sell,
    record_position,
    get_qty_held,
    remove_position,
    update_high
)
from dotenv import load_dotenv

load_dotenv()
POLYGON_KEY = os.getenv("POLYGON_API_KEY")

async def trade_chunk(chunk, chunk_index):
    uri = "wss://socket.polygon.io/stocks"
    held = set(get_positions())

    try:
        async with websockets.connect(uri, ping_interval=30, ping_timeout=30) as ws:
            await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
            auth_resp = await ws.recv()
            print(f"✅ Chunk {chunk_index} auth: {auth_resp}")

            param_str = ",".join([f"A.{sym}" for sym in chunk])
            await ws.send(json.dumps({"action": "subscribe", "params": param_str}))
            print(f"📡 Chunk {chunk_index} subscribed to {len(chunk)} tickers")

            # Listen for incoming messages
            while True:
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                    for ev in data:
                        if ev.get("ev") != "A":
                            continue
                        symbol = ev["sym"]
                        price = ev["c"]

                        if should_buy(symbol, price) and symbol not in held:
                            qty = calculate_qty(price)
                            place_order(symbol, qty, price)
                            record_position(symbol, price, qty)
                            held.add(symbol)
                            send_discord_alert(f"🟢 Bought {symbol} @ ${price:.2f} (qty: {qty})")

                        elif symbol in held:
                            update_high(symbol, price)
                            if should_sell(symbol, price):
                                qty = get_qty_held(symbol)
                                place_order(symbol, -qty, price)
                                remove_position(symbol)
                                held.remove(symbol)
                                send_discord_alert(f"💰 Sold {symbol} @ ${price:.2f} (qty: {qty})")

                except Exception as e:
                    print(f"⚠️ Chunk {chunk_index} error: {e}")
                    await asyncio.sleep(2)

    except Exception as e:
        print(f"❌ Connection failed for chunk {chunk_index}: {e}")
        await asyncio.sleep(5)

async def main():
    chunks = load_watchlist_chunks(chunk_size=75)  # limit to avoid 1008 error
    print(f"🚀 Starting {len(chunks)} WebSocket connections")

    tasks = [trade_chunk(chunk, i + 1) for i, chunk in enumerate(chunks)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    print(f"🔁 Bot booting at {datetime.now()}")
    asyncio.run(main())
