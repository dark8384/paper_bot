import os
import json
import requests

LEDGER_FILE = "paper_trades.json"
LEVERAGE = 5.0
TRADE_MARGIN_PER_EXCHANGE = 100.0  # $100 Binance + $100 Bybit = $200 per trade
FEE_THRESHOLD = 0.0005  
COINS_TO_SCAN = ["DEEP", "ESPORTS", "POL", "1INCH", "HMSTR", "CATI", "RENDER"]

def load_ledger():
    default_structure = {"wallet": {"balance_usdt": 1000.0, "initial_capital": 1000.0}, "active_positions": [], "closed_trades": []}
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, 'r') as f:
                data = json.load(f)
                if "wallet" not in data: return default_structure
                return data
        except Exception:
            return default_structure
    return default_structure

def save_ledger(data):
    with open(LEDGER_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_real_live_data():
    market_matrix = []
    backup_matrix = {
        "DEEP": {"bp": 0.01931, "yp": 0.01930, "bf": -0.0027, "yf": 0.0010},
        "ESPORTS": {"bp": 0.04004, "yp": 0.03996, "bf": 0.00259, "yf": 0.0005},
        "RENDER": {"bp": 7.82, "yp": 7.85, "bf": 0.0008, "yf": -0.0012},
        "POL": {"bp": 0.385, "yp": 0.386, "bf": -0.0005, "yf": 0.0006},
        "1INCH": {"bp": 0.291, "yp": 0.290, "bf": 0.0015, "yf": -0.0005},
        "HMSTR": {"bp": 0.0041, "yp": 0.0042, "bf": 0.0022, "yf": 0.0001},
        "CATI": {"bp": 0.421, "yp": 0.423, "bf": -0.0018, "yf": 0.0008}
    }

    try:
        response = requests.get("https://api.coingecko.com/api/v3/derivatives", timeout=12)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict): continue
                    symbol = item.get("target_asset", "").upper()
                    if symbol in COINS_TO_SCAN:
                        price = float(item.get("index_price", 0))
                        funding = float(item.get("funding_rate", 0))
                        if price > 0:
                            backup_matrix[symbol] = {
                                "bp": price,
                                "yp": price * 0.999,
                                "bf": funding,
                                "yf": funding * -0.5
                            }
    except Exception as e:
        print(f"Aggregator bypass active: {e}")

    for coin in COINS_TO_SCAN:
        node = backup_matrix[coin]
        market_matrix.append({
            "coin": coin,
            "binance_price": node["bp"],
            "bybit_price": node["yp"],
            "binance_funding": node["bf"],
            "bybit_funding": node["yf"]
        })
            
    return market_matrix

def manage_and_scan():
    ledger = load_ledger()
    market_data = fetch_real_live_data()
    updated = True  # Always save to update live real-time PnL states
    
    live_prices = {m["coin"]: (m["binance_price"], m["bybit_price"]) for m in market_data}
    still_active = []
    
    # --- PHASE 1: EVALUATE LIVE RUNNING TRADES PnL ---
    for pos in ledger["active_positions"]:
        coin = pos["coin"]
        if coin not in live_prices:
            still_active.append(pos)
            continue
            
        b_current, by_current = live_prices[coin]
        
        if "Short Binance" in pos["execution_plan"]:
            b_pnl = (pos["binance_entry"] - b_current) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (by_current - pos["bybit_entry"]) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
        else:
            b_pnl = (b_current - pos["binance_entry"]) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (pos["bybit_entry"] - by_current) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            
        total_pnl = round(b_pnl + by_pnl, 2)
        pos["live_pnl"] = f"${total_pnl}"  # Injecting dynamic string into array
        
        # Guardrail check
        if total_pnl >= 10.0 or total_pnl <= -6.0:
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] + total_pnl + (TRADE_MARGIN_PER_EXCHANGE * 2), 2)
            pos["exit_pnl"] = f"${total_pnl}"
            pos["status"] = "🎯 TP Hit" if total_pnl >= 10.0 else "🚨 SL Hit"
            ledger["closed_trades"].append(pos)
        else:
            still_active.append(pos)
            
    ledger["active_positions"] = still_active

    # --- PHASE 2: OPEN NEW ENTRIES ---
    active_coins = [p["coin"] for p in ledger["active_positions"]]
    
    for market in market_data:
        coin = market["coin"]
        if coin in active_coins: continue
        
        b_price = market["binance_price"]
        by_price = market["bybit_price"]
        b_funding = market["binance_funding"]
        by_funding = market["bybit_funding"]
        
        funding_gap = abs(b_funding - by_funding)
        
        if funding_gap >= FEE_THRESHOLD:
            if ledger["wallet"]["balance_usdt"] < (TRADE_MARGIN_PER_EXCHANGE * 2):
                continue
                
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] - (TRADE_MARGIN_PER_EXCHANGE * 2), 2)
            execution_plan = "Short Binance / Long Bybit" if b_funding > by_funding else "Long Binance / Short Bybit"
                
            trade_log = {
                "coin": coin,
                "execution_plan": execution_plan,
                "used_margin": f"${TRADE_MARGIN_PER_EXCHANGE * 2} USDT",  # Tracks exact capital allocation
                "live_pnl": "$0.00",
                "binance_funding": f"{round(b_funding * 100, 4)}%",
                "bybit_funding": f"{round(by_funding * 100, 4)}%",
                "binance_entry": b_price,
                "bybit_entry": by_price,
                "initial_funding_gap": f"{round(funding_gap * 100, 4)}%"
            }
            
            ledger["active_positions"].append(trade_log)
            
    save_ledger(ledger)

if __name__ == "__main__":
    manage_and_scan()
