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

def find_gamma_flip(strikes, ois, is_calls, ivs, spot, T=0.08, r=0.0):
    """
    Finds the Spot price S where net GEX is zero.
    Expects arrays/lists of:
      - strikes (K)
      - ois (Open Interest)
      - is_calls (boolean list where True = Call, False = Put)
      - ivs (Implied Volatilities)
    """
    def net_gamma_func(S):
        if S <= 0:
            return 0.0
        val = 0.0
        for K, oi, is_call, iv in zip(strikes, ois, is_calls, ivs):
            if iv <= 0.001 or oi <= 0:
                continue
            d1 = (np.log(S / K) + (r + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
            g = norm.pdf(d1) / (S * iv * np.sqrt(T))
            if is_call:
                val += g * oi
            else:
                val -= g * oi
        return val

    # Step 1: Search in a narrow, safe range where underflow doesn't occur [0.85 * spot, 1.15 * spot]
    lower_bound = 0.85 * spot
    upper_bound = 1.15 * spot
    
    try:
        f_low = net_gamma_func(lower_bound)
        f_high = net_gamma_func(upper_bound)
        if f_low * f_high < 0:
            return brentq(net_gamma_func, lower_bound, upper_bound)
    except Exception:
        pass

    # Step 2: Try a slightly wider range [0.7 * spot, 1.3 * spot]
    try:
        f_low = net_gamma_func(0.7 * spot)
        f_high = net_gamma_func(1.3 * spot)
        if f_low * f_high < 0:
            return brentq(net_gamma_func, 0.7 * spot, 1.3 * spot)
    except Exception:
        pass

    # Step 3: Scan grid [0.5 * spot, 1.5 * spot] to locate the sign change
    grid = np.linspace(0.5 * spot, 1.5 * spot, 100)
    vals = []
    for x in grid:
        try:
            vals.append(net_gamma_func(x))
        except Exception:
            vals.append(0.0)
            
    # Find sign changes but verify they are not due to underflow
    max_val = max(abs(v) for v in vals) if vals else 1.0
    threshold = 1e-8 * max_val
    
    for i in range(len(grid) - 1):
        if vals[i] * vals[i+1] <= 0:
            # Check if it's not just underflow (both values extremely close to 0)
            if abs(vals[i]) > threshold or abs(vals[i+1]) > threshold:
                try:
                    return brentq(net_gamma_func, grid[i], grid[i+1])
                except Exception:
                    return 0.5 * (grid[i] + grid[i+1])
                
    # Fallback: grid point closest to zero
    best_idx = np.argmin(np.abs(vals))
    return grid[best_idx]
