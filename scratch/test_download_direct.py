import os
from playwright.sync_api import sync_playwright

def test_download_direct():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin_direct.pdf"
    
    print("Launching browser with HTTP/2 disabled...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-http2", "--disable-gpu", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        
        try:
            print(f"Navigating directly to PDF: {url}...")
            # Переходим напрямую на PDF
            response = page.goto(url, wait_until="domcontentloaded")
            print(f"Response status: {response.status if response else 'None'}")
            
            # Попробуем скачать через page.evaluate или APIRequestContext
            print("Requesting PDF via page.request...")
            pdf_response = page.request.get(url)
            print(f"PDF Request status: {pdf_response.status}")
            
            if pdf_response.status == 200:
                with open(dest_path, 'wb') as f:
                    f.write(pdf_response.body())
                print("Download successful direct!")
                return True
            else:
                return False
        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    test_download_direct()
