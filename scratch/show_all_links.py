import re

def show_sections():
    with open("bulletin_page.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Находим все относительные и абсолютные ссылки, содержащие Section
    links = re.findall(r'href=["\']([^"\']*Section[^"\']*)["\']', html, re.IGNORECASE)
    print(f"Found {len(links)} Section links:")
    for idx, l in enumerate(sorted(set(links))):
        print(f"{idx+1:02d}: {l}")

if __name__ == "__main__":
    show_sections()
