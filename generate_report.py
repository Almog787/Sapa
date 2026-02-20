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
    for f in:
        if os.path.exists(f):
            name = os.path.basename(f)
            shutil.move(f, os.path.join(ARCHIVE_DIR, f"{ts}_{name}"))

def get_live_usd_ils():
    """Fetch live USD/ILS exchange rate with fail-safe."""
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data.iloc if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def generate_visuals(df, holdings):
    """Generate performance and allocation charts."""
    plt.switch_backend('Agg')
    
    # 1. Performance Graph
    plt.figure(figsize=(12, 6))
    portfolio_norm = (df / df.iloc) * 100
    plt.plot(df, portfolio_norm, label='My Portfolio', color='#1f77b4', linewidth=2.5)
    
    try:
        spy = yf.Ticker("^GSPC").history(start=df.min(), end=df.max() + timedelta(days=1))
        if not spy.empty:
            # הסרת ה-Timezone מנתוני יאהו כדי שיסתנכרנו עם ציר הזמן של התיק שלנו
            spy.index = spy.index.tz_localize(None) 
            spy_norm = (spy / spy.iloc) * 100
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
    last_row = df.iloc
    tickers = list(holdings.keys())
    
    # נוודא שהמחיר לא ריק לפני שאנחנו מציירים בגרף
    values = * holdings for t in tickers if t in last_row and pd.notnull(last_row)]
    labels =)]
    
    if values:  # מצייר רק אם יש נתונים
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
    
    # Process History Data
    df = pd.DataFrame(, **e} for e in history])
    df = pd.to_datetime(df).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    # משיכת מחיר קודם במקרה ש-API נכשל בדגימה מסוימת (מונע צניחה זמנית של שווי התיק)
    df.ffill(inplace=True)
    
    # Portfolio Value Calculation
    df = df.apply(lambda r: sum(r * holdings for t in tickers if t in r and pd.notnull(r)), axis=1)
    
    current_val_usd = df.iloc
    initial_val_usd = df.iloc
    total_ret = ((current_val_usd / initial_val_usd) - 1) * 100

    # --- Change Calculations ---
    
    # 1. Daily Change (Last vs ~24 hours ago)
    daily_change_pct, daily_change_ils = 0.0, 0.0
    one_day_ago = df.max() - timedelta(days=1)
    past_day_df = df <= one_day_ago]
    
    if not past_day_df.empty:
        prev_val_usd = past_day_df.iloc
    else:
        # Fallback to earliest record if less than a day of data
        prev_val_usd = df.iloc
        
    daily_change_pct = ((current_val_usd / prev_val_usd) - 1) * 100
    daily_change_ils = (current_val_usd - prev_val_usd) * usd_to_ils

    # 2. Weekly Change (Last vs ~7 days ago)
    weekly_change_pct, weekly_change_ils = 0.0, 0.0
    one_week_ago = df.max() - timedelta(days=7)
    past_week_df = df <= one_week_ago]
    
    if not past_week_df.empty:
        weekly_val_usd = past_week_df.iloc
    else:
        # Fallback to earliest record if less than a week of data
        weekly_val_usd = df.iloc
        
    weekly_change_pct = ((current_val_usd / weekly_val_usd) - 1) * 100
    weekly_change_ils = (current_val_usd - weekly_val_usd) * usd_to_ils

    # Risk Metrics
    rolling_max = df.cummax()
    max_drawdown = ((df / rolling_max) - 1).min() * 100

    # Stock Performance (Lifetime)
    perf_map = {}
    for t in tickers:
        if t in df.columns:
            # מסנן חוסרים כדי שהמחיר הראשון למניה חדשה ייקלט נכון
            valid_prices = df.dropna() 
            if len(valid_prices) >= 2:
                perf_map = ((valid_prices.iloc / valid_prices.iloc) - 1) * 100
                
    best_stock = max(perf_map, key=perf_map.get) if perf_map else "N/A"
    worst_stock = min(perf_map, key=perf_map.get) if perf_map else "N/A"

    generate_visuals(df, holdings)

    # --- Build README ---
    output =(./{CHART_FILE})\n",
        f"## 🥧 התפלגות נכסים",
        f"!(./{PIE_FILE})\n",
        f"## 📊 פירוט אחזקות",
        f"| מניה | כמות | שווי (₪) | משקל |",
        f"| :--- | :--- | :--- | :--- |"
    ]

    last_prices = df.iloc
    for t in tickers:
        if t in last_prices and pd.notnull(last_prices):
            val_ils = last_prices * holdings * usd_to_ils
            weight = (last_prices * holdings / current_val_usd) * 100
            output.append(f"| {t} | {holdings} | ₪{val_ils:,.0f} | {weight:.1f}% |")

    output.append(f"\n---")
    output.append(f"📂 *Data stored in `{DATA_DIR}`* |(https://almog787.github.io/Sapa/)")

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
