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
    Dollar gamma exposure for a 1% move in the underlying.

    The S^2 * 1% normalization makes values comparable across strikes and
    assets while retaining the contract multiplier and open interest.
    """
    if gamma <= 0.0 or open_interest <= 0.0 or contract_size <= 0.0 or S <= 0.0:
        return 0.0
    return gamma * open_interest * contract_size * S * S * 0.01

def calculate_absolute_gamma(gamma, open_interest):
    """
    Calculates Absolute Gamma.
    Keep raw gamma-open-interest units for stable relative comparisons.
    """
    return gamma * open_interest

def find_gamma_flip(strikes, ois, is_calls, ivs, spot, T=0.08, r=0.0, times=None):
    """
    Finds the Spot price S where net GEX is zero.
    Expects arrays/lists of:
      - strikes (K)
      - ois (Open Interest)
      - is_calls (boolean list where True = Call, False = Put)
      - ivs (Implied Volatilities)
      - times (optional per-row years-to-expiry; scalar T is the fallback)

    Returns None when the aggregate gamma does not cross zero in the search
    range. A minimum-magnitude grid point is not a valid zero-gamma level.
    """
    lengths = {len(strikes), len(ois), len(is_calls), len(ivs)}
    if len(lengths) != 1 or not strikes or spot <= 0.0:
        return None
    if times is None:
        row_times = [T] * len(strikes)
    else:
        if len(times) != len(strikes):
            raise ValueError("times must have the same length as strikes")
        row_times = times

    strike_values = np.asarray(strikes, dtype=float)
    oi_values = np.asarray(ois, dtype=float)
    iv_values = np.asarray(ivs, dtype=float)
    time_values = np.asarray(row_times, dtype=float)
    sign_values = np.where(np.asarray(is_calls, dtype=bool), 1.0, -1.0)
    valid_rows = (
        (strike_values > 0.0)
        & (oi_values > 0.0)
        & (iv_values > 0.001)
        & (time_values > 0.0)
        & np.isfinite(strike_values)
        & np.isfinite(oi_values)
        & np.isfinite(iv_values)
        & np.isfinite(time_values)
    )
    if not valid_rows.any() or not (sign_values[valid_rows] > 0).any() or not (sign_values[valid_rows] < 0).any():
        return None
    strike_values = strike_values[valid_rows]
    oi_values = oi_values[valid_rows]
    iv_values = iv_values[valid_rows]
    time_values = time_values[valid_rows]
    sign_values = sign_values[valid_rows]

    def net_gamma_func(S):
        if S <= 0:
            return np.nan
        sqrt_time = np.sqrt(time_values)
        d1 = (
            np.log(S / strike_values)
            + (r + 0.5 * iv_values**2) * time_values
        ) / (iv_values * sqrt_time)
        gamma_values = norm.pdf(d1) / (S * iv_values * sqrt_time)
        return float(np.sum(gamma_values * oi_values * sign_values))

    grid = np.linspace(0.5 * spot, 1.5 * spot, 401)
    vals = np.asarray([net_gamma_func(x) for x in grid], dtype=float)
    finite = np.isfinite(vals)
    if not finite.any():
        return None
    max_val = float(np.max(np.abs(vals[finite])))
    if max_val <= 0.0:
        return None
    threshold = max_val * 1e-10

    roots = []
    for i in range(len(grid) - 1):
        left, right = vals[i], vals[i + 1]
        if not np.isfinite(left) or not np.isfinite(right):
            continue
        if abs(left) <= threshold and abs(right) <= threshold:
            continue
        if left == 0.0:
            previous = vals[i - 1] if i > 0 else np.nan
            if (
                np.isfinite(previous)
                and abs(previous) > threshold
                and abs(right) > threshold
                and previous * right < 0.0
            ):
                roots.append(float(grid[i]))
            continue
        if left * right < 0.0:
            try:
                roots.append(float(brentq(net_gamma_func, grid[i], grid[i + 1])))
            except (ValueError, RuntimeError):
                continue

    if not roots:
        return None
    return min(roots, key=lambda value: abs(value - spot))
