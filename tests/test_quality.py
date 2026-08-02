import datetime

import pandas as pd

from src.quality import evaluate_summary_anomalies, load_previous_summary


def make_summary(spot=100.0, sigma=2.0, gamma_flip=105.0):
    return pd.DataFrame(
        {
            "Strike": [90.0, 110.0],
            "Total_GEX": [-1.0, 2.0],
            "Total_Abs_Gamma": [0.1, 0.2],
            "R68_High": [spot + sigma] * 2,
            "R68_Low": [spot - sigma] * 2,
            "R95_High": [spot + 2.0 * sigma] * 2,
            "R95_Low": [spot - 2.0 * sigma] * 2,
            "Futures_Spot": [spot] * 2,
            "Gamma_Flip": [gamma_flip] * 2,
            "Gamma_Flip_Status": ["FOUND"] * 2,
            "Quality_Status": ["OK"] * 2,
            "Spot_Source": ["PUT_CALL_PARITY"] * 2,
            "IV_Source": ["WEIGHTED_ATM"] * 2,
            "Spot_Fallback_Details": ["NONE"] * 2,
        }
    )


def test_valid_summary_passes_anomaly_check():
    report = evaluate_summary_anomalies(make_summary(), "NAS")

    assert report.status == "OK"
    assert report.codes == ()


def test_invalid_range_order_fails_closed():
    summary = make_summary()
    summary["R68_High"] = 99.0

    report = evaluate_summary_anomalies(summary, "NAS")

    assert report.status == "ERROR"
    assert "INVALID_RANGE_ORDER" in report.errors


def test_market_fallback_cannot_be_hidden_by_ok_quality():
    summary = make_summary()
    summary["IV_Source"] = "STATIC_FALLBACK"

    report = evaluate_summary_anomalies(summary, "NAS")

    assert report.status == "ERROR"
    assert "HIDDEN_MARKET_FALLBACK" in report.errors


def test_zero_gamma_is_visible_but_does_not_block_degraded_output():
    summary = make_summary()
    summary["Total_Abs_Gamma"] = 0.0
    summary["Gamma_Flip"] = 0.0
    summary["Gamma_Flip_Status"] = "NO_CROSSING"
    summary["Quality_Status"] = "DEGRADED"
    summary["IV_Source"] = "STATIC_FALLBACK"

    report = evaluate_summary_anomalies(summary, "NAS")

    assert report.status == "WARN"
    assert report.errors == ()
    assert report.warnings == ("NO_POSITIVE_GAMMA",)


def test_large_market_reference_changes_are_warnings():
    previous = make_summary(spot=100.0, sigma=2.0, gamma_flip=105.0)
    current = make_summary(spot=130.0, sigma=6.5, gamma_flip=160.0)

    report = evaluate_summary_anomalies(current, "NAS", previous)

    assert report.status == "WARN"
    assert set(report.warnings) == {"SPOT_SHIFT", "IV_SHIFT", "GAMMA_FLIP_SHIFT"}


def test_previous_summary_loader_uses_newest_earlier_file(tmp_path):
    older = make_summary(spot=95.0)
    expected = make_summary(spot=99.0)
    same_day = make_summary(spot=100.0)
    older.to_csv(tmp_path / "GEX_BTCUSD_2026-07-27.csv", index=False)
    expected.to_csv(tmp_path / "GEX_BTCUSD_2026-07-30.csv", index=False)
    same_day.to_csv(tmp_path / "GEX_BTCUSD_2026-07-31.csv", index=False)

    baseline_date, baseline, warning = load_previous_summary(
        tmp_path, "BTC", datetime.date(2026, 7, 31)
    )

    assert baseline_date == datetime.date(2026, 7, 30)
    assert warning is None
    assert baseline["Futures_Spot"].iloc[0] == 99.0
