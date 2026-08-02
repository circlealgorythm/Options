import os
import shutil
import glob

appdata = os.environ.get('APPDATA')
mt5_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')

source_mq5 = r'C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_Indicator.mq5'
source_ex5 = r'C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_Indicator.ex5'

if os.path.exists(mt5_dir):
    try:
        for folder in os.listdir(mt5_dir):
            indicators_dir = os.path.join(mt5_dir, folder, 'MQL5', 'Indicators')
            if os.path.isdir(indicators_dir):
                try:
                    shutil.copy2(source_mq5, indicators_dir)
                    shutil.copy2(source_ex5, indicators_dir)
                    print(f"Copied files to {indicators_dir}")
                except Exception as e:
                    print(f"Error copying to {indicators_dir}: {e}")
    except Exception as e:
        print(f"Error listing {mt5_dir}: {e}")
else:
    print(f"MT5 Terminal directory not found: {mt5_dir}")

# Also check Program Files just in case it is in portable mode
for pf in [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]:
    if pf:
        for path in glob.glob(os.path.join(pf, '*', 'MQL5', 'Indicators')):
            try:
                shutil.copy2(source_mq5, path)
                shutil.copy2(source_ex5, path)
                print(f"Copied files to {path}")
            except Exception as e:
                pass
