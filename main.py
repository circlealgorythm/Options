import os
import datetime
import pandas as pd
from src.parser import download_cme_bulletin, parse_cme_pdf
from src.bs_math import implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

def process_currency_data(df, currency):
    """
    Groups and splits options data into Call/Put formats.
    """
    if df.empty:
        return pd.DataFrame()
        
    if currency == 'GBP':
        # GBP is split into separate files (Call and Put)
        calls = df[df['Is_Call'] == True]
        puts = df[df['Is_Call'] == False]
        
        calls_grp = calls.groupby('Strike').agg({'Settle': 'max', 'OI': 'sum'}).reset_index()
        calls_grp.rename(columns={'Settle': 'Call_Settle', 'OI': 'Call_OI'}, inplace=True)
        
        puts_grp = puts.groupby('Strike').agg({'Settle': 'max', 'OI': 'sum'}).reset_index()
        puts_grp.rename(columns={'Settle': 'Put_Settle', 'OI': 'Put_OI'}, inplace=True)
        
        merged = pd.merge(calls_grp, puts_grp, on='Strike', how='outer').fillna(0.0)
        return merged
    else:
        # EUR options are mixed and must be split by delta relative to Spot
        # Auto-detect ATM spot by finding strikes with delta close to 0.5
        atm_rows = df[(df['Delta'] >= 0.45) & (df['Delta'] <= 0.55)]
        if not atm_rows.empty:
            spot = atm_rows['Strike'].mean()
        else:
            spot = 1.1500 # Fallback
            
        print(f"Auto-detected EUR Spot: {spot:.4f}")
        
        grouped = df.groupby('Strike')
        processed_rows = []
        
        for strike, group in grouped:
            if len(group) == 1:
                row = group.iloc[0]
                d = row['Delta']
                is_call = False
                if strike < spot:
                    is_call = (d >= 0.5)
                else:
                    is_call = (d < 0.5)
                
                if is_call:
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": row['Settle'], "Call_OI": row['OI'],
                        "Put_Settle": 0.0, "Put_OI": 0
                    })
                else:
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": 0.0, "Call_OI": 0,
                        "Put_Settle": row['Settle'], "Put_OI": row['OI']
                    })
            else:
                sorted_group = group.sort_values(by='Delta')
                r_low = sorted_group.iloc[0]
                r_high = sorted_group.iloc[-1]
                
                if strike < spot:
                    # Low delta is Put, high delta is Call
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": r_high['Settle'], "Call_OI": r_high['OI'],
                        "Put_Settle": r_low['Settle'], "Put_OI": r_low['OI']
                    })
                else:
                    # Low delta is Call, high delta is Put
                    processed_rows.append({
                        "Strike": strike, "Call_Settle": r_low['Settle'], "Call_OI": r_low['OI'],
                        "Put_Settle": r_high['Settle'], "Put_OI": r_high['OI']
                    })
                    
        return pd.DataFrame(processed_rows)

def calculate_gex_levels(df, currency, output_dir):
    if df.empty:
        return
        
    spot = df['Strike'].mean() # ATM approximation for Black-Scholes formulas
    contract_size = 125000 if currency == 'EUR' else 62500
    T = 0.08
    r = 0.0
    
    results = []
    for idx, row in df.iterrows():
        K = row['Strike']
        
        # Calls
        iv_call = implied_volatility(row['Call_Settle'], spot, K, T, r, 'C')
        gamma_call = bs_gamma(spot, K, T, r, iv_call)
        gex_call = calculate_gex(gamma_call, row['Call_OI'], contract_size, spot)
        abs_gamma_call = calculate_absolute_gamma(gamma_call, row['Call_OI'])
        
        # Puts
        iv_put = implied_volatility(row['Put_Settle'], spot, K, T, r, 'P')
        gamma_put = bs_gamma(spot, K, T, r, iv_put)
        gex_put = -calculate_gex(gamma_put, row['Put_OI'], contract_size, spot)
        abs_gamma_put = calculate_absolute_gamma(gamma_put, row['Put_OI'])
        
        results.append({
            "Strike": K,
            "Total_GEX": gex_call + gex_put,
            "Total_Abs_Gamma": abs_gamma_call + abs_gamma_put,
            "Call_OI": row['Call_OI'],
            "Put_OI": row['Put_OI']
        })
        
    res_df = pd.DataFrame(results)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    out_file = os.path.join(output_dir, f"GEX_{currency}USD_{today_str}.csv")
    res_df.to_csv(out_file, index=False)
    print(f"Saved {currency} levels to {out_file}")

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
        eur_clean = process_currency_data(eur_raw, "EUR")
        calculate_gex_levels(eur_clean, "EUR", DATA_DIR)
        
    # Step 3: Parse and process GBP data
    if gbp_call_ok and gbp_put_ok:
        gbp_calls = parse_cme_pdf(gbp_call_dest, "GBP", is_call_only=True)
        gbp_puts = parse_cme_pdf(gbp_put_dest, "GBP", is_call_only=False)
        gbp_clean = process_currency_data(pd.concat([gbp_calls, gbp_puts]), "GBP")
        calculate_gex_levels(gbp_clean, "GBP", DATA_DIR)
