import os
import re
import pandas as pd
import pdfplumber
from playwright.sync_api import sync_playwright

def download_cme_bulletin(url: str, dest_path: str):
    """
    Downloads the CME daily bulletin using Playwright to bypass basic anti-bot protections.
    """
    print(f"Downloading {url} to {dest_path}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # We use a standard user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # We navigate to the PDF URL
            # For PDF downloads, Playwright can sometimes handle them if we wait for download event
            # Or we can just try to fetch the bytes if it displays in browser
            response = page.goto(url, wait_until="networkidle")
            if response is None or response.status != 200:
                print(f"Failed to fetch {url}. Status: {response.status if response else 'Unknown'}")
                return False
                
            # Usually for direct PDFs, playwright's page.goto just downloads it or renders it.
            # We'll use requests through the page context to get the raw bytes
            client = page.context.new_cdp_session(page)
            cookies = page.context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            # Use requests with the same cookies and user-agent to download the actual PDF
            import requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
                "Referer": "https://www.cmegroup.com/"
            }
            res = requests.get(url, headers=headers, stream=True)
            if res.status_code == 200:
                with open(dest_path, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                return True
            else:
                print(f"Requests failed with status {res.status_code}")
                return False
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            return False
        finally:
            browser.close()

def parse_cme_pdf(pdf_path: str, currency_filter=None):
    """
    Parses the CME Currency Options PDF using pdfplumber.
    Extracts Strike, Premium, and Open Interest.
    Returns a DataFrame.
    """
    if currency_filter is None:
        currency_filter = ['EUR', 'GBP']
        
    data = []
    
    # This is a generalized parsing logic meant to be adapted to the exact CME layout.
    # The actual CME Daily Bulletin table has columns for Calls and Puts, Strikes, and Vol/OI.
    
    with pdfplumber.open(pdf_path) as pdf:
        current_currency = None
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
                
            # Simple heuristic to find currency sections
            if "EURO FX" in text.upper():
                current_currency = "EUR"
            elif "BRITISH POUND" in text.upper():
                current_currency = "GBP"
                
            if current_currency not in currency_filter:
                continue
                
            # Attempt to extract table data
            # Typically lines look like: 
            # Strike  Call-Sett  Put-Sett  Call-Vol  Put-Vol  Call-OI  Put-OI
            lines = text.split('\n')
            for line in lines:
                # Look for a line that starts with a strike price (e.g., 10500, 11000)
                # This is a highly simplified regex for demonstration
                match = re.match(r'^(\d{4,5})\s+([0-9.]+)\s+([0-9.]+)\s+\d+\s+\d+\s+(\d+)\s+(\d+)', line.strip())
                if match:
                    strike = float(match.group(1)) / 10000.0  # e.g., 11000 -> 1.1000
                    call_settle = float(match.group(2))
                    put_settle = float(match.group(3))
                    call_oi = int(match.group(4))
                    put_oi = int(match.group(5))
                    
                    data.append({
                        "Currency": current_currency,
                        "Strike": strike,
                        "Call_Settle": call_settle,
                        "Put_Settle": put_settle,
                        "Call_OI": call_oi,
                        "Put_OI": put_oi
                    })
                    
    df = pd.DataFrame(data)
    return df
