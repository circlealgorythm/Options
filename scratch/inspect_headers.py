with open("scratch/inspect_pdf.py", "w") as f:
    f.write("""
import pdfplumber

with pdfplumber.open("data/Section29_Canadian_Dollar_Call_Options.pdf") as pdf:
    for page_idx, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            lines = text.split('\\n')
            for line in lines:
                if any(kw in line.upper() for kw in ["OPT", "OPTION"]):
                    print(f"Page {page_idx+1}: {line}")
""")
