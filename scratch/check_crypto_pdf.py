import pdfplumber
import re

pdf_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data\Section74_Cryptocurrency.pdf"

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text()
        if not text:
            continue
        print(f"--- Page {page_num+1} ---")
        lines = text.split("\n")
        for line in lines[:15]:  # print first 15 lines of each page to see headers
            print(line)
