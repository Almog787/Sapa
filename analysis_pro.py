import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime

DATA_DIR = "data_hub"
HISTORY_FILE = os.path.join(DATA_DIR, "stock_history.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
REPORT_FILE = "ANALYSIS_REPORT.md"
PREDICTION_CHART = os.path.join(DATA_DIR, "predictions.png")

def get_reversion_details(df, ticker):
    current_price = df[ticker].iloc[-1]
    avg_price = df[ticker].mean()
    std_dev = df[ticker].std()
    z_score = (current_price - avg_price) / std_dev if std_dev > 0 else 0
    
    if z_score > 1.5:
        return "🔴 **מתיחת יתר למעלה**: המחיר גבוה משמעותית מהממוצע ההיסטורי שלך. סיכון מוגבר לתיקון."
    elif z_score < -1.5:
        return "🟢 **הזדמנות ערך**: המחיר נמוך משמעותית מהממוצע. ייתכן שמדובר בנקודת כניסה נוחה."
    return "⚪ **מחיר הוגן**: המניה נסחרת סביב הממוצע ההיסטורי שלה."

def get_momentum_details(df, ticker):
    prices = df[ticker].dropna()
    if len(prices) < 20: return "⏳ צבירת נתונים..."
    ma_short = prices.rolling(window=20).mean().iloc[-1]
    ma_long = prices.rolling(window=min(len(prices), 50)).mean().iloc[-1]
    
    if ma_short > ma_long:
        return "🚀 **מגמה עולה**: הממוצע לטווח קצר מעל הארוך - המומנטום חיובי."
    return "⚠️ **מגמה יורדת**: המומנטום נחלש, המחיר מתקשה לפרוץ למעלה."

def get_rsi_details(rsi):
    if rsi > 70:
        return "🔥 **קניית יתר**: המניה 'חמה' מדי. ייתכן שיידרש אוורור בקרוב."
    elif rsi < 30:
        return "🧊 **מכירת יתר**: פאניקה של מוכרים. לעיתים קרובות מקדים זינוק למעלה."
    return "⚖️ **ניטרלי**: עוצמת הקונים והמוכרים מאוזנת."

def main():
    if not os.path.exists(HISTORY_FILE) or not os.path.exists(PORTFOLIO_FILE):
        return
    with open(PORTFOLIO_FILE, 'r') as f: holdings = json.load(f)
    with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    
    df = pd.DataFrame([{"ts": e['timestamp'], **e['prices']} for e in history])
    df['ts'] = pd.to_datetime(df['ts'])
    df = df.sort_values('ts')
    
    tickers = list(holdings.keys())
    sections = []
    
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')

    for t in tickers:
        if t not in df.columns: continue
        
        rev = get_reversion_details(df, t)
        mom = get_momentum_details(df, t)
        
        # RSI חישוב
        delta = df[t].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi_val = 100 - (100 / (1 + rs.iloc[-1])) if not pd.isna(rs.iloc[-1]) else 50
        rsi_desc = get_rsi_details(rsi_val)
        
        sections.append(f"### 📈 {t}\n"
                        f"- **מצב מחיר:** {rev}\n"
                        f"- **מגמת מומנטום:** {mom}\n"
                        f"- **מדד עוצמה (RSI):** {rsi_val:.1f} - {rsi_desc}\n")
        
        plt.plot(df['ts'], (df[t]/df[t].iloc[0])*100, label=t, alpha=0.8, linewidth=2)

    plt.title("Portfolio Performance Comparison (Normalized)")
    plt.legend(); plt.savefig(PREDICTION_CHART, bbox_inches='tight'); plt.close()
    
    report = [
        "# 🧠 דוח ניתוח מפורט ותחזיות",
        f"עדכון: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n",
        "## 🔍 ניתוח מעמיק לפי מניה",
        "\n".join(sections),
        "## 📊 השוואת צמיחה יחסית",
        f"![Predictions](./{PREDICTION_CHART})",
        "\n---",
        "### 📔 מילון מונחים למשקיע:",
        "- **Mean Reversion (חזרה לממוצע):** הנחה שמחיר המניה תמיד יחזור לממוצע שלו. סטייה חריגה היא הזדמנות או נורת אזהרה.",
        "- **RSI (מדד עוצמה יחסית):** כלי שמודד את מהירות שינויי המחיר. עוזר לזהות מתי הציבור רץ לקנות/למכור בטירוף.",
        "- **Momentum (מומנטום):** בודק אם 'הרוח בגב' של המניה. מניה במומנטום חיובי נוטה להמשיך לעלות."
    ]
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))

if __name__ == "__main__": main()
