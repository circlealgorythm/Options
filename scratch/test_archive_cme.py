from curl_cffi import requests

def check_url(url):
    try:
        r = requests.head(url, impersonate="chrome120", allow_redirects=True, timeout=5)
        print(f"HEAD {url} -> Status: {r.status_code}")
        if r.status_code == 200:
            print("FOUND!!!")
            return True
    except Exception as e:
        print(f"Error {url}: {e}")
    return False

def test_archive():
    date_str1 = "20260506"
    date_str2 = "260506"
    date_str3 = "2026-05-06"
    
    # Возможные паттерны URL
    patterns = [
        # 1. С папкой даты в разном формате
        f"https://www.cmegroup.com/daily_bulletin/archive/2026/05/06/Section39_Euro_FX_And_Cme$Index_Options.pdf",
        f"https://www.cmegroup.com/daily_bulletin/archive/2026/05/Section39_Euro_FX_And_Cme$Index_Options.pdf",
        f"https://www.cmegroup.com/daily_bulletin/archive/{date_str3}/Section39_Euro_FX_And_Cme$Index_Options.pdf",
        f"https://www.cmegroup.com/daily_bulletin/{date_str3}/Section39_Euro_FX_And_Cme$Index_Options.pdf",
        f"https://www.cmegroup.com/daily_bulletin/{date_str1}/Section39_Euro_FX_And_Cme$Index_Options.pdf",
        
        # 2. С суффиксом даты в имени файла
        f"https://www.cmegroup.com/daily_bulletin/archive/Section39_Euro_FX_And_Cme$Index_Options_{date_str1}.pdf",
        f"https://www.cmegroup.com/daily_bulletin/archive/Section39_Euro_FX_And_Cme$Index_Options_{date_str3}.pdf",
        f"https://www.cmegroup.com/daily_bulletin/current/Section39_Euro_FX_And_Cme$Index_Options_{date_str1}.pdf",
        f"https://www.cmegroup.com/daily_bulletin/current/Section39_Euro_FX_And_Cme$Index_Options_{date_str3}.pdf",
        
        # 3. В старом ftp-пути (на всякий случай)
        f"https://www.cmegroup.com/ftp/bulletin/archive/2026/05/06/PG38.pdf",
        f"https://www.cmegroup.com/ftp/bulletin/archive/2026/05/PG38.pdf",
        f"https://www.cmegroup.com/ftp/bulletin/PG38_{date_str1}.pdf",
        f"https://www.cmegroup.com/ftp/bulletin/PG38_{date_str3}.pdf",
    ]
    
    for url in patterns:
        if check_url(url):
            return url
    print("No archive URLs found.")
    return None

if __name__ == "__main__":
    test_archive()
