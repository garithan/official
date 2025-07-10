import os
import requests
from alpaca_trade_api.rest import REST
import polygon
import time

TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_URL = os.getenv("ALPACA_BASE_URL")
POLYGON_KEY = os.getenv("POLYGON_API_KEY")

alpaca = REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_URL)

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    positions = alpaca.list_positions()
    return [p.symbol for p in positions]

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price):
    try:
        # Buy Market
        alpaca.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="gtc")

        # Limit Sell 50% at +5%
        target_1 = round(price * 1.05, 2)
        alpaca.submit_order(symbol=symbol, qty=int(qty * 0.5), side="sell", type="limit", limit_price=target_1, time_in_force="gtc")

        # Limit Sell 25% at +10%
        target_2 = round(price * 1.10, 2)
        alpaca.submit_order(symbol=symbol, qty=int(qty * 0.25), side="sell", type="limit", limit_price=target_2, time_in_force="gtc")

        # Trailing stop for 25%
        alpaca.submit_order(symbol=symbol, qty=qty - int(qty * 0.75), side="sell", type="trailing_stop", trail_percent=3, time_in_force="gtc")

        # Stop loss for all (use lowest quantity so duplicates don’t cancel)
        stop_price = round(price * 0.92, 2)
        alpaca.submit_order(symbol=symbol, qty=1, side="sell", type="stop", stop_price=stop_price, time_in_force="gtc")

        # Final exit planning (log only)
        send_discord_alert(f"""
✅ Bought {symbol} @ ${price:.2f} (qty: {qty})
🎯 Sell 50% @ ${target_1}
🎯 Sell 25% @ ${target_2}
🟠 Trail stop 25% @ 3%
🛑 Stop loss @ ${stop_price}
🕒 Final sell planned: 3:55PM ET
""")
    except Exception as e:
        print(f"❌ Failed to place orders for {symbol}: {e}")

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Discord error: {e}")

def should_buy(symbol):
    try:
        poly = polygon.rest.StocksClient(api_key=POLYGON_KEY)

        # Get float (shares outstanding - institutional holdings)
        ticker_details = poly.get_ticker_details(symbol)
        float_est = ticker_details.share_class_shares_outstanding or 0
        if float_est > 50000000:
            return False

        # RVOL check
        aggs = poly.get_aggs(symbol, 1, "day", limit=6)
        if len(aggs) < 6:
            return False
        today = aggs[-1]["v"]
        past = sum(a["v"] for a in aggs[:-1]) / 5
        rvol = today / past
        return rvol > 2
    except Exception as e:
        print(f"❌ Failed to fetch data for {symbol}: {e}")
        return False
