import os
import sys
import json
import requests
from bs4 import BeautifulSoup

# ==========================================
# 🛑 TRADING CONFIGURATION & SAFETY PARAMETERS
# ==========================================
LEVERAGE = 5.0                # Strict 5x Leverage Lock
MIN_NET_PROFIT_PCT = 0.04    # Minimum 0.04% Net Profit after Spread
MAX_SPREAD_PCT = 0.40        # Don't enter if spread is too high
MIN_FUNDING_GAP = 0.05       # Minimum acceptable funding gap
SL_PCT_FROM_ENTRY = 0.03     # Safe Price-Based SL at 3% (Way before 5x Liq at ~20%)
TP_PCT_FROM_ENTRY = 0.015    # Target 1.5% price move or spread normalization

DATA_URL = "https://dark8384.github.io/crypto-arbitrage-bot/"
LOG_FILE = "paper_trades.json"

def fetch_live_dashboard_data():
    """Parses live matrix dashboard to find optimized safe pairs like ESPORTS"""
    try:
        response = requests.get(DATA_URL, timeout=10)
        if response.status_code != 200:
            print("❌ Unable to fetch data from live dashboard.")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # In a real setup, this parses the JSON stream or table structure from the dashboard
        # Simulating parsed safe data extracted live from image_fe15a5.png stream
        opportunities = [
            {
                "coin": "ESPORTS",
                "binance_price": 0.034874,
                "bybit_price": 0.034880,
                "binance_fund": 0.2392,
                "bybit_fund": 0.0050,
                "gap": 0.2342,
                "spread": 0.0178,
                "est_net_profit": 0.2164,
                "execution_plan": "Long Binance / Short Bybit",
                "status": "SAFE"
            },
            {
                "coin": "DEEP",
                "binance_price": 0.027930,
                "bybit_price": 0.028030,
                "binance_fund": 0.0050,
                "bybit_fund": -0.4448,
                "gap": 0.4498,
                "spread": 0.3574,
                "est_net_profit": 0.0924,
                "execution_plan": "Long Binance / Short Bybit",
                "status": "SAFE"
            }
        ]
        return opportunities
    except Exception as e:
        print(f"Error fetching dashboard metrics: {e}")
        return []

def check_active_positions_and_safety():
    """Tracks current active positions and handles auto-kill switches (SL/TP/Funding Flip)"""
    if not os.path.exists(LOG_FILE):
        return
        
    with open(LOG_FILE, 'r') as f:
        positions = json.load(f)
        
    if not positions:
        return

    print("🔍 Scanning active legs for Funding Flips and Price-Based Stop-Losses...")
    updated_positions = []
    
    # Simulating a live price tick check from the dashboard stream
    live_opportunities = fetch_live_dashboard_data()
    live_dict = {op["coin"]: op for op in live_opportunities}

    for pos in positions:
        coin = pos["coin"]
        if coin in live_dict:
            current_metrics = live_dict[coin]
            
            # 🛑 CRITICAL SAFETY: FUNDING FLIP AUTO-EXIT DETECTOR
            # If the funding gap goes negative or flips direction against our active legs
            if pos["execution_plan"] == "Long Binance / Short Bybit" and current_metrics["binance_fund"] < current_metrics["bybit_fund"]:
                print(f"🚨 ALERT: Funding Rate flipped against active position on {coin}! Executing emergency auto-exit.")
                execute_hedge_close(pos, reason="Funding Rate Flip Protection")
                continue
                
            if pos["execution_plan"] == "Short Binance / Long Bybit" and current_metrics["bybit_fund"] < current_metrics["binance_fund"]:
                print(f"🚨 ALERT: Funding Rate flipped against active position on {coin}! Executing emergency auto-exit.")
                execute_hedge_close(pos, reason="Funding Rate Flip Protection")
                continue

            # 🛡️ PRICE-BASED STOP-LOSS & TAKE-PROFIT TRACKING
            # Simulating microsecond execution simulation based on price ticks
            simulated_current_price = current_metrics["binance_price"]
            
            if pos["execution_plan"] == "Long Binance / Short Bybit":
                # Long leg SL check
                if simulated_current_price <= pos["binance_sl"]:
                    print(f"🛑 Stop-Loss triggered on Binance for {coin}! Closing both positions instantly.")
                    execute_hedge_close(pos, reason="Price Stop-Loss Hit")
                    continue
                # Short leg SL check (If price spikes up)
                elif current_metrics["bybit_price"] >= pos["bybit_sl"]:
                    print(f"🛑 Stop-Loss triggered on Bybit for {coin}! Closing both positions instantly.")
                    execute_hedge_close(pos, reason="Price Stop-Loss Hit")
                    continue
                # Take-Profit Check
                elif simulated_current_price >= pos["binance_tp"]:
                    print(f"🎯 Target Profit reached for {coin}! Locking in gains.")
                    execute_hedge_close(pos, reason="Take Profit Target Hit")
                    continue
                    
            updated_positions.append(pos)
            
    with open(LOG_FILE, 'w') as f:
        json.dump(updated_positions, f, indent=4)

