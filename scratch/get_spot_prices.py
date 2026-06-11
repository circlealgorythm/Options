import urllib.request
import json
import ssl

# Bypass SSL verification
ssl_context = ssl._create_unverified_context()

tickers = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "XAUUSD": "XAUUSD=X",
    "NASUSD": "^NDX",
    "BTCUSD": "BTC-USD"
}

quotes = {}
for name, ticker in tickers.items():
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            price = meta['regularMarketPrice']
            quotes[name] = price
            print(f"{name}: {price}")
    except Exception as e:
        print(f"Error fetching {name}: {e}")

print("Quotes:", quotes)
