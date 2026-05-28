from curl_cffi import requests

def test_cffi():
    url = "https://www.cmegroup.com/"
    print(f"Downloading {url} using curl_cffi (impersonate='chrome120')...")
    try:
        response = requests.get(url, impersonate="chrome120", timeout=15)
        print("Status code:", response.status_code)
        print("Content preview:", response.text[:200])
        return True
    except Exception as e:
        print("Error:", e)
        return False

if __name__ == "__main__":
    test_cffi()
