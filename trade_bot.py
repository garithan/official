import os
import requests
from alpaca_trade_api import REST
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))

alpaca = REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL)

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    return [pos.symbol for pos in alpaca.list_positions()]

def calculate_qty(price):
    account = alpaca.get_account()
    capital = float(account.cash) * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

def place_order(symbol, qty, price):
    try:
        limit_price = round(price * 1.05, 2)
        stop_price = round(price * 0.92, 2)
        trail_percent = 3

        alpaca.submit_order(
            symbol=symbol,
            qty=int(qty * 0.5),
            side='sell',
            type='limit',
            time_in_force='gtc',
            limit_price=limit_price
        )

        alpaca.submit_order(
            symbol=symbol,
            qty=int(qty * 0.5),
            side='sell',
            type='trailing_stop',
            trail_percent=trail_percent,
            time_in_force='gtc'
        )

        alpaca.submit_order(
            symbol=symbol,
            qty=qty,
            side='sell',
            type='stop',
            stop_price=stop_price,
            time_in_force='gtc'
        )

        send_discord_alert(
            f"✅ Bought {symbol} @ ${price:.2f} (qty: {qty})\n"
            f"🎯 Sell 50% @ ${limit_price} (+5%)\n"
            f"🟠 Trail stop 50% @ {trail_percent}%\n"
            f"🛑 Stop loss @ ${stop_price} (-8%)"
        )
        print(f"🛒 Buy confirmed for {symbol}")
    except Exception as e:
        print(f"❌ Order error for {symbol}: {e}")

def should_buy(symbol, price):
    from random import random
    return random() > 0.999  # Placeholder logic
