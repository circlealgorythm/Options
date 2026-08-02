import os
import datetime
import re
import shutil
import pandas as pd
import pdfplumber
from src.parser import download_cme_bulletin, extract_bulletin_date, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma, find_gamma_flip
from src.expiry import MONTH_MAP, resolve_option_expiry, trading_days_to_expiry
from src.product_config import CATALOG_VERSION, contract_size_for, get_product_config

DEFAULT_MT5_GEX_DIR = r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX"

def resolve_session_date(pdf_path, bulletin_date=None, today=None):
    if today is None:
        today = datetime.date.today()

    publish_date = None
    try:
        publish_date = datetime.datetime.fromtimestamp(os.path.getmtime(pdf_path)).date()
    except OSError:
        pass

    resolved = None
    if publish_date is not None and publish_date >= today:
        resolved = today
    else:
        resolved = bulletin_date or publish_date or today

    # Adjust for weekend and Monday mapping
    if today.weekday() in [0, 5, 6]:  # Monday, Saturday, Sunday
        if resolved.weekday() in [3, 4, 5, 6]:  # Thursday, Friday, Saturday, Sunday
            days_to_monday = (0 - resolved.weekday()) % 7
            resolved += datetime.timedelta(days=days_to_monday)

    return resolved


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


def month_to_expiry_date(month_code, currency=None):
    """Backward-compatible monthly expiry resolver."""
    return resolve_option_expiry(None, month_code, currency)


def compute_dte(month_code, currency=None, as_of_date=None, option_type=None):
    """Compute CME trading days to the exact option-series expiry."""
    if as_of_date is None:
        as_of_date = datetime.date.today()
    expiry = resolve_option_expiry(option_type, month_code, currency, as_of_date)
    if expiry is None:
        return 21
    return trading_days_to_expiry(as_of_date, expiry)


def filter_supported_option_series(raw_df, currency):
    """Return catalog-supported rows and diagnostics for fail-closed filtering."""
    config = get_product_config(currency)
    if config is None:
        raise KeyError(f"Unsupported product: {currency}")
    if raw_df.empty:
        return raw_df.copy(), [], 0

    filtered = raw_df.copy()
    if 'Option_Type' not in filtered.columns:
        return filtered.iloc[0:0].copy(), ['<MISSING>'], len(filtered)
    filtered['Option_Type'] = filtered['Option_Type'].fillna('').astype(str).str.upper()
    supported_mask = filtered['Option_Type'].isin(config.supported_codes)
    unknown_rows = filtered.loc[~supported_mask]
    unknown_codes = sorted(code or '<MISSING>' for code in unknown_rows['Option_Type'].unique())
    return filtered.loc[supported_mask].copy(), unknown_codes, len(unknown_rows)


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

ATM_IV_DISTANCE_PCT = {
    'EUR': 0.02,
    'GBP': 0.02,
    'USDCAD': 0.02,
    'CAD': 0.02,
    'XAU': 0.03,
    'NAS': 0.03,
    'SPX': 0.03,
    'BTC': 0.10,
}

