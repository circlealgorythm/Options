import pdfplumber
import os

DATA_DIR = r"c:\Users\circlealgorythm\.antigravity\bot_grid\data"
pdf_call = os.path.join(DATA_DIR, "Section47_E_Mini_S_And_P_500_Call_Options.pdf")
pdf_put = os.path.join(DATA_DIR, "Section48_E_Mini_S_And_P_500_Put_Options.pdf")

def print_page_top(pdf_path, page_num, name):
    print(f"\n--- {name} Page {page_num} top 15 lines ---")
    with pdfplumber.open(pdf_path) as pdf:
        if page_num <= len(pdf.pages):
            page = pdf.pages[page_num - 1]
            text = page.extract_text() or ""
            lines = text.split('\n')
            for k in range(min(15, len(lines))):
                print(f"  {k+1}: {lines[k]}")
        else:
            print("Page out of range")

print_page_top(pdf_call, 33, "SPX Call")
print_page_top(pdf_call, 34, "SPX Call")
print_page_top(pdf_call, 35, "SPX Call")
print_page_top(pdf_put, 53, "SPX Put")
print_page_top(pdf_put, 54, "SPX Put")
