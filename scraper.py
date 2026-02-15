import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import pytz
import pandas as pd

# הגדרות קבצים
URLS_FILE = "urls.txt"
DATA_FILE = "data.json"
README_FILE = "README.md"
TZ_ISRAEL = pytz.timezone('Asia/Jerusalem')

def get_product_data(product_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        price = 0
        title = "מוצר ללא שם"

        # לוגיקה לאתר ACE
        if "ace.co.il" in product_url:
            title_tag = soup.find('h1', class_='page-title')
            title = title_tag.get_text(strip=True) if title_tag else title
            price_meta = soup.find('meta', property='product:price:amount')
            if price_meta:
                price = price_meta['content']
            else:
                price_span = soup.find('span', {'data-price-type': 'finalPrice'})
                if price_span:
                    price = price_span.get_text(strip=True).replace('₪', '').replace(',', '')

        # לוגיקה לאתר GoMobile
        elif "gomobile.co.il" in product_url:
            title_tag = soup.find('h1', class_='product_title')
            title = title_tag.get_text(strip=True) if title_tag else title
            price_tag = soup.find('ins') or soup.find('span', class_='woocommerce-Price-amount')
            if price_tag:
                # ניקוי תווים לא רצויים
                price_text = price_tag.get_text(strip=True)
                price = "".join(filter(str.isdigit, price_text))
        
        return {
            "timestamp": datetime.now(TZ_ISRAEL).strftime("%Y-%m-%d %H:%M:%S"),
            "price": float(price) if price else 0,
            "title": title,
            "url": product_url
        }
    except Exception as e:
        print(f"Error scraping {product_url}: {e}")
        return None

def update_database(new_entries):
    data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    
    data.extend(new_entries)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return data

def generate_readme(all_data):
    if not all_data:
        return

    df = pd.DataFrame(all_data)
    readme_content = "# 🤖 בוט מעקב מחירים אוטומטי\n\n"
    readme_content += f"**עדכון אחרון:** {datetime.now(TZ_ISRAEL).strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    for url in df['url'].unique():
        p_df = df[df['url'] == url]
        latest = p_df.iloc[-1]
        
        # חישוב שינוי מהדגימה הקודמת
        diff_text = "➖ ללא שינוי"
        if len(p_df) > 1:
            prev_price = p_df.iloc[-2]['price']
            if latest['price'] < prev_price:
                diff_text = f"🔻 ירידה של ₪{prev_price - latest['price']}"
            elif latest['price'] > prev_price:
                diff_text = f"🔺 עלייה של ₪{latest['price'] - prev_price}"

        readme_content += f"### [{latest['title']}]({url})\n"
        readme_content += f"- **מחיר נוכחי:** `₪{latest['price']}` ({diff_text})\n"
        readme_content += f"- **הכי זול שנצפה:** ₪{p_df['price'].min()}\n\n"
        
        # טבלת היסטוריה קצרה
        readme_content += "| תאריך | מחיר |\n|---|---|\n"
        for _, row in p_df.tail(5).iloc[::-1].iterrows():
            readme_content += f"| {row['timestamp']} | ₪{row['price']} |\n"
        readme_content += "\n---\n"

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(readme_content)

if __name__ == "__main__":
    if not os.path.exists(URLS_FILE):
        print(f"Error: {URLS_FILE} not found!")
        exit(1)

    with open(URLS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    results = []
    for url in urls:
        print(f"Checking: {url}")
        res = get_product_data(url)
        if res:
            results.append(res)
    
    if results:
        full_data = update_database(results)
        generate_readme(full_data)
        print("Scrape completed successfully.")
