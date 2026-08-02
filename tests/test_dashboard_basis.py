import datetime

import pytest

from Dashboard import run_dashboard


def test_market_basis_uses_synchronized_spot_and_futures(monkeypatch):
    prices = {"EURUSD=X": 1.1510, "6E=F": 1.1540}
    monkeypatch.setattr(
        run_dashboard,
        "_fetch_yahoo_reference",
        lambda ticker, selected_date=None: prices[ticker],
    )

    basis = run_dashboard.get_market_basis("EUR", datetime.date(2026, 7, 31))

    assert basis["spot"] == 1.1510
    assert basis["futures"] == 1.1540
    assert basis["offset"] == pytest.approx(-0.0030)
    assert basis["source"] == "historical_open"


def test_usdcad_futures_reference_is_inverted(monkeypatch):
    prices = {"USDCAD=X": 1.4000, "6C=F": 0.7100}
    monkeypatch.setattr(
        run_dashboard,
        "_fetch_yahoo_reference",
        lambda ticker, selected_date=None: prices[ticker],
    )

    basis = run_dashboard.get_market_basis("USDCAD")

    assert basis["futures"] == 1.0 / 0.7100
    assert basis["offset"] == pytest.approx(1.4000 - (1.0 / 0.7100))


def test_xau_does_not_apply_an_unsynchronized_proxy_offset():
    assert run_dashboard.get_market_basis("XAU") is None
