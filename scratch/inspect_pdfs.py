import pdfplumber

def inspect_pdf(file_path):
    print(f"\n================ Inspecting {file_path} ================")
    with pdfplumber.open(file_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        # Посмотрим текст на первой и второй страницах
        for i in range(min(5, len(pdf.pages))):
            text = pdf.pages[i].extract_text()
            if not text:
                continue
            lines = text.split("\n")
            print(f"--- Page {i+1} (first 20 lines) ---")
            for line in lines[:20]:
                print(line)

if __name__ == "__main__":
    inspect_pdf("Section39_Euro_FX_And_Cme$Index_Options.pdf")
    inspect_pdf("Section27_British_Pound_Call_Options.pdf")
