import os

main_py_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\main.py"
with open(main_py_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# find where def copy_csv_to_mt5 starts and where def cleanup_old_files starts
start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if line.startswith('def copy_csv_to_mt5'):
        start_idx = i
    if line.startswith('def cleanup_old_files'):
        end_idx = i
        break

new_lines = lines[:start_idx]
new_lines.append("def copy_csv_to_mt5(csv_path, mt5_gex_dir=None):\n")
new_lines.append("    import shutil\n")
new_lines.append("    import os\n")
new_lines.append("    filename = os.path.basename(csv_path)\n")
new_lines.append("    sub_dir = ''\n")
new_lines.append("    if 'XAU' in filename:\n")
new_lines.append("        sub_dir = 'XAU'\n")
new_lines.append("    elif 'NAS' in filename or 'SPX' in filename:\n")
new_lines.append("        sub_dir = 'NAS100'\n")
new_lines.append("    elif 'BTC' in filename or 'ETH' in filename:\n")
new_lines.append("        sub_dir = 'Crypto'\n")
new_lines.append("    elif 'USDCAD' in filename or 'CAD' in filename:\n")
new_lines.append("        sub_dir = 'USDCAD'\n")
new_lines.append("    paths_to_check = [\n")
new_lines.append("        r'C:\\Program Files',\n")
new_lines.append("        r'C:\\Program Files (x86)',\n")
new_lines.append("        os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')\n")
new_lines.append("    ]\n")
new_lines.append("    for base in paths_to_check:\n")
new_lines.append("        if not os.path.exists(base):\n")
new_lines.append("            continue\n")
new_lines.append("        for root, dirs, files in os.walk(base):\n")
new_lines.append("            if 'MQL5' in dirs:\n")
new_lines.append("                files_gex_dir = os.path.join(root, 'MQL5', 'Files', 'GEX', sub_dir)\n")
new_lines.append("                os.makedirs(files_gex_dir, exist_ok=True)\n")
new_lines.append("                try:\n")
new_lines.append("                    shutil.copy2(csv_path, files_gex_dir)\n")
new_lines.append("                    print(f'Copied {filename} to {files_gex_dir}')\n")
new_lines.append("                except Exception as e:\n")
new_lines.append("                    pass\n")
new_lines.append("                dirs.remove('MQL5')\n")
new_lines.append("\n")

new_lines.extend(lines[end_idx:])

with open(main_py_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed main.py copy logic!")
