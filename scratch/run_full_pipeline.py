import os
import re
import datetime
import numpy as np
import pandas as pd
import pdfplumber
from curl_cffi import requests
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

def download_section(section_name, dest_dir):
    url = f"https://www.cmegroup.com/daily_bulletin/current/{section_name}"
    dest_path = os.path.join(dest_dir, section_name)
    print(f"Downloading {url}...")
    try:
        r = requests.get(url, impersonate="chrome120", timeout=15)
        if r.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(r.content)
            print(f"Downloaded {section_name} ({len(r.content)} bytes)")
            return True
        else:
            print(f"Failed download {section_name}. Status: {r.status_code}")
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

def parse_pdf(file_path, currency, is_call_only=None):
    """
    is_call_only: True for Call-only files, False for Put-only, None for mixed (EUR)
    """
    data = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
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
                    
                # Ищем дельту
                delta_idx = -1
                for idx, part in enumerate(parts):
                    if re.match(r'^\.?\d{3}$', part) or re.match(r'^0\.\d{3}$', part):
                        delta_idx = idx
                        break
                if delta_idx == -1:
                    continue
                    
                delta = clean_value(parts[delta_idx])
                
                # Ищем Settle
                settle = 0.0
                for idx in range(delta_idx - 1, 0, -1):
                    part = parts[idx]
                    if '.' in part or part in ['CAB', '----'] or ('-' in part and len(part) > 1 and '.' in part) or ('+' in part and len(part) > 1 and '.' in part):
                        settle = clean_value(part)
                        break
                
                # Ищем OI
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
                    "Is_Call": is_call_only
                })
    return pd.DataFrame(data)

def process_currency_data(df, currency):
    """
    Группирует и разделяет Call/Put
    """
    if df.empty:
        return pd.DataFrame()
        
    if currency == 'GBP':
        # Для GBP у нас изначально размеченные строки
        calls = df[df['Is_Call'] == True]
        puts = df[df['Is_Call'] == False]
        
        # Группируем по страйку и суммируем OI, берем максимальный Settle
        calls_grp = calls.groupby('Strike').agg({'Settle': 'max', 'OI': 'sum'}).reset_index()
        calls_grp.rename(columns={'Settle': 'Call_Settle', 'OI': 'Call_OI'}, inplace=True)
        
        puts_grp = puts.groupby('Strike').agg({'Settle': 'max', 'OI': 'sum'}).reset_index()
        puts_grp.rename(columns={'Settle': 'Put_Settle', 'OI': 'Put_OI'}, inplace=True)
        
        merged = pd.merge(calls_grp, puts_grp, on='Strike', how='outer').fillna(0.0)
        merged['Currency'] = 'GBP'
        return merged
        
    else: # EUR
        # Нам нужно разделить по дельте относительно Spot.
        # Определяем Spot: средний страйк у строк с дельтой около 0.5
        atm_rows = df[(df['Delta'] >= 0.45) & (df['Delta'] <= 0.55)]
        if not atm_rows.empty:
            spot = atm_rows['Strike'].mean()
        else:
            spot = 1.1500 # дефолтный спот
            
        print(f"Auto-detected EUR Spot: {spot:.4f}")
        
        # Группируем по страйку
        grouped = df.groupby('Strike')
        processed_rows = []
        
        for strike, group in grouped:
            if len(group) == 1:
                row = group.iloc[0]
                d = row['Delta']
                is_call = False
                if strike < spot:
                    is_call = (d >= 0.5)
                else:
                    is_call = (d < 0.5)
                
                if is_call:
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": row['Settle'], "Call_OI": row['OI'],
                        "Put_Settle": 0.0, "Put_OI": 0
                    })
                else:
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": 0.0, "Call_OI": 0,
                        "Put_Settle": row['Settle'], "Put_OI": row['OI']
                    })
            else:
                # Если две или более строк (обычно две)
                sorted_group = group.sort_values(by='Delta') # от меньшей дельты к большей
                r_low = sorted_group.iloc[0] # меньшая дельта
                r_high = sorted_group.iloc[-1] # большая дельта
                
                if strike < spot:
                    # Меньшая дельта - Put, большая - Call
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": r_high['Settle'], "Call_OI": r_high['OI'],
                        "Put_Settle": r_low['Settle'], "Put_OI": r_low['OI']
                    })
                else:
                    # Меньшая дельта - Call, большая - Put
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": r_low['Settle'], "Call_OI": r_low['OI'],
                        "Put_Settle": r_high['Settle'], "Put_OI": r_high['OI']
                    })
                    
        res_df = pd.DataFrame(processed_rows)
        res_df['Currency'] = 'EUR'
        return res_df

def run_pipeline():
    today = datetime.date.today().strftime("%Y-%m-%d")
    tmp_dir = "."
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    
    # 1. Скачивание
    download_section("Section39_Euro_FX_And_Cme$Index_Options.pdf", tmp_dir)
    download_section("Section27_British_Pound_Call_Options.pdf", tmp_dir)
    download_section("Section28_British_Pound_Put_Options.pdf", tmp_dir)
    
    # 2. Парсинг
    eur_raw = parse_pdf("Section39_Euro_FX_And_Cme$Index_Options.pdf", "EUR", None)
    gbp_calls_raw = parse_pdf("Section27_British_Pound_Call_Options.pdf", "GBP", True)
    gbp_puts_raw = parse_pdf("Section28_British_Pound_Put_Options.pdf", "GBP", False)
    
    # 3. Обработка и группировка
    eur_clean = process_currency_data(eur_raw, "EUR")
    gbp_clean = process_currency_data(pd.concat([gbp_calls_raw, gbp_puts_raw]), "GBP")
    
    # 4. Расчет GEX
    T = 0.08
    r = 0.0
    
    for df, curr in [(eur_clean, 'EUR'), (gbp_clean, 'GBP')]:
        if df.empty:
            continue
            
        # Определяем спот из страйков ATM для расчета блэка-шоулза
        spot = df['Strike'].mean() # грубое приближение для расчетов БШ
        contract_size = 125000 if curr == 'EUR' else 62500
        
        results = []
        for idx, row in df.iterrows():
            K = row['Strike']
            
            # Call GEX
            iv_call = implied_volatility(row['Call_Settle'], spot, K, T, r, 'C')
            gamma_call = bs_gamma(spot, K, T, r, iv_call)
            gex_call = calculate_gex(gamma_call, row['Call_OI'], contract_size, spot)
            abs_gamma_call = calculate_absolute_gamma(gamma_call, row['Call_OI'])
            
            # Put GEX
            iv_put = implied_volatility(row['Put_Settle'], spot, K, T, r, 'P')
            gamma_put = bs_gamma(spot, K, T, r, iv_put)
            gex_put = -calculate_gex(gamma_put, row['Put_OI'], contract_size, spot)
            abs_gamma_put = calculate_absolute_gamma(gamma_put, row['Put_OI'])
            
            results.append({
                "Strike": K,
                "Total_GEX": gex_call + gex_put,
                "Total_Abs_Gamma": abs_gamma_call + abs_gamma_put,
                "Call_OI": row['Call_OI'],
                "Put_OI": row['Put_OI']
            })
            
        res_df = pd.DataFrame(results)
        out_file = os.path.join(data_dir, f"GEX_{curr}USD_{today}.csv")
        res_df.to_csv(out_file, index=False)
        print(f"Successfully saved {len(res_df)} rows to {out_file}")

if __name__ == "__main__":
    run_pipeline()
