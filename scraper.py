import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import pytz
import pandas as pd
import time

# --- הגדרות: רשימת מוצרים למעקב ---
# כאן אתה מוסיף את הקישורים שמצאנו
PRODUCTS = [
    {"url": "https://www.ace.co.il/5760921", "name": "ACE - Leader Sofa"},
    {"url": "https://www.zilberahit.co.il/product/%D7%A1%D7%A4%D7%94-%D7%A4%D7%99%D7%A0%D7%AA%D7%99%D7%AA-%D7%9C%D7%99%D7%93%D7%A8-leader/", "name": "Zilber - Leader Sofa"},
    # אפשר להוסיף עוד קישורים כאן
]

DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def get_price_from_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        price = "0"
        
        # לוגיקה לאתרים שונים
        if "ace.co.il" in url:
            price_meta = soup.find('meta', property='product:price:amount')
            if price_meta: price = price_meta['content']
            else:
                span = soup.find('span', {'data-price-type': 'finalPrice'})
                if span: price = span.get_text(strip=True)
                
        elif "zilberahit" in url:
             # התאמה לזילבר (צריך לוודא את ה-Class באתר שלהם, זה ניחוש מושכל)
             # לרוב בווקומרס/וורדפרס זה נראה כך:
             price_tag = soup.find('p', class_='price')
             if price_tag:
                 ins = price_tag.find('ins') # מחיר מבצע
                 if ins: price = ins.get_text(strip=True)
                 else: price = price_tag.get_text(strip=True)

        elif "shufersal" in url:
            # התאמה לשופרסל
            price_div = soup.find('span', class_='priceText')
            if price_div: price = price_div.get_text(strip=True)

        # ניקוי המחיר
        clean_price = ''.join(filter(lambda x: x.isdigit() or x == '.', str(price)))
        return float(clean_price) if clean_price else 0.0

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def update_database(products_list):
    # טעינת נתונים קיימים
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except: db = {}
    else:
        db = {}

    timestamp = datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S")
    
    # ריצה על כל המוצרים
    for prod in products_list:
        url = prod['url']
        name = prod['name']
        price = get_price_from_url(url)
        
        if price is not None:
            if url not in db:
                db[url] = {"name": name, "history": []}
            
            # הוספת דגימה
            db[url]["history"].append({
                "timestamp": timestamp,
                "price": price
            })
            
            # שמירה על היסטוריה סבירה (למשל 500 אחרונים)
            db[url]["history"] = db[url]["history"][-500:]
            print(f"Scraped {name}: {price}")
        else:
            print(f"Failed to scrape {name}")
        
        time.sleep(2) # נימוס לאתרים (השהייה קצרה)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)
    
    return db

def generate_readme(db):
    if not db: return

    md = "# 🤖 בוט השוואת מחירים\n\n"
    md += f"**עדכון אחרון:** {datetime.now(TZ_ISRAEL).strftime('%d/%m/%Y %H:%M')}\n\n"
    
    # טבלה מסכמת
    md += "## 🏆 טבלת השוואה נוכחית\n"
    md += "| שם המוצר | מחיר אחרון | שינוי |\n|---|---|---|\n"
    
    for url, data in db.items():
        if not data['history']: continue
        latest = data['history'][-1]
        price = latest['price']
        name = data['name']
        
        # חישוב שינוי
        change_icon = "➖"
        if len(data['history']) > 1:
            prev = data['history'][-2]['price']
            if price < prev: change_icon = "🔻 ירידה"
            elif price > prev: change_icon = "🔺 עליה"
            
        md += f"| [{name}]({url}) | ₪{price} | {change_icon} |\n"

    md += "\n---\n"
    
    # פירוט לכל מוצר
    for url, data in db.items():
        if not data['history']: continue
        md += f"### 📊 היסטוריה: {data['name']}\n"
        md += "| תאריך | מחיר |\n|---|---|\n"
        for entry in reversed(data['history'][-10:]): # 10 אחרונים
            md += f"| {entry['timestamp']} | ₪{entry['price']} |\n"
        md += "\n"

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(md)

if __name__ == "__main__":
    db = update_database(PRODUCTS)
    generate_readme(db)
