import os
import datetime
import re
import shutil
import pandas as pd
import pdfplumber
from src.parser import download_cme_bulletin, extract_bulletin_date, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma, find_gamma_flip

DEFAULT_MT5_GEX_DIR = r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX"

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
}

EUR_DAILY_BY_WEEKDAY = {0: 'SEC', 1: 'TEC', 2: 'WEC', 3: 'THC', 4: 'FRC'}
GBP_DAILY_BY_WEEKDAY = {0: 'MGB', 1: 'TGB', 2: 'WGB', 3: 'SBP', 4: 'FGB'}
import os
import datetime
import re
import shutil
import pandas as pd
import pdfplumber
from src.parser import download_cme_bulletin, extract_bulletin_date, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma, find_gamma_flip

DEFAULT_MT5_GEX_DIR = r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX"

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
}

EUR_DAILY_BY_WEEKDAY = {0: 'SEC', 1: 'TEC', 2: 'WEC', 3: 'THC', 4: 'FRC'}
GBP_DAILY_BY_WEEKDAY = {0: 'MGB', 1: 'TGB', 2: 'WGB', 3: 'SBP', 4: 'FGB'}

EUR_DAILY_CODES = ['SEC', 'TEC', 'WEC', 'THC', 'FRC']
EUR_WEEKLY_CODES = ['1EU', '2EU', '3EU', '4EU', '5EU']
GBP_SHORT_CODES = ['MGB', 'TGB', 'WGB', 'SBP', 'FGB', 'MGM']
GBP_WEEKLY_CODES = ['1BP', '2BP', '3BP', '4BP', '5BP']

EUR_DAILY_CODE_DOW = {'SEC': 0, 'TEC': 1, 'WEC': 2, 'THC': 3, 'FRC': 4}
EUR_WEEKLY_CODE_DOW = {'1EU': 0, '2EU': 1, '3EU': 2, '4EU': 3, '5EU': 4}
GBP_SHORT_CODE_DOW = {'MGB': 0, 'MGM': 0, 'TGB': 1, 'WGB': 2, 'SBP': 3, 'FGB': 4}
GBP_WEEKLY_CODE_DOW = {'1BP': 0, '2BP': 1, '3BP': 2, '4BP': 3, '5BP': 4}

XAU_DAILY_BY_WEEKDAY = {0: 'GMW', 1: 'GWT', 2: 'GWW', 3: 'GWR', 4: 'OG1'}
XAU_DAILY_CODES = ['GMW', 'GWT', 'GWW', 'GWR', 'OG1', 'OG2', 'OG3', 'OG4', 'OG5']
XAU_WEEKLY_CODES = ['OG1', 'OG2', 'OG3', 'OG4', 'OG5']
XAU_DAILY_CODE_DOW = {'GMW': 0, 'GWT': 1, 'GWW': 2, 'GWR': 3, 'OG1': 4}
XAU_WEEKLY_CODE_DOW = {'OG1': 4, 'OG2': 4, 'OG3': 4, 'OG4': 4, 'OG5': 4}

NAS_DAILY_BY_WEEKDAY = {0: 'Q1A', 1: 'Q1B', 2: 'Q1C', 3: 'Q1D', 4: 'QN1'}
NAS_DAILY_CODES = [f'Q{i}{d}' for i in range(1, 6) for d in ['A', 'B', 'C', 'D']] + ['QN1', 'QN2', 'QN3', 'QN4', 'QN']
NAS_WEEKLY_CODES = NAS_DAILY_CODES.copy()
NAS_DAILY_CODE_DOW = {}
for i in range(1, 6):
    NAS_DAILY_CODE_DOW[f'Q{i}A'] = 0
    NAS_DAILY_CODE_DOW[f'Q{i}B'] = 1
    NAS_DAILY_CODE_DOW[f'Q{i}C'] = 2
    NAS_DAILY_CODE_DOW[f'Q{i}D'] = 3
for q in ['QN1', 'QN2', 'QN3', 'QN4', 'QN']:
    NAS_DAILY_CODE_DOW[q] = 4
NAS_WEEKLY_CODE_DOW = NAS_DAILY_CODE_DOW.copy()

BTC_DAILY_BY_WEEKDAY = {0: 'BTC', 1: 'BTC', 2: 'BTC', 3: 'BTC', 4: 'BTC'}
BTC_DAILY_CODES = ['BTC']
BTC_WEEKLY_CODES = ['BTC']
BTC_DAILY_CODE_DOW = {'BTC': 0}
BTC_WEEKLY_CODE_DOW = {'BTC': 0}



CAD_DAILY_BY_WEEKDAY = {0: 'MCM', 1: 'TCD', 2: 'WCD', 3: 'SCD', 4: '1CD'}
CAD_DAILY_CODES = ['MCM', 'TCD', 'WCD', 'SCD', '1CD', '2CD', '3CD', '4CD', '5CD']
CAD_WEEKLY_CODES = CAD_DAILY_CODES.copy()
CAD_DAILY_CODE_DOW = {
    'MCM': 0, 'TCD': 1, 'WCD': 2, 'SCD': 3,
    '1CD': 4, '2CD': 4, '3CD': 4, '4CD': 4, '5CD': 4
}
CAD_WEEKLY_CODE_DOW = CAD_DAILY_CODE_DOW.copy()

SPX_DAILY_BY_WEEKDAY = {0: 'WK', 1: 'WK', 2: 'WK', 3: 'WK', 4: 'EMINI'}
SPX_DAILY_CODES = ['WK', 'EMINI', 'SME']
SPX_WEEKLY_CODES = SPX_DAILY_CODES.copy()
SPX_DAILY_CODE_DOW = {
    'WK': 4, 'EMINI': 4, 'SME': 4
}
SPX_WEEKLY_CODE_DOW = SPX_DAILY_CODE_DOW.copy()


