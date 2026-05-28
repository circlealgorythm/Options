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
        if is_call:
            iv = implied_volatility(row['Settle'], spot, K, T, r, 'C')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = row['OI']
            put_oi = 0
        else:
            iv = implied_volatility(row['Settle'], spot, K, T, r, 'P')
            gamma = bs_gamma(spot, K, T, r, iv)
            gex = -calculate_gex(gamma, row['OI'], contract_size, spot)
            abs_gamma = calculate_absolute_gamma(gamma, row['OI'])
            call_oi = 0
            put_oi = row['OI']
            
        calculated_rows.append({
            "Strike": K,
            "GEX": gex,
            "Abs_Gamma": abs_gamma,
            "Call_OI": call_oi,
            "Put_OI": put_oi
        })
        
    calc_df = pd.DataFrame(calculated_rows)
    
    # Group by Strike and sum values across all expirations/series
    summary = calc_df.groupby('Strike').agg({
        'GEX': 'sum',
        'Abs_Gamma': 'sum',
        'Call_OI': 'sum',
        'Put_OI': 'sum'
    }).reset_index()
    
    summary.rename(columns={'GEX': 'Total_GEX', 'Abs_Gamma': 'Total_Abs_Gamma'}, inplace=True)
    summary.insert(0, 'Currency', currency)
    
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
