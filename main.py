import os
import datetime
import re
import shutil
import pandas as pd
import pdfplumber
from src.parser import download_cme_bulletin, extract_bulletin_date, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

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
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

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

ETH_DAILY_BY_WEEKDAY = {0: 'ETH', 1: 'ETH', 2: 'ETH', 3: 'ETH', 4: 'ETH'}
ETH_DAILY_CODES = ['ETH']
ETH_WEEKLY_CODES = ['ETH']
ETH_DAILY_CODE_DOW = {'ETH': 0}
ETH_WEEKLY_CODE_DOW = {'ETH': 0}

CAD_DAILY_BY_WEEKDAY = {0: 'MCM', 1: 'TCD', 2: 'WCD', 3: 'SCD', 4: '1CD'}
CAD_DAILY_CODES = ['MCM', 'TCD', 'WCD', 'SCD', '1CD', '2CD', '3CD', '4CD', '5CD']
CAD_WEEKLY_CODES = CAD_DAILY_CODES.copy()
CAD_DAILY_CODE_DOW = {
    'MCM': 0, 'TCD': 1, 'WCD': 2, 'SCD': 3,
    '1CD': 4, '2CD': 4, '3CD': 4, '4CD': 4, '5CD': 4
}
CAD_WEEKLY_CODE_DOW = CAD_DAILY_CODE_DOW.copy()


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


def filter_nearest_month(df):
    if df.empty or 'Contract_Month' not in df.columns:
        return df
    month = nearest_month(df['Contract_Month'].dropna().unique())
    if month is None:
        return df.iloc[0:0]
    return df[df['Contract_Month'] == month]


def filter_nearest_code(df, code_dow_map, as_of_date):
    if df.empty or 'Option_Type' not in df.columns:
        return df

    available = [code for code in code_dow_map if code in set(df['Option_Type'])]
    if not available:
        return df.iloc[0:0]

    dow = as_of_date.weekday()
    code = sorted(available, key=lambda item: ((code_dow_map[item] - dow) % 5, code_dow_map[item], item))[0]
    return df[df['Option_Type'] == code]


def copy_csv_to_mt5(csv_path, mt5_gex_dir=None):
    target_dir = mt5_gex_dir or os.environ.get("MT5_GEX_DIR") or DEFAULT_MT5_GEX_DIR
    if not target_dir or not os.path.isdir(target_dir):
        print(f"MT5 GEX directory not found, skipping local copy: {target_dir}")
        return None

    filename = os.path.basename(csv_path)
    if "XAUUSD" in filename:
        target_dir = os.path.join(target_dir, "XAU")
        os.makedirs(target_dir, exist_ok=True)
    elif "NASUSD" in filename:
        target_dir = os.path.join(target_dir, "NAS100")
        os.makedirs(target_dir, exist_ok=True)
    elif "BTCUSD" in filename or "ETHUSD" in filename:
        target_dir = os.path.join(target_dir, "Crypto")
        os.makedirs(target_dir, exist_ok=True)
    elif "USDCAD" in filename:
        target_dir = os.path.join(target_dir, "USDCAD")
        os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, filename)
    try:
        shutil.copy2(csv_path, target_path)
        print(f"Copied {os.path.basename(csv_path)} to MT5 GEX directory: {target_path}")
        return target_path
    except OSError as exc:
        print(f"Warning: failed to copy {csv_path} to {target_path}: {exc}")
        return None


