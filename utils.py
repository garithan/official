import os
import random
import requests

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")
ALPACA_KEY_ID = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

import alpaca_trade_api as tradeapi

ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

alpaca = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL)

def get_positions():
    try:
        positions = alpaca.list_positions()
        return {pos.symbol: float(pos.avg_entry_price) for pos in positions}
    except Exception as e:
        print(f"⚠️ Failed to fetch positions: {e}")
        return {}

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price):
    order = {
        "symbol": symbol,
        "qty": qty,
        "side": "buy",
        "type": "market",
        "time_in_force": "day"
    }
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY_ID,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    try:
        resp = requests.post(f"{ALPACA_BASE_URL}/v2/orders", json=order, headers=headers)
        if resp.status_code in [200, 201]:
            msg = f"✅ Placed order: {symbol} x{qty} @ ~${price:.2f}"
            print(msg)
            send_discord_alert(msg)
        else:
            msg = f"❌ Order failed for {symbol} x{qty}: {resp.status_code} {resp.text}"
            print(msg)
            send_discord_alert(msg)
    except Exception as e:
        print(f"❌ Alpaca order error: {e}")
        send_discord_alert(f"❌ Alpaca order error for {symbol}: {e}")

def should_buy(symbol, price):
    # Replace this logic with actual indicator checks later
    return random.random() > 0.999

def send_discord_alert(message):
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": message})
        except Exception as e:
            print(f"⚠️ Discord alert failed: {e}")
