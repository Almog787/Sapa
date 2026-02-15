import yfinance as yf
import json
import os
from datetime import datetime
import pytz
import pandas as pd

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "stock_history.json"
TZ = pytz.timezone('Israel')

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def main():
    # 1. טעינת אחזקות
    if not os.path.exists(PORTFOLIO_FILE):
        print(f"❌ שגיאה: הקובץ {PORTFOLIO_FILE} לא נמצא")
        return
    
    with open(PORTFOLIO_FILE, 'r') as f:
        holdings = json.load(f)
    
    # נוסיף את המדד SPY כברירת מחדל כדי שנוכל להשוות ביצועים בקוד השני
    tickers = list(holdings.keys())
    if "SPY" not in tickers:
        tickers.append("SPY")

    history = load_json(HISTORY_FILE)

    # 2. השלמת נתונים היסטוריים (אם הקובץ ריק)
    if not history:
        print("⏳ מבצע השלמת נתונים שנה אחורה (פעם ראשונה בלבד)...")
        # הורדת נתונים מרוכזת
        data = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']
        
        # ניקוי ערכים חסרים והמרה למילון מהיר
        data = data.ffill().bfill() # מילוי חורים בנתונים
        for date, row in data.iterrows():
            history.append({
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S"),
                "prices": row.round(2).to_dict()
            })

    # 3. דגימה נוכחית
    print(f"🔄 דוגם מחירים עבור: {', '.join(tickers)}")
    try:
        # הורדת נתוני היום האחרון
        current_data = yf.download(tickers, period="1d", interval="1m", progress=False)['Close']
        
        if not current_data.empty:
            last_row = current_data.iloc[-1]
            new_timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            
            # בדיקה למניעת כפילויות (לפי דקה)
            last_ts = history[-1]['timestamp'] if history else ""
            if new_timestamp[:16] != last_ts[:16]: # השוואה עד רמת הדקה
                history.append({
                    "timestamp": new_timestamp,
                    "prices": last_row.round(2).to_dict()
                })
                print(f"✅ נתונים נוספו בהצלחה ({new_timestamp})")
            else:
                print("⏭️ דגימה כבר קיימת לדקה זו, מדלג...")
    
    except Exception as e:
        print(f"⚠️ שגיאה באיסוף נתונים: {e}")

    # 4. שמירה (מוגבל ל-5000 כניסות כדי לשמור על קובץ קטן ומהיר)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-5000:], f, indent=4)

if __name__ == "__main__":
    main()
