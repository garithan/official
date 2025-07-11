import os
import asyncio
from datetime import datetime, time
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TrailingStopOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from dotenv import load_dotenv
from utils import (
    should_buy, calculate_qty, send_discord_alert, get_positions
)

load_dotenv()

API_KEY = os.getenv("ALPACA_KEY_ID")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))

client = TradingClient(API_KEY, API_SECRET, paper=True)
positions = get_positions()

# Load and limit tickers
MAX_TICKERS = 150  # Adjust based on your Alpaca plan
with open("tickers.txt", "r") as f:
    tickers = [line.strip() for line in f.readlines() if line.strip()][:MAX_TICKERS]

stream = StockDataStream(API_KEY, API_SECRET)

async def handle_trade(data):
    symbol = data.symbol
    price = data.price

    if symbol in positions:
        return

    if not should_buy(symbol, price):
        return

    qty = calculate_qty(price)
    try:
        # Place limit buy
        limit_price = round(price * 1.01, 2)
        order = client.submit_order(
            order_data=LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price
            )
        )

        positions.add(symbol)

        await asyncio.sleep(3)

        client.submit_order(
            order_data=LimitOrderRequest(
                symbol=symbol,
                qty=int(qty * 0.4),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=round(price * 1.05, 2)
            )
        )

        client.submit_order(
            order_data=TrailingStopOrderRequest(
                symbol=symbol,
                qty=int(qty * 0.6),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                trail_percent=3.0
            )
        )

        async def sell_at_eod():
            while True:
                now = datetime.now()
                if time(15, 55) <= now.time() <= time(15, 56):
                    client.close_position(symbol)
                    break
                await asyncio.sleep(30)
        asyncio.create_task(sell_at_eod())

        send_discord_alert(f"""
Bought {symbol} @ ${price:.2f} (qty: {qty})
Sell 40% @ +5%
Trail stop 60% @ 3%
Final sell: 3:55PM closeout
""")

    except Exception as e:
        print(f"Error placing orders for {symbol}: {e}")

async def main():
    for symbol in tickers:
        stream.subscribe_trades(handle_trade, symbol)
        await asyncio.sleep(0.05)  # Delay to avoid flooding connection
    await stream._run_forever()

if __name__ == "__main__":
    asyncio.run(main())
