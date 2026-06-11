import os

main_py_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\main.py"
with open(main_py_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:138] # Keep up to line 138 (0-indexed 137)
new_lines.append("def copy_csv_to_mt5(csv_path, mt5_gex_dir=None):\n")
new_lines.append("    import shutil\n")
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
new_lines.append("                files_gex_dir = os.path.join(root, 'MQL5', 'Files', 'GEX')\n")
new_lines.append("                os.makedirs(files_gex_dir, exist_ok=True)\n")
new_lines.append("                try:\n")
new_lines.append("                    shutil.copy2(csv_path, files_gex_dir)\n")
new_lines.append("                    print(f'Copied {os.path.basename(csv_path)} to {files_gex_dir}')\n")
new_lines.append("                except Exception as e:\n")
new_lines.append("                    pass\n")
new_lines.append("                dirs.remove('MQL5')\n")
new_lines.append("\n")

# Now append lines from 153 onwards (0-indexed 152)
new_lines.extend(lines[152:])

with open(main_py_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed main.py!")