def month_sort_key(month):
    if not isinstance(month, str) or len(month) < 5:
        return (9999, 99)
    mon = month[:3].upper()
    try:
        year = 2000 + int(month[3:5])
    except ValueError:
        return (9999, 99)
    return (year, MONTH_MAP.get(mon, 99))


def nearest_month(months):
    valid_months = [m for m in months if month_sort_key(m) != (9999, 99)]
    return sorted(valid_months, key=month_sort_key)[0] if valid_months else None


def get_fridays(year, month):
    import calendar
    fridays = []
    for week in calendar.monthcalendar(year, month):
        if week[calendar.FRIDAY] != 0:
            fridays.append(week[calendar.FRIDAY])
    return fridays

def get_wednesdays(year, month):
    import calendar
    wednesdays = []
    for week in calendar.monthcalendar(year, month):
        if week[calendar.WEDNESDAY] != 0:
            wednesdays.append(week[calendar.WEDNESDAY])
    return wednesdays

def month_to_expiry_date(month_code, currency=None):
    """Convert month code to specific expiry date based on asset class."""
    import calendar
    if not month_code or len(month_code) < 5:
        return None
    mon = month_code[:3].upper()
    try:
        year = 2000 + int(month_code[3:5])
    except (ValueError, IndexError):
        return None
    month_num = MONTH_MAP.get(mon)
    if month_num is None:
        return None
        
    if currency in ['EUR', 'GBP', 'CAD', 'USDCAD']:
        # 2nd Friday before 3rd Wednesday
        weds = get_wednesdays(year, month_num)
        third_wed = datetime.date(year, month_num, weds[2] if len(weds) >= 3 else weds[-1])
        # Minus 12 days always lands on the 2nd Friday before
        expiry = third_wed - datetime.timedelta(days=12)
        return expiry
        
    elif currency == 'BTC':
        # Last Friday
        fridays = get_fridays(year, month_num)
        return datetime.date(year, month_num, fridays[-1])
        
    elif currency == 'XAU':
        # 4th business day before the month-end of the PRIOR month
        if month_num == 1:
            prior_y = year - 1
            prior_m = 12
        else:
            prior_y = year
            prior_m = month_num - 1
            
        # Get last day of prior month
        _, last_day = calendar.monthrange(prior_y, prior_m)
        d = datetime.date(prior_y, prior_m, last_day)
        
        # We need the 4th business day prior to the delivery month.
        bday_count = 0
        while True:
            if d.weekday() < 5:
                bday_count += 1
                if bday_count == 4:
                    return d
            d -= datetime.timedelta(days=1)
            
    else:
        # SPX, NAS, and Default: 3rd Friday
        fridays = get_fridays(year, month_num)
        third_friday = fridays[2] if len(fridays) >= 3 else fridays[-1]
        return datetime.date(year, month_num, third_friday)


def compute_dte(month_code, currency=None, as_of_date=None):
    """Compute trading days to expiry. Returns at least 1."""
    if as_of_date is None:
        as_of_date = datetime.date.today()
    expiry = month_to_expiry_date(month_code, currency)
    if expiry is None:
        return 21
    dte = 0
    current = as_of_date
    while current < expiry:
        current += datetime.timedelta(days=1)
        if current.weekday() < 5:
            dte += 1
    return max(dte, 1)


MIN_DTE_FOR_IV = 5  # Auto-roll to next month when DTE < this

MIN_IV_THRESHOLD = {
    'EUR': 0.02, 'GBP': 0.015, 'USDCAD': 0.015, 'CAD': 0.015,
    'XAU': 0.05, 'NAS': 0.05, 'SPX': 0.05,
    'BTC': 0.15,
}

FALLBACK_IV = {
    'XAU': 0.15, 'NAS': 0.12, 'SPX': 0.15, 'BTC': 0.50,
    'EUR': 0.07, 'GBP': 0.06, 'USDCAD': 0.06, 'CAD': 0.06,
}


def is_valid_daily_df(df):
    if df.empty:
        return False
    has_calls = (df['Call_OI'] > 0).any() and (df['Call_Settle'] > 0.0).any()
    has_puts = (df['Put_OI'] > 0).any() and (df['Put_Settle'] > 0.0).any()
    return has_calls and has_puts


def filter_nearest_month(df):
    if df.empty or 'Contract_Month' not in df.columns:
        return df
    months = df['Contract_Month'].dropna().unique()
    if len(months) == 0:
        return df
    
    valid_months = [m for m in months if month_sort_key(m) != (9999, 99)]
    if not valid_months:
        return df.iloc[0:0]
        
    sorted_months = sorted(valid_months, key=month_sort_key)
    for m in sorted_months:
        sub_df = df[df['Contract_Month'] == m]
        if is_valid_daily_df(sub_df):
            return sub_df
            
    return df[df['Contract_Month'] == sorted_months[0]]


def filter_nearest_code(df, code_dow_map, as_of_date):
    if df.empty or 'Option_Type' not in df.columns:
        return df

    available = [code for code in code_dow_map if code in set(df['Option_Type'])]
    if not available:
        return df.iloc[0:0]

    dow_to_codes = {}
    for code in available:
        d = code_dow_map[code]
        if d not in dow_to_codes:
            dow_to_codes[d] = []
        dow_to_codes[d].append(code)

    valid_dows = []
    for d, codes in dow_to_codes.items():
        combined_df = df[df['Option_Type'].isin(codes)]
        if is_valid_daily_df(combined_df):
            valid_dows.append(d)

    current_dow = as_of_date.weekday()
    
    if valid_dows:
        target_dow = sorted(valid_dows, key=lambda d: ((d - current_dow) % 5, d))[0]
    else:
        target_dow = sorted(dow_to_codes.keys(), key=lambda d: ((d - current_dow) % 5, d))[0]
        
    target_codes = dow_to_codes[target_dow]
    return df[df['Option_Type'].isin(target_codes)]



