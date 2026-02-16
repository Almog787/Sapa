import yfinance as yf
import json
import os
from datetime import datetime
import pytz
import pandas as pd
import logging

# --- Paths & Config ---
BASE_DIR = "data_hub"
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
HISTORY_FILE = os.path.join(BASE_DIR, "stock_history.json")
LOG_FILE = os.path.join(BASE_DIR, "error_log.txt")
TZ = pytz.timezone('Israel')
MAX_ROWS = 10000

os.makedirs(BASE_DIR, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format='%(asctime)s: %(message)s')

def main():
    if not os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'w') as f: json.dump({"SPY": 1}, f)
    
    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    tickers = list(holdings.keys())
    if "SPY" not in tickers: tickers.append("SPY")

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f: history = json.load(f)
    else:
        history = []

    # Backfill logic
    if not history:
        print("Backfilling...")
        df = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']
        df = df.ffill().bfill()
        for dt, row in df.iterrows():
            history.append({
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "prices": {t: round(float(v), 2) for t, v in row.to_dict().items() if pd.notna(v)}
            })

    # Live sample
    try:
        live = yf.download(tickers, period="1d", interval="1m", progress=False)['Close']
        if not live.empty:
            last = live.iloc[-1]
            ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            if not history or history[-1]['timestamp'][:16] != ts[:16]:
                history.append({
                    "timestamp": ts,
                    "prices": {t: round(float(v), 2) for t, v in last.to_dict().items() if pd.notna(v)}
                })
    except Exception as e:
        logging.error(f"Sampling failed: {e}")

    history = sorted(history, key=lambda x: x['timestamp'])[-MAX_ROWS:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)

if __name__ == "__main__":
    main()
