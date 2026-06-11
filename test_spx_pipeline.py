import os
import datetime
import pandas as pd
from main import download_cme_bulletin, extract_bulletin_date, parse_cme_pdf, calculate_gex_pipeline

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

sp_call_section = "Section47_E_Mini_S_And_P_500_Call_Options.pdf"
sp_put_section = "Section48_E_Mini_S_And_P_500_Put_Options.pdf"

sp_call_dest = os.path.join(DATA_DIR, sp_call_section)
sp_put_dest = os.path.join(DATA_DIR, sp_put_section)

sp_call_ok = download_cme_bulletin(sp_call_section, sp_call_dest)
sp_put_ok = download_cme_bulletin(sp_put_section, sp_put_dest)

if sp_call_ok and sp_put_ok:
    try:
        sp_bulletin_date = extract_bulletin_date(sp_call_dest) or extract_bulletin_date(sp_put_dest) or datetime.date.today()
        session_date = datetime.date.today()
        print(f"[SPX] CME bulletin trade date: {sp_bulletin_date}; session date: {session_date}")
        sp_calls = parse_cme_pdf(sp_call_dest, "SPX", is_call_only=True)
        sp_puts = parse_cme_pdf(sp_put_dest, "SPX", is_call_only=False)
        sp_raw = pd.concat([sp_calls, sp_puts])
        if not sp_raw.empty:
            sp_raw = sp_raw[sp_raw['Strike'] >= 2000.0]
        print("SPX Raw rows:", len(sp_raw))
        calculate_gex_pipeline(sp_raw, "SPX", DATA_DIR, session_date)
    except Exception as e:
        print(f"[SPX] Error during processing: {e}")