def cleanup_old_files(target_dir=None, days_to_keep=30):
    import time
    base_dir = target_dir or os.environ.get("MT5_GEX_DIR") or DEFAULT_MT5_GEX_DIR
    if not base_dir or not os.path.isdir(base_dir):
        return

    print(f"Cleaning up files older than {days_to_keep} days in: {base_dir}")
    now = time.time()
    cutoff = now - (days_to_keep * 86400)

    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            if filename.startswith("GEX_") and filename.endswith(".csv"):
                filepath = os.path.join(root, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    if mtime < cutoff:
                        os.remove(filepath)
                        print(f"Deleted old GEX file: {filepath} (modified {time.ctime(mtime)})")
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
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(EUR_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, EUR_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(EUR_DAILY_CODES)]
        return filter_nearest_month(filter_nearest_code(daily, EUR_DAILY_CODE_DOW, as_of_date))

    if currency == 'GBP':
        target_code = GBP_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(GBP_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, GBP_WEEKLY_CODE_DOW, as_of_date))

        short = calc_df[calc_df['Option_Type'].isin(GBP_SHORT_CODES)]
        return filter_nearest_month(filter_nearest_code(short, GBP_SHORT_CODE_DOW, as_of_date))

    if currency == 'XAU':
        target_code = XAU_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(XAU_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, XAU_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(XAU_DAILY_CODES)]
        return filter_nearest_month(filter_nearest_code(daily, XAU_DAILY_CODE_DOW, as_of_date))

    if currency == 'NAS':
        target_code = NAS_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(NAS_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, NAS_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(NAS_DAILY_CODES)]
        return filter_nearest_month(filter_nearest_code(daily, NAS_DAILY_CODE_DOW, as_of_date))

    if currency == 'BTC':
        target_code = BTC_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)
        return filter_nearest_month(calc_df)

    if currency == 'ETH':
        target_code = ETH_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)
        return filter_nearest_month(calc_df)

    if currency in ['CAD', 'USDCAD']:
        target_code = CAD_DAILY_BY_WEEKDAY.get(dow)
        exact = calc_df[calc_df['Option_Type'] == target_code]
        if not exact.empty:
            return filter_nearest_month(exact)

        weekly = calc_df[calc_df['Option_Type'].isin(CAD_WEEKLY_CODES)]
        if not weekly.empty:
            return filter_nearest_month(filter_nearest_code(weekly, CAD_WEEKLY_CODE_DOW, as_of_date))

        daily = calc_df[calc_df['Option_Type'].isin(CAD_DAILY_CODES)]
        return filter_nearest_month(filter_nearest_code(daily, CAD_DAILY_CODE_DOW, as_of_date))

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
        raise RuntimeError(f"{currency} summary is missing required MDD data: {', '.join(missing)}")


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


