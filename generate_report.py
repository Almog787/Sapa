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

# Logging setup
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def archive_visuals():
    """ארכוב תמונות ישנות לפני יצירת חדשות"""
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M")
    for f in [CHART_FILE, PIE_FILE]:
        if os.path.exists(f):
            name = os.path.basename(f)
            shutil.move(f, os.path.join(ARCHIVE_DIR, f"{ts}_{name}"))

def get_live_usd_ils():
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def generate_visuals(df, holdings):
    """יצירת גרפים מתקדמים: ביצועים מול מדד ופילוח נכסים"""
    plt.switch_backend('Agg')
    
    # 1. גרף ביצועים מול S&P 500
    plt.figure(figsize=(12, 6))
    # נרמול ל-100 (תשואה באחוזים מנקודת ההתחלה)
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    plt.plot(df['ts'], portfolio_norm, label='התיק שלי', color='#1f77b4', linewidth=2.5)
    
    try:
        # משיכת נתוני מדד להשוואה
        spy = yf.Ticker("^GSPC").history(start=df['ts'].min(), end=df['ts'].max() + timedelta(days=1))
        if not spy.empty:
            spy_norm = (spy['Close'] / spy['Close'].iloc[0]) * 100
            plt.plot(spy.index, spy_norm, label='S&P 500 (Benchmark)', color='#ff7f0e', linestyle='--', alpha=0.7)
    except Exception as e:
        logging.error(f"Benchmark error: {e}")

    plt.title('Performance vs Benchmark (Normalized to 100)', fontsize=14)
    plt.ylabel('Value')
    plt.grid(True, alpha=0.2)
    plt.legend()
    plt.savefig(CHART_FILE)
    plt.close()

    # 2. גרף עוגה - התפלגות נכסים
    plt.figure(figsize=(8, 8))
    last_prices = df.iloc[-1]
    tickers = list(holdings.keys())
    values = [last_prices[t] * holdings[t] for t in tickers if t in last_prices]
    labels = [t for t in tickers if t in last_prices]
    
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
    
    # עיבוד נתונים
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    # חישוב שווי תיק בדולרים לכל נקודת זמן
    df['total_usd'] = df.apply(lambda r: sum(r[t] * holdings[t] for t in tickers if t in r), axis=1)
    
    # מדדי ביצועים
    current_val_usd = df['total_usd'].iloc[-1]
    initial_val_usd = df['total_usd'].iloc[0]
    total_ret = ((current_val_usd / initial_val_usd) - 1) * 100
    
    # חישוב Max Drawdown (הסיכון המקסימלי שנחווה)
    rolling_max = df['total_usd'].cummax()
    drawdown = (df['total_usd'] / rolling_max) - 1
    max_drawdown = drawdown.min() * 100

    # מציאת המניה המנצחת והמאכזבת
    start_prices = df.iloc[0]
    last_prices = df.iloc[-1]
    perf_map = {t: ((last_prices[t]/start_prices[t])-1)*100 for t in tickers if t in start_prices and t in last_prices}
    best_stock = max(perf_map, key=perf_map.get)
    worst_stock = min(perf_map, key=perf_map.get)

    generate_visuals(df, holdings)

    # --- בניית ה-README ---
    output = [
        f"# 📊 Portfolio Dashboard",
        f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n",
        f"## 💰 סיכום ביצועים כולל",
        f"- **שווי תיק:** `₪{current_val_usd * usd_to_ils:,.0f}`",
        f"- **תשואה מצטברת:** `{total_ret:+.2f}%`",
        f"- **מקס' ירידה מהשיא (Drawdown):** `{max_drawdown:.2f}%`",
        f"- **מניית הכוכב 🚀:** {best_stock} ({perf_map[best_stock]:+.1f}%)",
        f"- **המאכזבת 📉:** {worst_stock} ({perf_map[worst_stock]:+.1f}%)\n",
        f"## 📈 גרף ביצועים (מול S&P 500)",
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

    output.append(f"\n---")
    output.append(f"📂 *כל הנתונים והארכיון שמורים בתיקיית `{DATA_DIR}`*")

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
