import os
import re
import datetime
from email.utils import parsedate_to_datetime
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

MONTH_NUM_TO_CODE = {v: k for k, v in MONTH_NAME_MAP.items()}

def month_code_from_yyyymm00(token: str):
    if not re.match(r'^20\d{6}$', token):
        return None
    month_num = int(token[4:6])
    month_code = MONTH_NUM_TO_CODE.get(month_num)
    if month_code is None:
        return None
    return f"{month_code}{token[2:4]}"

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
            last_modified = response.headers.get("last-modified")
            if last_modified:
                try:
                    modified_dt = parsedate_to_datetime(last_modified)
                    os.utime(dest_path, (modified_dt.timestamp(), modified_dt.timestamp()))
                except (TypeError, ValueError, OSError):
                    pass
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

def extract_oi(parts):
    idx = len(parts) - 1
    # 1. Skip contract high/low if present (at most 2 columns)
    skipped_range = 0
    while idx >= 0 and skipped_range < 2:
        val = parts[idx]
        if val == "----" or "." in val:
            idx -= 1
            skipped_range += 1
        else:
            break
            
    # 2. Skip OI Change
    if idx >= 0:
        val = parts[idx]
        if val in ["UNCH", "UNCHANGE", "UNCHANGED", "----"]:
            idx -= 1
        elif val.isdigit():
            if idx > 0 and parts[idx - 1] in ["+", "-"]:
                idx -= 2
        elif any(sign in val for sign in ["+", "-"]):
            idx -= 1
            
    # 3. Open Interest
    if idx >= 0:
        val = parts[idx]
        cleaned = re.sub(r'\D', '', val)
        if cleaned:
            return int(cleaned)
    return 0


