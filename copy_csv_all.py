import os
import shutil
import glob

data_dir = r'C:\Users\circlealgorythm\.antigravity\bot_grid\data'

paths_to_check = [
    r'C:\Program Files',
    r'C:\Program Files (x86)',
    r'C:\Users\circlealgorythm\AppData\Roaming\MetaQuotes\Terminal'
]

found_any = False
for base in paths_to_check:
    if not os.path.exists(base):
        continue
    for root, dirs, files in os.walk(base):
        if 'MQL5' in dirs:
            files_gex_dir = os.path.join(root, 'MQL5', 'Files', 'GEX')
            
            # Create the directory if it doesn't exist
            os.makedirs(files_gex_dir, exist_ok=True)
            
            print(f"Found MT5 GEX folder: {files_gex_dir}")
            
            # Copy all CSV files from bot_grid\data to Files\GEX
            for csv_file in glob.glob(os.path.join(data_dir, '*.csv')):
                try:
                    shutil.copy2(csv_file, files_gex_dir)
                except Exception as e:
                    print(f"-> Error copying {csv_file}: {e}")
                    
            print(f"-> Successfully copied CSVs to {files_gex_dir}")
            found_any = True
            
            # Don't recurse into MQL5 itself
            dirs.remove('MQL5')

if not found_any:
    print("Could not find any MQL5/Files/GEX folders.")
