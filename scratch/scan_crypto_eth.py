import pdfplumber

pdf_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data\Section74_Cryptocurrency.pdf"

eth_mentions = []
with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "ETH" in text or "ETHER" in text.upper() or "MET" in text:
            eth_mentions.append((page_num + 1, text))

print(f"Found mentions on {len(eth_mentions)} pages.")
for page_num, text in eth_mentions:
    print(f"\n================ Page {page_num} ================")
    # Print lines that contain ETH or ETHER or MET
    for line in text.split("\n"):
        if any(w in line.upper() for w in ["ETH", "ETHER", "MET"]):
            print(line[:100])
