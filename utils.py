import os
import random
import json

def load_watchlist():
    with open("tickers.txt", "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def get_positions():
    # Replace with real broker positions (e.g. Alpaca API)
    return []

def calculate_qty(price, capital=1000):
    return max(1, int(capital / price))

def place_order(symbol, qty, price):
    print(f"🛒 Placing order: {symbol} x {qty} @ ${price:.2f}")

def should_buy(symbol):
    # Replace with actual logic
    return random.random() > 0.99
