import yfinance as yf
import json
import os
from datetime import datetime
import pytz
import pandas as pd

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "stock_history.json"
TZ = pytz.timezone('Israel')

def ensure_files_exist():
    """יוצר קבצי בסיס אם הם חסרים במאגר"""
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    if not os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            # ברירת מחדל אם הקובץ נמחק
            json.dump({"SPY": 1}, f)

def main():
    ensure_files_exist()
    
    with open(PORTFOLIO_FILE, 'r') as f:
        holdings = json.load(f)
    
    tickers = list(holdings.keys())
    # תמיד נוסיף את SPY לצורך השוואת מדד בדוח
    if "SPY" not in tickers:
        tickers.append("SPY")

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        try:
            history = json.load(f)
        except:
            history = []

    # השלמת נתונים שנה אחורה אם ההיסטוריה ריקה
    if not history:
        print("Initial backfill starts...")
        data = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']
        data = data.ffill().bfill()
        for date, row in data.iterrows():
            history.append({
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S"),
                "prices": row.round(2).to_dict()
            })

    # דגימה נוכחית (מחיר אחרון)
    try:
        current_data = yf.download(tickers, period="1d", interval="1m", progress=False)['Close']
        if not current_data.empty:
            last_row = current_data.iloc[-1]
            new_timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            
            # מניעת כפילויות לפי דקה
            if not history or history[-1]['timestamp'][:16] != new_timestamp[:16]:
                history.append({
                    "timestamp": new_timestamp,
                    "prices": last_row.round(2).to_dict()
                })
    except Exception as e:
        print(f"Sampling error: {e}")

    # שמירה (מוגבל ל-5000 שורות כדי שהקובץ לא יהיה כבד מדי)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-5000:], f, indent=4)

if __name__ == "__main__":
    main()
