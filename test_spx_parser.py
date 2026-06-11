import pandas as pd
from src.parser import parse_cme_pdf

pdf_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data\Section47_E_Mini_S_And_P_500_Call_Options.pdf"
df = parse_cme_pdf(pdf_path, "SPX", is_call_only=True)
print(f"Parsed rows: {len(df)}")
if not df.empty:
    print(df.head(10))
    print(df.tail(10))
