import os
import shutil

csv_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data\GEX_SPXUSD_2026-06-11.csv"
paths_to_check = [
    r'C:\Program Files',
    r'C:\Program Files (x86)',
    os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
]

for base in paths_to_check:
    if not os.path.exists(base):
        continue
    for root, dirs, files in os.walk(base):
        if 'MQL5' in dirs:
            files_gex_dir = os.path.join(root, 'MQL5', 'Files', 'GEX', 'NAS100')
            os.makedirs(files_gex_dir, exist_ok=True)
            try:
                shutil.copy2(csv_path, files_gex_dir)
                print(f'Force copied to {files_gex_dir}')
            except Exception as e:
                print(e)
            dirs.remove('MQL5')
