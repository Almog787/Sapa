import requests
from bs4 import BeautifulSoup
import json
import os
import re
import argparse
from datetime import datetime
import pytz
import pandas as pd
from urllib.parse import urljoin

# הגדרות
URLS_FILE = "urls.txt"
DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def get_product_data(product_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        response = requests.get(product_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        price = None
        title = None

        # 1. חילוץ כותרת
        title_meta = soup.find("meta", property="og:title") or soup.find("meta", dict(name="title"))
        if title_meta:
            title = title_meta["content"]
        else:
            title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "מוצר ללא שם"

        # 2. חילוץ מחיר גנרי
        # א. מטא דאטה
        price_meta = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
        if price_meta:
            price = price_meta["content"]
        
        # ב. JSON-LD
        if not price:
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    js = json.loads(script.string)
                    if isinstance(js, dict):
                        offer = js.get('offers')
                        if isinstance(offer, dict): price = offer.get('price')
                        elif isinstance(offer, list): price = offer[0].get('price')
                    if price: break
                except: continue

        # ג. Regex כגיבוי
        if not price:
            price_elem = soup.find(class_=re.compile(r'price|final-price|current-price', re.I))
            if price_elem:
                price = "".join(filter(lambda x: x.isdigit() or x == '.', price_elem.get_text().replace(',', '')))

        # ניקוי סופי
        if price:
            price = float(re.findall(r'\d+\.?\d*', str(price))[0])

        return {
            "timestamp": datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S"),
            "price": price if price else 0,
            "title": title.strip(),
            "url": product_url
        }
    except Exception as e:
        print(f"Error scraping {product_url}: {e}")
        return None

def discover_links(category_url):
    """חילוץ קישורי מוצרים מדף קטגוריה ומניעת כפילויות"""
    print(f"🔎 מחפש מוצרים בכתובת: {category_url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(category_url, headers=headers, timeout=20)
        soup = BeautifulSoup(res.content, 'html.parser')
        new_links = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(x in href for x in ['/product/', '/p/', '/items/', '/product-page/']):
                full_url = urljoin(category_url, href).split('?')[0].split('#')[0]
                new_links.add(full_url)
        
        # קריאת קישורים קיימים למניעת כפילויות
        existing = set()
        if os.path.exists(URLS_FILE):
            with open(URLS_FILE, 'r') as f:
                existing = set(line.strip() for line in f if line.strip())
        
        final_links = new_links - existing
        if final_links:
            with open(URLS_FILE, 'a') as f:
                for link in final_links:
                    f.write(f"\n{link}")
            print(f"✅ נוספו {len(final_links)} קישורים חדשים!")
        else:
            print("בחירה הסתיימה: לא נמצאו קישורים חדשים שלא קיימים כבר.")
    except Exception as e:
        print(f"Discovery error: {e}")

def update_database(new_entries):
    data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try: data = json.load(f)
            except: data = []
    data.extend(new_entries)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return data

def generate_readme(all_data):
    if not all_data: return
    df = pd.DataFrame(all_data)
    content = "# 🤖 בוט מעקב מחירים\n\n"
    content += f"**עדכון אחרון:** {datetime.now(TZ_ISRAEL).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for url in df['url'].unique():
        p_df = df[df['url'] == url]
        latest = p_df.iloc[-1]
        diff = "➖"
        if len(p_df) > 1:
            prev = p_df.iloc[-2]['price']
            if latest['price'] < prev: diff = f"🔻 ירידה של ₪{prev-latest['price']}"
            elif latest['price'] > prev: diff = f"🔺 עלייה של ₪{latest['price']-prev}"
        
        content += f"### [{latest['title']}]({url})\n"
        content += f"- **מחיר:** `₪{latest['price']}` | **שינוי:** {diff}\n"
        content += f"- **הכי זול:** ₪{p_df[p_df['price']>0]['price'].min() if not p_df[p_df['price']>0].empty else 0}\n\n"
    
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover", help="Category URL")
    args = parser.parse_args()

    if args.discover:
        discover_links(args.discover)
    else:
        if not os.path.exists(URLS_FILE): exit()
        with open(URLS_FILE, 'r') as f:
            urls = list(set(line.strip() for line in f if line.strip() and not line.startswith("#")))
        
        results = [get_product_data(u) for u in urls]
        results = [r for r in results if r]
        if results:
            full_data = update_database(results)
            generate_readme(full_data)
