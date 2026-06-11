from curl_cffi import requests
import re

url = "https://www.cmegroup.com/daily_bulletin/current/"
try:
    r = requests.get(url, impersonate='chrome')
    if r.status_code == 200:
        html = r.text
        links = re.findall(r'Section\d+[^"]*\.pdf', html)
        sp_links = [l for l in links if '500' in l or 'S_And_P' in l or 'Standard' in l]
        print("S&P 500 related links:", sp_links)
        print("Total links found:", len(links))
    else:
        print(f"Status Code: {r.status_code}")
except Exception as e:
    print("Error:", e)
