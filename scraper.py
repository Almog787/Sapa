import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import pytz
import pandas as pd
import time

# --- הגדרות: רשימת מוצרים למעקב ---
PRODUCTS = [
    {"url": "https://www.ace.co.il/5760921", "name": "ACE - Leader Sofa"},
    {"url": "https://www.zilberahit.co.il/product/%D7%A1%D7%A4%D7%94-%D7%A4%D7%99%D7%A0%D7%AA%D7%99%D7%AA-%D7%9C%D7%99%D7%93%D7%A8-leader/", "name": "Zilber - Leader Sofa"},
    {"url": "https://www.shufersal.co.il/online/he/p/P_7296073387848", "name": "Shufersal - Mezzo (Similar)"}
]

DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def get_price_from_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        price = "0"
        
        # לוגיקה לאתר ACE
        if "ace.co.il" in url:
            price_meta = soup.find('meta', property='product:price:amount')
            if price_meta: 
                price = price_meta['content']
            else:
                span = soup.find('span', {'data-price-type': 'finalPrice'})
                if span: price = span.get_text(strip=True)
                
        # לוגיקה לאתר Zilber (משער שמבוסס WooCommerce/WordPress)
        elif "zilberahit" in url:
             price_tag = soup.find(class_='price') # חיפוש גנרי יותר
             if price_tag:
                 ins = price_tag.find('ins')
                 if ins: 
                     price = ins.get_text(strip=True)
                 else: 
                     price = price_tag.get_text(strip=True)

        # לוגיקה לאתר Shufersal
        elif "shufersal" in url:
            price_div = soup.find('span', class_='priceText')
            if price_div: 
                price = price_div.get_text(strip=True)
            else:
                # ניסיון נוסף לשופרסל אם ה-class השתנה
                price_meta = soup.find('meta', property='product:price:amount')
                if price_meta: price = price_meta['content']

        # ניקוי המחיר מסימנים (₪ ,) והמרתו למספר
        clean_price_str = ''.join(c for c in str(price) if c.isdigit() or c == '.')
        
        if not clean_price_str:
            return 0.0
            
        return float(clean_price_str)

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def update_database(products_list):
    # טעינת נתונים
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                content = json.load(f)
                # --- התיקון הקריטי כאן ---
                # אם הקובץ הוא רשימה (מהקוד הישן), נמחק אותו ונתחיל מילון חדש
                if isinstance(content, list):
                    print("Old database format detected. Resetting to new format.")
                    db = {}
                else:
                    db = content
            except: 
                db = {}
    else:
        db = {}

    timestamp = datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S")
    
    # ריצה על כל המוצרים
    for prod in products_list:
        url = prod['url']
        name = prod['name']
        
        try:
            current_price = get_price_from_url(url)
        except:
            current_price = None

        if current_price is not None and current_price > 0:
            if url not in db:
                db[url] = {"name": name, "history": []}
            
            # הוספת דגימה
            db[url]["history"].append({
                "timestamp": timestamp,
                "price": current_price
            })
            
            # שמירה על 500 רשומות אחרונות
            db[url]["history"] = db[url]["history"][-500:]
            print(f"✅ Scraped {name}: {current_price}")
        else:
            print(f"❌ Failed to scrape {name}")
        
        time.sleep(2) # השהייה קצרה

    # שמירה לקובץ
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)
    
    return db

def generate_readme(db):
    if not db: return

    md = "# 🤖 בוט השוואת מחירים - ספות\n\n"
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
    
    # פירוט היסטוריה לכל מוצר
    for url, data in db.items():
        if not data['history']: continue
        
        md += f"### 📊 היסטוריה: {data['name']}\n"
        md += "| תאריך | מחיר |\n|---|---|\n"
        
        # הצגת 10 דגימות אחרונות מהסוף להתחלה
        for entry in reversed(data['history'][-10:]): 
            md += f"| {entry['timestamp']} | ₪{entry['price']} |\n"
        md += "\n"

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(md)

if __name__ == "__main__":
    print("Starting scraper...")
    db = update_database(PRODUCTS)
    generate_readme(db)
    print("Done.")
