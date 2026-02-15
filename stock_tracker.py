import yfinance as yf
import json
import os
import pandas as pd
from datetime import datetime
import pytz

# הגדרות
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "stock_history.json"
README_FILE = "README.md"
TZ = pytz.timezone('Israel')

def get_portfolio_value():
    # 1. טעינת האחזקות
    with open(PORTFOLIO_FILE, 'r') as f:
        holdings = json.load(f)
    
    tickers = list(holdings.keys())
    # 2. שליפת נתונים מהבורסה
    data = yf.download(tickers, period="1d", interval="1h")['Close']
    
    current_prices = {}
    total_value = 0
    details = []

    for ticker, amount in holdings.items():
        # לוקח את המחיר האחרון הזמין
        price = data[ticker].iloc[-1]
        value = price * amount
        total_value += value
        details.append({
            "ticker": ticker,
            "amount": amount,
            "price": round(price, 2),
            "value": round(value, 2)
        })
    
    return total_value, details

def calculate_monthly_gain(history, current_total):
    """
    חישוב רווח מה-10 לחודש הקודם עד עכשיו
    """
    now = datetime.now(TZ)
    # הגדרת תאריך היעד: ה-10 לחודש הנוכחי או הקודם
    if now.day >= 10:
        start_date = now.replace(day=10, hour=0, minute=0)
    else:
        # אם אנחנו לפני ה-10, נחזור לחודש הקודם
        month = now.month - 1 if now.month > 1 else 12
        year = now.year if now.month > 1 else now.year - 1
        start_date = datetime(year, month, 10, tzinfo=TZ)

    # חיפוש הערך הכי קרוב לתאריך ה-10 בחודש בתוך ההיסטוריה
    df_hist = pd.DataFrame(history)
    if df_hist.empty: return 0
    
    df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
    # סינון הנתונים שהוקלטו הכי קרוב ל-start_date
    start_value_row = df_hist[df_hist['timestamp'] >= start_date.strftime("%Y-%m-%d")]
    
    if not start_value_row.empty:
        base_value = start_value_row.iloc[0]['total_value']
        return current_total - base_value
    return 0

# --- לוגיקת עדכון וניהול קבצים (דומה למה שבנינו קודם) ---
def main():
    total_v, details = get_portfolio_value()
    timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    new_entry = {
        "timestamp": timestamp,
        "total_value": round(total_v, 2),
        "details": details
    }
    
    # עדכון היסטוריה
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    history.append(new_entry)
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)
    
    # חישוב רווח חודשי (מה-10 ל-10)
    monthly_gain = calculate_monthly_gain(history, total_v)
    
    # עדכון README
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 📈 מעקב תיק השקעות\n\n")
        f.write(f"**שווי תיק כולל:** ${round(total_v, 2)}\n\n")
        f.write(f"**רווח/הפסד מה-10 לחודש:** ${round(monthly_gain, 2)}\n\n")
        f.write(f"| מניה | כמות | מחיר יחידה | שווי כולל |\n|---|---|---|---|\n")
        for d in details:
            f.write(f"| {d['ticker']} | {d['amount']} | ${d['price']} | ${d['value']} |\n")

if __name__ == "__main__":
    main()
