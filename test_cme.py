from curl_cffi import requests
import re

response = requests.get('https://www.cmegroup.com/daily_bulletin/current/', impersonate='chrome')
html = response.text

matches = re.findall(r'Section\d+[^>]*\.pdf', html)
for m in matches:
    print(m)
