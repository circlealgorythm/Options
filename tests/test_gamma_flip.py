import pytest
import numpy as np
from src.bs_math import find_gamma_flip

def test_gamma_flip_symmetric():
    # Symmetric case: Call at 105, Put at 95. Equal OI and IV.
    # The GEX zero crossover should be around 100.
    strikes = [105.0, 95.0]
    ois = [1000, 1000]
    is_calls = [True, False]
    ivs = [0.2, 0.2]
    spot = 100.0
    
    flip_price = find_gamma_flip(strikes, ois, is_calls, ivs, spot, T=0.08, r=0.0)
    # It should be extremely close to 100.0
    assert abs(flip_price - 100.0) < 1.0

def test_gamma_flip_call_dominated():
    # If calls have significantly more OI than puts, the flip level should shift lower/higher
    # Let's verify that the algorithm finishes and returns a valid float value.
    strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
    ois = [500, 1000, 2000, 5000, 1500]
    is_calls = [False, False, True, True, True]
    ivs = [0.15, 0.15, 0.15, 0.15, 0.15]
    spot = 100.0
    
    flip_price = find_gamma_flip(strikes, ois, is_calls, ivs, spot, T=0.08, r=0.0)
    assert isinstance(flip_price, float)
    assert flip_price > 0.0


def test_gamma_flip_returns_none_without_a_sign_crossing():
    flip_price = find_gamma_flip(
        strikes=[90.0, 100.0, 110.0],
        ois=[1000, 2000, 1500],
        is_calls=[True, True, True],
        ivs=[0.2, 0.2, 0.2],
        spot=100.0,
        T=0.08,
    )

    assert flip_price is None


def test_gamma_flip_uses_each_rows_expiry():
    flip_price = find_gamma_flip(
        strikes=[95.0, 100.0, 105.0, 110.0],
        ois=[4500, 1500, 3500, 900],
        is_calls=[False, False, True, True],
        ivs=[0.18, 0.22, 0.16, 0.25],
        spot=100.0,
        times=[5 / 252, 60 / 252, 5 / 252, 60 / 252],
    )

    assert flip_price == pytest.approx(100.4621641126, abs=1e-6)
