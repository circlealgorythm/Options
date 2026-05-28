import pdfplumber

def find_headers():
    with pdfplumber.open("Section39_Euro_FX_And_Cme$Index_Options.pdf") as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            # Ищем подстроки CALL и PUT (регистронезависимо)
            calls = [m.start() for m in re.finditer(r'CALL', text, re.IGNORECASE)]
            puts = [m.start() for m in re.finditer(r'PUT', text, re.IGNORECASE)]
            
            # Посмотрим, есть ли слова "CALL OPTIONS" или "PUT OPTIONS" или "CALLS" или "PUTS"
            print(f"Page {idx+1}:")
            lines = text.split("\n")
            for line in lines:
                if any(x in line.upper() for x in ["CALL", "PUT", "OPTION"]):
                    # Но отфильтруем просто "OPTIONS" в шапке
                    if "EURO FX" in line.upper() or "BRITISH" in line.upper() or "BULLETIN" in line.upper():
                        continue
                    print("  ", line)

import re
if __name__ == "__main__":
    find_headers()
