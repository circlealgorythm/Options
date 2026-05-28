import os
import re
import datetime
import pandas as pd
import pdfplumber
from curl_cffi import requests
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

def clean_value(val):
    if not val or val == "----" or val == "CAB":
        return 0.0
    cleaned = re.sub(r'[BA\+\-\*]', '', val).strip()
    try:
        return float(cleaned)
    except:
        return 0.0

def parse_pdf(file_path, currency, is_call_only=None):
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

def run_test():
    eur_raw = parse_pdf("Section39_Euro_FX_And_Cme$Index_Options.pdf", "EUR", None)
    
    # Определяем спот по дельте около 0.5
    atm_rows = eur_raw[(eur_raw['Delta'] >= 0.45) & (eur_raw['Delta'] <= 0.55)]
    spot = atm_rows['Strike'].mean() if not atm_rows.empty else 1.1700
    print(f"Detected EUR Spot: {spot:.4f}")
    
    T = 0.08
    r = 0.0
    contract_size = 125000
    
    results = []
    for idx, row in eur_raw.iterrows():
        K = row['Strike']
        
        # Определяем Call это или Put
        if row['Is_Call'] is not None:
            is_call = row['Is_Call']
        else:
            # Правило дельты относительно Spot
            if K < spot:
                is_call = (row['Delta'] >= 0.5)
            else:
                is_call = (row['Delta'] < 0.5)
                
        # Рассчитываем GEX
        if is_call:
            iv = implied_volatility(row['Settle'], spot, K, T, r, 'C')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = row['OI']
            put_oi = 0
        else:
            iv = implied_volatility(row['Settle'], spot, K, T, r, 'P')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = -calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = 0
            put_oi = row['OI']
            
        results.append({
            "Strike": K,
            "GEX": gex,
            "Abs_Gamma": abs_gamma,
            "Call_OI": call_oi,
            "Put_OI": put_oi
        })
        
    df = pd.DataFrame(results)
    
    # Теперь группируем по страйку и суммируем!
    summary = df.groupby('Strike').agg({
        'GEX': 'sum',
        'Abs_Gamma': 'sum',
        'Call_OI': 'sum',
        'Put_OI': 'sum'
    }).reset_index()
    
    summary.rename(columns={'GEX': 'Total_GEX', 'Abs_Gamma': 'Total_Abs_Gamma'}, inplace=True)
    summary['Currency'] = 'EUR'
    
    # Выведем строки около спота
    near_spot = summary[(summary['Strike'] >= spot - 0.02) & (summary['Strike'] <= spot + 0.02)]
    print("\nSummary near Spot:")
    print(near_spot.to_string(index=False))

if __name__ == "__main__":
    run_test()
