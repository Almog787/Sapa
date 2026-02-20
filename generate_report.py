import json
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import os
import shutil
import logging

# --- Paths Configuration ---
DATA_DIR = "data_hub"
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
HISTORY_FILE = os.path.join(DATA_DIR, "stock_history.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
LOG_FILE = os.path.join(DATA_DIR, "error_log.txt")
CHART_FILE = os.path.join(DATA_DIR, "portfolio_performance.png")
PIE_FILE = os.path.join(DATA_DIR, "asset_allocation.png")
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

# Ensure directories exist
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Logging setup
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def archive_visuals():
    """Archive old visuals before creating new ones."""
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M")
    for f in [CHART_FILE, PIE_FILE]:
        if os.path.exists(f):
            name = os.path.basename(f)
            shutil.move(f, os.path.join(ARCHIVE_DIR, f"{ts}_{name}"))

def get_live_usd_ils():
    """Fetch live USD/ILS exchange rate with fail-safe."""
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def generate_visuals(df, holdings):
    """Generate performance and allocation charts."""
    plt.switch_backend('Agg')
    
    # 1. Performance Graph
    plt.figure(figsize=(12, 6))
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    plt.plot(df['ts'], portfolio_norm, label='My Portfolio', color='#1f77b4', linewidth=2.5)
    
    try:
        spy = yf.Ticker("^GSPC").history(start=df['ts'].min(), end=df['ts'].max() + timedelta(days=1))
        if not spy.empty:
            spy.index = spy.index.tz_localize(None) 
            spy_norm = (spy['Close'] / spy['Close'].iloc[0]) * 100
            plt.plot(spy.index, spy_norm, label='S&P 500 (Benchmark)', color='#ff7f0e', linestyle='--', alpha=0.7)
    except Exception as e:
        logging.error(f"Benchmark error: {e}")

    plt.title('Performance vs Benchmark (Normalized to 100)', fontsize=14)
    plt.grid(True, alpha=0.2)
    plt.legend()
    plt.savefig(CHART_FILE)
    plt.close()

    # 2. Asset Allocation
    plt.figure(figsize=(8, 8))
    last_row = df.iloc[-1]
    tickers = list(holdings.keys())
    values = [last_row[t] * holdings[t] for t in tickers if t in last_row and pd.notnull(last_row[t])]
    labels = [t for t in tickers if t in last_row and pd.notnull(last_row[t])]
    
    if values:
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Pastel1.colors)
        plt.title('Asset Allocation (USD Weight)')
        plt.savefig(PIE_FILE)
    plt.close()

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return

    archive_visuals()

    try:
        with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    except Exception as e:
        logging.error(f"JSON Load error: {e}")
        return

    if not history: return

    usd_to_ils = get_live_usd_ils()
    tickers = list(holdings.keys())
    
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    price_cols = [t for t in tickers if t in df.columns]
    df[price_cols] = df[price_cols].ffill()
    
    df['total_usd'] = df.apply(lambda r: sum(r[t] * holdings[t] for t in tickers if t in r and pd.notnull(r[t])), axis=1)
    
    current_val_usd = df['total_usd'].iloc[-1]
    initial_val_usd = df['total_usd'].iloc[0]
    total_ret = ((current_val_usd / initial_val_usd) - 1) * 100

    # Change Calculations
    one_day_ago = df['ts'].max() - timedelta(days=1)
    past_day_df = df[df['ts'] <= one_day_ago]
    prev_val_usd = past_day_df['total_usd'].iloc[-1] if not past_day_df.empty else df['total_usd'].iloc[0]
    daily_change_pct = ((current_val_usd / prev_val_usd) - 1) * 100
    daily_change_ils = (current_val_usd - prev_val_usd) * usd_to_ils

    one_week_ago = df['ts'].max() - timedelta(days=7)
    past_week_df = df[df['ts'] <= one_week_ago]
    weekly_val_usd = past_week_df['total_usd'].iloc[-1] if not past_week_df.empty else df['total_usd'].iloc[0]
    weekly_change_pct = ((current_val_usd / weekly_val_usd) - 1) * 100
    weekly_change_ils = (current_val_usd - weekly_val_usd) * usd_to_ils

    # Risk Metrics
    rolling_max = df['total_usd'].cummax()
    max_drawdown = ((df['total_usd'] / rolling_max) - 1).min() * 100

    # Performance Leaderboard
    perf_map = {}
    for t in tickers:
        if t in df.columns:
            valid_prices = df[t].dropna() 
            if len(valid_prices) >= 2:
                perf_map[t] = ((valid_prices.iloc[-1] / valid_prices.iloc[0]) - 1) * 100
    best_stock = max(perf_map, key=perf_map.get) if perf_map else "N/A"
    worst_stock = min(perf_map, key=perf_map.get) if perf_map else "N/A"

    generate_visuals(df, holdings)

    # --- Build Bilingual README ---
    update_time = datetime.now(TZ).strftime('%d/%m/%Y %H:%M')
    
    output = [
        f"# 📊 Portfolio Tracking Dashboard | מעקב תיק השקעות",
        f"**Last Update / עדכון אחרון:** {update_time} | **USD/ILS:** ₪{usd_to_ils:.3f}\n",
        
        f"## 💰 Performance Summary | סיכום ביצועים",
        f"| Metric | Value | נתון |",
        f"| :--- | :--- | :--- |",
        f"| **Portfolio Value** | `₪{current_val_usd * usd_to_ils:,.0f}` | **שווי תיק** |",
        f"| **Daily Change** | `{daily_change_pct:+.2f}%` (₪{daily_change_ils:,.0f}) | **שינוי יומי** |",
        f"| **Weekly Change** | `{weekly_change_pct:+.2f}%` (₪{weekly_change_ils:,.0f}) | **שינוי שבועי** |",
        f"| **Total Return** | `{total_ret:+.2f}%` | **תשואה מצטברת** |",
        f"| **Max Drawdown** | `{max_drawdown:.2f}%` | **ירידה מקסימלית** |",
        f"| **Best Performer 🚀** | {best_stock} ({perf_map.get(best_stock, 0):+.1f}%) | **המניה המנצחת** |",
        f"| **Worst Performer 📉** | {worst_stock} ({perf_map.get(worst_stock, 0):+.1f}%) | **המניה המאכזבת** |\n",
        
        f"## 📈 Visuals | גרפים",
        f"### Performance vs S&P 500",
        f"![Performance](./{CHART_FILE})\n",
        f"### Asset Allocation | התפלגות נכסים",
        f"![Allocation](./{PIE_FILE})\n",
        
        f"## 📊 Holdings Detail | פירוט אחזקות",
        f"| Ticker | Amount | Value (₪) | Weight |",
        f"| :--- | :--- | :--- | :--- |"
    ]

    last_prices = df.iloc[-1]
    for t in tickers:
        if t in last_prices and pd.notnull(last_prices[t]):
            val_ils = last_prices[t] * holdings[t] * usd_to_ils
            weight = (last_prices[t] * holdings[t] / current_val_usd) * 100
            output.append(f"| {t} | {holdings[t]} | ₪{val_ils:,.0f} | {weight:.1f}% |")

    # --- Instructions Section (Bilingual) ---
    output.append(f"\n---")
    output.append(f"## ⚙️ How to Update? | הוראות עדכון")
    
    # English Instructions
    output.append(f"### 🇺🇸 English")
    output.append(f"To update your portfolio without downloading any files:")
    output.append(f"1. Go to the `data_hub` folder and open `portfolio.json`.")
    output.append(f"2. Click the **pencil icon** (Edit this file).")
    output.append(f"3. Add or modify stocks in the format: `\"TICKER\": AMOUNT`. (Example: `\"AAPL\": 10`).")
    output.append(f"4. Click **Commit changes** at the bottom.")
    
    # Hebrew Instructions
    output.append(f"### 🇮🇱 עברית")
    output.append(f"כדי לעדכן את המניות בתיק ללא הורדת קבצים:")
    output.append(f"1. היכנסו לתיקייה `data_hub` ופתחו את הקובץ `portfolio.json`.")
    output.append(f"2. לחצו על אייקון העיפרון (**Edit this file**).")
    output.append(f"3. הוסיפו או עדכנו מניות בפורמט: `\"סימול\": כמות`. (לדוגמה: `\"TSLA\": 5`).")
    output.append(f"4. לחצו על **Commit changes** בתחתית העמוד.\n")

    output.append(f"📂 *Data stored in `{DATA_DIR}`* | [Live Site](https://almog787.github.io/Sapa/)")

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
