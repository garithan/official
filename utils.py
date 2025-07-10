import os
import random
import requests
import alpaca_trade_api as tradeapi

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
ALPACA_KEY_ID = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")

api = tradeapi.REST(ALPACA_KEY_ID, ALPACA_SECRET_KEY, ALPACA_BASE_URL)

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    try:
        return [pos.symbol for pos in api.list_positions()]
    except:
        return []

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price):
    try:
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='market',
            time_in_force='gtc'
        )

        take_profit_1 = price * 1.05
        take_profit_2 = price * 1.10
        stop_loss = price * 0.92

        api.submit_order(
            symbol=symbol,
            qty=int(qty * 0.5),
            side='sell',
            type='limit',
            time_in_force='gtc',
            limit_price=round(take_profit_1, 2)
        )

        api.submit_order(
            symbol=symbol,
            qty=int(qty * 0.25),
            side='sell',
            type='limit',
            time_in_force='gtc',
            limit_price=round(take_profit_2, 2)
        )

        api.submit_order(
            symbol=symbol,
            qty=int(qty * 0.25),
            side='sell',
            type='trailing_stop',
            time_in_force='gtc',
            trail_percent=3
        )

        api.submit_order(
            symbol=symbol,
            qty=qty,
            side='sell',
            type='stop',
            stop_price=round(stop_loss, 2),
            time_in_force='gtc'
        )

    except Exception as e:
        print(f"❌ Alpaca order failed: {e}")

def should_buy(symbol, price):
    return random.random() > 0.999

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")
