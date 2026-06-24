import os
import json
import random

LEDGER_FILE = "paper_trades.json"
LEVERAGE = 5.0
TRADE_MARGIN_PER_EXCHANGE = 100.0  # $100 Binance + $100 Bybit = $200 total per trade
COINS_TO_SCAN = ["DEEP", "ESPORTS", "POL", "1INCH", "HMSTR", "CATI", "RENDER"]

def load_ledger():
    default_structure = {"wallet": {"balance_usdt": 1000.0, "initial_capital": 1000.0}, "active_positions": [], "closed_trades": []}
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, 'r') as f:
                data = json.load(f)
                if "wallet" not in data or "closed_trades" not in data: return default_structure
                return data
        except Exception:
            return default_structure
    return default_structure

def save_ledger(data):
    with open(LEDGER_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def generate_market_data():
    """Simulates highly dynamic, realistic crypto futures movements & rotating funding rates"""
    market_matrix = []
    base_prices = {
        "DEEP": 0.01931, "ESPORTS": 0.04004, "POL": 0.385, 
        "1INCH": 0.291, "HMSTR": 0.0041, "CATI": 0.421, "RENDER": 7.82
    }
    
    for coin in COINS_TO_SCAN:
        # Realistic price swings (-1.5% to +1.5%) per run
        price_move_b = random.uniform(-0.015, 0.015)
        price_move_by = random.uniform(-0.015, 0.015)
        
        # Rotating funding rates (can flip positive or negative randomly)
        funding_b = random.uniform(-0.003, 0.003)
        funding_by = random.uniform(-0.003, 0.003)
        
        market_matrix.append({
            "coin": coin,
            "binance_price": round(base_prices[coin] * (1 + price_move_b), 5),
            "bybit_price": round(base_prices[coin] * (1 + price_move_by), 5),
            "binance_funding": funding_b,
            "bybit_funding": funding_by
        })
    return market_matrix

def manage_and_scan():
    ledger = load_ledger()
    market_data = generate_market_data()
    updated = True  # Always updates to ensure floating PnL moves
    
    live_market = {m["coin"]: m for m in market_data}
    still_active = []
    
    # --- PHASE 1: EVALUATE LIVE TRADES & BOOK REALISTIC PnL ---
    for pos in ledger["active_positions"]:
        coin = pos["coin"]
        if coin not in live_market:
            still_active.append(pos)
            continue
            
        m = live_market[coin]
        b_current = m["binance_price"]
        by_current = m["bybit_price"]
        
        # Updating live changing funding rates on display
        pos["binance_funding"] = f"{round(m['binance_funding'] * 100, 3)}%"
        pos["bybit_funding"] = f"{round(m['bybit_funding'] * 100, 3)}%"
        
        # PnL Calculation based on position direction with 5x leverage applied
        if "Short Binance" in pos["execution_plan"]:
            b_pnl = (pos["binance_entry"] - b_current) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (by_current - pos["bybit_entry"]) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
        else:
            b_pnl = (b_current - pos["binance_entry"]) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (pos["bybit_entry"] - by_current) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            
        total_pnl = round(b_pnl + by_pnl, 2)
        pos["live_pnl"] = f"${total_pnl}"
        
        # Target Engine: Take Profit at +$8.00 or Stop Loss at -$4.00
        if total_pnl >= 8.0 or total_pnl <= -4.0:
            # Return capital ($200) + add or subtract PnL from Virtual Balance
            returned_funds = (TRADE_MARGIN_PER_EXCHANGE * 2) + total_pnl
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] + returned_funds, 2)
            
            pos["exit_pnl"] = f"${total_pnl}"
            pos["status"] = "🎯 TP Hit" if total_pnl >= 8.0 else "🚨 SL Hit"
            ledger["closed_trades"].append(pos)
            print(f"🔒 Closed {coin}! Result: {pos['status']} | PnL: ${total_pnl}")
        else:
            still_active.append(pos)
            
    ledger["active_positions"] = still_active

    # --- PHASE 2: OPEN NEW ENTRIES IF FUNDS AVAILABLE ---
    active_coins = [p["coin"] for p in ledger["active_positions"]]
    
    for market in market_data:
        coin = market["coin"]
        if coin in active_coins: continue
        
        b_funding = market["binance_funding"]
        by_funding = market["bybit_funding"]
        funding_gap = abs(b_funding - by_funding)
        
        # Entry if spread gap is greater than 0.05%
        if funding_gap >= 0.0005:
            if ledger["wallet"]["balance_usdt"] < (TRADE_MARGIN_PER_EXCHANGE * 2):
                continue  # Skip if dummy funds are insufficient
                
            # Deduct virtual margin
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] - (TRADE_MARGIN_PER_EXCHANGE * 2), 2)
            execution_plan = "Short Binance / Long Bybit" if b_funding > by_funding else "Long Binance / Short Bybit"
            
            trade_log = {
                "coin": coin,
                "execution_plan": execution_plan,
                "used_margin": f"${TRADE_MARGIN_PER_EXCHANGE * 2} USDT",
                "leverage": f"{LEVERAGE}x",
                "total_size": f"${(TRADE_MARGIN_PER_EXCHANGE * 2) * LEVERAGE} USDT", # $1000 Position Size
                "live_pnl": "$0.00",
                "binance_funding": f"{round(b_funding * 100, 3)}%",
                "bybit_funding": f"{round(by_funding * 100, 3)}%",
                "binance_entry": market["binance_price"],
                "bybit_entry": market["bybit_price"],
                "initial_funding_gap": f"{round(funding_gap * 100, 3)}%"
            }
            ledger["active_positions"].append(trade_log)
            print(f"🚀 Opened position for {coin}")
            
    save_ledger(ledger)

if __name__ == "__main__":
    manage_and_scan()
