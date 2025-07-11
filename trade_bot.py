
import asyncio
import json
import websockets
import os
from datetime import datetime
from dotenv import load_dotenv
from utils import (
    should_buy,
    should_sell,
    calculate_qty,
    place_order,
    record_position,
    update_high,
    get_qty_held,
    remove_position,
    get_positions,
    send_discord_alert
)

load_dotenv()

POLYGON_KEY = os.getenv("POLYGON_API_KEY")
POSITIONS = set(get_positions())

async def handle_ticker_data(ev):
    symbol = ev["sym"]
    price = ev["c"]

    if should_buy(symbol, price) and symbol not in POSITIONS:
        qty = calculate_qty(price)
        place_order(symbol, qty, price)
        record_position(symbol, price, qty)
        POSITIONS.add(symbol)
        send_discord_alert(f"🟢 Bought {symbol} @ ${price:.2f} (qty: {qty})")

    elif symbol in POSITIONS:
        update_high(symbol, price)
        if should_sell(symbol, price):
            qty = get_qty_held(symbol)
            place_order(symbol, -qty, price)
            remove_position(symbol)
            POSITIONS.remove(symbol)
            send_discord_alert(f"💰 Sold {symbol} @ ${price:.2f} (qty: {qty})")

async def stream_polygon_data(tickers):
    uri = f"wss://socket.polygon.io/stocks"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action": "auth", "params": POLYGON_KEY}))
        auth_resp = await ws.recv()
        print(f"✅ Auth response: {auth_resp}")

        subs = ",".join([f"A.{t}" for t in tickers])
        await ws.send(json.dumps({"action": "subscribe", "params": subs}))
        print(f"📡 Subscribed to {len(tickers)} tickers")

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                for ev in data:
                    if ev.get("ev") == "A":
                        await handle_ticker_data(ev)
            except Exception as e:
                print(f"⚠️ Error: {e}")
                await asyncio.sleep(5)

async def main():
    with open("tickers.txt", "r") as f:
        tickers = [line.strip() for line in f.readlines() if line.strip()]
    await stream_polygon_data(tickers)

if __name__ == "__main__":
    print(f"🔁 Bot started at {datetime.now()}")
    asyncio.run(main())
