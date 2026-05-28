import re
from curl_cffi import requests

def parse_bulletin_page():
    url = "https://www.cmegroup.com/dailybulletin"
    print(f"Fetching {url}...")
    
    try:
        response = requests.get(url, impersonate="chrome120", timeout=15)
        print("Status code:", response.status_code)
        
        # Сохраним HTML для анализа
        html = response.text
        with open("bulletin_page.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Page HTML saved. Analyzing links...")
        
        # Ищем все ссылки, содержащие .pdf или pg или bulletin
        links = re.findall(r'href=["\'](https?://[^"\']+\.pdf[^"\']*)["\']', html, re.IGNORECASE)
        print(f"Found {len(links)} PDF links:")
        for l in links[:20]:
            print("  ", l)
            
        # Также поищем ссылки на разделы (например, pg38 или page 38)
        pg_links = re.findall(r'href=["\']([^"\']*(?:pg|page|bulletin)[^"\']*)["\']', html, re.IGNORECASE)
        print(f"\nFound {len(pg_links)} bulletin/page links:")
        for l in pg_links[:20]:
            print("  ", l)
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    parse_bulletin_page()
