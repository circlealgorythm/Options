import os
import datetime
import re
import pandas as pd
import pdfplumber
from src.parser import download_cme_bulletin, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

def calculate_gex_pipeline(raw_df, currency, output_dir):
    if raw_df.empty:
        print(f"No raw data for {currency}")
        return
        
    # Auto-detect Spot price from ATM options (delta close to 0.5)
    atm_rows = raw_df[(raw_df['Delta'] >= 0.45) & (raw_df['Delta'] <= 0.55)]
    if not atm_rows.empty:
        spot = atm_rows['Strike'].mean()
    else:
        spot = 1.1500 if currency == 'EUR' else 1.3400 # Fallbacks
        
    print(f"[{currency}] Detected Spot price: {spot:.4f}")
    
    # Calculate ATM implied volatility and daily sigma
    import math
    if not raw_df.empty:
        raw_df = raw_df.reset_index(drop=True)
        atm_idx = (raw_df['Strike'] - spot).abs().idxmin()
        atm_row = raw_df.loc[atm_idx]
        price_atm = atm_row['Settle'] / 100.0
        is_call_val = atm_row['Is_Call']
        if isinstance(is_call_val, pd.Series):
            is_call_val = is_call_val.iloc[0]
        strike_atm = atm_row['Strike']
        if isinstance(strike_atm, pd.Series):
            strike_atm = strike_atm.iloc[0]
        iv_atm = implied_volatility(price_atm, spot, strike_atm, 0.08, 0.0, 'C' if is_call_val else 'P')
        if iv_atm <= 0.001:
            iv_atm = 0.07 if currency == 'EUR' else 0.08
    else:
        iv_atm = 0.07 if currency == 'EUR' else 0.08
        
    sigma_1d = spot * iv_atm * (1.0 / math.sqrt(252.0))
    print(f"[{currency}] ATM IV: {iv_atm:.2%}, Daily Sigma: {sigma_1d:.5f}")
    
    contract_size = 125000 if currency == 'EUR' else 62500
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
        price = row['Settle'] / 100.0
        
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
    
    def get_max_oi_settle(df, type_prefix):
        oi_col = f'{type_prefix}_OI'
        settle_col = f'{type_prefix}_Settle'
        valid_df = df[(df[oi_col] > 0) & (df[settle_col] > 0.0)]
        if not valid_df.empty:
            idx_max = valid_df[oi_col].idxmax()
            return valid_df.loc[[idx_max], ['Strike', settle_col, oi_col]].set_index('Strike')
        return pd.DataFrame(columns=[settle_col, oi_col])
        
    # Determine Global DF
    global_codes = ['EUU', 'GBU']
    global_df = calc_df[calc_df['Option_Type'].isin(global_codes)]
    if not global_df.empty:
        month_oi = global_df.groupby('Contract_Month')['Call_OI'].sum() + global_df.groupby('Contract_Month')['Put_OI'].sum()
        max_month = month_oi.idxmax()
        global_df = global_df[global_df['Contract_Month'] == max_month]
    else:
        global_df = calc_df
        
    # Determine Daily DF
    daily_codes = ['SEC', 'TEC', 'WEC', 'THC', 'FRC', 'SBP', 'TGB', 'WGB', 'MGM']
    daily_candidates = calc_df[calc_df['Option_Type'].isin(daily_codes)]
    
    if not daily_candidates.empty:
        dow = datetime.datetime.today().weekday()
        eur_daily = {0: 'SEC', 1: 'TEC', 2: 'WEC', 3: 'THC', 4: 'FRC'}
        gbp_daily = {0: 'MGB', 1: 'TGB', 2: 'WGB', 3: 'SBP', 4: 'FGB'}
        target_code = eur_daily.get(dow) if currency == 'EUR' else gbp_daily.get(dow)
        
        daily_df = daily_candidates[daily_candidates['Option_Type'] == target_code]
        if daily_df.empty:
            daily_df = daily_candidates
            
        month_oi = daily_df.groupby('Contract_Month')['Call_OI'].sum() + daily_df.groupby('Contract_Month')['Put_OI'].sum()
        if not month_oi.empty:
            min_month = month_oi.idxmin()
            daily_df = daily_df[daily_df['Contract_Month'] == min_month]
    else:
        weekly_codes = ['1EU', '2EU', '3EU', '4EU', '5EU', '1BP', '2BP', '3BP', '4BP', '5BP']
        daily_candidates = calc_df[calc_df['Option_Type'].isin(weekly_codes)]
        if not daily_candidates.empty:
            month_oi = daily_candidates.groupby('Contract_Month')['Call_OI'].sum() + daily_candidates.groupby('Contract_Month')['Put_OI'].sum()
            min_month = month_oi.idxmin()
            daily_df = daily_candidates[daily_candidates['Contract_Month'] == min_month]
        else:
            daily_df = pd.DataFrame(columns=calc_df.columns)
    
    daily_call = get_max_oi_settle(daily_df, 'Call').rename(columns={'Call_OI': 'Daily_Call_OI', 'Call_Settle': 'Daily_Call_Settle'})
    daily_put = get_max_oi_settle(daily_df, 'Put').rename(columns={'Put_OI': 'Daily_Put_OI', 'Put_Settle': 'Daily_Put_Settle'})
    
    global_call = get_max_oi_settle(global_df, 'Call').rename(columns={'Call_OI': 'Global_Call_OI', 'Call_Settle': 'Global_Call_Settle'})
    global_put = get_max_oi_settle(global_df, 'Put').rename(columns={'Put_OI': 'Global_Put_OI', 'Put_Settle': 'Global_Put_Settle'})
    
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
    
    # Save to CSV
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    out_file = os.path.join(output_dir, f"GEX_{currency}USD_{today_str}.csv")
    summary.to_csv(out_file, index=False)
    print(f"Saved {currency} levels to {out_file} ({len(summary)} strikes)")

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
        eur_raw = parse_cme_pdf(eur_dest, "EUR", is_call_only=None)
        calculate_gex_pipeline(eur_raw, "EUR", DATA_DIR)
        
    # Step 3: Parse and process GBP data
    if gbp_call_ok and gbp_put_ok:
        gbp_calls = parse_cme_pdf(gbp_call_dest, "GBP", is_call_only=True)
        gbp_puts = parse_cme_pdf(gbp_put_dest, "GBP", is_call_only=False)
        gbp_raw = pd.concat([gbp_calls, gbp_puts])
        calculate_gex_pipeline(gbp_raw, "GBP", DATA_DIR)
