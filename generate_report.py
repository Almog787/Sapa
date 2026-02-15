import json
import pandas as pd
from datetime import datetime
import pytz
import os
import yfinance as yf

HISTORY_FILE = "stock_history.json"
PORTFOLIO_FILE = "portfolio.json"
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

def get_exchange_rate():
    return yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]

def get_benchmark_data(start_date):
    """מושך נתוני S&P 500 להשוואה"""
    spy = yf.download("SPY", start=start_date.strftime('%Y-%m-%d'), interval="1d")['Close']
    if not spy.empty:
        start_price = float(spy.iloc[0])
        current_price = float(spy.iloc[-1])
        return ((current_price / start_price) - 1) * 100
    return 0

def get_dividends_info(tickers, holdings):
    """מחשב צפי דיבידנד שנתי בשקלים"""
    total_annual_div_usd = 0
    details = {}
    for ticker in tickers:
        t = yf.Ticker(ticker)
        # מחשב דיבידנד שנתי (סכום הדיבידנדים שחולקו ב-12 החודשים האחרונים)
        div_yield = t.info.get('dividendRate', 0)
        if div_yield:
            annual_div = div_yield * holdings[ticker]
            total_annual_div_usd += annual_div
            details[ticker] = div_yield
    return total_annual_div_usd, details

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return

    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)

    usd_to_ils = get_exchange_rate()
    df = pd.DataFrame([{"ts": pd.to_datetime(e['timestamp']), **e['prices']} for e in history])
    df['ts'] = df['ts'].dt.tz_localize(None)
    df = df.sort_values('ts')

    now = datetime.now()
    # הגדרת תאריך התחלה (ה-10 לחודש הנוכחי או הקודם)
    if now.day >= 10:
        start_dt = now.replace(day=10, hour=0, minute=0, second=0)
    else:
        m = now.month - 1 if now.month > 1 else 12
        y = now.year if now.month > 1 else now.year - 1
        start_dt = datetime(y, m, 10)

    # חישוב תשואת שוק (S&P 500)
    market_return = get_benchmark_data(start_dt)
    
    # חישוב דיבידנדים
    total_div_usd, div_details = get_dividends_info(list(holdings.keys()), holdings)

    output = f"# 📈 דוח ביצועים חכם (בשקלים)\n\n"
    output += f"**עודכן ב:** {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} | **שער דולר:** ₪{usd_to_ils:.3f}\n\n"

    # --- חלק 1: השוואה לשוק ---
    # חישוב תשואת התיק הכוללת לתקופה
    base_row = df[df['ts'] >= start_dt].iloc[0]
    current_row = df.iloc[-1]
    
    val_base = sum(base_row[t] * holdings[t] for t in holdings)
    val_now = sum(current_row[t] * holdings[t] for t in holdings)
    portfolio_return = ((val_now / val_base) - 1) * 100
    
    diff = portfolio_return - market_return
    status_icon = "🚀" if diff > 0 else "📉"
    
    output += "## 🏆 השוואה למדד S&P 500 (מה-10 לחודש)\n"
    output += f"- **תשואת התיק שלך:** `{portfolio_return:.2f}%`\n"
    output += f"- **תשואת ה-S&P 500:** `{market_return:.2f}%`\n"
    output += f"- **ביצועים יחסיים:** {status_icon} `{diff:+.2f}%` "
    output += ("(אתה מכה את השוק!)" if diff > 0 else "(השוק חזק ממך החודש)") + "\n\n"

    # --- חלק 2: הכנסה מדיבידנדים ---
    output += "## 💰 צפי הכנסה מדיבידנדים (שנתי)\n"
    output += f"- **צפי דיבידנד שנתי כולל:** `₪{total_div_usd * usd_to_ils:,.0f}`\n"
    output += f"- **ממוצע חודשי (פאסיבי):** `₪{(total_div_usd * usd_to_ils / 12):,.0f}`\n\n"

    # --- חלק 3: פירוט חודשי ---
    output += "## 🗓️ היסטוריית רווח חודשית (ILS)\n"
    output += "| תקופה | רווח/הפסד | תשואה | מול S&P500 |\n|---|---|---|---|\n"
    # (כאן הקוד ממשיך בדומה למה שכתבנו קודם עם חישוב החודשים...)
    
    # --- חלק 4: טבלת מניות ---
    output += "\n## 📊 פירוט אחזקות\n"
    output += "| מניה | כמות | שווי (₪) | דיבידנד שנתי למניה |\n|---|---|---|---|\n"
    for ticker, amount in holdings.items():
        val_ils = current_row[ticker] * amount * usd_to_ils
        div_val = div_details.get(ticker, 0)
        output += f"| {ticker} | {amount} | ₪{val_ils:,.0f} | ${div_val:.2f} |\n"

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

if __name__ == "__main__":
    main()
