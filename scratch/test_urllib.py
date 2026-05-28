import urllib.request

def test_urllib():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin_urllib.pdf"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    print(f"Downloading via urllib: {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            print("Status code:", response.getcode())
            with open(dest_path, "wb") as f:
                f.write(response.read())
            print("Success!")
            return True
    except Exception as e:
        print("Error:", e)
        return False

if __name__ == "__main__":
    test_urllib()
