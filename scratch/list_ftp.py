from ftplib import FTP

def list_ftp():
    host = "ftp.cmegroup.com"
    try:
        ftp = FTP(host)
        ftp.login()
        print("Connected.")
        
        print("Current directory:", ftp.pwd())
        
        # Получаем список файлов/папок
        items = []
        ftp.dir(items.append)
        print("\n".join(items[:50]))
        
        # Попробуем зайти в папку bulletin, если она есть
        print("\nChecking 'bulletin' folder:")
        try:
            ftp.cwd("bulletin")
            print("Successfully entered 'bulletin'. Contents:")
            bulletin_items = []
            ftp.dir(bulletin_items.append)
            print("\n".join(bulletin_items[:50]))
        except Exception as e:
            print("Failed to enter 'bulletin':", e)
            
        ftp.quit()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    list_ftp()
