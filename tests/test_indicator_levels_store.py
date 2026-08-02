import copy
import json

import pytest

from Dashboard.indicator_levels_store import (
    IndicatorLevelsError,
    load_indicator_manifest,
    manifest_filename,
    validate_indicator_manifest,
)


def valid_manifest(asset="EUR", report_date="2026-08-03"):
    return {
        "schema_version": 1,
        "producer": "CME_GEX_Levels_Indicator",
        "asset": asset,
        "report_date": report_date,
        "generated_at": "2026-08-03T09:00:00",
        "source_csv": f"GEX_{asset}USD_{report_date}.csv",
        "coordinate_system": "MT5_SPOT",
        "selection": {
            "filter_mode": "absolute",
            "min_gex_filter": 1000.0,
            "active_gex_filter": 1000.0,
            "filter_reference_abs_gex": 5000.0,
            "min_gex_percent": 15.0,
            "max_visible_rows": 24,
            "max_strike_distance_percent": 6.0,
            "max_key_distance_percent": 12.0,
            "visible_count": 2,
        },
        "market": {
            "futures_spot": 1.15,
            "mt5_spot_reference": 1.151,
            "fw_offset": 0.001,
            "fw_offset_status": "mt5_d1_open",
        },
        "expiries": {
            "daily_month": "AUG26",
            "daily_expiry": "2026-08-03",
            "global_month": "SEP26",
            "global_expiry": "2026-09-04",
        },
        "quality": {
            "quality_status": "PASS",
            "quality_reasons": "NONE",
            "anomaly_status": "OK",
            "anomaly_codes": "NONE",
            "anomaly_details": "NONE",
            "anomaly_baseline_date": "2026-07-31",
            "gamma_flip_status": "FOUND",
        },
        "diagnostics": {
            "spot_source": "PUT_CALL_PARITY",
            "iv_source": "WEIGHTED_ATM",
            "iv_expiry": "2026-08-07",
            "iv_dte": 4,
            "estimated_expiry_types": "NONE",
        },
        "key_levels": {
            "spot_reference": {"chart_price": 1.151},
            "zero_gamma": {"chart_price": 1.149},
            "daily_call_mdd": {
                "chart_price": 1.16,
                "strike": 1.155,
                "settle": 0.004,
                "oi": 100.0,
            },
            "daily_put_mdd": {
                "chart_price": 1.142,
                "strike": 1.145,
                "settle": 0.004,
                "oi": 90.0,
            },
            "global_call": None,
            "global_put": None,
            "max_abs_gamma": None,
            "r68_high": {"chart_price": 1.16},
            "r68_low": {"chart_price": 1.142},
            "r95_high": {"chart_price": 1.17},
            "r95_low": {"chart_price": 1.132},
        },
        "visible_strikes": [
            {
                "strike": 1.155,
                "chart_price": 1.156,
                "total_gex": 5000.0,
                "total_abs_gamma": 2000.0,
                "gex_strength_percent": 100,
                "ag_strength_percent": 80,
                "roles": ["daily_call"],
            },
            {
                "strike": 1.145,
                "chart_price": 1.146,
                "total_gex": -4000.0,
                "total_abs_gamma": 1500.0,
                "gex_strength_percent": 80,
                "ag_strength_percent": 60,
                "roles": ["daily_put"],
            },
        ],
    }


def test_exact_manifest_load_and_identity_validation(tmp_path):
    payload = valid_manifest()
    path = tmp_path / manifest_filename("EUR", "2026-08-03")
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_indicator_manifest(tmp_path, "EUR", "2026-08-03")

    assert loaded["market"]["fw_offset"] == pytest.approx(0.001)
    assert loaded["selection"]["visible_count"] == 2
    with pytest.raises(FileNotFoundError):
        load_indicator_manifest(tmp_path, "EUR", "2026-08-04")


def test_manifest_rejects_date_mismatch_and_duplicate_visible_strikes():
    payload = valid_manifest()
    with pytest.raises(IndicatorLevelsError, match="date mismatch"):
        validate_indicator_manifest(payload, expected_asset="EUR", expected_date="2026-08-04")

    duplicate = copy.deepcopy(payload)
    duplicate["visible_strikes"].append(copy.deepcopy(duplicate["visible_strikes"][0]))
    duplicate["selection"]["visible_count"] = 3
    with pytest.raises(IndicatorLevelsError, match="Duplicate visible strike"):
        validate_indicator_manifest(duplicate)


def test_manifest_requires_daily_mdd_and_mt5_coordinates():
    missing_mdd = valid_manifest()
    missing_mdd["key_levels"]["daily_put_mdd"] = None
    with pytest.raises(IndicatorLevelsError, match="daily_put_mdd is required"):
        validate_indicator_manifest(missing_mdd)

    wrong_coordinates = valid_manifest()
    wrong_coordinates["coordinate_system"] = "CME_FUTURES"
    with pytest.raises(IndicatorLevelsError, match="coordinate system"):
        validate_indicator_manifest(wrong_coordinates)

    wrong_mdd = valid_manifest()
    wrong_mdd["key_levels"]["daily_call_mdd"]["chart_price"] = 1.5
    with pytest.raises(IndicatorLevelsError, match="MT5 formula"):
        validate_indicator_manifest(wrong_mdd)
