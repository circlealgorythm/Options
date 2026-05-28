import os
from playwright.sync_api import sync_playwright

def test_download_firefox():
    url = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    dest_path = "test_bulletin_firefox.pdf"
    
    print("Launching Firefox browser...")
    with sync_playwright() as p:
        try:
            browser = p.firefox.launch(headless=True)
        except Exception as e:
            print(f"Failed to launch Firefox: {e}")
            print("Trying to install firefox via playwright...")
            # Попробуем запустить команду установки
            return False
            
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        
        try:
            print("Navigating to CME home page via Firefox...")
            page.goto("https://www.cmegroup.com/", wait_until="domcontentloaded")
            print("DOM loaded successfully!")
            
            print(f"Requesting PDF via page.request: {url}...")
            response = page.request.get(url, headers={
                "Referer": "https://www.cmegroup.com/"
            })
            
            print(f"Response status: {response.status}")
            if response.status == 200:
                with open(dest_path, 'wb') as f:
                    f.write(response.body())
                print("Download successful using Firefox!")
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
    test_download_firefox()