def calculate_gex_pipeline(raw_df, currency, output_dir, as_of_date=None):
    if raw_df.empty:
        print(f"No raw data for {currency}")
        return
        
    # Auto-detect Spot price from ATM options (delta close to 0.5)
    atm_rows = raw_df[(raw_df['Delta'] >= 0.45) & (raw_df['Delta'] <= 0.55)]
    if not atm_rows.empty:
        nearest_m = nearest_month(atm_rows['Contract_Month'].dropna().unique())
        if nearest_m:
            spot = atm_rows[atm_rows['Contract_Month'] == nearest_m]['Strike'].mean()
        else:
            spot = atm_rows['Strike'].mean()
    else:
        spot = 4600.0 if currency == 'XAU' else (30000.0 if currency == 'NAS' else (66000.0 if currency == 'BTC' else (3400.0 if currency == 'ETH' else (1.1500 if currency == 'EUR' else (1.3700 if currency == 'USDCAD' else 1.3400))))) # Fallbacks
        
    print(f"[{currency}] Detected Spot price: {spot:.4f}")
    
    # Calculate ATM implied volatility and daily sigma
    import math
    if not raw_df.empty:
        raw_df = raw_df.reset_index(drop=True)
        atm_idx = (raw_df['Strike'] - spot).abs().idxmin()
        atm_row = raw_df.loc[atm_idx]
        price_atm = atm_row['Settle']
        is_call_val = atm_row['Is_Call']
        if isinstance(is_call_val, pd.Series):
            is_call_val = is_call_val.iloc[0]
        strike_atm = atm_row['Strike']
        if isinstance(strike_atm, pd.Series):
            strike_atm = strike_atm.iloc[0]
        iv_atm = implied_volatility(price_atm, spot, strike_atm, 0.08, 0.0, 'C' if is_call_val else 'P')
        if iv_atm <= 0.001:
            iv_atm = 0.15 if currency == 'XAU' else (0.12 if currency == 'NAS' else (0.50 if currency == 'BTC' else (0.55 if currency == 'ETH' else (0.07 if currency == 'EUR' else (0.06 if currency == 'USDCAD' else 0.08)))))
    else:
        iv_atm = 0.15 if currency == 'XAU' else (0.12 if currency == 'NAS' else (0.50 if currency == 'BTC' else (0.55 if currency == 'ETH' else (0.07 if currency == 'EUR' else (0.06 if currency == 'USDCAD' else 0.08)))))
        
    sigma_1d = spot * iv_atm * (1.0 / math.sqrt(252.0))
    print(f"[{currency}] ATM IV: {iv_atm:.2%}, Daily Sigma: {sigma_1d:.5f}")
    
    contract_size = 100000 if currency == 'USDCAD' else (5 if currency == 'BTC' else (50 if currency == 'ETH' else (20 if currency == 'NAS' else (100 if currency == 'XAU' else (125000 if currency == 'EUR' else 62500)))))
    T = 0.08
    r = 0.0
    
    calculated_rows = []
    for idx, row in raw_df.iterrows():
        K = row['Strike']
        
        # Determine Option Type (Call or Put)
        if row['Is_Call'] is not None:
            is_call = row['Is_Call']
        else:
            # Delta-based heuristic relative to Spot
            if K < spot:
                is_call = (row['Delta'] >= 0.5)
            else:
                is_call = (row['Delta'] < 0.5)
                
        # Calculate Greeks & GEX
        price = row['Settle']
        
        if is_call:
            iv = implied_volatility(price, spot, K, T, r, 'C')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = row['OI']
            put_oi = 0
            call_settle = price
            put_settle = 0.0
        else:
            iv = implied_volatility(price, spot, K, T, r, 'P')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = -calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = 0
            put_oi = row['OI']
            call_settle = 0.0
            put_settle = price
            
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
        
    calc_df = pd.DataFrame(calculated_rows)
    
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
    max_month = 'UNKNOWN'
    global_codes = {
        'EUR': ['EUU'],
        'GBP': ['GBU'],
        'XAU': ['OG'],
        'NAS': ['EMINI'],
        'BTC': ['BTC'],
        'ETH': ['ETH'],
        'USDCAD': ['CAU']
    }.get(currency, ['OG'])
    global_df = calc_df[calc_df['Option_Type'].isin(global_codes)]
    if not global_df.empty:
        month_oi = global_df.groupby('Contract_Month')['Call_OI'].sum() + global_df.groupby('Contract_Month')['Put_OI'].sum()
        max_month = month_oi.idxmax()
        global_df = global_df[global_df['Contract_Month'] == max_month]
    else:
        global_df = calc_df
        
    # Determine Daily DF
    daily_df = select_daily_contracts(calc_df, currency, as_of_date)
    
    daily_call = select_near_spot_mdd_settle(daily_df, 'Call', spot).rename(columns={'Call_OI': 'Daily_Call_OI', 'Call_Settle': 'Daily_Call_Settle'})
    daily_put = select_near_spot_mdd_settle(daily_df, 'Put', spot).rename(columns={'Put_OI': 'Daily_Put_OI', 'Put_Settle': 'Daily_Put_Settle'})
    
    global_call = get_max_oi_level(global_df, 'Call').rename(columns={'Call_OI': 'Global_Call_OI'})
    global_put = get_max_oi_level(global_df, 'Put').rename(columns={'Put_OI': 'Global_Put_OI'})
    
    # Group by Strike and sum values across all expirations/series
    summary = calc_df.groupby('Strike').agg({
        'GEX': 'sum',
        'Abs_Gamma': 'sum'
    }).reset_index()
    
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
        eur_bulletin_date = extract_bulletin_date(eur_dest) or datetime.date.today()
        session_date = datetime.date.today()
        print(f"[EUR] CME bulletin trade date: {eur_bulletin_date}; session date: {session_date}")
        eur_raw = parse_cme_pdf(eur_dest, "EUR", is_call_only=None)
        calculate_gex_pipeline(eur_raw, "EUR", DATA_DIR, session_date)
        
    # Step 3: Parse and process GBP data
    if gbp_call_ok and gbp_put_ok:
        gbp_bulletin_date = extract_bulletin_date(gbp_call_dest) or extract_bulletin_date(gbp_put_dest) or datetime.date.today()
        session_date = datetime.date.today()
        print(f"[GBP] CME bulletin trade date: {gbp_bulletin_date}; session date: {session_date}")
        gbp_calls = parse_cme_pdf(gbp_call_dest, "GBP", is_call_only=True)
        gbp_puts = parse_cme_pdf(gbp_put_dest, "GBP", is_call_only=False)
        gbp_raw = pd.concat([gbp_calls, gbp_puts])
        calculate_gex_pipeline(gbp_raw, "GBP", DATA_DIR, session_date)

    # Step 4: Parse and process XAU data
    xau_section = "Section64_Metals_Option_Products.pdf"
    xau_dest = os.path.join(DATA_DIR, xau_section)
    xau_ok = download_cme_bulletin(xau_section, xau_dest)
    if xau_ok:
        xau_bulletin_date = extract_bulletin_date(xau_dest) or datetime.date.today()
        session_date = datetime.date.today()
        print(f"[XAU] CME bulletin trade date: {xau_bulletin_date}; session date: {session_date}")
        xau_raw = parse_cme_pdf(xau_dest, "XAU", is_call_only=None)
        if not xau_raw.empty:
            gold_option_types = ['OG', 'GMW', 'GWT', 'GWW', 'GWR', 'OG1', 'OG2', 'OG3', 'OG4', 'OG5', 'MMG', 'FMG']
            xau_raw = xau_raw[xau_raw['Option_Type'].isin(gold_option_types)]
        calculate_gex_pipeline(xau_raw, "XAU", DATA_DIR, session_date)

    # Step 5: Parse and process NAS data
    nas_section = "Section40_Nasdaq_100_And_E_Mini_Nasdaq_100_Options.pdf"
    nas_dest = os.path.join(DATA_DIR, nas_section)
    nas_ok = download_cme_bulletin(nas_section, nas_dest)
    if nas_ok:
        nas_bulletin_date = extract_bulletin_date(nas_dest) or datetime.date.today()
        session_date = datetime.date.today()
        print(f"[NAS] CME bulletin trade date: {nas_bulletin_date}; session date: {session_date}")
        nas_raw = parse_cme_pdf(nas_dest, "NAS", is_call_only=None)
        if not nas_raw.empty:
            nas_raw = nas_raw[nas_raw['Strike'] >= 10000.0]
        calculate_gex_pipeline(nas_raw, "NAS", DATA_DIR, session_date)

    # Step 6: Parse and process Crypto data
    crypto_section = "Section74_Cryptocurrency.pdf"
    crypto_dest = os.path.join(DATA_DIR, crypto_section)
    crypto_ok = download_cme_bulletin(crypto_section, crypto_dest)
    if crypto_ok:
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
            
        # Process ETH
        eth_raw = crypto_raw[crypto_raw['Option_Type'] == 'ETH']
        if not eth_raw.empty:
            calculate_gex_pipeline(eth_raw, "ETH", DATA_DIR, session_date)
        else:
            print("[Crypto] Warning: No ETH option rows found.")

    # Step 7: Parse and process USDCAD data
    cad_call_section = "Section29_Canadian_Dollar_Call_Options.pdf"
    cad_put_section = "Section30_Canadian_Dollar_Put_Options.pdf"
    cad_call_dest = os.path.join(DATA_DIR, cad_call_section)
    cad_put_dest = os.path.join(DATA_DIR, cad_put_section)
    
    cad_call_ok = download_cme_bulletin(cad_call_section, cad_call_dest)
    cad_put_ok = download_cme_bulletin(cad_put_section, cad_put_dest)
    
    if cad_call_ok and cad_put_ok:
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

    # Step 8: Clean up old GEX files in MT5 directory (keep 30 days)
    cleanup_old_files()

