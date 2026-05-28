import pandas as pd
import os

DATA_DIR = r"c:\Users\circlealgorythm\.antigravity\bot_grid\data"
gbp_call_section = os.path.join(DATA_DIR, "Section27_British_Pound_Call_Options.pdf")
gbp_put_section = os.path.join(DATA_DIR, "Section28_British_Pound_Put_Options.pdf")

import sys
sys.path.insert(0, r"c:\Users\circlealgorythm\.antigravity\bot_grid")
from src.parser import parse_cme_pdf

gbp_calls = parse_cme_pdf(gbp_call_section, "GBP", is_call_only=True)
gbp_puts = parse_cme_pdf(gbp_put_section, "GBP", is_call_only=False)
gbp_raw = pd.concat([gbp_calls, gbp_puts]).reset_index(drop=True)

print("gbp_raw columns:", gbp_raw.columns)
print("gbp_raw count:", len(gbp_raw))

# Filter for strike 1.3550
strike_1_355 = gbp_raw[gbp_raw['Strike'] == 1.355]
print("Strike 1.3550 raw rows:")
print(strike_1_355)
