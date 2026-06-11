from curl_cffi import requests

urls = [
    'https://www.cmegroup.com/daily_bulletin/current/Section47_E_Mini_S_And_P_500_Call_Options.pdf',
    'https://www.cmegroup.com/daily_bulletin/current/Section48_E_Mini_S_And_P_500_Put_Options.pdf',
    'https://www.cmegroup.com/daily_bulletin/current/Section47_E-mini_S&P_500_Call_Options.pdf',
    'https://www.cmegroup.com/daily_bulletin/current/Section48_E-mini_S&P_500_Put_Options.pdf',
    'https://www.cmegroup.com/daily_bulletin/current/Section47_E_Mini_S_And_P_500_Options.pdf'
]

for url in urls:
    r = requests.get(url, impersonate='chrome', allow_redirects=False)
    if r.status_code == 200:
        print(f"SUCCESS (200 OK): {url.split('/')[-1]}")
    else:
        print(f"FAILED ({r.status_code}): {url.split('/')[-1]}")
