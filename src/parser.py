import os
import re
import pandas as pd
import pdfplumber
from curl_cffi import requests

def download_cme_bulletin(url_or_section: str, dest_path: str):
    """
    Downloads a CME daily bulletin section using curl_cffi to bypass Akamai WAF.
    """
    section_name = url_or_section.split('/')[-1]
    url = f"https://www.cmegroup.com/daily_bulletin/current/{section_name}"
    
    print(f"Downloading {url} to {dest_path} using curl_cffi...")
    try:
        response = requests.get(url, impersonate="chrome120", timeout=20)
        if response.status_code == 200:
            with open(dest_path, 'wb') as f:
                f.write(response.content)
            print(f"Successfully downloaded {section_name} ({len(response.content)} bytes)")
            return True
        else:
            print(f"Failed to download {section_name}. Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading {section_name}: {e}")
        return False

def clean_value(val):
    if not val or val == "----" or val == "CAB":
        return 0.0
    cleaned = re.sub(r'[BA\+\-\*]', '', val).strip()
    try:
        return float(cleaned)
    except:
        return 0.0

def parse_cme_pdf(pdf_path: str, currency: str, is_call_only: bool = None):
    """
    Parses a CME Daily Bulletin PDF for a specific currency option data.
    is_call_only: True if processing Call options only, False for Put only, None for mixed (EUR).
    """
    data = []
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF path {pdf_path} does not exist.")
        return pd.DataFrame()
        
    expiry_idx = 0
    last_strike = -1.0
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split('\n')
            for line in lines:
                parts = line.split()
                if not parts or not parts[0].isdigit():
                    continue
                if len(parts) < 8:
                    continue
                    
                strike_raw = parts[0]
                strike = float(strike_raw)
                if currency == 'EUR':
                    strike /= 10000.0
                else:
                    strike /= 1000.0
                    
                if last_strike > 0 and strike < last_strike - 0.005:
                    expiry_idx += 1
                last_strike = strike
                    
                # Find Delta index
                delta_idx = -1
                for idx, part in enumerate(parts):
                    if re.match(r'^\.?\d{3}$', part) or re.match(r'^0\.\d{3}$', part):
                        delta_idx = idx
                        break
                if delta_idx == -1:
                    continue
                    
                delta = clean_value(parts[delta_idx])
                
                # Find Settle index (scanning left from delta)
                settle = 0.0
                for idx in range(delta_idx - 1, 0, -1):
                    part = parts[idx]
                    if '.' in part or part in ['CAB', '----'] or ('-' in part and len(part) > 1 and '.' in part) or ('+' in part and len(part) > 1 and '.' in part):
                        settle = clean_value(part)
                        break
                        
                # Find Open Interest index (scanning right from delta)
                oi = 0
                for idx in range(delta_idx + 1, len(parts)):
                    part = parts[idx]
                    cleaned = re.sub(r'[A-Z\+\-\*]', '', part).strip()
                    if cleaned.isdigit() and len(cleaned) > 0:
                        oi = int(cleaned)
                        
                data.append({
                    "Strike": strike,
                    "Settle": settle,
                    "Delta": delta,
                    "OI": oi,
                    "Is_Call": is_call_only,
                    "Expiry_Idx": expiry_idx
                })
                
    return pd.DataFrame(data)
