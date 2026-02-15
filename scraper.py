import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import pytz
import pandas as pd

# הגדרות
URL = "https://www.ace.co.il/5760921"
DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def get_current_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ניסיון לשלוף כותרת
        title_tag = soup.find('h1', class_='page-title')
        title = title_tag.get_text(strip=True) if title_tag else "לא נמצא שם מוצר"
        
        # ניסיון לשלוף מחיר (ACE משתמשים במבנה ספציפי)
        # ננסה למצוא לפי תגית meta או class
        price = "0"
        price_meta = soup.find('meta', property='product:price:amount')
        if price_meta:
            price = price_meta['content']
        else:
            # גיבוי: חיפוש אלמנט מחיר
            price_span = soup.find('span', {'data-price-type': 'finalPrice'})
            if price_span:
                price = price_span.get_text(strip=True).replace('₪', '').replace(',', '')
        
        return {
            "timestamp": datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S"),
            "price": float(price),
            "title": title,
            "url": URL
        }
    except Exception as e:
        print(f"Error scraping: {e}")
        return None

def update_database(new_data):
    if not os.path.exists(DATA_FILE):
        data = []
    else:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    
    # בדיקה האם יש שינוי מהמחיר האחרון או שזה הריצה הראשונה
    # אנחנו שומרים כל דגימה, אבל בדוח נדגיש שינויים
    data.append(new_data)
    
    # שמירה (אופציונלי: אפשר לשמור רק 1000 אחרונים כדי לא להעמיס)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return data

def generate_readme(data):
    if not data:
        return

    latest = data[-1]
    count = len(data)
    
    # חישוב נתונים לטבלה (ניקח את ה-10 האחרונים)
    df = pd.DataFrame(data)
    df['price'] = pd.to_numeric(df['price'])
    
    min_price = df['price'].min()
    max_price = df['price'].max()
    avg_price = df['price'].mean()
    
    # יצירת גרף טקסטואלי פשוט לשינויים
    history_md = "| תאריך ושעה | מחיר | שינוי |\n|---|---|---|\n"
    
    last_price = None
    # מציג את ה-10 דגימות האחרונות (הופך סדר כדי שהכי חדש יהיה למעלה)
    for entry in reversed(data[-20:]): 
        current_price = entry['price']
        change_icon = "➖"
        
        if last_price is not None:
            if current_price < last_price:
                change_icon = "🔻 ירידה"
            elif current_price > last_price:
                change_icon = "🔺 עליה"
        
        history_md += f"| {entry['timestamp']} | ₪{current_price} | {change_icon} |\n"
        last_price = current_price

    readme_content = f"""
# 🤖 בוט מעקב מחירים - ACE

**שם המוצר:** [{latest['title']}]({latest['url']})  
**המחיר העדכני:** ₪{latest['price']}  
**זמן בדיקה אחרון:** {latest['timestamp']} (שעון ישראל)

---

### 📊 סטטיסטיקה
- **סה"כ דגימות:** {count}
- **מחיר מינימום שנצפה:** ₪{min_price}
- **מחיר מקסימום שנצפה:** ₪{max_price}

### 🕒 היסטוריה (20 דגימות אחרונות)
{history_md}

---
*הבוט רץ אוטומטית כל 15 דקות דרך GitHub Actions*
"""
    
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(readme_content)

if __name__ == "__main__":
    current_data = get_current_data()
    if current_data:
        print(f"Data fetched: {current_data}")
        all_data = update_database(current_data)
        generate_readme(all_data)
    else:
        print("Failed to fetch data.")
