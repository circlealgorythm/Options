import os

main_py_path = r"C:\Users\circlealgorythm\.antigravity\bot_grid\main.py"
with open(main_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add SPX constants after CAD
cad_constants = """CAD_WEEKLY_CODE_DOW = CAD_DAILY_CODE_DOW.copy()
"""
spx_constants = """
SPX_DAILY_BY_WEEKDAY = {0: 'E1A', 1: 'E1B', 2: 'E1C', 3: 'E1D', 4: 'EW'}
SPX_DAILY_CODES = ['E1A', 'E1B', 'E1C', 'E1D', 'EW', 'EW1', 'EW2', 'EW3', 'EW4', 'EZ', 'EOW', 'EOW1', 'EOW2', 'EOW3', 'EOW4']
SPX_WEEKLY_CODES = SPX_DAILY_CODES.copy()
SPX_DAILY_CODE_DOW = {
    'E1A': 0, 'E1B': 1, 'E1C': 2, 'E1D': 3,
    'EW': 4, 'EW1': 4, 'EW2': 4, 'EW3': 4, 'EW4': 4, 'EZ': 4,
    'EOW': 4, 'EOW1': 4, 'EOW2': 4, 'EOW3': 4, 'EOW4': 4
}
SPX_WEEKLY_CODE_DOW = SPX_DAILY_CODE_DOW.copy()
"""

if "SPX_DAILY_BY_WEEKDAY" not in content:
    content = content.replace(cad_constants, cad_constants + spx_constants)

# 2. Add SPX to code_map
cad_code_map = """        "CAD": ["CAU", "1CD", "2CD", "3CD", "4CD", "5CD"]"""
spx_code_map = """        "CAD": ["CAU", "1CD", "2CD", "3CD", "4CD", "5CD"],
        "SPX": ['E1A', 'E1B', 'E1C', 'E1D', 'EW', 'EW1', 'EW2', 'EW3', 'EW4', 'EZ', 'EOW', 'EOW1', 'EOW2', 'EOW3', 'EOW4']"""
if '"SPX":' not in content:
    content = content.replace(cad_code_map, spx_code_map)

# 3. Add SPX block to get_daily_contract
cad_daily_block = """    if currency in ['CAD', 'USDCAD']:
        target_code = CAD_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(CAD_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, CAD_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(CAD_DAILY_CODES)]
        return filter_nearest_month(filter_nearest_code(daily, CAD_DAILY_CODE_DOW, as_of_date))"""

spx_daily_block = """
    if currency == 'SPX':
        target_code = SPX_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(SPX_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, SPX_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(SPX_DAILY_CODES)]
        if not daily.empty:
            return filter_nearest_month(filter_nearest_code(daily, SPX_DAILY_CODE_DOW, as_of_date))
        return filter_nearest_month(calc_df)
"""

if "currency == 'SPX'" not in content:
    content = content.replace(cad_daily_block, cad_daily_block + spx_daily_block)

# 4. Add SPX to global_codes
global_codes = """        'USDCAD': ['CAU']
    }"""
spx_global_codes = """        'USDCAD': ['CAU'],
        'SPX': ['EW']
    }"""
if "'SPX': ['EW']" not in content:
    content = content.replace(global_codes, spx_global_codes)

with open(main_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied!")
