import os
import shutil

source_mq5 = r'C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_Indicator.mq5'
source_ex5 = r'C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_Indicator.ex5'

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
        # We don't want to go too deep, but we need to find MQL5/Indicators
        if 'MQL5' in dirs:
            ind_path = os.path.join(root, 'MQL5', 'Indicators')
            if os.path.exists(ind_path):
                print(f"Found MT5 Indicators folder: {ind_path}")
                try:
                    shutil.copy2(source_mq5, ind_path)
                    shutil.copy2(source_ex5, ind_path)
                    print(f"-> Successfully copied to {ind_path}")
                    found_any = True
                except Exception as e:
                    print(f"-> Error: {e}")
            # Don't recurse into MQL5 itself
            dirs.remove('MQL5')

if not found_any:
    print("Could not find any MQL5/Indicators folders.")
