import json
import pandas as pd
from datetime import datetime
import pytz
import os
import yfinance as yf

# הגדרות קבצים
HISTORY_FILE = "stock_history.json"
PORTFOLIO_FILE = "portfolio.json"
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

def get_exchange_rate():
    """שער דולר-שקל עדכני"""
    return yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]

def get_benchmark_return(start_date, end_date):
    """חישוב תשואת S&P 500 לתקופה ספציפית"""
    try:
        spy = yf.download("SPY", start=start_date.strftime('%Y-%m-%d'), 
                          end=(end_date).strftime('%Y-%m-%d'), progress=False)['Close']
        if len(spy) >= 2:
            return ((float(spy.iloc[-1]) / float(spy.iloc[0])) - 1) * 100
    except:
        pass
    return 0

def get_dividends_info(tickers, holdings):
    """איסוף נתוני דיבידנד שנתי למניה"""
    total_annual_div_usd = 0
    details = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            div_rate = t.info.get('dividendRate', 0)
            if div_rate is None: div_rate = 0
            details[ticker] = div_rate
            total_annual_div_usd += (div_rate * holdings[ticker])
        except:
            details[ticker] = 0
    return total_annual_div_usd, details

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        print("Missing files!")
        return

    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)

    usd_to_ils = get_exchange_rate()
    
    # עיבוד נתוני היסטוריה
    df = pd.DataFrame([{"ts": pd.to_datetime(e['timestamp']), **e['prices']} for e in history])
    df['ts'] = df['ts'].dt.tz_localize(None)
    df = df.sort_values('ts')

    now_fixed = datetime.now()
    
    # --- בניית ה-README ---
    output = f"# 📈 דוח ביצועי תיק מניות חכם\n\n"
    output += f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n\n"

    # 1. חישוב תקופת חודש שוטף (מה-10 האחרון)
    if now_fixed.day >= 10:
        current_period_start = now_fixed.replace(day=10, hour=0, minute=0, second=0)
    else:
        m = now_fixed.month - 1 if now_fixed.month > 1 else 12
        y = now_fixed.year if now_fixed.month > 1 else now_fixed.year - 1
        current_period_start = datetime(y, m, 10)

    # 2. השוואה למדד S&P 500 (חודש נוכחי)
    market_ret_curr = get_benchmark_return(current_period_start, now_fixed)
    base_row_curr = df[df['ts'] >= current_period_start].iloc[0]
    last_row_curr = df.iloc[-1]
    
    val_base_curr = sum(base_row_curr[t] * holdings[t] for t in holdings)
    val_now_curr = sum(last_row_curr[t] * holdings[t] for t in holdings)
    port_ret_curr = ((val_now_curr / val_base_curr) - 1) * 100
    diff_curr = port_ret_curr - market_ret_curr
    
    output += "## 🏆 ביצועים מול השוק (מה-10 לחודש)\n"
    output += f"- **תשואת התיק:** `{port_ret_curr:+.2f}%` | **S&P 500:** `{market_ret_curr:+.2f}%` \n"
    output += f"- **ביצועים יחסיים:** {'🚀' if diff_curr > 0 else '📉'} `{diff_curr:+.2f}%` \n\n"

    # 3. דיבידנדים
    total_div_usd, div_details = get_dividends_info(list(holdings.keys()), holdings)
    output += "## 💰 צפי הכנסה מדיבידנדים (שנתי)\n"
    output += f"- **סכום שנתי מוערך:** `₪{total_div_usd * usd_to_ils:,.0f}`\n"
    output += f"- **ממוצע חודשי פאסיבי:** `₪{(total_div_usd * usd_to_ils / 12):,.0f}`\n\n"

    # 4. היסטוריה של 12 חודשים (מה-10 ל-10)
    output += "## 🗓️ היסטוריית רווח חודשית (₪)\n"
    output += "| תקופה | רווח/הפסד | תשואה | מול S&P500 |\n|---|---|---|---|\n"
    
    monthly_rows = []
    for i in range(12):
        # חישוב חלון זמן לכל חודש
        target_m = now_fixed.month - i
        target_y = now_fixed.year
        while target_m <= 0:
            target_m += 12
            target_y -= 1
        
        m_end = datetime(target_y, target_m, 10)
        # חודש לפניו
        s_m = target_m - 1
        s_y = target_y
        if s_m <= 0:
            s_m = 12
            s_y -= 1
        m_start = datetime(s_y, s_m, 10)

        # שליפת נתונים מה-DF
        period_data = df[(df['ts'] >= m_start) & (df['ts'] <= m_end)]
        if len(period_data) >= 2:
            b_row = period_data.iloc[0]
            e_row = period_data.iloc[-1]
            
            p_gain_usd = sum((e_row[t] - b_row[t]) * holdings[t] for t in holdings)
            p_start_val = sum(b_row[t] * holdings[t] for t in holdings)
            p_ret = (p_gain_usd / p_start_val * 100) if p_start_val != 0 else 0
            
            # השוואת שוק לאותו חודש
            m_ret = get_benchmark_return(m_start, m_end)
            m_diff = p_ret - m_ret
            
            icon = "🟢" if p_gain_usd >= 0 else "🔴"
            period_str = f"{m_start.strftime('%m/%y')} - {m_end.strftime('%m/%y')}"
            monthly_rows.append(f"| {period_str} | {icon} ₪{p_gain_usd * usd_to_ils:,.0f} | {p_ret:.2f}% | {m_diff:+.1f}% |")

    output += "\n".join(monthly_rows) + "\n\n"

    # 5. פירוט אחזקות
    output += "## 📊 פירוט אחזקות נוכחי\n"
    output += "| מניה | כמות | שווי (₪) | דיבידנד שנתי |\n|---|---|---|---|\n"
    total_val_ils = 0
    for ticker, amount in holdings.items():
        price_ils = last_row_curr[ticker] * usd_to_ils
        val_ils = price_ils * amount
        total_val_ils += val_ils
        div_val = div_details.get(ticker, 0)
        output += f"| {ticker} | {amount} | ₪{val_ils:,.0f} | ${div_val:.2f} |\n"

    output += f"\n**שווי תיק כולל:** `₪{total_val_ils:,.0f}`\n"

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(output)
    print("Report generated successfully!")

if __name__ == "__main__":
    main()
