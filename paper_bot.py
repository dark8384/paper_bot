import os
import json
import requests

LEDGER_FILE = "paper_trades.json"
LEVERAGE = 5.0
TRADE_MARGIN_PER_EXCHANGE = 100.0  # Har trade me $100 Binance + $100 Bybit lagega
FEE_THRESHOLD = 0.0005  # Minimum 0.05% net funding gap to qualify for live test
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
    """
    Fetches 100% real-time spot/perpetual prices and live funding rates directly from exchange public APIs.
    """
    market_matrix = []
    
    # 1. Fetch Binance Live Data
    binance_prices = {}
    binance_funding = {}
    try:
        b_p_res = requests.get("https://fapi.binance.com/fapi/v1/ticker/price", timeout=10).json()
        for item in b_p_res:
            symbol = item['symbol']
            if symbol.endswith("USDT"):
                binance_prices[symbol.replace("USDT", "")] = float(item['price'])
                
        b_f_res = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=10).json()
        for item in b_f_res:
            symbol = item['symbol']
            if symbol.endswith("USDT"):
                binance_funding[symbol.replace("USDT", "")] = float(item['lastFundingRate'])
    except Exception as e:
        print(f"Binance Live Stream Error: {e}")

    # 2. Fetch Bybit Live Data
    bybit_prices = {}
    bybit_funding = {}
    try:
        by_res = requests.get("https://api.bybit.com/v5/market/tickers?category=linear", timeout=10).json()
        if by_res.get("retCode") == 0:
            for item in by_res['result']['list']:
                symbol = item['symbol']
                if symbol.endswith("USDT"):
                    coin = symbol.replace("USDT", "")
                    bybit_prices[coin] = float(item['lastPrice'])
                    bybit_funding[coin] = float(item['fundingRate'])
    except Exception as e:
        print(f"Bybit Live Stream Error: {e}")

    # 3. Consolidate Matrix
    for coin in COINS_TO_SCAN:
        if coin in binance_prices and coin in bybit_prices and coin in binance_funding and coin in bybit_funding:
            market_matrix.append({
                "coin": coin,
                "binance_price": binance_prices[coin],
                "bybit_price": bybit_prices[coin],
                "binance_funding": binance_funding[coin],
                "bybit_funding": bybit_funding[coin]
            })
            
    return market_matrix

def manage_and_scan():
    ledger = load_ledger()
    market_data = fetch_real_live_data()
    
    updated = False
    
    # --- PHASE 1: UPDATE LIVE PnL & MONITOR TP/SL CLOSURES ---
    live_prices = {m["coin"]: (m["binance_price"], m["bybit_price"]) for m in market_data}
    still_active = []
    
    for pos in ledger["active_positions"]:
        coin = pos["coin"]
        if coin not in live_prices:
            still_active.append(pos)
            continue
            
        b_current, by_current = live_prices[coin]
        
        # Calculate individual leg returns based on plan direction
        if "Short Binance" in pos["execution_plan"]:
            b_pnl = (pos["binance_entry"] - b_current) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (by_current - pos["bybit_entry"]) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
        else:
            b_pnl = (b_current - pos["binance_entry"]) / pos["binance_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            by_pnl = (pos["bybit_entry"] - by_current) / pos["bybit_entry"] * TRADE_MARGIN_PER_EXCHANGE * LEVERAGE
            
        total_pnl = round(b_pnl + by_pnl, 2)
        
        # Check Stop-Loss or Take-Profit Triggers (Combined Leg Guardrail)
        if total_pnl >= 10.0 or total_pnl <= -6.0:  # TP at +$10, SL at -$6
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] + total_pnl, 2)
            pos["exit_pnl"] = f"${total_pnl}"
            pos["status"] = "🎯 TP Hit" if total_pnl >= 10.0 else "🚨 SL Hit"
            ledger["closed_trades"].append(pos)
            updated = True
            print(f"🔒 Position Closed for {coin}! PnL: ${total_pnl}")
        else:
            still_active.append(pos)
            
    ledger["active_positions"] = still_active

    # --- PHASE 2: SCAN FOR NEW REAL-TIME ENTRIES ---
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
            # Check wallet limits
            if ledger["wallet"]["balance_usdt"] < (TRADE_MARGIN_PER_EXCHANGE * 2):
                print("⚠️ Virtual Funds low! Skipping new opportunity.")
                break
                
            # Allocate Margin
            ledger["wallet"]["balance_usdt"] = round(ledger["wallet"]["balance_usdt"] - (TRADE_MARGIN_PER_EXCHANGE * 2), 2)
            
            if b_funding > by_funding:
                execution_plan = "Short Binance / Long Bybit"
            else:
                execution_plan = "Long Binance / Short Bybit"
                
            trade_log = {
                "coin": coin,
                "execution_plan": execution_plan,
                "binance_funding": f"{round(b_funding * 100, 4)}%",
                "bybit_funding": f"{round(by_funding * 100, 4)}%",
                "binance_entry": b_price,
                "bybit_entry": by_price,
                "initial_funding_gap": f"{round(funding_gap * 100, 4)}%"
            }
            
            ledger["active_positions"].append(trade_log)
            print(f"🚀 Real Live Trade Entered! {coin} | Gap: {round(funding_gap * 100, 4)}%")
            updated = True
            
    if updated:
        save_ledger(ledger)

if __name__ == "__main__":
    manage_and_scan()
