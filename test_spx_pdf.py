import pdfplumber
import os

pdf_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data\Section47_E_Mini_S_And_P_500_Call_Options.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for i in range(min(5, len(pdf.pages))):
        text = pdf.pages[i].extract_text()
        if text:
            print(f"--- PAGE {i} ---")
            lines = text.split('\n')
            for line in lines[:20]:
                print(line)
