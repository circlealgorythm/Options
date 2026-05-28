import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

def forward_to_spot(forward_price, forward_points, point_multiplier=10000):
    """
    Converts Futures/Forward price to Spot price.
    Assuming Forward = Spot + Forward Points / multiplier.
    """
    return forward_price - (forward_points / point_multiplier)

def bs_call_price(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

def bs_put_price(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

def implied_volatility(price, S, K, T, r, option_type='C'):
    if T <= 0 or price <= 0:
        return 0.001
        
    def objective(sigma):
        if option_type == 'C':
            return bs_call_price(S, K, T, r, sigma) - price
        else:
            return bs_put_price(S, K, T, r, sigma) - price
            
    try:
        # Volatility usually between 0.1% and 300%
        return brentq(objective, 1e-4, 3.0)
    except (ValueError, RuntimeError):
        # Fallback or boundary cases
        return 0.001

def calculate_gex(gamma, open_interest, contract_size, S):
    """
    Calculates Gamma Exposure (GEX) for a single strike.
    GEX = Gamma * Open Interest * Contract Size * S
    Some conventions also divide or adjust by 100 or 1% S.
    We will use the standard absolute value representation.
    """
    return gamma * open_interest * contract_size

def calculate_absolute_gamma(gamma, open_interest):
    """
    Calculates Absolute Gamma.
    Abs Gamma = Gamma * Open Interest
    """
    return gamma * open_interest
