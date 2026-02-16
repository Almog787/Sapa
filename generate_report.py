import json
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import os
import logging

# --- Configuration & Constants ---
HISTORY_FILE = "stock_history.json"
PORTFOLIO_FILE = "portfolio.json"
README_FILE = "README.md"
LOG_FILE = "error_log.txt"
CHART_FILE = "portfolio_performance.png"
PIE_FILE = "asset_allocation.png"
TZ = pytz.timezone('Israel')
ANCHOR_DAY = 10

# Initialize logging
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'w').close()

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_usd_ils():
    """Fetches the current USD/ILS exchange rate."""
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def calculate_portfolio_value(row, holdings, tickers):
    """Calculates total portfolio value in USD for a given row of prices."""
    return sum(row[t] * holdings[t] for t in tickers if t in row)

def generate_visuals(df, holdings, usd_rate):
    """Generates performance and allocation charts using matplotlib."""
    plt.switch_backend('Agg') # Non-GUI backend for GitHub Actions
    
    # 1. Performance Chart (Portfolio vs S&P 500)
    plt.figure(figsize=(10, 5))
    
    # Normalize values to 100 for comparison
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    
    plt.plot(df['ts'], portfolio_norm, label='My Portfolio', color='#1f77b4', linewidth=2)
    
    # Fetch Benchmark (S&P 500)
    try:
        spy = yf.Ticker("^GSPC").history(start=df['ts'].min(), end=df['ts'].max() + timedelta(days=1))
        if not spy.empty:
            spy_norm = (spy['Close'] / spy['Close'].iloc[0]) * 100
            plt.plot(spy.index, spy_norm, label='S&P 500 (Benchmark)', color='#ff7f0e', linestyle='--')
    except:
        pass

    plt.title('Portfolio vs Benchmark (Normalized to 100)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(CHART_FILE)
    plt.close()

    # 2. Allocation Pie Chart
    last_prices = df.iloc[-1]
    values = [last_prices[t] * holdings[t] for t in holdings.keys() if t in last_prices]
    labels = [t for t in holdings.keys() if t in last_prices]
    
    plt.figure(figsize=(7, 7))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
    plt.title('Asset Allocation')
    plt.savefig(PIE_FILE)
    plt.close()

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        logging.error("Required files missing.")
        return

    try:
        with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    except Exception as e:
        logging.error(f"JSON Read Error: {e}")
        return

    if not history: return

    usd_to_ils = get_live_usd_ils()
    tickers = list(holdings.keys())
    
    # DataFrame Processing
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    # Core Calculations
    df['total_usd'] = df.apply(lambda r: calculate_portfolio_value(r, holdings, tickers), axis=1)
    
    current_val_usd = df['total_usd'].iloc[-1]
    initial_val_usd = df['total_usd'].iloc[0]
    total_ret = ((current_val_usd / initial_val_usd) - 1) * 100
    
    # Risk Metric: Max Drawdown
    rolling_max = df['total_usd'].cummax()
    drawdown = (df['total_usd'] / rolling_max) - 1
    max_drawdown = drawdown.min() * 100

    # Best/Worst Performers (Last 30 days or available)
    start_prices = df.iloc[0]
    last_prices = df.iloc[-1]
    perf_map = {t: ((last_prices[t]/start_prices[t])-1)*100 for t in tickers if t in start_prices and t in last_prices}
    best_stock = max(perf_map, key=perf_map.get)
    worst_stock = min(perf_map, key=perf_map.get)

    # Generate Images
    generate_visuals(df, holdings, usd_to_ils)

    # --- Build README ---
    output = [
        f"# 📊 Portfolio Dashboard",
        f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n",
        f"## 💰 סיכום ביצועים כולל",
        f"- **שווי תיק:** `₪{current_val_usd * usd_to_ils:,.0f}`",
        f"- **תשואה מצטברת:** `{total_ret:+.2f}%`",
        f"- **מקס' ירידה מהשיא (Drawdown):** `{max_drawdown:.2f}%`",
        f"- **מניית החודש 🚀:** {best_stock} ({perf_map[best_stock]:+.1f}%)",
        f"- **המאכזבת 📉:** {worst_stock} ({perf_map[worst_stock]:+.1f}%)\n",
        f"## 📈 גרף ביצועים",
        f"![Performance](./{CHART_FILE})\n",
        f"## 🥧 התפלגות נכסים",
        f"![Allocation](./{PIE_FILE})\n",
        f"## 📊 פירוט אחזקות",
        f"| מניה | כמות | שווי (₪) | משקל בתיק |",
        f"| :--- | :--- | :--- | :--- |"
    ]

    for t in tickers:
        if t in last_prices:
            val_ils = last_prices[t] * holdings[t] * usd_to_ils
            weight = (last_prices[t] * holdings[t] / current_val_usd) * 100
            output.append(f"| {t} | {holdings[t]} | ₪{val_ils:,.0f} | {weight:.1f}% |")

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
