import os
import glob
from main import copy_csv_to_mt5

data_dir = r"C:\Users\circlealgorythm\.antigravity\bot_grid\data"
for csv_file in glob.glob(os.path.join(data_dir, "*.csv")):
    copy_csv_to_mt5(csv_file)