ATM_IV_STRIKE_COUNT = {
    'EUR': 3,
    'GBP': 3,
    'USDCAD': 3,
    'CAD': 3,
    'XAU': 3,
    'NAS': 3,
    'SPX': 3,
    'BTC': 5,
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

def select_daily_call_put_by_codes(calc_df, call_codes, put_codes):
    if calc_df.empty or 'Option_Type' not in calc_df.columns:
        return pd.DataFrame(columns=calc_df.columns)

    call_base = calc_df[
        calc_df['Option_Type'].isin(call_codes) &
        (calc_df['Call_OI'] > 0) &
        (calc_df['Call_Settle'] > 0.0)
    ].copy()
    if call_base.empty:
        return pd.DataFrame(columns=calc_df.columns)

    call_df = filter_nearest_month(call_base)
    selected_month = nearest_month(call_df['Contract_Month'].dropna().unique())
    if not selected_month:
        return pd.DataFrame(columns=calc_df.columns)

    same_code_put_base = calc_df[
        calc_df['Option_Type'].isin(call_codes) &
        (calc_df['Contract_Month'] == selected_month) &
        (calc_df['Put_OI'] > 0) &
        (calc_df['Put_Settle'] > 0.0)
    ].copy()

    if not same_code_put_base.empty:
        put_df = same_code_put_base
    else:
        put_base = calc_df[
            calc_df['Option_Type'].isin(put_codes) &
            (calc_df['Put_OI'] > 0) &
            (calc_df['Put_Settle'] > 0.0)
        ].copy()
        put_df = put_base[put_base['Contract_Month'] == selected_month].copy()

    if put_df.empty:
        put_df = filter_nearest_month(put_base)

    combined = pd.concat([call_df, put_df], ignore_index=True)
    return combined if is_valid_daily_df(combined) else pd.DataFrame(columns=calc_df.columns)



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


def cleanup_old_files(target_dir=None, days_to_keep=7):
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
    """Select one nearest actual expiry for Daily MDD without mixing weeks."""
    if calc_df.empty:
        return pd.DataFrame(columns=calc_df.columns)
    if as_of_date is None:
        as_of_date = datetime.date.today()
    currency = currency.upper()
    config = get_product_config(currency)
    allowed_codes = config.daily_codes if config else frozenset()
    candidates = calc_df[calc_df['Option_Type'].isin(allowed_codes)].copy()
    if candidates.empty and currency == 'BTC':
        candidates = calc_df.copy()
    if candidates.empty:
        return pd.DataFrame(columns=calc_df.columns)

    if 'Expiry_Date' not in candidates.columns:
        candidates['Expiry_Date'] = candidates.apply(
            lambda row: resolve_option_expiry(
                row.get('Option_Type'), row.get('Contract_Month'), currency, as_of_date
            ),
            axis=1,
        )
    candidates = candidates[candidates['Expiry_Date'].notna()].copy()
    if candidates.empty:
        return pd.DataFrame(columns=calc_df.columns)

    valid_groups = []
    for expiry, expiry_df in candidates.groupby('Expiry_Date'):
        if is_valid_daily_df(expiry_df):
            valid_groups.append((expiry, expiry_df))
    if not valid_groups:
        return pd.DataFrame(columns=calc_df.columns)

    future_groups = [item for item in valid_groups if item[0] >= as_of_date]
    pool = future_groups or valid_groups
    selected_expiry, selected = min(
        pool,
        key=lambda item: (abs((item[0] - as_of_date).days), item[0]),
    )
    return selected.copy()

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


def _infer_series_forward(series_df, fallback_spot):
    """Infer a forward from the dense cluster of put-call parity candidates."""
    candidates = []
    for strike, strike_df in series_df.groupby('Strike'):
        premiums = sorted({float(value) for value in strike_df['Settle'] if value > 0.0})
        if len(premiums) < 2:
            continue
        premium_gap = premiums[-1] - premiums[0]
        if premium_gap <= 0.0:
            continue
        candidates.extend([float(strike) + premium_gap, float(strike) - premium_gap])

    # On expiration day CME can publish only intrinsic value for the liquid
    # side while the opposite side settles at zero. Those rows still identify
    # the forward through K +/- premium; the repeated correct branch forms a
    # dense cluster across strikes.
    if not candidates:
        for row in series_df.itertuples():
            premium = float(row.Settle)
            if premium > 0.0:
                candidates.extend([float(row.Strike) + premium, float(row.Strike) - premium])
    if not candidates:
        return None

    scale = fallback_spot if fallback_spot > 0.0 else float(series_df['Strike'].median())
    tolerance = max(abs(scale) * 0.0025, 1e-6)
    best = max(
        candidates,
        key=lambda candidate: (
            sum(abs(other - candidate) <= tolerance for other in candidates),
            -abs(candidate - scale),
        ),
    )
    cluster = [candidate for candidate in candidates if abs(candidate - best) <= tolerance]
    forward = float(pd.Series(cluster).median())
    if scale > 0.0 and not (0.5 * scale <= forward <= 1.5 * scale):
        return None
    return forward


def infer_mixed_option_sides(df, fallback_spot):
    """Classify combined CME CALLS & PUTS rows without a hard strike split."""
    if df.empty or 'Is_Call' not in df.columns or not df['Is_Call'].isna().any():
        return df.copy()

    result = df.copy()
    if 'Delta' not in result.columns:
        result['Delta'] = 0.0
    else:
        result['Delta'] = pd.to_numeric(result['Delta'], errors='coerce').fillna(0.0)
    group_columns = ['Option_Type', 'Contract_Month']
    for _, series_df in result.groupby(group_columns, dropna=False):
        unresolved = series_df[series_df['Is_Call'].isna()]
        if unresolved.empty:
            continue
        forward = _infer_series_forward(series_df, fallback_spot) or fallback_spot

        for strike, strike_df in unresolved.groupby('Strike'):
            indices = strike_df.index
            deltas = result.loc[indices, 'Delta'].clip(lower=0.0, upper=1.0)
            if float(strike) <= forward:
                inferred_calls = deltas >= 0.5
            else:
                inferred_calls = deltas <= 0.5

            # If delta is absent for every duplicate row, premium identifies the
            # ITM side relative to the inferred forward.
            if len(indices) >= 2 and (deltas == 0.0).all():
                premiums = result.loc[indices, 'Settle']
                call_index = premiums.idxmax() if float(strike) <= forward else premiums.idxmin()
                inferred_calls = pd.Series(False, index=indices)
                inferred_calls.loc[call_index] = True

            result.loc[indices, 'Is_Call'] = inferred_calls.astype(bool).values

    return result


def estimate_spot_from_put_call_parity(month_df, fallback_spot):
    """
    Estimate the futures/forward reference from matching calls and puts.

    CME bulletins can contain several option series in the same contract month.
    Mixing those series by month alone can pair a weekly call with a monthly put
    and produce a false ATM strike. Keep parity candidates inside one
    Option_Type and ignore zero-OI rows, which are often stale settlement marks.
    """
    if month_df.empty:
        return None

    required_cols = {'Option_Type', 'Strike', 'Settle', 'OI', 'Is_Call'}
    if not required_cols.issubset(month_df.columns):
        return None

    candidates = []
    valid_df = month_df[(month_df['OI'] > 0) & (month_df['Settle'] > 0.0)].copy()
    if valid_df.empty:
        return None

    for _, series_df in valid_df.groupby('Option_Type', dropna=False):
        calls = series_df[series_df['Is_Call'] == True].groupby('Strike')['Settle'].max()
        puts = series_df[series_df['Is_Call'] == False].groupby('Strike')['Settle'].max()
        common = calls.index.intersection(puts.index)
        if common.empty:
            continue

        parity_spots = common.to_series().astype(float) + calls[common].astype(float) - puts[common].astype(float)
        parity_spots = parity_spots[parity_spots > 0.0]
        if fallback_spot > 0.0:
            parity_spots = parity_spots[(parity_spots >= 0.5 * fallback_spot) & (parity_spots <= 1.5 * fallback_spot)]

        candidates.extend(parity_spots.tolist())

    if not candidates:
        return None

    return float(pd.Series(candidates).median())

def weighted_median(values, weights):
    if len(values) == 0:
        return None
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total_weight = sum(w for _, w in pairs)
    if total_weight <= 0:
        return None
    midpoint = total_weight / 2.0
    running = 0.0
    for value, weight in pairs:
        running += weight
        if running >= midpoint:
            return float(value)
    return float(pairs[-1][0])

def estimate_atm_iv(option_df, currency, spot, T, r, min_iv):
    if option_df.empty or spot <= 0.0:
        return None

    distance_pct = ATM_IV_DISTANCE_PCT.get(currency, 0.03)
    valid_df = option_df[(option_df['OI'] > 0) & (option_df['Settle'] > 0.0)].copy()
    if valid_df.empty:
        return None

    valid_df['Distance_Pct'] = (valid_df['Strike'] - spot).abs() / spot
    strike_count = ATM_IV_STRIKE_COUNT.get(currency, 3)
    nearest_strikes = sorted(valid_df['Strike'].dropna().unique(), key=lambda strike: abs(strike - spot))[:strike_count]
    candidates = valid_df[valid_df['Strike'].isin(nearest_strikes)].copy()
    if len(candidates) < 2:
        candidates = valid_df[valid_df['Distance_Pct'] <= distance_pct].copy()
    if len(candidates) < 2:
        candidates = valid_df[valid_df['Distance_Pct'] <= distance_pct * 2.0].copy()
    if candidates.empty:
        return None

    iv_values = []
    weights = []
    for _, row in candidates.iterrows():
        option_type = 'C' if bool(row['Is_Call']) else 'P'
        iv = implied_volatility(row['Settle'], spot, row['Strike'], T, r, option_type)
        if min_iv <= iv <= 3.0:
            iv_values.append(iv)
            weights.append(max(float(row['OI']), 1.0))

    return weighted_median(iv_values, weights)

def select_iv_month(months, currency, as_of_date):
    sorted_months = sorted([m for m in months if month_sort_key(m) != (9999, 99)], key=month_sort_key)
    if not sorted_months:
        return None, 21, None, None

    original_month = sorted_months[0]
    original_dte = compute_dte(original_month, currency, as_of_date)
    selected_month = original_month
    selected_dte = original_dte
    for candidate_month in sorted_months:
        candidate_dte = compute_dte(candidate_month, currency, as_of_date)
        if candidate_dte >= MIN_DTE_FOR_IV:
            selected_month = candidate_month
            selected_dte = candidate_dte
            break

    return selected_month, selected_dte, original_month, original_dte

def convert_cad_options_to_usdcad(cad_raw, cad_spot):
    usdcad_raw = cad_raw.copy()
    usdcad_raw['Strike'] = 1.0 / cad_raw['Strike']
    usdcad_raw['Is_Call'] = ~cad_raw['Is_Call']

    call_mask = cad_raw['Is_Call'] == True
    put_mask = cad_raw['Is_Call'] == False
    usdcad_raw['Settle'] = 0.0

    # CADUSD call -> USDCAD put. Exact breakeven conversion:
    # CAD BE = K + p, USDCAD BE = 1 / (K + p), premium = 1/K - BE.
    call_denominator = cad_raw.loc[call_mask, 'Strike'] + cad_raw.loc[call_mask, 'Settle']
    valid_call = call_mask & (cad_raw['Strike'] > 0.0) & (call_denominator > 0.0)
    usdcad_raw.loc[valid_call, 'Settle'] = (
        (1.0 / cad_raw.loc[valid_call, 'Strike']) -
        (1.0 / (cad_raw.loc[valid_call, 'Strike'] + cad_raw.loc[valid_call, 'Settle']))
    )

    # CADUSD put -> USDCAD call. CAD BE = K - p, USDCAD BE = 1 / (K - p),
    # premium = BE - 1/K.
    put_denominator = cad_raw.loc[put_mask, 'Strike'] - cad_raw.loc[put_mask, 'Settle']
    valid_put = put_mask & (cad_raw['Strike'] > 0.0) & (put_denominator > 0.0)
    usdcad_raw.loc[valid_put, 'Settle'] = (
        (1.0 / (cad_raw.loc[valid_put, 'Strike'] - cad_raw.loc[valid_put, 'Settle'])) -
        (1.0 / cad_raw.loc[valid_put, 'Strike'])
    )

    # Fallback for malformed rows that cannot be converted exactly.
    invalid = usdcad_raw['Settle'] <= 0.0
    usdcad_raw.loc[invalid, 'Settle'] = cad_raw.loc[invalid, 'Settle'] / (cad_raw.loc[invalid, 'Strike'] * cad_spot)
    return usdcad_raw

def detect_spot_and_classify(raw_df, currency):
    if raw_df.empty:
        return FALLBACK_SPOT_MAP.get(currency, 1.0), {}, raw_df
        
    df = raw_df.copy()
    
    df['Strike'] = pd.to_numeric(df['Strike'], errors='coerce')
    df['Settle'] = pd.to_numeric(df['Settle'], errors='coerce')
    df['OI'] = pd.to_numeric(df['OI'], errors='coerce')
    df = df.dropna(subset=['Contract_Month', 'Strike', 'Settle'])
    # CME PDFs repeat many tables in native and decimal quote formats. Round
    # their mathematically identical values before identity-based deduplication
    # so 0.008199999... and 0.0082 do not double OI/GEX.
    df['Strike'] = df['Strike'].round(10)
    df['Settle'] = df['Settle'].round(10)
    if 'Delta' in df.columns:
        df['Delta'] = pd.to_numeric(df['Delta'], errors='coerce').fillna(0.0)
        df.sort_values('Delta', inplace=True)
        df = df.drop_duplicates(
            subset=['Option_Type', 'Contract_Month', 'Strike', 'Settle', 'OI', 'Is_Call'],
            keep='last',
        )
    fallback_spot = FALLBACK_SPOT_MAP.get(currency, 1.0)
    df = infer_mixed_option_sides(df, fallback_spot)
    df = df.drop_duplicates(
        subset=['Option_Type', 'Contract_Month', 'Strike', 'Settle', 'OI', 'Is_Call']
    ).reset_index(drop=True)
    
    # Compute spot per contract month
    df_for_spot = df.copy()
    df_for_spot['Settle'] = df_for_spot['Settle'].round(6)
    df_for_spot = df_for_spot.drop_duplicates(subset=['Option_Type', 'Contract_Month', 'Strike', 'Settle', 'OI'])
    
    min_settle_threshold = {
        'EUR': 0.0001, 'GBP': 0.0001, 'USDCAD': 0.0001, 'CAD': 0.0001,
        'XAU': 1.0, 'NAS': 5.0, 'SPX': 5.0, 'BTC': 100.0,
    }.get(currency, 1.0)
    
    spots_per_month = {}
    months = df_for_spot['Contract_Month'].unique()
    for m in months:
        m_df = df_for_spot[df_for_spot['Contract_Month'] == m]
        spot_m = fallback_spot
        
        # If Is_Call is perfectly known, use it
        if not m_df['Is_Call'].isna().all():
            parity_spot = estimate_spot_from_put_call_parity(m_df, fallback_spot)
            if parity_spot is not None:
                spot_m = parity_spot
            else:
                series_forwards = [
                    _infer_series_forward(series_df, fallback_spot)
                    for _, series_df in m_df.groupby('Option_Type', dropna=False)
                ]
                series_forwards = [value for value in series_forwards if value is not None]
                if series_forwards:
                    spot_m = float(pd.Series(series_forwards).median())
                else:
                    calls = m_df[(m_df['Is_Call'] == True) & (m_df['OI'] > 0)].groupby('Strike')['Settle'].max()
                    puts = m_df[(m_df['Is_Call'] == False) & (m_df['OI'] > 0)].groupby('Strike')['Settle'].max()
                    common = calls.index.intersection(puts.index)
                    if not common.empty:
                        diffs = (calls[common] - puts[common]).abs()
                        valid_common = [s for s in common if calls[s] >= min_settle_threshold and puts[s] >= min_settle_threshold]
                        if valid_common:
                            spot_m = diffs[valid_common].idxmin()
                        else:
                            spot_m = diffs.idxmin()
        else:
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
        
    # Conservative fallback for malformed rows that still could not be inferred.
    if df['Is_Call'].isna().any():
        for idx, row in df[df['Is_Call'].isna()].iterrows():
            m = row['Contract_Month']
            strike = row['Strike']
            spot_guess = spots_per_month.get(m, global_spot)
            df.at[idx, 'Is_Call'] = strike >= spot_guess

    df['Is_Call'] = df['Is_Call'].astype(bool)

    return global_spot, spots_per_month, df

def calculate_gex_pipeline(raw_df, currency, output_dir, as_of_date=None):
    if raw_df.empty:
        print(f"No raw data for {currency}")
        return

    calculation_date = as_of_date or datetime.date.today()
    config = get_product_config(currency)
    supported_raw, unknown_option_types, unknown_row_count = filter_supported_option_series(
        raw_df, currency
    )
    if supported_raw.empty:
        raise RuntimeError(
            f"[{currency}] No supported CME option series remain after fail-closed filtering"
        )

    spot, spots_per_month, classified_df = detect_spot_and_classify(supported_raw, currency)
    print(f"[{currency}] Detected Spot price: {spot:.4f}")
    
    import math
    
    r = 0.0
    unresolved_expiry_count = 0
    expired_row_count = 0
    estimated_expiry_types = []

    if not classified_df.empty:
        classified_df = classified_df.reset_index(drop=True)
        classified_df['Expiry_Date'] = classified_df.apply(
            lambda row: resolve_option_expiry(
                row.get('Option_Type'), row.get('Contract_Month'), currency, calculation_date
            ),
            axis=1,
        )
        unresolved_expiry_count = int(classified_df['Expiry_Date'].isna().sum())
        expired_mask = classified_df['Expiry_Date'].apply(
            lambda expiry: expiry is not None and expiry < calculation_date
        )
        expired_row_count = int(expired_mask.sum())
        classified_df = classified_df[
            classified_df['Expiry_Date'].notna() & ~expired_mask
        ].copy()
        if classified_df.empty:
            raise RuntimeError(
                f"[{currency}] No non-expired option rows with a resolved CME expiry"
            )

        estimated_expiry_types = sorted(
            set(classified_df['Option_Type']) & set(config.rolling_weekdays)
        )
        classified_df['_Estimated_Expiry'] = classified_df['Option_Type'].isin(
            config.rolling_weekdays
        )
        # Prefer an exact numbered code over its bulletin aggregate alias when
        # both text layers describe the same contract row.
        classified_df.sort_values('_Estimated_Expiry', inplace=True)
        classified_df.drop_duplicates(
            subset=[
                'Contract_Month', 'Expiry_Date', 'Strike', 'Settle', 'OI', 'Is_Call'
            ],
            keep='first',
            inplace=True,
        )
        classified_df['DTE'] = classified_df['Expiry_Date'].apply(
            lambda expiry: trading_days_to_expiry(calculation_date, expiry)
        )
        classified_df['_T'] = classified_df['DTE'].apply(
            lambda dte: max(float(dte) / 252.0, 1.0 / 252.0)
        )

        # Estimate ATM IV from one exact expiry instead of blending daily,
        # weekly, and monthly premiums that only share a contract month.
        iv_candidates = classified_df[
            (classified_df['DTE'] >= MIN_DTE_FOR_IV) &
            (classified_df['OI'] > 0) &
            (classified_df['Settle'] > 0.0)
        ].copy()
        if iv_candidates.empty:
            iv_candidates = classified_df[
                (classified_df['DTE'] > 0) &
                (classified_df['OI'] > 0) &
                (classified_df['Settle'] > 0.0)
            ].copy()
        if iv_candidates.empty:
            iv_candidates = classified_df.copy()

        valid_expiries = sorted(iv_candidates['Expiry_Date'].dropna().unique())
        iv_expiry = valid_expiries[0] if valid_expiries else None
        iv_expiry_df = iv_candidates[iv_candidates['Expiry_Date'] == iv_expiry] if iv_expiry else iv_candidates
        iv_dte = int(iv_expiry_df['DTE'].iloc[0]) if not iv_expiry_df.empty else 21
        T_iv = max(iv_dte / 252.0, 1.0 / 252.0)

        min_iv = MIN_IV_THRESHOLD.get(currency, 0.03)
        iv_atm = estimate_atm_iv(iv_expiry_df, currency, spot, T_iv, r, min_iv)
        if iv_atm is None:
            atm_idx = (iv_expiry_df['Strike'] - spot).abs().idxmin()
            atm_row = iv_expiry_df.loc[atm_idx]
            price_atm = atm_row['Settle']
            is_call_val = atm_row['Is_Call']
            if isinstance(is_call_val, pd.Series):
                is_call_val = is_call_val.iloc[0]
            strike_atm = atm_row['Strike']
            if isinstance(strike_atm, pd.Series):
                strike_atm = strike_atm.iloc[0]
            iv_atm = implied_volatility(price_atm, spot, strike_atm, T_iv, 0.0, 'C' if is_call_val else 'P')

        # Minimum IV sanity check
        if iv_atm < min_iv:
            iv_atm = FALLBACK_IV.get(currency, 0.08)
    else:
        iv_atm = FALLBACK_IV.get(currency, 0.08)
        
    sigma_1d = spot * iv_atm * (1.0 / math.sqrt(252.0))
    print(f"[{currency}] ATM IV: {iv_atm:.2%}, Daily Sigma: {sigma_1d:.5f}")

    quality_status = 'WARN' if unknown_row_count or unresolved_expiry_count else (
        'ESTIMATED' if estimated_expiry_types else 'OK'
    )
    print(
        f"[{currency}] Data quality: {quality_status}; input={len(raw_df)}, "
        f"used={len(classified_df)}, unknown={unknown_row_count}, "
        f"unresolved_expiry={unresolved_expiry_count}, expired={expired_row_count}"
    )
    if unknown_option_types:
        print(f"[{currency}] Excluded unknown option types: {', '.join(unknown_option_types)}")
    if estimated_expiry_types:
        print(f"[{currency}] Estimated bulletin aliases: {', '.join(estimated_expiry_types)}")
    
    calculated_rows = []
    strikes_list = []
    ois_list = []
    is_calls_list = []
    ivs_list = []
    times_list = []
    multipliers_list = []
    
    for idx, row in classified_df.iterrows():
        K = row['Strike']
        is_call = row['Is_Call']
        m = row.get('Contract_Month')
        
        local_spot = spots_per_month.get(m, spot)
                
        price = row['Settle']
        T = float(row.get('_T', 0.08))
        contract_size = contract_size_for(currency, row['Option_Type'])
        
        # Cap deep ITM/OTM strikes: if strike is >30% from spot, zero GEX
        # These are noise that blows up the visual scale
        strike_distance_pct = abs(K - local_spot) / local_spot if local_spot > 0 else 0
        skip_gex = strike_distance_pct > 0.30
        
        if price <= 0.0 or skip_gex:
            iv = 0.001
            gamma = 0.0
            gex = 0.0
            abs_gamma = 0.0
            if skip_gex and price > 0.0:
                # Still compute IV for gamma_flip but zero out display GEX
                if is_call:
                    iv = implied_volatility(price, local_spot, K, T, r, 'C')
                else:
                    iv = implied_volatility(price, local_spot, K, T, r, 'P')
        elif is_call:
            iv = implied_volatility(price, local_spot, K, T, r, 'C')
            gamma = bs_gamma(local_spot, K, T, r, iv) if iv > 0.001 else 0.0
            gex = calculate_gex(gamma, row['OI'], contract_size, local_spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'], contract_size)
        else:
            iv = implied_volatility(price, local_spot, K, T, r, 'P')
            gamma = bs_gamma(local_spot, K, T, r, iv) if iv > 0.001 else 0.0
            gex = -calculate_gex(gamma, row['OI'], contract_size, local_spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'], contract_size)

        call_oi = row['OI'] if is_call else 0
        put_oi = row['OI'] if not is_call else 0
        call_settle = price if is_call else 0.0
        put_settle = price if not is_call else 0.0
            
        calculated_rows.append({
            "Strike": K,
            "Option_Type": row['Option_Type'],
            "Contract_Month": row['Contract_Month'],
            "Expiry_Date": row.get('Expiry_Date'),
            "DTE": row.get('DTE', 21),
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
        times_list.append(T)
        multipliers_list.append(contract_size)
        
    calc_df = pd.DataFrame(calculated_rows)
    gamma_flip_val = find_gamma_flip(
        strikes_list,
        ois_list,
        is_calls_list,
        ivs_list,
        spot,
        r=r,
        times=times_list,
        multipliers=multipliers_list,
    )
    if gamma_flip_val is None:
        print(f"[{currency}] Gamma Flip: no zero crossing in the validated search range")
    else:
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
    global_df = calc_df[calc_df['Option_Type'].isin(config.global_codes)]
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
    daily_month = daily_df['Contract_Month'].iloc[0] if not daily_df.empty else None
    daily_reference_spot = spots_per_month.get(daily_month, spot)

    daily_call = select_near_spot_mdd_settle(daily_df, 'Call', daily_reference_spot).rename(columns={'Call_OI': 'Daily_Call_OI', 'Call_Settle': 'Daily_Call_Settle'})
    daily_put = select_near_spot_mdd_settle(daily_df, 'Put', daily_reference_spot).rename(columns={'Put_OI': 'Daily_Put_OI', 'Put_Settle': 'Daily_Put_Settle'})
    
    global_call = get_max_oi_level(global_call_df, 'Call').rename(columns={'Call_OI': 'Global_Call_OI'})
    global_put = get_max_oi_level(global_put_df, 'Put').rename(columns={'Put_OI': 'Global_Put_OI'})
    
    # Group by Strike and sum values across all expirations/series
    summary = calc_df.groupby('Strike').agg({
        'GEX': 'sum',
        'Abs_Gamma': 'sum'
    }).reset_index()
    
    summary = summary.merge(daily_call, on='Strike', how='left')
    summary = summary.merge(daily_put, on='Strike', how='left')
    summary = summary.merge(global_call, on='Strike', how='left')
    summary = summary.merge(global_put, on='Strike', how='left')
    
    for column in summary.columns.difference(['Currency']):
        summary[column] = pd.to_numeric(summary[column], errors='coerce').fillna(0.0)
    
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
    daily_expiry = daily_df['Expiry_Date'].iloc[0] if not daily_df.empty and 'Expiry_Date' in daily_df.columns else None
    global_expiries = global_call_df['Expiry_Date'].dropna() if not global_call_df.empty and 'Expiry_Date' in global_call_df.columns else []
    global_expiry = min(global_expiries) if len(global_expiries) else None
    summary['Daily_Expiry'] = daily_expiry.isoformat() if daily_expiry else 'UNKNOWN'
    summary['Global_Expiry'] = global_expiry.isoformat() if global_expiry else 'UNKNOWN'

    # Store futures spot price directly so EA doesn't derive it from R68
    summary['Futures_Spot'] = spot
    summary['Gamma_Flip'] = gamma_flip_val if gamma_flip_val is not None else 0.0
    summary['Gamma_Flip_Status'] = 'FOUND' if gamma_flip_val is not None else 'NO_CROSSING'
    summary['Quality_Status'] = quality_status
    summary['Series_Catalog_Version'] = CATALOG_VERSION
    summary['Input_Rows'] = len(raw_df)
    summary['Used_Rows'] = len(classified_df)
    summary['Excluded_Unknown_Rows'] = unknown_row_count
    summary['Excluded_Unresolved_Expiry_Rows'] = unresolved_expiry_count
    summary['Excluded_Expired_Rows'] = expired_row_count
    summary['Unknown_Option_Types'] = ';'.join(unknown_option_types) or 'NONE'
    summary['Estimated_Expiry_Types'] = ';'.join(estimated_expiry_types) or 'NONE'
    validate_mdd_summary(summary, currency)
    
    # Save to CSV
    output_date = as_of_date if as_of_date is not None else datetime.date.today()
    today_str = output_date.strftime("%Y-%m-%d")
    filename = f"GEX_USDCAD_{today_str}.csv" if currency == "USDCAD" else f"GEX_{currency}USD_{today_str}.csv"
    out_file = os.path.join(output_dir, filename)
    summary.to_csv(out_file, index=False)
    print(f"Saved {currency} levels to {out_file} ({len(summary)} strikes)")
    copy_csv_to_mt5(out_file)

if __name__ == "__main__":
    import sys
    if datetime.date.today().weekday() in [5, 6] and "--force" not in sys.argv:
        print("Weekend detected (Saturday/Sunday). Skipping pipeline execution to avoid confusion. Use --force to override.")
        sys.exit(0)

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
            session_date = resolve_session_date(eur_dest, eur_bulletin_date)
            print(f"[EUR] CME bulletin trade date: {eur_bulletin_date}; session date: {session_date}")
            eur_raw = parse_cme_pdf(eur_dest, "EUR", is_call_only=None)
            calculate_gex_pipeline(eur_raw, "EUR", DATA_DIR, session_date)
        except Exception as e:
            print(f"[EUR] Error during processing: {e}")
        
    # Step 3: Parse and process GBP data
    if gbp_call_ok and gbp_put_ok:
        try:
            gbp_bulletin_date = extract_bulletin_date(gbp_call_dest) or extract_bulletin_date(gbp_put_dest) or datetime.date.today()
            session_date = resolve_session_date(gbp_call_dest, gbp_bulletin_date)
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
            session_date = resolve_session_date(xau_dest, xau_bulletin_date)
            print(f"[XAU] CME bulletin trade date: {xau_bulletin_date}; session date: {session_date}")
            xau_raw = parse_cme_pdf(xau_dest, "XAU", is_call_only=None)
            if not xau_raw.empty:
                gold_option_types = get_product_config('XAU').supported_codes
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
            session_date = resolve_session_date(nas_dest, nas_bulletin_date)
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
            session_date = resolve_session_date(sp_call_dest, sp_bulletin_date)
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
            session_date = resolve_session_date(crypto_dest, crypto_bulletin_date)
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
            session_date = resolve_session_date(cad_call_dest, cad_bulletin_date)
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
                
                usdcad_raw = convert_cad_options_to_usdcad(cad_raw, cad_spot)
                
                calculate_gex_pipeline(usdcad_raw, "USDCAD", DATA_DIR, session_date)
        except Exception as e:
            print(f"[USDCAD] Error during processing: {e}")

    # Step 8: Clean up old GEX files in MT5 directory and local data directory (keep 7 days)
    cleanup_old_files(days_to_keep=7)
    cleanup_old_files(target_dir=DATA_DIR, days_to_keep=7)

