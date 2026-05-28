import os
from ftplib import FTP

def test_ftp_download():
    host = "ftp.cmegroup.com"
    remote_path = "bulletin/PG38.pdf"
    dest_path = "test_bulletin_ftp.pdf"
    
    print(f"Connecting to FTP {host} anonymously...")
    try:
        ftp = FTP(host)
        ftp.login()  # anonymous login
        print("Logged in successfully. Downloading bulletin...")
        
        # Получаем размер файла
        try:
            size = ftp.size(remote_path)
            print(f"File size: {size} bytes")
        except Exception as e:
            print(f"Could not get size: {e}")
            
        with open(dest_path, 'wb') as f:
            ftp.retrbinary(f"RETR {remote_path}", f.write)
            
        print("Download complete via FTP!")
        ftp.quit()
        return True
    except Exception as e:
        print(f"FTP Error: {e}")
        return False

if __name__ == "__main__":
    test_ftp_download()
