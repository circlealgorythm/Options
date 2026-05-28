import pdfplumber

def dump_page39():
    with pdfplumber.open("Section39_Euro_FX_And_Cme$Index_Options.pdf") as pdf:
        # Выведем полностью 3-ю и 4-ю страницы
        for p_idx in [2, 3]:
            page = pdf.pages[p_idx]
            print(f"\n================ PAGE {p_idx+1} ================")
            print(page.extract_text())

if __name__ == "__main__":
    dump_page39()
