import os, sys
import pandas as pd

# Add root folder to path
sys.path.append(os.getcwd())

from src.parser import parse_cme_pdf

DATA_DIR = 'data'
eur_raw = parse_cme_pdf(os.path.join(DATA_DIR, 'Section39_Euro_FX_And_Cme$Index_Options.pdf'), 'EUR')
gbp_calls = parse_cme_pdf(os.path.join(DATA_DIR, 'Section27_British_Pound_Call_Options.pdf'), 'GBP', is_call_only=True)
gbp_puts = parse_cme_pdf(os.path.join(DATA_DIR, 'Section28_British_Pound_Put_Options.pdf'), 'GBP', is_call_only=False)
gbp_raw = pd.concat([gbp_calls, gbp_puts])

print('=== EUR RAW ATM ROWS ===')
spot_eur = 1.1726
print(eur_raw[(eur_raw['Strike'] - spot_eur).abs() < 0.005].head(10))

print('=== GBP RAW ATM ROWS ===')
spot_gbp = 1.3431
print(gbp_raw[(gbp_raw['Strike'] - spot_gbp).abs() < 0.005].head(10))
