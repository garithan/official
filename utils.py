import os
import random
import requests

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    return []

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price, sym):
    print(f"🛒 Placing order: {symbol} x {qty} @ ${price:.2f}")
    send_discord_alert(f"""
✅ Bought {symbol} @ ${price:.2f} (qty: {qty})
🎯 Sell 50% @ +5%
🎯 Sell 25% @ +10%
🟠 Trail stop 25% @ 3%
🕒 Final sell: 3:55PM closeout
🛑 Stop loss @ -8%
""")

def should_buy(symbol, price):
    return random.random() > 0.999

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")
