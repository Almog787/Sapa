import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import pytz
import pandas as pd

# הגדרות
# רשימת הכתובות למעקב - הוסף כאן את הלינקים המדויקים של דפי המוצר
STORES = [
    {"name": "ACE", "url": "https://www.ace.co.il/5760921"},
    {"name": "KSP", "url": "https://ksp.co.il/web/item/330000"}, # דוגמה ללינק
    {"name": "Ivory", "url": "https://www.ivory.co.il/catalog.php?id=11111"}, # דוגמה ללינק
    {"name": "SamMobile", "url": "https://www.sammobile.co.il/s25ultra"}, # דוגמה ללינק
    {"name": "Dynamic", "url": "https://www.gomobile.co.il/s25-ultra"},
    {"name": "Eline", "url": "https://www.eline.co.il/s25-ultra"},
    {"name": "Pelephone", "url": "https://www.pelephone.co.il/s25"},
    {"name": "Partner", "url": "https://www.partner.co.il/s25"},
    {"name": "HotMobile", "url": "https://www.hotmobile.co.il/s25"},
    {"name": "Cellcom", "url": "https://www.cellcom.co.il/s25"}
]

DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def scrape_store(store_info):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        response = requests.get(store_info["url"], headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # חיפוש כותרת גנרי
        title = "לא נמצא שם מוצר"
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # חיפוש מחיר - מנסה כמה שיטות נפוצות
        price = 0.0
        # שיטה 1: Meta tags (נפוץ באתרי מסחר)
        price_meta = soup.find('meta', property='product:price:amount') or soup.find('meta', property='og:price:amount')
        
        if price_meta:
            price = float(price_meta['content'].replace(',', ''))
        else:
            # שיטה 2: חיפוש טקסטואלי של סימן ₪ או מחיר
            # כאן נדרשת התאמה אישית לכל אתר אם השיטה הגנרית נכשלת
            price_text = soup.find(string=lambda t: '₪' in t if t else False)
            if not price_text:
                # גיבוי לאתר ACE ספציפית
                price_span = soup.find('span', {'data-price-type': 'finalPrice'})
                if price_span:
                    price_text = price_span.get_text()
            
            if price_text:
                import re
                numbers = re.findall(r'\d+', price_text.replace(',', ''))
                if numbers:
                    price = float(numbers[0])

        return {
            "store": store_info["name"],
            "timestamp": datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S"),
            "price": price,
            "title": title,
            "url": store_info["url"]
        }
    except Exception as e:
        print(f"Error scraping {store_info['name']}: {e}")
        return None

def update_database(new_entries):
    if not os.path.exists(DATA_FILE):
        data = []
    else:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    
    data.extend(new_entries)
    
    # שמירת 2000 דגימות אחרונות בלבד כדי למנוע קובץ ענקי
    data = data[-2000:]
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return data

def generate_readme(data):
    if not data:
        return

    df = pd.DataFrame(data)
    # המרת מחיר למספר (למקרה שיש מחירים אפסיים מסריקות שנכשלו)
    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
    
    # השגת המחיר האחרון מכל חנות
    latest_per_store = df.sort_values('timestamp').groupby('store').last().reset_index()
    latest_per_store = latest_per_store.sort_values(by='price')

    # יצירת טבלת השוואה נוכחית
    comparison_table = "| חנות | מחיר נוכחי | מוצר | לינק |\n|---|---|---|---|\n"
    for _, row in latest_per_store.iterrows():
        price_display = f"₪{row['price']}" if row['price'] > 0 else "לא זוהה"
        comparison_table += f"| {row['store']} | **{price_display}** | {row['title']} | [קישור]({row['url']}) |\n"

    # יצירת היסטוריה כללית (15 עדכונים אחרונים)
    history_md = "| זמן בדיקה | חנות | מחיר |\n|---|---|---|\n"
    for _, row in df.tail(15).iloc[::-1].iterrows():
        history_md += f"| {row['timestamp']} | {row['store']} | ₪{row['price']} |\n"

    readme_content = f"""
# 📱 מעקב מחירים Galaxy S25 Ultra

הבוט בודק מחירים ב-10 חנויות שונות בכל 15 דקות.

### 💰 השוואת מחירים (מעודכן לכל חנות)
{comparison_table}

---

### 🕒 עדכונים אחרונים (לוג פעילות)
{history_md}

---
*הבוט רץ על GitHub Actions. עודכן לאחרונה בשעון ישראל: {datetime.now(TZ_ISRAEL).strftime("%H:%M:%S")}*
"""
    
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(readme_content)

if __name__ == "__main__":
    results = []
    for store in STORES:
        print(f"Scraping {store['name']}...")
        store_data = scrape_store(store)
        if store_data:
            results.append(store_data)
    
    if results:
        all_history = update_database(results)
        generate_readme(all_history)
        print("Success!")
    else:
        print("No data collected.")
