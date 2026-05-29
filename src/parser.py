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
        
    current_contract_month = "UNKNOWN"
    current_option_type = "UNKNOWN"
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split('\n')
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                    
                # Look for section headers indicating option type and contract month
                if not parts[0].isdigit():
                    if "OPT" in parts:
                        opt_idx = parts.index("OPT")
                        if opt_idx >= 1:
                            current_option_type = parts[opt_idx - 1]
                    
                    for p in parts:
                        if re.match(r'^[A-Z]{3}\d{2}$', p):
                            current_contract_month = p
                            break
                    continue
                    
                if len(parts) < 8:
                    continue
                    
                strike_raw = parts[0]
                strike = float(strike_raw)
                if currency == 'EUR':
                    strike /= 10000.0
                else:
                    strike /= 1000.0
                    
                # Find Delta index (scanning from right to left to avoid Open/High/Low prices)
                # Note: Delta must start with a dot or 0. to avoid matching whole number volume/OI (e.g. 253)
                delta_idx = -1
                for idx in range(len(parts) - 1, 0, -1):
                    part = parts[idx]
                    # Delta is usually a clean decimal like .146 or 0.146.
                    # Avoid Bid/Ask quotes containing letters A/B
                    if (re.match(r'^\.\d{3}$', part) or re.match(r'^0\.\d{3}$', part)) and not any(c in part for c in ['A', 'B', 'C', 'V', 'K']):
                        delta_idx = idx
                        break
                if delta_idx < 5:
                    continue
                    
                delta = clean_value(parts[delta_idx])
                
                # Settle is usually at delta_idx - 2, and Net Change is at delta_idx - 1.
                # However, sometimes Settle and Change are glued together (e.g. '.00430-0.00130').
                settle = 0.0
                if delta_idx >= 2:
                    settle_str = parts[delta_idx - 2]
                    change_str = parts[delta_idx - 1]
                    
                    if re.search(r'\d[\+\-]\d', change_str):
                        settle_str = change_str
                        
                    clean_part = settle_str
                    # Handle cases like '.03080-0.00030' or '.100-7' or '2.30-' by splitting at - or +
                    for sign in ['-', '+']:
                        if sign in settle_str and settle_str.index(sign) > 0:
                            clean_part = settle_str.split(sign)[0]
                            break
                    raw_settle = clean_value(clean_part)
                    
                    # Scale the settle price based on currency and format
                    if currency == 'EUR':
                        is_decimal_quoted = False
                        if '.' in clean_part:
                            num_part = re.sub(r'[^\d.]', '', clean_part).strip()
                            if '.' in num_part:
                                after_dot = num_part.split('.')[1]
                                if len(after_dot) >= 5:
                                    is_decimal_quoted = True
                        
                        if is_decimal_quoted:
                            settle = raw_settle
                        else:
                            settle = raw_settle / 1000.0
                    elif currency == 'GBP':
                        settle = raw_settle / 100.0
                    else:
                        settle = raw_settle
                        
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
                    "Contract_Month": current_contract_month,
                    "Option_Type": current_option_type
                })
                
    return pd.DataFrame(data)
