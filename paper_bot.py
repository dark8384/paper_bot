import os
import json
import requests

# 1. Configuration & Constants
LEDGER_FILE = "paper_trades.json"
LEVERAGE = 5.0
FEE_THRESHOLD = 0.0010  # Minimum 0.10% net funding gap to enter

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_ledger(data):
    with open(LEDGER_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_live_market_data():
    """
    Simulating live API data fetch from your tracking matrix stream.
    In real production, this would call ccxt (Binance/Bybit public endpoints).
    """
    # Fallback/Mock Data capturing current volatile candidates
    return [
        {
            "coin": "ESPORTS",
            "binance_price": 0.04004,
            "bybit_price": 0.03996,
            "binance_funding": 0.00259,  # +0.0259%
            "bybit_funding": 0.00050     # +0.0050%
        },
        {
            "coin": "DEEP",
            "binance_price": 0.02793,
            "bybit_price": 0.02803,
            "binance_funding": 0.004498, # +0.4498%
            "bybit_funding": 0.00010     # +0.0010%
        }
    ]

def scan_and_execute():
    positions = load_ledger()
    market_data = fetch_live_market_data()
    
    updated = False

    for market in market_data:
        coin = market["coin"]
        b_price = market["binance_price"]
        by_price = market["bybit_price"]
        b_funding = market["binance_funding"]
        by_funding = market["bybit_funding"]

        # Double entry check - Skip if this coin is already running
        if any(p["coin"] == coin for p in positions):
            continue

        # Calculate Net Funding Spread (Absolute Gap)
        funding_gap = abs(b_funding - by_funding)

        # Execute only if the spread is juicy enough
        if funding_gap >= FEE_THRESHOLD:
            
            # --- CORRECTED ARBITRAGE DIRECTION LOGIC ---
            # Rule: Positive funding means Long pays Short. 
            # We must SHORT the exchange with the HIGHER positive funding rate to RECEIVE the fee.
            
            if b_funding > by_funding:
                # Binance rate is higher -> Short Binance (Receive high fee) / Long Bybit (Pay lower fee)
                execution_plan = "Short Binance / Long Bybit"
                
                # Setup Mathematical SL/TP based on 5x Leverage safety margins
                binance_sl = round(b_price * 1.03, 6)  # Short SL (If price spikes 3%)
                binance_tp = round(b_price * 0.95, 6)  # Short TP (If price drops 5%)
                
                bybit_sl = round(by_price * 0.97, 6)   # Long SL (If price drops 3%)
                bybit_tp = round(by_price * 1.05, 6)   # Long TP (If price spikes 5%)
            else:
                # Bybit rate is higher -> Short Bybit (Receive high fee) / Long Binance (Pay lower fee)
                execution_plan = "Long Binance / Short Bybit"
                
                binance_sl = round(b_price * 0.97, 6)  # Long SL
                binance_tp = round(b_price * 1.05, 6)  # Long TP
                
                bybit_sl = round(by_price * 1.03, 6)   # Short SL
                bybit_tp = round(by_price * 0.95, 6)   # Short TP

            # Constructing the safe simulation log
            trade_log = {
                "coin": coin,
                "leverage_lock": f"{LEVERAGE}x",
                "execution_plan": execution_plan,
                "binance_entry": b_price,
                "bybit_entry": by_price,
                "binance_sl": binance_sl,
                "binance_tp": binance_tp,
                "bybit_sl": bybit_sl,
                "bybit_tp": bybit_tp,
                "initial_funding_gap": f"{round(funding_gap * 100, 4)}%"
            }

            positions.append(trade_log)
            print(f"🔥 Perfect Funding Arbitrage Found for {coin}!")
            print(f"📋 Strategy: {execution_plan} | Gap: {round(funding_gap * 100, 4)}%")
            updated = True

    if updated:
        save_ledger(positions)
        print("✅ Paper trades successfully locked in ledger state.")
    else:
        print("😴 No new directional gaps found or positions already occupied.")

if __name__ == "__main__":
    scan_and_execute()
