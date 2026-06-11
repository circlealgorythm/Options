import os
import sys
import datetime
import pandas as pd

def extract_metrics(date_str=None):
    if date_str is None:
        date_str = datetime.date.today().strftime("%Y-%m-%d")
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "..", "data")
    
    currencies = ["EUR", "GBP", "XAU", "NAS", "SPX", "BTC", "USDCAD"]
    
    print(f"# GEX OPTION METRICS FOR {date_str}\n")
    
    for currency in currencies:
        if currency == "USDCAD":
            filename = f"GEX_USDCAD_{date_str}.csv"
        else:
            filename = f"GEX_{currency}USD_{date_str}.csv"
            
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            print(f"## {currency}: File {filename} not found\n")
            continue
            
        try:
            df = pd.read_csv(filepath)
            if df.empty:
                print(f"## {currency}: File is empty\n")
                continue
                
            # Extract metadata from the first row
            spot = df["Futures_Spot"].iloc[0] if "Futures_Spot" in df.columns else df["Strike"].mean()
            r68_high = df["R68_High"].iloc[0] if "R68_High" in df.columns else 0.0
            r68_low = df["R68_Low"].iloc[0] if "R68_Low" in df.columns else 0.0
            r95_high = df["R95_High"].iloc[0] if "R95_High" in df.columns else 0.0
            r95_low = df["R95_Low"].iloc[0] if "R95_Low" in df.columns else 0.0
            global_month = df["Global_Month"].iloc[0] if "Global_Month" in df.columns else "UNKNOWN"
            daily_month = df["Daily_Month"].iloc[0] if "Daily_Month" in df.columns else "UNKNOWN"
            
            # Find key levels
            # 1. Daily Call MDD
            daily_call_mdd_df = df[df["Daily_Call_OI"] > 0]
            if not daily_call_mdd_df.empty:
                daily_call_mdd_strike = daily_call_mdd_df["Strike"].iloc[0]
                daily_call_mdd_settle = daily_call_mdd_df["Daily_Call_Settle"].iloc[0]
                daily_call_mdd_oi = daily_call_mdd_df["Daily_Call_OI"].iloc[0]
            else:
                daily_call_mdd_strike, daily_call_mdd_settle, daily_call_mdd_oi = 0.0, 0.0, 0.0
                
            # 2. Daily Put MDD
            daily_put_mdd_df = df[df["Daily_Put_OI"] > 0]
            if not daily_put_mdd_df.empty:
                daily_put_mdd_strike = daily_put_mdd_df["Strike"].iloc[0]
                daily_put_mdd_settle = daily_put_mdd_df["Daily_Put_Settle"].iloc[0]
                daily_put_mdd_oi = daily_put_mdd_df["Daily_Put_OI"].iloc[0]
            else:
                daily_put_mdd_strike, daily_put_mdd_settle, daily_put_mdd_oi = 0.0, 0.0, 0.0
                
            # 3. Global Call (Max Call OI Strike)
            glob_call_df = df[df["Global_Call_OI"] > 0]
            if not glob_call_df.empty:
                glob_call_strike = glob_call_df["Strike"].iloc[0]
                glob_call_oi = glob_call_df["Global_Call_OI"].iloc[0]
            else:
                glob_call_strike, glob_call_oi = 0.0, 0.0
                
            # 4. Global Put (Max Put OI Strike)
            glob_put_df = df[df["Global_Put_OI"] > 0]
            if not glob_put_df.empty:
                glob_put_strike = glob_put_df["Strike"].iloc[0]
                glob_put_oi = glob_put_df["Global_Put_OI"].iloc[0]
            else:
                glob_put_strike, glob_put_oi = 0.0, 0.0
                
            # 5. Max Positive GEX Strike
            pos_gex_df = df[df["Total_GEX"] > 0]
            if not pos_gex_df.empty:
                max_pos_idx = pos_gex_df["Total_GEX"].idxmax()
                max_pos_strike = pos_gex_df.loc[max_pos_idx, "Strike"]
                max_pos_val = pos_gex_df.loc[max_pos_idx, "Total_GEX"]
            else:
                max_pos_strike, max_pos_val = 0.0, 0.0
                
            # 6. Max Negative GEX (Max Abs Gamma) Strike
            neg_gex_df = df[df["Total_GEX"] < 0]
            if not neg_gex_df.empty:
                max_neg_idx = neg_gex_df["Total_GEX"].idxmin()
                max_neg_strike = neg_gex_df.loc[max_neg_idx, "Strike"]
                max_neg_val = neg_gex_df.loc[max_neg_idx, "Total_GEX"]
            else:
                max_neg_strike, max_neg_val = 0.0, 0.0
                
            # 7. Zero Gamma (GEX crossing zero closest to spot)
            sorted_df = df.sort_values("Strike").reset_index(drop=True)
            zero_gamma_strike = 0.0
            min_dist = float('inf')
            for i in range(len(sorted_df) - 1):
                gex1 = sorted_df.loc[i, "Total_GEX"]
                gex2 = sorted_df.loc[i+1, "Total_GEX"]
                strike1 = sorted_df.loc[i, "Strike"]
                strike2 = sorted_df.loc[i+1, "Strike"]
                
                # Check sign flip
                if gex1 * gex2 <= 0 and gex1 != gex2:
                    t = abs(gex1) / (abs(gex1) + abs(gex2))
                    candidate = strike1 + t * (strike2 - strike1)
                    dist = abs(candidate - spot)
                    if dist < min_dist:
                        min_dist = dist
                        zero_gamma_strike = candidate
            
            # If the exact Gamma_Flip was calculated in the pipeline, use it directly
            if "Gamma_Flip" in df.columns and df["Gamma_Flip"].iloc[0] > 0:
                zero_gamma_strike = df["Gamma_Flip"].iloc[0]

            print(f"## Asset: {currency} (Active Months: Global={global_month}, Daily={daily_month})")
            print(f"- **Futures Spot:** {spot:.5f}")
            print(f"- **Expected Move (R68):** {r68_low:.5f} — {r68_high:.5f}")
            print(f"- **Expected Move (R95):** {r95_low:.5f} — {r95_high:.5f}")
            print(f"- **Zero Gamma (GEX Flip):** {zero_gamma_strike:.5f}")
            print(f"- **Max Positive GEX Wall:** {max_pos_strike:.5f} (Value: {max_pos_val:.2f})")
            print(f"- **Max Negative GEX (Abs Gamma Wall):** {max_neg_strike:.5f} (Value: {max_neg_val:.2f})")
            print(f"- **Daily Call MDD Boundary:** Strike {daily_call_mdd_strike:.5f} (Settle: {daily_call_mdd_settle:.5f}, OI: {int(daily_call_mdd_oi)})")
            print(f"- **Daily Put MDD Boundary:** Strike {daily_put_mdd_strike:.5f} (Settle: {daily_put_mdd_settle:.5f}, OI: {int(daily_put_mdd_oi)})")
            print(f"- **Global Call Wall:** {glob_call_strike:.5f} (OI: {int(glob_call_oi)})")
            print(f"- **Global Put Wall:** {glob_put_strike:.5f} (OI: {int(glob_put_oi)})\n")
            
        except Exception as e:
            print(f"## {currency}: Error parsing file: {e}\n")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    extract_metrics(date_arg)
