import os, sys
import pandas as pd
import numpy as np

# Add root folder to path
sys.path.append(os.getcwd())

from src.bs_math import implied_volatility, bs_gamma

# Test EUR
# Spot EUR = 1.1726, Strike = 1.1700, DTE = 30 days (T = 0.08)
spot_eur = 1.1726
strike_eur = 1.1700
settle_eur_raw = 4.2  # from raw output

print("=== EUR IV TESTS ===")
for div in [10000.0, 1000.0, 100.0]:
    price = settle_eur_raw / div
    iv = implied_volatility(price, spot_eur, strike_eur, 0.08, 0.0, 'C')
    print(f"Div {div:8.1f} | Price {price:.6f} | IV {iv:.2%}")

# Test GBP
# Spot GBP = 1.3431, Strike = 1.342, DTE = 30 days (T = 0.08)
spot_gbp = 1.3431
strike_gbp = 1.342
settle_gbp_raw = 0.82  # from raw output

print("\n=== GBP IV TESTS ===")
for div in [1000.0, 100.0, 10.0, 1.0]:
    price = settle_gbp_raw / div
    iv = implied_volatility(price, spot_gbp, strike_gbp, 0.08, 0.0, 'C')
    print(f"Div {div:8.1f} | Price {price:.6f} | IV {iv:.2%}")
