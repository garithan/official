
import os
import requests
from collections import deque

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TRADE_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", "2"))
ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_URL = os.getenv("ALPACA_BASE_URL")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

green_candle_history = {}
stock_metadata = {}

def load_watchlist_chunks(chunk_size=400):
    with open("tickers.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

def get_positions():
    try:
        response = requests.get(f"{ALPACA_URL}/v2/positions", headers=HEADERS)
        response.raise_for_status()
        return [pos["symbol"] for pos in response.json()]
    except Exception as e:
        print(f"❌ Failed to fetch positions: {e}")
        return []

def calculate_qty(price):
    capital = 1000 * (TRADE_PERCENT / 100)
    return max(1, int(capital / price))

def place_order(symbol, qty, price, side="buy", order_type="market", time_in_force="day"):
    order = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force
    }
    try:
        res = requests.post(f"{ALPACA_URL}/v2/orders", json=order, headers=HEADERS)
        res.raise_for_status()
        print(f"✅ Order placed: {side.upper()} {symbol} x{qty}")
    except Exception as e:
        print(f"❌ Failed to place {side} order: {e}")

def place_exit_orders(symbol, qty, entry_price):
    try:
        limit_price_1 = round(entry_price * 1.05, 2)
        limit_price_2 = round(entry_price * 1.10, 2)
        stop_loss_price = round(entry_price * 0.92, 2)
        trail_percent = 3

        orders = [
            {"qty": int(qty * 0.50), "type": "limit", "limit_price": limit_price_1},
            {"qty": int(qty * 0.25), "type": "limit", "limit_price": limit_price_2},
            {"qty": int(qty * 0.25), "type": "trailing_stop", "trail_percent": trail_percent},
            {"qty": qty, "type": "stop", "stop_price": stop_loss_price}
        ]

        for order in orders:
            base = {
                "symbol": symbol,
                "side": "sell",
                "time_in_force": "gtc"
            }
            base.update(order)
            res = requests.post(f"{ALPACA_URL}/v2/orders", json=base, headers=HEADERS)
            res.raise_for_status()
            print(f"📤 Exit order placed: {order}")

    except Exception as e:
        print(f"❌ Failed to place exit orders: {e}")

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

def should_buy(symbol, price):
    meta = stock_metadata.get(symbol, {"rvol": 2.5, "float": 30_000_000})
    if meta["rvol"] < 2 or meta["float"] > 50_000_000:
        return False

    history = green_candle_history.setdefault(symbol, deque(maxlen=3))
    history.append(price)

    return len(history) == 3 and history[0] < history[1] < history[2]
