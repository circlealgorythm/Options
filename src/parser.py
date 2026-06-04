import os
import re
import datetime
import pandas as pd
import pdfplumber
from curl_cffi import requests

MONTH_NAME_MAP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

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

def parse_bulletin_date_from_text(text: str):
    match = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})\b', text)
    if not match:
        return None

    month = MONTH_NAME_MAP.get(match.group(1).upper())
    if month is None:
        return None

    return datetime.date(int(match.group(3)), month, int(match.group(2)))

def extract_bulletin_date(pdf_path: str):
    if not os.path.exists(pdf_path):
        return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            text = page.extract_text() or ""
            bulletin_date = parse_bulletin_date_from_text(text)
            if bulletin_date is not None:
                return bulletin_date

    return None

def parse_cme_pdf(pdf_path: str, currency: str, is_call_only: bool = None):
    """
    Parses a CME Daily Bulletin PDF for a specific currency option data.
    is_call_only: True if processing Call options only, False for Put only, None for mixed (EUR).
    """
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
    is_call_state = is_call_only
    
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
                    line_upper = line.upper()
                    is_header = False
                    if any(kw in line_upper for kw in ["CALL", "PUT", "OPTIONS", "OPTION", "OOF", "OPT"]):
                        is_header = True
                    
                    if is_header:
                        first_token = parts[0]
                        # If first token is a contract month (e.g. JUN26), check the next token
                        first_cleaned = re.sub(r'[^A-Z0-9]', '', first_token.upper())
                        if re.match(r'^[A-Z]{3}\d{2}$', first_cleaned) and len(parts) > 1:
                            token_to_check = parts[1]
                        else:
                            token_to_check = first_token
                            
                        option_code = re.sub(r'[^A-Z0-9]', '', token_to_check.upper())
                        # Length 2-5, ignore PGxx, FOR, TOTAL, RTO, and contract months
                        if (2 <= len(option_code) <= 5) and not option_code.startswith("PG") and option_code not in ["FOR", "TOTAL", "RTO"] and not re.match(r'^[A-Z]{3}\d{2}$', option_code):
                            current_option_type = option_code
                            
                    if currency in ['XAU', 'BTC', 'ETH'] and is_header:
                        if "CALL" in line_upper:
                            is_call_state = True
                        elif "PUT" in line_upper:
                            is_call_state = False
                        else:
                            is_call_state = None
                            
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
                elif currency in ['XAU', 'NAS', 'NQ', 'BTC', 'ETH']:
                    pass
                else:
                    strike /= 1000.0
                    
                # Find Delta index (scanning from right to left to avoid Open/High/Low prices)
                # Note: Delta must start with a dot or 0. to avoid matching whole number volume/OI (e.g. 253)
                delta_idx = -1
                for idx in range(len(parts) - 1, 0, -1):
                    part = parts[idx]
                    # Delta is usually a clean decimal like .146 or 0.146.
                    # Avoid Bid/Ask quotes containing letters A/B
                    if (re.match(r'^\.\d{3,4}$', part) or re.match(r'^0\.\d{3,4}$', part)) and not any(c in part for c in ['A', 'B', 'C', 'V', 'K']):
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
                        is_decimal_quoted = False
                        if '.' in clean_part:
                            num_part = re.sub(r'[^\d.]', '', clean_part).strip()
                            if '.' in num_part and len(num_part.split('.')[1]) >= 5:
                                is_decimal_quoted = True

                        settle = raw_settle if is_decimal_quoted else raw_settle / 100.0
                    elif currency == 'XAU':
                        settle = raw_settle
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
                    "Is_Call": is_call_state,
                    "Contract_Month": current_contract_month,
                    "Option_Type": current_option_type
                })
                
    return pd.DataFrame(data)
