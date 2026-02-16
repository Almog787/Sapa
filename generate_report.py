import json
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import pytz
import os
import shutil

# --- Paths ---
DATA_DIR = "data_hub"
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
HISTORY_FILE = os.path.join(DATA_DIR, "stock_history.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
CHART_FILE = os.path.join(DATA_DIR, "performance.png")
PIE_FILE = os.path.join(DATA_DIR, "allocation.png")
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_old():
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M")
    for f in [CHART_FILE, PIE_FILE]:
        if os.path.exists(f):
            shutil.move(f, os.path.join(ARCHIVE_DIR, f"{ts}_{os.path.basename(f)}"))

def main():
    if not os.path.exists(HISTORY_FILE): return
    archive_old()
    
    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts'])
    df = df.sort_values('ts')
    
    tickers = list(holdings.keys())
    df['total_usd'] = df.apply(lambda r: sum(r[t]*holdings[t] for t in tickers if t in r), axis=1)
    
    # Visuals
    plt.switch_backend('Agg')
    plt.figure(figsize=(10, 5))
    plt.plot(df['ts'], (df['total_usd']/df['total_usd'].iloc[0]-1)*100, color='#007bff', linewidth=2)
    plt.title('Portfolio Growth (%)', fontsize=14)
    plt.grid(True, alpha=0.2)
    plt.savefig(CHART_FILE)
    
    plt.figure(figsize=(6, 6))
    last_vals = [df['total_usd'].iloc[-1]] # simplistic for pie
    plt.pie([df.iloc[-1][t]*holdings[t] for t in tickers], labels=tickers, autopct='%1.1f%%')
    plt.savefig(PIE_FILE)

    # README Update
    rate = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    curr_usd = df['total_usd'].iloc[-1]
    
    content = [
        f"# 📈 Stock Portfolio Dashboard",
        f"**Last Sync:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} (Israel Time)\n",
        f"## 🚀 Performance Summary",
        f"- **Current Value:** `₪{curr_usd * rate:,.0f}`",
        f"- **Total Return:** `{((curr_usd/df['total_usd'].iloc[0])-1)*100:+.2f}%`",
        f"- **USD/ILS Rate:** `₪{rate:.3f}`\n",
        f"## 📊 Growth Chart",
        f"![Growth](./{CHART_FILE})\n",
        f"## 🥧 Asset Allocation",
        f"![Allocation](./{PIE_FILE})\n",
        f"---",
        f"*All data and archives are stored in the `{DATA_DIR}` folder.*"
    ]
    with open(README_FILE, 'w', encoding='utf-8') as f: f.write("\n".join(content))

if __name__ == "__main__":
    main()
