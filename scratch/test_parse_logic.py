import pdfplumber
import re
import pandas as pd

def clean_value(val):
    if not val or val == "----" or val == "CAB":
        return 0.0
    cleaned = re.sub(r'[BA\+\-\*]', '', val).strip()
    try:
        return float(cleaned)
    except:
        return 0.0

def parse_pdf_test(file_path, currency):
    print(f"\nParsing {file_path} for {currency}...")
    data = []
    
    with pdfplumber.open(file_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split("\n")
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                    
                if not parts[0].isdigit():
                    continue
                    
                strike_raw = parts[0]
                if len(parts) < 8:
                    continue
                    
                strike = float(strike_raw)
                if currency == 'EUR':
                    strike /= 10000.0
                else:
                    strike /= 1000.0
                    
                # Ищем индекс дельты
                delta_idx = -1
                for idx, part in enumerate(parts):
                    if re.match(r'^\.?\d{3}$', part) or re.match(r'^0\.\d{3}$', part):
                        delta_idx = idx
                        break
                        
                if delta_idx == -1:
                    continue
                    
                delta = clean_value(parts[delta_idx])
                
                # Улучшенный поиск Settle:
                # Идем влево от дельты и ищем первый токен, содержащий точку (или CAB / ----),
                # который является ценой settle.
                settle = 0.0
                settle_raw = ""
                for idx in range(delta_idx - 1, 0, -1):
                    part = parts[idx]
                    # Если токен содержит точку или является CAB/----, это и есть наш Settle!
                    if '.' in part or part in ['CAB', '----'] or ('-' in part and len(part) > 1 and '.' in part) or ('+' in part and len(part) > 1 and '.' in part):
                        settle_raw = part
                        settle = clean_value(part)
                        break
                
                # OI - это целое число. Ищем его после дельты
                oi = 0
                for idx in range(delta_idx + 1, len(parts)):
                    part = parts[idx]
                    cleaned = re.sub(r'[A-Z\+\-\*]', '', part).strip()
                    if cleaned.isdigit() and len(cleaned) > 0:
                        oi = int(cleaned)
                        
                data.append({
                    "Strike": strike,
                    "Settle_Raw": settle_raw,
                    "Settle": settle,
                    "Delta": delta,
                    "OI": oi,
                    "Raw_Line": line
                })
                
    df = pd.DataFrame(data)
    print(f"Extracted {len(df)} rows.")
    # Выведем строки, где Settle > 0, для проверки правильности
    active_df = df[df['Settle'] > 0]
    if not active_df.empty:
        print("Sample of active rows:")
        print(active_df[['Strike', 'Settle_Raw', 'Settle', 'Delta', 'OI']].head(15))
    return df

if __name__ == "__main__":
    parse_pdf_test("Section39_Euro_FX_And_Cme$Index_Options.pdf", "EUR")
    parse_pdf_test("Section27_British_Pound_Call_Options.pdf", "GBP")
