import pytest
from src.bs_math import calculate_absolute_gamma, calculate_gex, forward_to_spot, bs_call_price, bs_gamma, implied_volatility

def test_forward_to_spot():
    assert forward_to_spot(1.1050, 50, 10000) == 1.1000
    assert forward_to_spot(1.1000, -25, 10000) == 1.1025

def test_bs_call_price():
    # S=100, K=100, T=1, r=0.05, sigma=0.2 => C ~ 10.4506
    price = bs_call_price(100, 100, 1, 0.05, 0.2)
    assert abs(price - 10.4506) < 0.01

def test_implied_volatility():
    price = 10.4506
    iv = implied_volatility(price, 100, 100, 1, 0.05, 'C')
    assert abs(iv - 0.2) < 0.01

def test_bs_gamma():
    # S=100, K=100, T=1, r=0.05, sigma=0.2 => Gamma ~ 0.01876
    gamma = bs_gamma(100, 100, 1, 0.05, 0.2)
    assert abs(gamma - 0.01876) < 0.001

def test_gex_is_dollar_gamma_for_one_percent_move():
    assert calculate_gex(0.02, 10, 100, 4000) == 3_200_000.0
    assert calculate_absolute_gamma(0.02, 10) == 0.2
    assert calculate_absolute_gamma(0.02, 10, 100) == 20.0
