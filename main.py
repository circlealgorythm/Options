import os
import datetime
import pandas as pd
from src.parser import download_cme_bulletin, parse_cme_pdf
from src.bs_math import forward_to_spot, implied_volatility, bs_gamma, calculate_gex, calculate_absolute_gamma

def process_cme_data(pdf_path: str, output_dir: str):
    df = parse_cme_pdf(pdf_path, currency_filter=['EUR', 'GBP'])
    
    if df.empty:
        print("No data extracted from PDF. This may require an update to the PDF parser regex.")
        return
        
    print(f"Extracted {len(df)} strikes.")
    
    # We assume Forward Points are 0 for the sake of the base logic if not provided.
    # In a fully operational setting, Forward Points would be fetched from another CME source or broker.
    # We use a dummy underlying price if not known, or we can use the max OI strike.
    
    # Let's say we have an assumed underlying spot S = 1.1000 for EUR, 1.2500 for GBP
    # For a real system, you'd find the ATM strike by looking at max Open Interest 
    # or the strike where Call Settle ~= Put Settle.
    # Let's assume a futures price of 1.1050 and forward points of 50.
    # The true Spot = Futures - Forward Points / 10000
    
    # Calculate Greeks
    # Time to expiration T (in years). Dummy = 0.08 (approx 1 month)
    T = 0.08
    r = 0.0  # futures so r=0 is standard
    
    results = []
    
    for idx, row in df.iterrows():
        # Example dummy usage of forward_to_spot
        fwd_price = 1.1050 if row['Currency'] == 'EUR' else 1.2550
        fwd_points = 50
        S = forward_to_spot(fwd_price, fwd_points, 10000)
        
        contract_size = 125000 if row['Currency'] == 'EUR' else 62500
        
        K = row['Strike']
        
        # Calls
        iv_call = implied_volatility(row['Call_Settle'], S, K, T, r, 'C')
        gamma_call = bs_gamma(S, K, T, r, iv_call)
        # Call GEX is positive
        gex_call = calculate_gex(gamma_call, row['Call_OI'], contract_size, S)
        abs_gamma_call = calculate_absolute_gamma(gamma_call, row['Call_OI'])
        
        # Puts
        iv_put = implied_volatility(row['Put_Settle'], S, K, T, r, 'P')
        gamma_put = bs_gamma(S, K, T, r, iv_put)
        # Put GEX is negative
        gex_put = -calculate_gex(gamma_put, row['Put_OI'], contract_size, S)
        abs_gamma_put = calculate_absolute_gamma(gamma_put, row['Put_OI'])
        
        results.append({
            "Currency": row['Currency'],
            "Strike": K,
            "Total_GEX": gex_call + gex_put,
            "Total_Abs_Gamma": abs_gamma_call + abs_gamma_put,
            "Call_OI": row['Call_OI'],
            "Put_OI": row['Put_OI'],
            "Call_GEX": gex_call,
            "Put_GEX": gex_put
        })
        
    res_df = pd.DataFrame(results)
    
    # Save to CSV
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    for curr in ['EUR', 'GBP']:
        curr_df = res_df[res_df['Currency'] == curr]
        if not curr_df.empty:
            out_file = os.path.join(output_dir, f"GEX_{curr}USD_{today_str}.csv")
            curr_df.to_csv(out_file, index=False)
            print(f"Saved {curr} data to {out_file}")

if __name__ == "__main__":
    PDF_URL = "https://www.cmegroup.com/ftp/bulletin/PG38.pdf"
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    pdf_dest = os.path.join(DATA_DIR, f"cme_bulletin_{today}.pdf")
    
    success = download_cme_bulletin(PDF_URL, pdf_dest)
    if success:
        process_cme_data(pdf_dest, DATA_DIR)
    else:
        # Just to test process logic if a local dummy PDF exists, though it won't.
        pass
