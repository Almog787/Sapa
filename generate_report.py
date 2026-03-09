import json
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import os
import logging

# --- Paths & Configuration ---
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

# --- Helpers ---
def get_live_usd_ils():
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except Exception as e:
        logging.error(f"Exchange rate error: {e}")
        return 3.65

def get_performance_bar(pct):
    if pd.isna(pct): return "⬜⬜⬜⬜⬜"
    bars = int(min(abs(pct) / 10, 5))
    return ("🟩" * bars if pct > 0 else "🟥" * bars) + ("⬜" * (5 - bars))

def generate_visuals(df, holdings_data):
    plt.switch_backend('Agg')
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    ax1.plot(df['ts'], portfolio_norm, label='My Portfolio', color='#007AFF', linewidth=3)
    
    try:
        spy = yf.Ticker("^GSPC").history(start=df['ts'].min(), end=df['ts'].max() + timedelta(days=1))
        if not spy.empty:
            spy.index = spy.index.tz_localize(None) 
            spy_norm = (spy['Close'] / spy['Close'].iloc[0]) * 100
            ax1.plot(spy.index, spy_norm, label='S&P 500 (Benchmark)', color='#FF9500', linestyle='--', alpha=0.8)
    except: pass

    ax1.set_title('Performance vs Benchmark', fontsize=14)
    ax1.grid(True, alpha=0.2)
    ax1.legend()
    
    rolling_max = portfolio_norm.cummax()
    drawdown = ((portfolio_norm - rolling_max) / rolling_max) * 100
    ax2.fill_between(df['ts'], drawdown, 0, color='#FF3B30', alpha=0.3)
    ax2.set_ylabel('Drawdown %')
    
    plt.tight_layout()
    plt.savefig(CHART_FILE)
    plt.close()

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE): return

    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)

    usd_to_ils = get_live_usd_ils()
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    tickers = list(holdings.keys())
    price_cols = [t for t in tickers if t in df.columns]
    df[price_cols] = df[price_cols].ffill()
    
    df['total_usd'] = df.apply(lambda r: sum(r[t] * holdings[t]['amount'] for t in tickers if t in r and pd.notnull(r[t])), axis=1)
    
    current_val_usd = df['total_usd'].iloc[-1]
    total_invested_usd = sum(h['amount'] * h['avg_price'] for h in holdings.values())
    total_pnl_pct = ((current_val_usd / total_invested_usd) - 1) * 100
    
    portfolio_norm = (df['total_usd'] / df['total_usd'].iloc[0]) * 100
    max_drawdown = (((portfolio_norm - portfolio_norm.cummax()) / portfolio_norm.cummax()) * 100).min()

    generate_visuals(df, holdings)

    # --- בניית טבלת מניות עם הסברים ---
    stock_rows = []
    for t in tickers:
        curr_p = df[t].iloc[-1]
        avg_p = holdings[t]['avg_price']
        gain_pct = ((curr_p / avg_p) - 1) * 100
        stock_rows.append(f"| **{t}** | {get_performance_bar(gain_pct)} | {holdings[t]['amount']} | ${curr_p:,.2f} | **{gain_pct:+.2f}%** |")

    update_time = datetime.now(TZ).strftime('%d/%m/%Y %H:%M')
    
    output = [
        f"# 📊 Portfolio Dashboard | מעקב תיק השקעות",
        f"> **Last Update:** `{update_time}` | **USD/ILS:** `₪{usd_to_ils:.3f}`\n",
        
        f"## 💎 Portfolio Summary | סיכום התיק",
        f"| נתון | ערך | הסבר קצר |",
        f"| :--- | :--- | :--- |",
        f"| **שווי נוכחי (ILS)** | `₪{current_val_usd * usd_to_ils:,.0f}` | השווי הכולל של התיק שלך בשקלים נכון לרגע זה. |",
        f"| **רווח/הפסד כולל** | `{total_pnl_pct:+.2f}%` | אחוז השינוי מההשקעה המקורית (Cost Basis). |",
        f"| **Max Drawdown** | `{max_drawdown:.2f}%` | **מדד סיכון:** הירידה החדה ביותר שחווה התיק מהשיא שלו. עוזר להבין תנודתיות. |",
        
        f"\n## 📜 Holdings | פירוט החזקות",
        f"| Ticker | Momentum | Shares | Price | P&L % |",
        f"| :--- | :--- | :--- | :--- | :--- |",
        "\n".join(stock_rows),
        
        f"\n## 📈 Visual Analytics | ניתוח ויזואלי",
        f"![Performance](./{CHART_FILE})",
        
        f"\n---",
        f"### 📔 מילון מונחים מקוצר:",
        f"- **Momentum (הבר הוויזואלי):** ייצוג גרפי של ביצועי המניה. כל בלוק מייצג 10% רווח/הפסד.",
        f"- **Normalized Performance:** השוואה של התיק ל-S&P 500 כאילו שניהם התחילו ב-100 נקודות.",
        f"- **Drawdown (הגרף האדום):** מציג כמה התיק "דימם" מהשיא שלו בכל נקודת זמן.",
        f"\n*Created by Almog787*"
    ]

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__": main()
