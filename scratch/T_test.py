import os, sys
sys.path.append(os.getcwd())
from src.bs_math import implied_volatility

spot_eur = 1.1726
strike_eur = 1.1700
settle_eur_raw = 4.2

print("=== EUR IV with different T ===")
for T in [0.08, 0.02, 0.01, 0.005]: # 30 days, 7 days, 3.6 days, 1.8 days
    for div in [10000.0, 1000.0]:
        price = settle_eur_raw / div
        iv = implied_volatility(price, spot_eur, strike_eur, T, 0.0, 'C')
        print(f"T {T:.4f} | Div {div:8.1f} | Price {price:.6f} | IV {iv:.2%}")