def copy_csv_to_mt5(csv_path, mt5_gex_dir=None):
    import shutil
    import os
    filename = os.path.basename(csv_path)
    sub_dir = ''
    if 'XAU' in filename:
        sub_dir = 'XAU'
    elif 'NAS' in filename or 'SPX' in filename:
        sub_dir = 'NAS100'
    elif 'BTC' in filename:
        sub_dir = 'Crypto'
    elif 'USDCAD' in filename or 'CAD' in filename:
        sub_dir = 'USDCAD'

    copied_path = None

    if mt5_gex_dir:
        files_gex_dir = os.path.join(mt5_gex_dir, sub_dir) if sub_dir else mt5_gex_dir
        os.makedirs(files_gex_dir, exist_ok=True)
        try:
            dest_file = os.path.join(files_gex_dir, filename)
            shutil.copy2(csv_path, dest_file)
            print(f'Copied {filename} to {files_gex_dir}')
            copied_path = dest_file
        except Exception as e:
            print(f'Error copying to {files_gex_dir}: {e}')
    else:
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
                    files_gex_dir = os.path.join(root, 'MQL5', 'Files', 'GEX', sub_dir)
                    os.makedirs(files_gex_dir, exist_ok=True)
                    try:
                        dest_file = os.path.join(files_gex_dir, filename)
                        shutil.copy2(csv_path, dest_file)
                        print(f'Copied {filename} to {files_gex_dir}')
                        copied_path = dest_file
                    except Exception as e:
                        pass
                    dirs.remove('MQL5')

    return copied_path


def cleanup_old_files(target_dir=None, days_to_keep=14):
    import datetime
    base_dir = target_dir or os.environ.get("MT5_GEX_DIR") or DEFAULT_MT5_GEX_DIR
    if not base_dir or not os.path.isdir(base_dir):
        return

    print(f"Cleaning up files older than {days_to_keep} days in: {base_dir}")
    today = datetime.date.today()
    limit = today - datetime.timedelta(days=days_to_keep)

    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            if filename.startswith("GEX_") and filename.endswith(".csv"):
                filepath = os.path.join(root, filename)
                basename = os.path.basename(filename)
                parts = basename.replace(".csv", "").split("_")
                if len(parts) >= 3:
                    date_part = parts[-1]
                    try:
                        file_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
                        if file_date < limit:
                            os.remove(filepath)
                            print(f"Deleted old GEX file (by filename date): {filepath} (date {date_part})")
                    except ValueError:
                        try:
                            import time
                            mtime = os.path.getmtime(filepath)
                            cutoff = time.time() - (days_to_keep * 86400)
                            if mtime < cutoff:
                                os.remove(filepath)
                                print(f"Deleted old GEX file (by mtime): {filepath} (modified {time.ctime(mtime)})")
                        except OSError as e:
                            print(f"Error deleting file {filepath}: {e}")
                    except OSError as e:
                        print(f"Error deleting file {filepath}: {e}")


