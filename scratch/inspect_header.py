import pdfplumber

def inspect_header():
    with pdfplumber.open("Section39_Euro_FX_And_Cme$Index_Options.pdf") as pdf:
        # Выведем первые 30 строк страницы 4
        page = pdf.pages[3]
        text = page.extract_text()
        lines = text.split("\n")
        print("Page 4 Header Lines:")
        for idx, line in enumerate(lines[:30]):
            print(f"{idx+1:02d}: {line}")

if __name__ == "__main__":
    inspect_header()
