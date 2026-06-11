import urllib.request
import json
import re

url = "https://api.allorigins.win/get?url=https://www.cmegroup.com/daily_bulletin/current/"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        html = data.get('contents', '')
        links = re.findall(r'Section\d+[^"]*\.pdf', html)
        for link in links:
            if '500' in link or 'S_And_P' in link or 'Standard' in link or 'SP' in link:
                print("FOUND:", link)
        print("Total links found:", len(links))
except Exception as e:
    print("Error:", e)
