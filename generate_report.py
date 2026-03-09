import json
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import os
import logging

# --- Paths Configuration ---
DATA_DIR = "data_hub"
HISTORY_FILE = os.path.join(DATA_DIR, "stock_history.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
LOG_FILE = os.path.join(DATA_DIR, "error_log.txt")
CHART_FILE = os.path.join(DATA_DIR, "portfolio_performance.png")
PIE_FILE = os.path.join(DATA_DIR, "asset_allocation.png")
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_usd_ils():
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def generate_visuals(df, holdings_data):
    plt.switch_backend('Agg')
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    
    # 1. Performance Graph
    plt.figure(figsize=(12, 6))
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    plt.plot(df['ts'], portfolio_norm, label='My Portfolio', color='#007AFF', linewidth=3)
    
    try:
        spy = yf.Ticker("^GSPC").history(start=df['ts'].min(), end=df['ts'].max() + timedelta(days=1))
        if not spy.empty:
            spy.index = spy.index.tz_localize(None) 
            spy_norm = (spy['Close'] / spy['Close'].iloc[0]) * 100
            plt.plot(spy.index, spy_norm, label='S&P 500 (Benchmark)', color='#FF9500', linestyle='--', alpha=0.8, linewidth=2)
    except Exception as e:
        logging.error(f"Benchmark error: {e}")

    plt.title('Performance vs Benchmark (Normalized to 100)', fontsize=14, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(frameon=True, shadow=True)
    plt.savefig(CHART_FILE, dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Asset Allocation (Donut)
    plt.figure(figsize=(10, 10))
    last_row = df.iloc[-1]
    tickers = list(holdings_data.keys())
    values = [last_row[t] * holdings_data[t]['amount'] for t in tickers if t in last_row and pd.notnull(last_row[t])]
    labels = [t for t in tickers if t in last_row and pd.notnull(last_row[t])]
    
    if values:
        colors = ['#FF595E', '#FFCA3A', '#8AC926', '#1982C4', '#6A4C93', '#4267B2']
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors[:len(values)], pctdistance=0.85, explode=[0.02]*len(values))
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        plt.gcf().gca().add_artist(centre_circle)
        plt.title('Asset Allocation (USD Weight)', fontsize=16, fontweight='bold')
        plt.savefig(PIE_FILE, dpi=300, bbox_inches='tight')
    plt.close()

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return

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
    
    # Fill missing prices
    price_cols = [t for t in tickers if t in df.columns]
    df[price_cols] = df[price_cols].ffill()
    
    # Calculate Total Value (New structure)
    df['total_usd'] = df.apply(lambda r: sum(r[t] * holdings[t]['amount'] for t in tickers if t in r and pd.notnull(r[t])), axis=1)
    
    current_val_usd = df['total_usd'].iloc[-1]
    
    # 1. Total Invested (Cost Basis)
    total_invested_usd = sum(h['amount'] * h['avg_price'] for h in holdings.values())
    total_pnl_usd = current_val_usd - total_invested_usd
    total_pnl_pct = (total_pnl_usd / total_invested_usd) * 100

    # 2. Daily Change
    one_day_ago = df['ts'].max() - timedelta(days=1)
    past_day_df = df[df['ts'] <= one_day_ago]
    prev_val_usd = past_day_df['total_usd'].iloc[-1] if not past_day_df.empty else df['total_usd'].iloc[0]
    daily_change_pct = ((current_val_usd / prev_val_usd) - 1) * 100
    daily_change_ils = (current_val_usd - prev_val_usd) * usd_to_ils

    generate_visuals(df, holdings)

    # --- Build Stock Table ---
    stock_rows = []
    for t in tickers:
        if t in df.columns:
            curr_p = df[t].iloc[-1]
            avg_p = holdings[t]['avg_price']
            amt = holdings[t]['amount']
            gain_pct = ((curr_p / avg_p) - 1) * 100
            gain_ils = (curr_p - avg_p) * amt * usd_to_ils
            emoji = "🟢" if gain_pct > 0 else "🔴"
            stock_rows.append(f"| {t} | {amt} | ${avg_p:,.2f} | ${curr_p:,.2f} | {emoji} {gain_pct:+.2f}% | ₪{gain_ils:,.0f} |")

    update_time = datetime.now(TZ).strftime('%d/%m/%Y %H:%M')
    
    output = [
        f"# 📊 Portfolio Dashboard | מעקב תיק השקעות",
        f"**Last Update:** {update_time} | **USD/ILS:** ₪{usd_to_ils:.3f}\n",
        
        f"## 💰 Portfolio Summary | סיכום התיק",
        f"| Metric | Value | נתון |",
        f"| :--- | :--- | :--- |",
        f"| **Current Value** | `₪{current_val_usd * usd_to_ils:,.0f}` | **שווי נוכחי** |",
        f"| **Total Invested** | `₪{total_invested_usd * usd_to_ils:,.0f}` | **סך השקעה** |",
        f"| **Total Profit/Loss** | `{total_pnl_pct:+.2f}%` (₪{total_pnl_usd * usd_to_ils:,.0f}) | **רווח/הפסד כולל** |",
        f"| **Daily Change** | `{daily_change_pct:+.2f}%` | **שינוי יומי** |",
        
        f"\n## 📜 Holdings | פירוט החזקות",
        f"| Ticker | Shares | Avg. Cost | Current Price | P&L % | P&L ILS |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- |",
        "\n".join(stock_rows),
        
        f"\n## 📈 Charts | גרפים",
        f"![Performance](./{CHART_FILE})",
        f"![Allocation](./{PIE_FILE})",
        f"\n---",
        f"📂 *Created by Almog787*"
    ]

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
