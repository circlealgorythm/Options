import os
from playwright.sync_api import sync_playwright

def test_download_chrome():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin_chrome.pdf"
    
    print("Launching system Google Chrome...")
    with sync_playwright() as p:
        try:
            # Запускаем системный Chrome
            browser = p.chromium.launch(
                headless=True,
                channel="chrome",
                args=["--disable-http2"]
            )
        except Exception as e:
            print(f"Failed to launch Chrome channel: {e}")
            return False
            
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        
        try:
            print("Navigating to CME home page...")
            page.goto("https://www.cmegroup.com/", wait_until="domcontentloaded")
            print("DOM loaded successfully!")
            
            # Скачиваем PDF через APIRequestContext
            print(f"Requesting PDF via page.request: {url}...")
            response = page.request.get(url, headers={
                "Referer": "https://www.cmegroup.com/"
            })
            
            print(f"Response status: {response.status}")
            if response.status == 200:
                with open(dest_path, 'wb') as f:
                    f.write(response.body())
                print("Download successful using system Chrome!")
                return True
            else:
                print(f"Failed. Status: {response.status}")
                return False
        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    test_download_chrome()
