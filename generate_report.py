import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os
import logging

# --- Configuration ---
HISTORY_FILE = "stock_history.json"
PORTFOLIO_FILE = "portfolio.json"
README_FILE = "README.md"
LOG_FILE = "error_log.txt"
TZ = pytz.timezone('Israel')
ANCHOR_DAY = 10

# Initialize logging
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'w').close()

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_usd_ils():
    """Fetches current USD/ILS exchange rate."""
    try:
        ticker = yf.Ticker("ILS=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 3.65
    except:
        return 3.65

def calculate_portfolio_value(row, holdings, tickers):
    """Helper to calculate total USD value for a specific history row."""
    return sum(row[t] * holdings[t] for t in tickers if t in row)

def get_monthly_performance(df, holdings, tickers, usd_rate):
    """Calculates performance windows from 10th to 10th."""
    perf_records = []
    df = df.sort_values('ts')
    
    # Get unique months/years in the data
    df['year_month'] = df['ts'].dt.to_period('M')
    available_months = sorted(df['year_month'].unique(), reverse=True)
    
    for i in range(len(available_months) - 1):
        try:
            current_month = available_months[i]
            prev_month = available_months[i+1]
            
            target_end = datetime(current_month.year, current_month.month, ANCHOR_DAY)
            target_start = datetime(prev_month.year, prev_month.month, ANCHOR_DAY)
            
            # Find closest available data points
            end_row = df[df['ts'] <= target_end].iloc[-1]
            start_row = df[df['ts'] <= target_start].iloc[-1]
            
            if start_row['ts'] == end_row['ts']:
                continue
                
            val_start = calculate_portfolio_value(start_row, holdings, tickers)
            val_end = calculate_portfolio_value(end_row, holdings, tickers)
            
            perf_records.append({
                "period": f"{start_row['ts'].strftime('%d/%m')} - {end_row['ts'].strftime('%d/%m/%y')}",
                "return": ((val_end / val_start) - 1) * 100,
                "gain_ils": (val_end - val_start) * usd_rate
            })
        except (IndexError, Exception):
            continue
    return perf_records

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return

    try:
        with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    except:
        return

    if not history: return

    usd_to_ils = get_live_usd_ils()
    tickers = list(holdings.keys())
    
    # Process history into DataFrame
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.sort_values('ts')
    
    # Values for calculations
    first_row = df.iloc[0]
    last_row = df.iloc[-1]
    
    initial_val_usd = calculate_portfolio_value(first_row, holdings, tickers)
    current_val_usd = calculate_portfolio_value(last_row, holdings, tickers)
    
    # Total P/L calculation
    total_return = ((current_val_usd / initial_val_usd) - 1) * 100
    total_gain_ils = (current_val_usd - initial_val_usd) * usd_to_ils

    # Build Output
    output = [
        f"# 📈 דוח ביצועי תיק מניות", 
        f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n",
        f"## 💰 סיכום רווח מצטבר (מתחילת התיעוד)",
        f"- **רווח כולל:** `₪{total_gain_ils:,.0f}`",
        f"- **תשואה כוללת:** `{total_return:+.2f}%`",
        f"- **תאריך תחילת מעקב:** {first_row['ts'].strftime('%d/%m/%Y')}\n"
    ]

    # Calculate Monthly Windows
    performance_data = get_monthly_performance(df, holdings, tickers, usd_to_ils)
    
    if performance_data:
        latest = performance_data[0]
        output.append(f"## 🏆 ביצועים לחודש האחרון ({latest['period']})")
        output.append(f"- **תשואה:** `{latest['return']:+.2f}%` | **רווח:** `₪{latest['gain_ils']:,.0f}`\n")

        output.append("## 📅 היסטוריית רווחים (מ-10 ל-10)")
        output.append("| תקופה | תשואה | רווח/הפסד |")
        output.append("| :--- | :--- | :--- |")
        for record in performance_data[:12]:
            icon = "🟢" if record['return'] >= 0 else "🔴"
            output.append(f"| {record['period']} | {icon} `{record['return']:+.2f}%` | `₪{record['gain_ils']:,.0f}` |")
        output.append("")

    # Holdings Table
    output.append("## 📊 פירוט אחזקות")
    output.append("| מניה | כמות | שווי (₪) |")
    output.append("| :--- | :--- | :--- |")
    for t in tickers:
        if t in last_row:
            val = last_row[t] * holdings[t] * usd_to_ils
            output.append(f"| {t} | {holdings[t]} | ₪{val:,.0f} |")

    output.append(f"\n**שווי כולל:** `₪{current_val_usd * usd_to_ils:,.0f}`")

    # Save to README
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    main()
