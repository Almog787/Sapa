import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os
import logging

HISTORY_FILE = "stock_history.json"
PORTFOLIO_FILE = "portfolio.json"
README_FILE = "README.md"
LOG_FILE = "error_log.txt"
TZ = pytz.timezone('Israel')

# הבטחת קיום קובץ לוג
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'w').close()

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_usd_ils():
    try:
        return yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 3.65

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return

    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)

    if not history: return

    usd_to_ils = get_live_usd_ils()
    tickers = list(holdings.keys())
    
    # עיבוד נתונים
    df = pd.DataFrame([{"ts": pd.to_datetime(e['timestamp']), **e['prices']} for e in history])
    df['ts'] = df['ts'].dt.tz_localize(None)
    df = df.sort_values('ts')
    
    # חישוב שווי תיק דולרי
    df['total_usd'] = df.apply(lambda row: sum(row[t] * holdings[t] for t in tickers if t in row), axis=1)

    now = datetime.now()
    output = [f"# 📈 דוח ביצועי תיק מניות", 
              f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n"]

    # חישוב תשואה (מה-10 לחודש)
    anchor = 10
    start_dt = now.replace(day=anchor) if now.day >= anchor else (now.replace(day=anchor) - timedelta(days=30))
    
    subset = df[df['ts'] >= start_dt]
    if len(subset) >= 2:
        v_start, v_end = subset['total_usd'].iloc[0], subset['total_usd'].iloc[-1]
        ret = ((v_end / v_start) - 1) * 100
        gain_ils = (v_end - v_start) * usd_to_ils
        output.append(f"## 🏆 ביצועים (מה-10 לחודש)\n- **תשואה:** `{ret:+.2f}%`\n- **רווח/הפסד:** `₪{gain_ils:,.0f}`\n")

    # טבלת אחזקות
    output.append("## 📊 פירוט אחזקות")
    output.append("| מניה | כמות | שווי (₪) |\n|---|---|---|")
    last_prices = df.iloc[-1]
    for t in tickers:
        if t == "SPY" and holdings.get(t, 0) == 0: continue
        val = last_prices[t] * holdings[t] * usd_to_ils
        output.append(f"| {t} | {holdings[t]} | ₪{val:,.0f} |")

    output.append(f"\n**שווי כולל:** `₪{df['total_usd'].iloc[-1] * usd_to_ils:,.0f}`")

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