def select_daily_contracts(calc_df, currency, as_of_date=None):
    """
    Selects short-dated option rows for Daily MDD.

    The exact weekday code is preferred. If CME omits it, EUR falls back to
    weekly 1EU-5EU contracts; GBP bulletins often use short GBP codes instead
    of 1BP-5BP, so GBP falls back to the nearest available GBP short block.
    """
    if calc_df.empty:
        return pd.DataFrame(columns=calc_df.columns)

    if as_of_date is None:
        as_of_date = datetime.date.today()
    dow = as_of_date.weekday()

    currency = currency.upper()
    if currency == 'EUR':
        target_code = EUR_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(EUR_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, EUR_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        daily = calc_df[calc_df['Option_Type'].isin(EUR_DAILY_CODES)]
        nearest_daily = filter_nearest_code(daily, EUR_DAILY_CODE_DOW, as_of_date) if not daily.empty else pd.DataFrame()
        return filter_nearest_month(nearest_daily)

    if currency == 'GBP':
        target_code = GBP_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(GBP_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, GBP_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        short = calc_df[calc_df['Option_Type'].isin(GBP_SHORT_CODES)]
        nearest_short = filter_nearest_code(short, GBP_SHORT_CODE_DOW, as_of_date) if not short.empty else pd.DataFrame()
        return filter_nearest_month(nearest_short)

    if currency == 'XAU':
        target_code = XAU_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(XAU_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, XAU_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        daily = calc_df[calc_df['Option_Type'].isin(XAU_DAILY_CODES)]
        nearest_daily = filter_nearest_code(daily, XAU_DAILY_CODE_DOW, as_of_date) if not daily.empty else pd.DataFrame()
        return filter_nearest_month(nearest_daily)

    if currency == 'NAS':
        week_num = (as_of_date.day - 1) // 7 + 1
        if dow == 0:
            target_code = f'Q{week_num}A'
        elif dow == 1:
            target_code = f'Q{week_num}B'
        elif dow == 2:
            target_code = f'Q{week_num}C'
        elif dow == 3:
            target_code = f'Q{week_num}D'
        elif dow == 4:
            target_code = f'QN{week_num}' if week_num <= 4 else 'QN'
        else:
            target_code = 'QN1'
            
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(NAS_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, NAS_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        daily = calc_df[calc_df['Option_Type'].isin(NAS_DAILY_CODES)]
        nearest_daily = filter_nearest_code(daily, NAS_DAILY_CODE_DOW, as_of_date) if not daily.empty else pd.DataFrame()
        return filter_nearest_month(nearest_daily)

    if currency == 'BTC':
        target_code = BTC_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)
        return filter_nearest_month(calc_df)

    if currency in ['CAD', 'USDCAD']:
        target_code = CAD_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(CAD_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, CAD_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        daily = calc_df[calc_df['Option_Type'].isin(CAD_DAILY_CODES)]
        nearest_daily = filter_nearest_code(daily, CAD_DAILY_CODE_DOW, as_of_date) if not daily.empty else pd.DataFrame()
        return filter_nearest_month(nearest_daily)
    if currency == 'SPX':
        target_code = SPX_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if is_valid_daily_df(exact):
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(SPX_WEEKLY_CODES)]
        nearest_weekly = filter_nearest_code(weekly, SPX_WEEKLY_CODE_DOW, as_of_date) if not weekly.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_weekly):
            return filter_nearest_month(nearest_weekly)

        daily = calc_df[calc_df['Option_Type'].isin(SPX_DAILY_CODES)]
        nearest_daily = filter_nearest_code(daily, SPX_DAILY_CODE_DOW, as_of_date) if not daily.empty else pd.DataFrame()
        if is_valid_daily_df(nearest_daily):
            return filter_nearest_month(nearest_daily)
        return filter_nearest_month(calc_df)


    return pd.DataFrame(columns=calc_df.columns)

def validate_mdd_summary(summary, currency):
    required = [
        ("Daily_Call", "Daily_Call_OI", "Daily_Call_Settle"),
        ("Daily_Put", "Daily_Put_OI", "Daily_Put_Settle"),
        ("Global_Call", "Global_Call_OI", None),
        ("Global_Put", "Global_Put_OI", None),
    ]

    missing = []
    for label, oi_col, settle_col in required:
        if summary[oi_col].max() <= 0.0 or (settle_col is not None and summary[settle_col].max() <= 0.0):
            missing.append(label)

    daily_month = str(summary["Daily_Month"].iloc[0]) if "Daily_Month" in summary.columns and not summary.empty else "UNKNOWN"
    global_month = str(summary["Global_Month"].iloc[0]) if "Global_Month" in summary.columns and not summary.empty else "UNKNOWN"
    if daily_month == "UNKNOWN":
        missing.append("Daily_Month")
    if global_month == "UNKNOWN":
        missing.append("Global_Month")

    if missing:
        print(f"WARNING: {currency} summary is missing required MDD data: {', '.join(missing)}")


def select_near_spot_mdd_settle(df, type_prefix, spot_price):
    oi_col = f'{type_prefix}_OI'
    settle_col = f'{type_prefix}_Settle'
    if df.empty:
        return pd.DataFrame(columns=['Strike', settle_col, oi_col])

    valid_df = df[(df[oi_col] > 0) & (df[settle_col] > 0.0)].copy()
    if valid_df.empty:
        return pd.DataFrame(columns=['Strike', settle_col, oi_col])

    if type_prefix == 'Call':
        preferred = valid_df[valid_df['Strike'] >= spot_price].copy()
    else:
        preferred = valid_df[valid_df['Strike'] <= spot_price].copy()

    if preferred.empty:
        preferred = valid_df

    preferred['Distance_To_Spot'] = (preferred['Strike'] - spot_price).abs()
    preferred.sort_values(
        ['Distance_To_Spot', oi_col, settle_col],
        ascending=[True, False, False],
        inplace=True,
    )
    return preferred.iloc[[0]][['Strike', settle_col, oi_col]]


GLOBAL_CODES_MAP = {
    'EUR': ['EUU'],
    'GBP': ['GBU'],
    'XAU': ['OG'],
    'NAS': ['QN'],
    'BTC': ['BTC'],

    'USDCAD': ['CAU'],
    'CAD': ['CAU'],
    'SPX': ['MINI', 'EMINI']
}

FALLBACK_SPOT_MAP = {
    'EUR': 1.1400,
    'GBP': 1.3200,
    'USDCAD': 1.4150,
    'CAD': 0.7050,
    'XAU': 4060.0,
    'NAS': 28500.0,
    'SPX': 7280.0,
    'BTC': 63000.0,
}

def detect_spot_and_classify(raw_df, currency):
    if raw_df.empty:
        return FALLBACK_SPOT_MAP.get(currency, 1.0), {}, raw_df
        
    df = raw_df.copy()
    
    df['Strike'] = pd.to_numeric(df['Strike'], errors='coerce')
    df['Settle'] = pd.to_numeric(df['Settle'], errors='coerce')
    df['OI'] = pd.to_numeric(df['OI'], errors='coerce')
    df = df.dropna(subset=['Contract_Month', 'Strike', 'Settle'])
    
    # Compute spot per contract month
    df_for_spot = df.copy()
    df_for_spot['Settle'] = df_for_spot['Settle'].round(6)
    df_for_spot = df_for_spot.drop_duplicates(subset=['Option_Type', 'Contract_Month', 'Strike', 'Settle', 'OI'])
    
    min_settle_threshold = {
        'EUR': 0.0001, 'GBP': 0.0001, 'USDCAD': 0.0001, 'CAD': 0.0001,
        'XAU': 1.0, 'NAS': 5.0, 'SPX': 5.0, 'BTC': 100.0,
    }.get(currency, 1.0)
    
    spots_per_month = {}
    fallback_spot = FALLBACK_SPOT_MAP.get(currency, 1.0)
    
    months = df_for_spot['Contract_Month'].unique()
    for m in months:
        m_df = df_for_spot[df_for_spot['Contract_Month'] == m]
        spot_m = fallback_spot
        
        # If Is_Call is perfectly known, use it
        if not m_df['Is_Call'].isna().all():
            calls = m_df[m_df['Is_Call'] == True].groupby('Strike')['Settle'].max()
            puts = m_df[m_df['Is_Call'] == False].groupby('Strike')['Settle'].max()
            common = calls.index.intersection(puts.index)
            if not common.empty:
                diffs = (calls[common] - puts[common]).abs()
                # filter by min_settle_threshold if needed
                valid_common = [s for s in common if calls[s] >= min_settle_threshold and puts[s] >= min_settle_threshold]
                if valid_common:
                    spot_m = diffs[valid_common].idxmin()
                else:
                    spot_m = diffs.idxmin()
        else:
            # If Is_Call is missing (e.g. EUR mixed CALLS & PUTS table), we cannot 
            # find the spot using diffs because each strike only has one OTM option.
            # We must rely on the user-provided fallback spot to classify the options.
            spot_m = fallback_spot
        
        if abs(spot_m - fallback_spot) / fallback_spot > 0.2:
            print(f"[{currency}] Computed spot {spot_m} for month {m} deviates >20% from fallback {fallback_spot}. Using fallback.")
            spot_m = fallback_spot
            
        spots_per_month[m] = spot_m
        
    # Determine global spot for logging/fallback
    valid_months = [m for m, s in spots_per_month.items() if s != fallback_spot]
    if valid_months:
        near_month = nearest_month(valid_months)
        global_spot = spots_per_month[near_month]
    else:
        global_spot = fallback_spot
        
    # Classify Is_Call == None using month-specific spots
    if df['Is_Call'].isna().any():
        for idx, row in df[df['Is_Call'].isna()].iterrows():
            m = row['Contract_Month']
            strike = row['Strike']
            strike = row['Strike']
            spot_guess = spots_per_month.get(m, global_spot)
            df.at[idx, 'Is_Call'] = strike >= spot_guess

    return global_spot, spots_per_month, df

def calculate_gex_pipeline(raw_df, currency, output_dir, as_of_date=None):
    if raw_df.empty:
        print(f"No raw data for {currency}")
        return
        
    spot, spots_per_month, classified_df = detect_spot_and_classify(raw_df, currency)
    print(f"[{currency}] Detected Spot price: {spot:.4f}")
    
    import math
    
    # Pre-compute DTE for each contract month
    month_T_cache = {}
    if not classified_df.empty:
        for m in classified_df['Contract_Month'].dropna().unique():
            dte = compute_dte(m, currency, as_of_date)
            month_T_cache[m] = max(dte / 252.0, 1.0 / 252.0)
    
    r = 0.0
    
    if not classified_df.empty:
        classified_df = classified_df.reset_index(drop=True)
        
        # Determine which month to use for ATM IV (auto-rollover)
        all_months = classified_df['Contract_Month'].dropna().unique()
        sorted_iv_months = sorted([m for m in all_months if month_sort_key(m) != (9999, 99)], key=month_sort_key)
        
        iv_month = sorted_iv_months[0] if sorted_iv_months else None
        iv_dte = compute_dte(iv_month, currency, as_of_date) if iv_month else 21
        
        if iv_dte < MIN_DTE_FOR_IV and len(sorted_iv_months) > 1:
            old_month, old_dte = iv_month, iv_dte
            iv_month = sorted_iv_months[1]
            iv_dte = compute_dte(iv_month, currency, as_of_date)
            print(f"[{currency}] Near-expiry rollover: {old_month} (DTE={old_dte}) -> {iv_month} (DTE={iv_dte})")
        
        T_iv = max(iv_dte / 252.0, 1.0 / 252.0)
        
        # Find ATM in IV month
        iv_month_df = classified_df[classified_df['Contract_Month'] == iv_month] if iv_month else classified_df
        if iv_month_df.empty:
            iv_month_df = classified_df
        
        atm_idx = (iv_month_df['Strike'] - spot).abs().idxmin()
        atm_row = iv_month_df.loc[atm_idx]
        price_atm = atm_row['Settle']
        is_call_val = atm_row['Is_Call']
        if isinstance(is_call_val, pd.Series):
            is_call_val = is_call_val.iloc[0]
        strike_atm = atm_row['Strike']
        if isinstance(strike_atm, pd.Series):
            strike_atm = strike_atm.iloc[0]
        iv_atm = implied_volatility(price_atm, spot, strike_atm, T_iv, 0.0, 'C' if is_call_val else 'P')
        
        # Minimum IV sanity check
        min_iv = MIN_IV_THRESHOLD.get(currency, 0.03)
        if iv_atm < min_iv:
            iv_atm = FALLBACK_IV.get(currency, 0.08)
    else:
        iv_atm = FALLBACK_IV.get(currency, 0.08)
        
    sigma_1d = spot * iv_atm * (1.0 / math.sqrt(252.0))
    print(f"[{currency}] ATM IV: {iv_atm:.2%}, Daily Sigma: {sigma_1d:.5f}")
    
    contract_size = 100000 if currency == 'USDCAD' else (5 if currency == 'BTC' else (20 if currency == 'NAS' else (100 if currency == 'XAU' else (125000 if currency == 'EUR' else (50 if currency == 'SPX' else 62500)))))
    
    calculated_rows = []
    strikes_list = []
    ois_list = []
    is_calls_list = []
    ivs_list = []
    
    for idx, row in classified_df.iterrows():
        K = row['Strike']
        is_call = row['Is_Call']
        m = row.get('Contract_Month')
        
        local_spot = spots_per_month.get(m, spot)
                
        price = row['Settle']
        T = month_T_cache.get(m, 0.08)
        
        # Cap deep ITM/OTM strikes: if strike is >30% from spot, zero GEX
        # These are noise that blows up the visual scale
        strike_distance_pct = abs(K - local_spot) / local_spot if local_spot > 0 else 0
        skip_gex = strike_distance_pct > 0.30
        
        if price <= 0.0 or skip_gex:
            iv = 0.001
            gamma = 0.0
            gex = 0.0
            abs_gamma = 0.0
            if price > 0.0 and not skip_gex:
                pass  # price <= 0 case
            elif skip_gex and price > 0.0:
                # Still compute IV for gamma_flip but zero out display GEX
                if is_call:
                    iv = implied_volatility(price, local_spot, K, T, r, 'C')
                else:
                    iv = implied_volatility(price, local_spot, K, T, r, 'P')
        elif is_call:
            iv = implied_volatility(price, local_spot, K, T, r, 'C')
            gamma = bs_gamma(local_spot, K, T, r, iv) if iv > 0.001 else 0.0
            gex = calculate_gex(gamma, row['OI'], contract_size, local_spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
        else:
            iv = implied_volatility(price, local_spot, K, T, r, 'P')
            gamma = bs_gamma(local_spot, K, T, r, iv) if iv > 0.001 else 0.0
            gex = -calculate_gex(gamma, row['OI'], contract_size, local_spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])

        call_oi = row['OI'] if is_call else 0
        put_oi = row['OI'] if not is_call else 0
        call_settle = price if is_call else 0.0
        put_settle = price if not is_call else 0.0
            
        calculated_rows.append({
            "Strike": K,
            "Option_Type": row['Option_Type'],
            "Contract_Month": row['Contract_Month'],
            "GEX": gex,
            "Abs_Gamma": abs_gamma,
            "Call_OI": call_oi,
            "Put_OI": put_oi,
            "Call_Settle": call_settle,
            "Put_Settle": put_settle
        })
        
        strikes_list.append(K)
        ois_list.append(row['OI'])
        is_calls_list.append(is_call)
        ivs_list.append(iv)
        
    calc_df = pd.DataFrame(calculated_rows)
    T_flip = month_T_cache.get(nearest_month(list(month_T_cache.keys())), 0.08) if month_T_cache else 0.08
    gamma_flip_val = find_gamma_flip(strikes_list, ois_list, is_calls_list, ivs_list, spot, T_flip, r)
    print(f"[{currency}] Calculated Gamma Flip level: {gamma_flip_val:.5f}")

    
    def get_max_oi_level(df, type_prefix):
        oi_col = f'{type_prefix}_OI'
        if df.empty:
            return pd.DataFrame(columns=['Strike', oi_col])
        valid_df = df[df[oi_col] > 0]
        if not valid_df.empty:
            idx_max = valid_df[oi_col].idxmax()
            return valid_df.loc[[idx_max], ['Strike', oi_col]]
        return pd.DataFrame(columns=['Strike', oi_col])

    # Determine Global DF
    global_codes = {
        'EUR': ['EUU'],
        'GBP': ['GBU'],
        'XAU': ['OG'],
        'NAS': ['QN', 'QN1', 'QN2', 'QN3', 'QN4'],
        'BTC': ['BTC'],
        'USDCAD': ['CAU'],
        'SPX': ['MINI', 'EMINI']
    }.get(currency, ['OG'])
    
    global_df = calc_df[calc_df['Option_Type'].isin(global_codes)]
    if not global_df.empty:
        call_month_oi = global_df.groupby('Contract_Month')['Call_OI'].sum()
        put_month_oi = global_df.groupby('Contract_Month')['Put_OI'].sum()
        
        # Create a dataframe to find months with BOTH calls and puts
        monthly_oi = pd.DataFrame({'Call_OI': call_month_oi, 'Put_OI': put_month_oi}).fillna(0)
        
        # Filter to months with > 0 for both
        valid_months = monthly_oi[(monthly_oi['Call_OI'] > 0) & (monthly_oi['Put_OI'] > 0)].copy()
        
        if not valid_months.empty:
            valid_months['Total_OI'] = valid_months['Call_OI'] + valid_months['Put_OI']
            max_month = valid_months['Total_OI'].idxmax()
        else:
            total_month_oi = call_month_oi.add(put_month_oi, fill_value=0)
            max_month = total_month_oi.idxmax() if not total_month_oi.empty else None
            
        global_call_df = global_df[global_df['Contract_Month'] == max_month] if max_month else global_df
        global_put_df = global_df[global_df['Contract_Month'] == max_month] if max_month else global_df
    else:
        global_call_df = calc_df
        global_put_df = calc_df
        max_month = 'UNKNOWN'
        
    # Determine Daily DF
    daily_df = select_daily_contracts(calc_df, currency, as_of_date)
    
    daily_call = select_near_spot_mdd_settle(daily_df, 'Call', spot).rename(columns={'Call_OI': 'Daily_Call_OI', 'Call_Settle': 'Daily_Call_Settle'})
    daily_put = select_near_spot_mdd_settle(daily_df, 'Put', spot).rename(columns={'Put_OI': 'Daily_Put_OI', 'Put_Settle': 'Daily_Put_Settle'})
    
    global_call = get_max_oi_level(global_call_df, 'Call').rename(columns={'Call_OI': 'Global_Call_OI'})
    global_put = get_max_oi_level(global_put_df, 'Put').rename(columns={'Put_OI': 'Global_Put_OI'})
    
    # Group by Strike and sum values across all expirations/series
    summary = calc_df.groupby('Strike').agg({
        'GEX': 'sum',
        'Abs_Gamma': 'sum'
    }).reset_index()
    
    # Winsorize GEX outliers: cap at P97.5 to prevent single dominant strike
    # from squashing all other levels in the MT5 noise filter
    nonzero_gex = summary[summary['GEX'] != 0]['GEX'].abs()
    if len(nonzero_gex) > 10:
        cap = nonzero_gex.quantile(0.975)
        summary['GEX'] = summary['GEX'].clip(lower=-cap, upper=cap)
    
    summary = summary.merge(daily_call, on='Strike', how='left')
    summary = summary.merge(daily_put, on='Strike', how='left')
    summary = summary.merge(global_call, on='Strike', how='left')
    summary = summary.merge(global_put, on='Strike', how='left')
    
    summary.fillna(0.0, inplace=True)
    
    summary.rename(columns={'GEX': 'Total_GEX', 'Abs_Gamma': 'Total_Abs_Gamma'}, inplace=True)
    summary.insert(0, 'Currency', currency)
    
    # Add volatility bands columns
    summary['R68_High'] = spot + sigma_1d
    summary['R68_Low'] = spot - sigma_1d
    summary['R95_High'] = spot + 2.0 * sigma_1d
    summary['R95_Low'] = spot - 2.0 * sigma_1d
    
    # Add active contract month columns
    summary['Global_Month'] = max_month if not global_df.empty else 'UNKNOWN'
    active_daily_month = daily_df['Contract_Month'].iloc[0] if not daily_df.empty and 'Contract_Month' in daily_df.columns else 'UNKNOWN'
    summary['Daily_Month'] = active_daily_month

    # Store futures spot price directly so EA doesn't derive it from R68
    summary['Futures_Spot'] = spot
    summary['Gamma_Flip'] = gamma_flip_val
    validate_mdd_summary(summary, currency)
    
    # Save to CSV
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    filename = f"GEX_USDCAD_{today_str}.csv" if currency == "USDCAD" else f"GEX_{currency}USD_{today_str}.csv"
    out_file = os.path.join(output_dir, filename)
    summary.to_csv(out_file, index=False)
    print(f"Saved {currency} levels to {out_file} ({len(summary)} strikes)")
    copy_csv_to_mt5(out_file)

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Define files to process
    eur_section = "Section39_Euro_FX_And_Cme$Index_Options.pdf"
    gbp_call_section = "Section27_British_Pound_Call_Options.pdf"
    gbp_put_section = "Section28_British_Pound_Put_Options.pdf"
    
    eur_dest = os.path.join(DATA_DIR, eur_section)
    gbp_call_dest = os.path.join(DATA_DIR, gbp_call_section)
    gbp_put_dest = os.path.join(DATA_DIR, gbp_put_section)
    
    # Step 1: Download PDFs
    eur_ok = download_cme_bulletin(eur_section, eur_dest)
    gbp_call_ok = download_cme_bulletin(gbp_call_section, gbp_call_dest)
    gbp_put_ok = download_cme_bulletin(gbp_put_section, gbp_put_dest)
    
    # Step 2: Parse and process EUR data
    if eur_ok:
        try:
            eur_bulletin_date = extract_bulletin_date(eur_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[EUR] CME bulletin trade date: {eur_bulletin_date}; session date: {session_date}")
            eur_raw = parse_cme_pdf(eur_dest, "EUR", is_call_only=None)
            calculate_gex_pipeline(eur_raw, "EUR", DATA_DIR, session_date)
        except Exception as e:
            print(f"[EUR] Error during processing: {e}")
        
    # Step 3: Parse and process GBP data
    if gbp_call_ok and gbp_put_ok:
        try:
            gbp_bulletin_date = extract_bulletin_date(gbp_call_dest) or extract_bulletin_date(gbp_put_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[GBP] CME bulletin trade date: {gbp_bulletin_date}; session date: {session_date}")
            gbp_calls = parse_cme_pdf(gbp_call_dest, "GBP", is_call_only=True)
            gbp_puts = parse_cme_pdf(gbp_put_dest, "GBP", is_call_only=False)
            gbp_raw = pd.concat([gbp_calls, gbp_puts])
            calculate_gex_pipeline(gbp_raw, "GBP", DATA_DIR, session_date)
        except Exception as e:
            print(f"[GBP] Error during processing: {e}")

    # Step 4: Parse and process XAU data
    xau_section = "Section64_Metals_Option_Products.pdf"
    xau_dest = os.path.join(DATA_DIR, xau_section)
    xau_ok = download_cme_bulletin(xau_section, xau_dest)
    if xau_ok:
        try:
            xau_bulletin_date = extract_bulletin_date(xau_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[XAU] CME bulletin trade date: {xau_bulletin_date}; session date: {session_date}")
            xau_raw = parse_cme_pdf(xau_dest, "XAU", is_call_only=None)
            if not xau_raw.empty:
                gold_option_types = ['OG', 'GMW', 'GWT', 'GWW', 'GWR', 'OG1', 'OG2', 'OG3', 'OG4', 'OG5', 'MMG', 'FMG']
                xau_raw = xau_raw[xau_raw['Option_Type'].isin(gold_option_types)]
            calculate_gex_pipeline(xau_raw, "XAU", DATA_DIR, session_date)
        except Exception as e:
            print(f"[XAU] Error during processing: {e}")

    # Step 5: Parse and process NAS data
    nas_section = "Section40_Nasdaq_100_And_E_Mini_Nasdaq_100_Options.pdf"
    nas_dest = os.path.join(DATA_DIR, nas_section)
    nas_ok = download_cme_bulletin(nas_section, nas_dest)
    if nas_ok:
        try:
            nas_bulletin_date = extract_bulletin_date(nas_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[NAS] CME bulletin trade date: {nas_bulletin_date}; session date: {session_date}")
            nas_raw = parse_cme_pdf(nas_dest, "NAS", is_call_only=None)
            if not nas_raw.empty:
                nas_raw = nas_raw[nas_raw['Strike'] >= 10000.0]
            calculate_gex_pipeline(nas_raw, "NAS", DATA_DIR, session_date)
        except Exception as e:
            print(f"[NAS] Error during processing: {e}")

    # Step 5b: Parse and process S&P 500 data
    sp_call_section = "Section47_E_Mini_S_And_P_500_Call_Options.pdf"
    sp_put_section = "Section48_E_Mini_S_And_P_500_Put_Options.pdf"
    
    sp_call_dest = os.path.join(DATA_DIR, sp_call_section)
    sp_put_dest = os.path.join(DATA_DIR, sp_put_section)
    
    sp_call_ok = download_cme_bulletin(sp_call_section, sp_call_dest)
    sp_put_ok = download_cme_bulletin(sp_put_section, sp_put_dest)
    
    if sp_call_ok and sp_put_ok:
        try:
            sp_bulletin_date = extract_bulletin_date(sp_call_dest) or extract_bulletin_date(sp_put_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[SPX] CME bulletin trade date: {sp_bulletin_date}; session date: {session_date}")
            sp_calls = parse_cme_pdf(sp_call_dest, "SPX", is_call_only=True)
            sp_puts = parse_cme_pdf(sp_put_dest, "SPX", is_call_only=False)
            sp_raw = pd.concat([sp_calls, sp_puts])
            if not sp_raw.empty:
                sp_raw = sp_raw[sp_raw['Strike'] >= 2000.0]
            calculate_gex_pipeline(sp_raw, "SPX", DATA_DIR, session_date)
        except Exception as e:
            print(f"[SPX] Error during processing: {e}")

    # Step 6: Parse and process Crypto data
    crypto_section = "Section74_Cryptocurrency.pdf"
    crypto_dest = os.path.join(DATA_DIR, crypto_section)
    crypto_ok = download_cme_bulletin(crypto_section, crypto_dest)
    if crypto_ok:
        try:
            crypto_bulletin_date = extract_bulletin_date(crypto_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[Crypto] CME bulletin trade date: {crypto_bulletin_date}; session date: {session_date}")
            crypto_raw = parse_cme_pdf(crypto_dest, "BTC", is_call_only=None)
            
            # Process BTC
            btc_raw = crypto_raw[crypto_raw['Option_Type'] == 'BTC']
            if not btc_raw.empty:
                calculate_gex_pipeline(btc_raw, "BTC", DATA_DIR, session_date)
            else:
                print("[Crypto] Warning: No BTC option rows found.")
                

        except Exception as e:
            print(f"[Crypto] Error during processing: {e}")

    # Step 7: Parse and process USDCAD data
    cad_call_section = "Section29_Canadian_Dollar_Call_Options.pdf"
    cad_put_section = "Section30_Canadian_Dollar_Put_Options.pdf"
    cad_call_dest = os.path.join(DATA_DIR, cad_call_section)
    cad_put_dest = os.path.join(DATA_DIR, cad_put_section)
    
    cad_call_ok = download_cme_bulletin(cad_call_section, cad_call_dest)
    cad_put_ok = download_cme_bulletin(cad_put_section, cad_put_dest)
    
    if cad_call_ok and cad_put_ok:
        try:
            cad_bulletin_date = extract_bulletin_date(cad_call_dest) or extract_bulletin_date(cad_put_dest) or datetime.date.today()
            session_date = datetime.date.today()
            print(f"[USDCAD] CME bulletin trade date: {cad_bulletin_date}; session date: {session_date}")
            cad_calls = parse_cme_pdf(cad_call_dest, "CAD", is_call_only=True)
            cad_puts = parse_cme_pdf(cad_put_dest, "CAD", is_call_only=False)
            cad_raw = pd.concat([cad_calls, cad_puts]).reset_index(drop=True)
            
            if not cad_raw.empty:
                atm_rows = cad_raw[(cad_raw['Delta'] >= 0.45) & (cad_raw['Delta'] <= 0.55)]
                if not atm_rows.empty:
                    nearest_m = nearest_month(atm_rows['Contract_Month'].dropna().unique())
                    if nearest_m:
                        cad_spot = atm_rows[atm_rows['Contract_Month'] == nearest_m]['Strike'].mean()
                    else:
                        cad_spot = atm_rows['Strike'].mean()
                else:
                    cad_spot = 0.7200
                    
                print(f"[CAD] Detected raw CADUSD spot price for conversion: {cad_spot:.5f}")
                
                usdcad_raw = cad_raw.copy()
                usdcad_raw['Strike'] = 1.0 / cad_raw['Strike']
                usdcad_raw['Is_Call'] = ~cad_raw['Is_Call']
                usdcad_raw['Settle'] = cad_raw['Settle'] / (cad_raw['Strike'] * cad_spot)
                
                calculate_gex_pipeline(usdcad_raw, "USDCAD", DATA_DIR, session_date)
        except Exception as e:
            print(f"[USDCAD] Error during processing: {e}")

    # Step 8: Clean up old GEX files in MT5 directory and local data directory (keep 14 days)
    cleanup_old_files(days_to_keep=14)
    cleanup_old_files(target_dir=DATA_DIR, days_to_keep=14)