def execute_hedge_close(position, reason):
    print(f"🔒 [CLOSED] Both exchanges cleared for {position['coin']}. Reason: {reason}")

def scan_and_execute_trades():
    """Scans for high net-profit, low-spread entries matching 5x parameters"""
    opportunities = fetch_live_dashboard_data()
    
    for op in opportunities:
        if op["status"] == "SAFE" and op["est_net_profit"] >= MIN_NET_PROFIT_PCT and op["spread"] <= MAX_SPREAD_PCT:
            print(f"\n💎 Perfect Candidate Found: {op['coin']}")
            print(f"📊 Net Profit Potential: +{op['est_net_profit']}% | Current Spread: {op['spread']}%")
            
            # Calculate automatic price-based targets based on entry values
            b_price = op["binance_price"]
            by_price = op["bybit_price"]
            
            if op["execution_plan"] == "Long Binance / Short Bybit":
                b_sl = b_price * (1.0 - SL_PCT_FROM_ENTRY)
                b_tp = b_price * (1.0 + TP_PCT_FROM_ENTRY)
                by_sl = by_price * (1.0 + SL_PCT_FROM_ENTRY)
                by_tp = by_price * (1.0 - TP_PCT_FROM_ENTRY)
            else:
                b_sl = b_price * (1.0 + SL_PCT_FROM_ENTRY)
                b_tp = b_price * (1.0 - TP_PCT_FROM_ENTRY)
                by_sl = by_price * (1.0 - SL_PCT_FROM_ENTRY)
                by_tp = by_price * (1.0 + TP_PCT_FROM_ENTRY)

            trade_log = {
                "coin": op["coin"],
                "leverage_lock": f"{LEVERAGE}x",
                "execution_plan": op["execution_plan"],
                "binance_entry": b_price,
                "bybit_entry": by_price,
                "binance_sl": round(b_sl, 6),
                "binance_tp": round(b_tp, 6),
                "bybit_sl": round(by_sl, 6),
                "bybit_tp": round(by_tp, 6),
                "initial_funding_gap": f"{op['gap']}%"
            }
            
            print(f"🚀 Initializing Position with locked {LEVERAGE}x Leverage...")
            print(f"🔒 Binance SL: {trade_log['binance_sl']} | Bybit SL: {trade_log['bybit_sl']}")
            
            # Save transaction state to log file
            positions = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as f:
                    try: positions = json.load(f)
                    except: positions = []
            
            # Prevent double entry
            if not any(p["coin"] == op["coin"] for p in positions):
                positions.append(trade_log)
                with open(LOG_FILE, 'w') as f:
                    json.dump(positions, f, indent=4)
                print(f"✅ Successfully hedged trade logged in {LOG_FILE}.")

if __name__ == "__main__":
    check_active_positions_and_safety()
    scan_and_execute_trades()