def extract_delta(parts, settle_idx):
    """Extract delta after the settlement-change field in a bulletin row."""
    if settle_idx < 0 or settle_idx + 1 >= len(parts):
        return 0.0

    cursor = settle_idx + 1
    if parts[cursor] in {"+", "-"}:
        # Some text layers split a point change into sign and magnitude.
        cursor += 2
    else:
        # Native rows use an integer change; decimal-quote duplicate pages use
        # a signed decimal. Neither field is delta.
        cursor += 1

    for delta_token in parts[cursor:cursor + 2]:
        clean_delta = re.sub(r'[AB+\-*]', '', delta_token)
        if '.' not in clean_delta:
            continue
        try:
            candidate_delta = float(clean_delta)
        except ValueError:
            continue
        if 0.0 <= candidate_delta <= 1.0:
            return candidate_delta
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

                if currency in ['NAS', 'NQ'] and len(parts) >= 3 and parts[2].upper() == 'MID':
                    numeric_month = month_code_from_yyyymm00(parts[0].upper())
                    if numeric_month:
                        current_contract_month = numeric_month
                        current_option_type = re.sub(r'[^A-Z0-9]', '', parts[1].upper())
                        is_call_state = False
                        continue
                    
                # Look for section headers indicating option type and contract month
                if not parts[0].isdigit():
                    line_upper = line.upper()
                    if "BULLETIN" in line_upper:
                        continue

                    # NASDAQ MID tables are split into a month-code call block
                    # (e.g. "JUN26 QWW MID") and a numeric-date put block
                    # (e.g. "20260600 QWW MID"). Preserve both sides.
                    if currency in ['NAS', 'NQ'] and len(parts) >= 3 and parts[2].upper() == 'MID':
                        first = parts[0].upper()
                        second = re.sub(r'[^A-Z0-9]', '', parts[1].upper())
                        numeric_month = month_code_from_yyyymm00(first)
                        if numeric_month and second:
                            current_contract_month = numeric_month
                            current_option_type = second
                            is_call_state = False
                            continue
                        if re.match(r'^[A-Z]{3}\d{2}$', first) and second:
                            current_contract_month = first
                            current_option_type = second
                            is_call_state = True
                            continue
                        
                    is_header = False
                    if any(kw in line_upper for kw in ["CALL", "PUT", "OPTIONS", "OPTION", "OOF", "OPT"]):
                        is_header = True
                    elif re.match(r'^[A-Z]{3}\d{2}$', parts[0].upper()) and len(parts) >= 2 and re.match(r'^[A-Z]', parts[1]):
                        is_header = True
                    elif len(parts) >= 3 and parts[-1].upper() in ['C', 'P']:
                        is_header = True
                    
                    if is_header:
                        # Extract option code from header (handle parent-child codes e.g. GBU OPT - 2BP)
                        header_line_clean = re.sub(r'\(.*?\)', '', line)
                        if "-" in header_line_clean:
                            sub_parts = header_line_clean.split("-")
                            if len(sub_parts) > 1:
                                tail_tokens = sub_parts[-1].strip().split()
                                if tail_tokens:
                                    token = tail_tokens[0]
                                    candidate = re.sub(r'[^A-Z0-9]', '', token.upper())
                                    if candidate and not candidate.isdigit():
                                        option_code = candidate
                                    else:
                                        # Numeric tail (e.g. "100" from "NASDAQ-100") — fall back to first token
                                        fb_parts = header_line_clean.split()
                                        if fb_parts:
                                            fb0 = re.sub(r'[^A-Z0-9]', '', fb_parts[0].upper())
                                            if re.match(r'^[A-Z]{3}\d{2}$', fb0) and len(fb_parts) > 1:
                                                option_code = re.sub(r'[^A-Z0-9]', '', fb_parts[1].upper())
                                            else:
                                                option_code = fb0
                        else:
                            clean_parts = header_line_clean.split()
                            if clean_parts:
                                first_token = clean_parts[0]
                                first_cleaned = re.sub(r'[^A-Z0-9]', '', first_token.upper())
                                if re.match(r'^[A-Z]{3}\d{2}$', first_cleaned) and len(clean_parts) > 1:
                                    token_to_check = clean_parts[1]
                                else:
                                    token_to_check = first_token
                                option_code = re.sub(r'[^A-Z0-9]', '', token_to_check.upper())
                            else:
                                option_code = ""
                        
                        if (2 <= len(option_code) <= 5) and not option_code.startswith("PG") and option_code not in ["FOR", "TOTAL", "RTO"] and not re.match(r'^[A-Z]{3}\d{2}$', option_code):
                            current_option_type = option_code
                            
                    if is_header:
                        if "CALL" in line_upper and "PUT" in line_upper:
                            is_call_state = None
                        elif "CALL" in line_upper:
                            is_call_state = True
                        elif "PUT" in line_upper:
                            is_call_state = False
                        elif parts[-1].upper() == 'C':
                            is_call_state = True
                        elif parts[-1].upper() == 'P':
                            is_call_state = False
                            
                    if "EXPIRATION" not in line_upper:
                        for p in parts:
                            if re.match(r'^[A-Z]{3}\d{2}$', p):
                                current_contract_month = p
                                break
                    continue
                    
                if len(parts) < 8:
                    continue
                    
                strike_raw = parts[0]
                strike = float(strike_raw)
                if currency in ['EUR', 'CAD']:
                    strike /= 10000.0
                elif currency in ['XAU', 'NAS', 'NQ', 'BTC', 'SPX']:
                    pass
                else:
                    strike /= 1000.0
                
                # Robust Settle Price Extraction
                settle = 0.0
                settle_str = "0.0"
                settle_idx = -1
                for i_idx in range(4, min(7, len(parts))):
                    token = parts[i_idx]
                    if '/' not in token and any(c.isdigit() for c in token):
                        settle_str = token
                        settle_idx = i_idx
                        break
                
                if settle_str != "0.0":
                    is_glued = False
                    for sign in ['-', '+']:
                        if sign in settle_str and settle_str.index(sign) > 0:
                            is_glued = True
                            parts_split = settle_str.split(sign)
                            settle_str = parts_split[0]
                            break
                    clean_settle = re.sub(r'[BA\+\-\*]', '', settle_str).strip()
                    try:
                        raw_settle = float(clean_settle)
                    except:
                        raw_settle = 0.0
                        
                    if currency == 'EUR':
                        is_decimal_quoted = False
                        if '.' in clean_settle:
                            num_part = re.sub(r'[^\d.]', '', clean_settle).strip()
                            if '.' in num_part and len(num_part.split('.')[1]) >= 5:
                                is_decimal_quoted = True
                        settle = raw_settle if is_decimal_quoted else raw_settle / 1000.0
                    elif currency in ['GBP', 'CAD']:
                        is_decimal_quoted = False
                        if '.' in clean_settle:
                            num_part = re.sub(r'[^\d.]', '', clean_settle).strip()
                            if '.' in num_part and len(num_part.split('.')[1]) >= 5:
                                is_decimal_quoted = True
                        settle = raw_settle if is_decimal_quoted else raw_settle / 100.0
                    else:
                        settle = raw_settle
                        
                # Robust Open Interest Extraction
                oi = extract_oi(parts)
                
                # Robust Delta Extraction
                delta = extract_delta(parts, settle_idx)
                                
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
