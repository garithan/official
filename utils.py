import os
import random
import requests
import alpaca_trade_api as tradeapi

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL)

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    positions = api.list_positions()
    return [p.symbol for p in positions]

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price):
    try:
        qty_50 = int(qty * 0.5)
        qty_25 = int(qty * 0.25)
        qty_trail = qty - qty_50 - qty_25

        if qty_50 > 0:
            api.submit_order(
                symbol=symbol,
                qty=qty_50,
                side='sell',
                type='limit',
                time_in_force='day',
                limit_price=round(price * 1.05, 2)
            )

        if qty_25 > 0:
            api.submit_order(
                symbol=symbol,
                qty=qty_25,
                side='sell',
                type='limit',
                time_in_force='day',
                limit_price=round(price * 1.10, 2)
            )

        if qty_trail > 0:
            api.submit_order(
                symbol=symbol,
                qty=qty_trail,
                side='sell',
                type='trailing_stop',
                trail_percent=3,
                time_in_force='gtc'
            )
    except Exception as e:
        print(f"❌ Sell order failed for {symbol}: {e}")

def should_buy(symbol, price):
    return random.random() > 0.999

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")
