import os
import random
import requests
import json
from alpaca_trade_api.rest import REST

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
api = REST(ALPACA_KEY, ALPACA_SECRET, BASE_URL)

POSITIONS_FILE = "positions.json"

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    try:
        with open(POSITIONS_FILE, "r") as f:
            return list(json.load(f).keys())
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
            side="buy",
            type="market",
            time_in_force="gtc"
        )
        message = (
            f"✅ Bought {symbol} @ ${price:.2f} (qty: {qty})\n"
            "🎯 Sell 50% @ +5%\n"
            "🎯 Sell 25% @ +10%\n"
            "🟠 Trail stop 25% @ 3%\n"
            "🕒 Final sell: 3:55PM closeout\n"
            "🛑 Stop loss @ -8%"
        )
        send_discord_alert(message)
    except Exception as e:
        print(f"❌ Failed to place buy order: {e}")

def record_position(symbol, price, qty):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}
    data[symbol] = {"price": price, "qty": qty}
    with open(POSITIONS_FILE, "w") as f:
        json.dump(data, f)

def should_buy(symbol, price):
    return random.random() > 0.999  # Replace with your logic

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")


def get_qty_held(symbol):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
        return data[symbol]["qty"]
    except:
        return 0

def remove_position(symbol):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
        if symbol in data:
            del data[symbol]
        with open(POSITIONS_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def record_position(symbol, price, qty):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}
    data[symbol] = {"price": price, "qty": qty, "high": price}
    with open(POSITIONS_FILE, "w") as f:
        json.dump(data, f)

def update_high(symbol, new_price):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
        if symbol in data and new_price > data[symbol]["high"]:
            data[symbol]["high"] = new_price
            with open(POSITIONS_FILE, "w") as f:
                json.dump(data, f)
    except:
        pass

def should_sell(symbol, price):
    try:
        with open(POSITIONS_FILE, "r") as f:
            data = json.load(f)
        entry = data.get(symbol)
        if not entry:
            return False
        entry_price = entry["price"]
        high = entry["high"]
        change = (price - entry_price) / entry_price

        # Hard stop loss at -8%
        if change <= -0.08:
            send_discord_alert(f"🔻 STOP LOSS: {symbol} dropped {change:.2%}")
            return True

        # Trailing stop: if price drops 3% from the high
        if high and (price < high * 0.97):
            send_discord_alert(f"🔁 TRAILING STOP: {symbol} dropped from high ${high:.2f} to ${price:.2f}")
            return True

        return False
    except:
        return False
