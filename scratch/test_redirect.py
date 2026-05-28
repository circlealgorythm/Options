from curl_cffi import requests

def test_session():
    url_home = "https://www.cmegroup.com/"
    url_pdf = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    
    print("Creating session...")
    s = requests.Session()
    
    try:
        print(f"Requesting {url_home} to establish session cookies...")
        r1 = s.get(url_home, impersonate="chrome120", timeout=10)
        print("Home status:", r1.status_code)
        
        print(f"Requesting PDF: {url_pdf}...")
        r2 = s.get(url_pdf, impersonate="chrome120", timeout=10)
        print("PDF status:", r2.status_code)
        print("PDF Response headers:", dict(r2.headers))
        print("PDF Content (first 100 bytes):", r2.content[:100])
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_session()
