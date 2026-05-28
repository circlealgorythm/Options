import os
from playwright.sync_api import sync_playwright

def test_download_edge_download_event():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin_edge.pdf"
    
    print("Launching system Microsoft Edge...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="msedge",
            args=["--disable-http2"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            accept_downloads=True
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        
        try:
            print("Navigating to CME home page...")
            page.goto("https://www.cmegroup.com/", wait_until="domcontentloaded")
            print("DOM loaded successfully!")
            
            print(f"Triggering download for: {url}...")
            # Ждем события скачивания
            with page.expect_download() as download_info:
                # Переходим на страницу PDF, что должно вызвать скачивание
                page.goto(url, wait_until="commit")
                
            download = download_info.value
            download.save_as(dest_path)
            print(f"Download successful! Saved to {dest_path}")
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    test_download_edge_download_event()
