import os
from curl_cffi import requests

def download_file(section_name):
    url = f"https://www.cmegroup.com/daily_bulletin/current/{section_name}"
    print(f"Downloading {url}...")
    try:
        r = requests.get(url, impersonate="chrome120", timeout=15)
        if r.status_code == 200:
            with open(section_name, "wb") as f:
                f.write(r.content)
            print(f"Successfully downloaded {section_name} ({len(r.content)} bytes)")
            return True
        else:
            print(f"Failed to download {section_name}. Status code: {r.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading {section_name}: {e}")
        return False

def test():
    sections = [
        "Section39_Euro_FX_And_Cme$Index_Options.pdf",
        "Section27_British_Pound_Call_Options.pdf",
        "Section28_British_Pound_Put_Options.pdf"
    ]
    for s in sections:
        download_file(s)

if __name__ == "__main__":
    test()
