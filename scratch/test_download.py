import os
from playwright.sync_api import sync_playwright

def test_download():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin.pdf"
    
    print("Launching browser with debug flags...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-http2", 
                "--disable-gpu", 
                "--no-sandbox",
                "--ignore-certificate-errors",
                "--disable-web-security"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()
        page.set_default_timeout(15000)
        
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
                print("Download successful!")
                return True
            else:
                print(f"Failed to download. Status: {response.status}")
                return False
        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    test_download()
