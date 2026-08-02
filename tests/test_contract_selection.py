import datetime
import os

import pandas as pd
import pytest

import main as main_module

from main import (
    copy_csv_to_mt5,
    convert_cad_options_to_usdcad,
    detect_spot_and_classify,
    estimate_atm_iv,
    resolve_atm_iv_reference,
    resolve_session_date,
    select_daily_contracts,
    select_iv_month,
    select_near_spot_mdd_settle,
    validate_mdd_summary,
)
from src.parser import month_code_from_yyyymm00, parse_bulletin_date_from_text


def make_rows(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "Option_Type",
            "Contract_Month",
            "Strike",
            "GEX",
            "Abs_Gamma",
            "Call_OI",
            "Put_OI",
            "Call_Settle",
            "Put_Settle",
        ],
    )


def test_resolve_session_date_uses_publish_date_only_after_current_bulletin(tmp_path):
    pdf_path = tmp_path / "bulletin.pdf"
    pdf_path.write_bytes(b"%PDF")
    today = datetime.date(2026, 6, 25)
    bulletin_date = datetime.date(2026, 6, 24)

    old_ts = datetime.datetime(2026, 6, 24, 7, 0).timestamp()
    os.utime(pdf_path, (old_ts, old_ts))
    assert resolve_session_date(pdf_path, bulletin_date, today) == bulletin_date

    current_ts = datetime.datetime(2026, 6, 25, 7, 29).timestamp()
    os.utime(pdf_path, (current_ts, current_ts))
    assert resolve_session_date(pdf_path, bulletin_date, today) == today


def test_resolve_session_date_weekend_and_monday_mapping(tmp_path):
    pdf_path = tmp_path / "bulletin.pdf"
    pdf_path.write_bytes(b"%PDF")

    # Case 1: Run on Monday (2026-06-29) with Friday's bulletin (2026-06-26)
    today = datetime.date(2026, 6, 29)
    bulletin_date = datetime.date(2026, 6, 26)
    # File modification time is Saturday morning (2026-06-27)
    publish_ts = datetime.datetime(2026, 6, 27, 8, 0).timestamp()
    os.utime(pdf_path, (publish_ts, publish_ts))
    assert resolve_session_date(pdf_path, bulletin_date, today) == datetime.date(2026, 6, 29)

    # Case 2: Run on Saturday (2026-06-27) with Friday's bulletin (2026-06-26)
    today_sat = datetime.date(2026, 6, 27)
    assert resolve_session_date(pdf_path, bulletin_date, today_sat) == datetime.date(2026, 6, 29)

    # Case 3: Run on Friday (2026-06-26) with Thursday's bulletin (2026-06-25)
    today_fri = datetime.date(2026, 6, 26)
    bulletin_date_thu = datetime.date(2026, 6, 25)
    publish_ts_fri = datetime.datetime(2026, 6, 26, 8, 0).timestamp()
    os.utime(pdf_path, (publish_ts_fri, publish_ts_fri))
    assert resolve_session_date(pdf_path, bulletin_date_thu, today_fri) == datetime.date(2026, 6, 26)

    # Case 4: Run on Monday (2026-07-06) with Thursday's bulletin (2026-07-02) due to Friday holiday
    today_mon_holiday = datetime.date(2026, 7, 6)
    bulletin_date_thu_holiday = datetime.date(2026, 7, 2)
    publish_ts_holiday = datetime.datetime(2026, 7, 3, 8, 0).timestamp()
    os.utime(pdf_path, (publish_ts_holiday, publish_ts_holiday))
    assert resolve_session_date(pdf_path, bulletin_date_thu_holiday, today_mon_holiday) == datetime.date(2026, 7, 6)



def test_eur_friday_falls_back_to_weekly_before_other_daily_codes():
    calc_df = make_rows(
        [
            ("SEC", "MAY26", 1.1600, 0, 0, 6, 0, 0.0041, 0.0),
            ("WEC", "JUN26", 1.1700, 0, 0, 1750, 0, 0.0047, 0.0),
            ("5EU", "MAY26", 1.1600, 0, 0, 2365, 0, 0.0045, 0.0),
            ("5EU", "MAY26", 1.1625, 0, 0, 0, 517, 0.0, 0.0013),
        ]
    )

    selected = select_daily_contracts(calc_df, "EUR", datetime.date(2026, 5, 29))

    assert set(selected["Option_Type"]) == {"5EU"}
    assert set(selected["Contract_Month"]) == {"MAY26"}


def test_gbp_uses_bulletin_weekday_for_exact_short_code():
    calc_df = make_rows(
        [
            ("MGM", "JUN26", 1.3400, 0, 0, 3120, 9743, 0.0117, 0.0195),
            ("SBP", "MAY26", 1.3420, 0, 0, 12, 30, 0.0018, 0.0013),
            ("WGB", "MAY26", 1.3370, 0, 0, 1, 0, 0.0084, 0.0),
        ]
    )

    selected = select_daily_contracts(calc_df, "GBP", datetime.date(2026, 5, 28))

    assert set(selected["Contract_Month"]) == {"MAY26"}
    assert "SBP" in set(selected["Option_Type"])


def test_gbp_fallback_selects_one_nearest_short_code_not_mixed_codes():
    calc_df = make_rows(
        [
            ("MGM", "JUN26", 1.3400, 0, 0, 3120, 9743, 0.0117, 0.0195),
            ("SBP", "JUN26", 1.3420, 0, 0, 12, 30, 0.0018, 0.0013),
            ("WGB", "JUN26", 1.3370, 0, 0, 1, 0, 0.0084, 0.0),
        ]
    )

    selected = select_daily_contracts(calc_df, "GBP", datetime.date(2026, 5, 29))

    assert set(selected["Option_Type"]) == {"MGM"}


def test_exact_weekday_daily_code_takes_precedence():
    calc_df = make_rows(
        [
            ("WGB", "JUN26", 1.3450, 0, 0, 35, 30, 0.0031, 0.0066),
            ("SBP", "MAY26", 1.3420, 0, 0, 12, 30, 0.0018, 0.0013),
        ]
    )

    selected = select_daily_contracts(calc_df, "GBP", datetime.date(2026, 6, 3))

    assert set(selected["Option_Type"]) == {"WGB"}
    assert set(selected["Contract_Month"]) == {"JUN26"}


def test_copy_csv_to_mt5_uses_configured_directory(tmp_path):
    source = tmp_path / "GEX_EURUSD_2026-05-29.csv"
    target_dir = tmp_path / "terminal" / "MQL5" / "Files" / "GEX"
    target_dir.mkdir(parents=True)
    source.write_text("Currency,Strike\nEUR,1.16\n", encoding="utf-8")

    copied = copy_csv_to_mt5(str(source), str(target_dir))

    assert copied == str(target_dir / source.name)
    assert (target_dir / source.name).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_numeric_mid_header_month_code_parses_to_cme_month():
    assert month_code_from_yyyymm00("20260600") == "JUN26"
    assert month_code_from_yyyymm00("20260700") == "JUL26"


def test_validate_mdd_summary_rejects_missing_daily_levels():
    summary = pd.DataFrame(
        [
            {
                "Daily_Call_OI": 0.0,
                "Daily_Call_Settle": 0.0,
                "Daily_Put_OI": 0.0,
                "Daily_Put_Settle": 0.0,
                "Global_Call_OI": 10.0,
                "Global_Put_OI": 20.0,
                "Daily_Month": "UNKNOWN",
                "Global_Month": "JUN26",
            }
        ]
    )

    try:
        validate_mdd_summary(summary, "GBP")
    except RuntimeError as exc:
        assert "Daily_Call" in str(exc)
        assert "Daily_Put" in str(exc)
        assert "Daily_Month" in str(exc)
    else:
        raise AssertionError("Expected missing daily MDD data to fail validation")


def test_parse_bulletin_date_from_header_text():
    text = "PG27 BULLETIN # 101@ BRITISH POUND CALL OPTIONS Thu, May 28, 2026 PG27"

    assert parse_bulletin_date_from_text(text) == datetime.date(2026, 5, 28)


def test_daily_mdd_selects_nearest_call_above_spot_instead_of_max_oi():
    calc_df = make_rows(
        [
            ("MGM", "JUN26", 1.3420, 0, 0, 55, 0, 0.0073, 0.0),
            ("MGM", "JUN26", 1.3800, 0, 0, 640, 0, 0.0003, 0.0),
        ]
    )

    selected = select_near_spot_mdd_settle(calc_df, "Call", 1.3411)

    assert selected.iloc[0]["Strike"] == 1.3420
    assert selected.iloc[0]["Call_Settle"] == 0.0073


def test_daily_mdd_selects_nearest_put_below_spot_instead_of_max_oi():
    calc_df = make_rows(
        [
            ("MGM", "JUN26", 1.3400, 0, 0, 0, 59, 0.0, 0.0051),
            ("MGM", "JUN26", 1.3250, 0, 0, 0, 911, 0.0, 0.0015),
        ]
    )

    selected = select_near_spot_mdd_settle(calc_df, "Put", 1.3411)

    assert selected.iloc[0]["Strike"] == 1.3400
    assert selected.iloc[0]["Put_Settle"] == 0.0051


def test_nas_daily_mdd_rejects_call_and_put_from_different_expiries():
    calc_df = make_rows(
        [
            ("QWW", "JUN26", 29700.0, 100, 0, 72, 0, 211.0, 0.0),
            ("QN4", "JUN26", 29650.0, 0, 100, 0, 16, 0.0, 401.5),
            ("QN2", "JUL26", 29650.0, 0, 100, 0, 10, 0.0, 759.75),
        ]
    )

    selected = select_daily_contracts(calc_df, "NAS", datetime.date(2026, 6, 24))

    assert selected.empty


def test_nas_daily_mdd_prefers_same_mid_code_put_when_parser_has_it():
    calc_df = make_rows(
        [
            ("QWW", "JUN26", 29670.0, 100, 0, 10, 0, 226.25, 0.0),
            ("QWW", "JUN26", 29670.0, 0, 100, 0, 1, 0.0, 230.25),
            ("QN4", "JUN26", 29670.0, 0, 100, 0, 1, 0.0, 410.25),
        ]
    )

    selected = select_daily_contracts(calc_df, "NAS", datetime.date(2026, 6, 24))

    assert set(selected["Option_Type"]) == {"QWW"}
    assert (selected["Put_OI"] > 0).any()


def test_spx_daily_mdd_uses_real_wednesday_code_not_quarterly_emini():
    calc_df = make_rows(
        [
            ("XWS", "JUN26", 7440.0, 0, 0, 8, 31, 28.5, 31.0),
            ("EMINI", "SEP26", 7450.0, 0, 0, 4231, 1800, 223.25, 235.5),
        ]
    )

    selected = select_daily_contracts(calc_df, "SPX", datetime.date(2026, 6, 24))

    assert set(selected["Option_Type"]) == {"XWS"}
    assert set(selected["Contract_Month"]) == {"JUN26"}


def test_usdcad_conversion_preserves_exact_breakeven_premium():
    cad_raw = pd.DataFrame(
        [
            {"Strike": 0.7050, "Settle": 0.0010, "Is_Call": True},
            {"Strike": 0.7050, "Settle": 0.0010, "Is_Call": False},
        ]
    )

    converted = convert_cad_options_to_usdcad(cad_raw, 0.7050)

    put_from_call = converted.iloc[0]
    call_from_put = converted.iloc[1]
    assert put_from_call["Is_Call"] == False
    assert call_from_put["Is_Call"] == True
    assert abs((put_from_call["Strike"] - put_from_call["Settle"]) - (1.0 / 0.7060)) < 1e-12
    assert abs((call_from_put["Strike"] + call_from_put["Settle"]) - (1.0 / 0.7040)) < 1e-12


def test_gbp_fallback_when_exact_code_has_no_calls():
    # SBP has puts only, no calls
    # MGM has both calls and puts
    calc_df = make_rows(
        [
            ("MGM", "JUN26", 1.3400, 0, 0, 3120, 9743, 0.0117, 0.0195),
            ("SBP", "JUN26", 1.3420, 0, 0, 0, 30, 0.0, 0.0013),
        ]
    )

    # Date is May 28, 2026 (Thursday -> dow = 3 -> SBP)
    selected = select_daily_contracts(calc_df, "GBP", datetime.date(2026, 5, 28))

    # Should fallback to MGM because SBP is invalid (no calls)
    assert set(selected["Option_Type"]) == {"MGM"}


def test_xau_spot_detection_uses_same_series_and_positive_oi():
    raw_df = pd.DataFrame(
        [
            # Stale/zero-OI mark that used to dominate month-level call max.
            {"Option_Type": "GWT", "Contract_Month": "JUN26", "Strike": 4700.0, "Settle": 550.6, "OI": 0, "Is_Call": True},
            {"Option_Type": "GWT", "Contract_Month": "JUN26", "Strike": 4700.0, "Settle": 0.5, "OI": 43, "Is_Call": True},
            # Matching call/put inside the same OG4 series implies spot near 4149.5.
            {"Option_Type": "OG4", "Contract_Month": "JUN26", "Strike": 4700.0, "Settle": 0.2, "OI": 206, "Is_Call": True},
            {"Option_Type": "OG4", "Contract_Month": "JUN26", "Strike": 4700.0, "Settle": 550.7, "OI": 1, "Is_Call": False},
            {"Option_Type": "OG4", "Contract_Month": "JUN26", "Strike": 4000.0, "Settle": 149.6, "OI": 10, "Is_Call": True},
            {"Option_Type": "OG4", "Contract_Month": "JUN26", "Strike": 4000.0, "Settle": 0.2, "OI": 10, "Is_Call": False},
        ]
    )

    spot, spots_per_month, _ = detect_spot_and_classify(raw_df, "XAU")

    assert abs(spots_per_month["JUN26"] - 4149.4) < 0.2
    assert abs(spot - 4149.4) < 0.2


def test_observed_spot_is_not_rejected_by_a_stale_static_fallback():
    raw_df = pd.DataFrame(
        [
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.60, "Settle": 0.02, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.60, "Settle": 0.01, "OI": 100, "Is_Call": False},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.62, "Settle": 0.01, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.62, "Settle": 0.02, "OI": 100, "Is_Call": False},
        ]
    )

    spot, _, _, diagnostics = detect_spot_and_classify(
        raw_df, "EUR", include_diagnostics=True
    )

    assert spot == pytest.approx(1.61)
    assert diagnostics["global_source"] == "PUT_CALL_PARITY"
    assert diagnostics["fallback_details"] == {}


def test_outlier_contract_month_uses_observed_global_reference():
    raw_df = pd.DataFrame(
        [
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.15, "Settle": 0.02, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.15, "Settle": 0.01, "OI": 100, "Is_Call": False},
            {"Option_Type": "EUU", "Contract_Month": "DEC26", "Strike": 1.60, "Settle": 0.02, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "DEC26", "Strike": 1.60, "Settle": 0.01, "OI": 100, "Is_Call": False},
        ]
    )

    spot, spots, _, diagnostics = detect_spot_and_classify(
        raw_df, "EUR", include_diagnostics=True
    )

    assert spot == pytest.approx(1.16)
    assert spots["DEC26"] == pytest.approx(spot)
    assert diagnostics["fallback_details"]["DEC26"].startswith(
        "GLOBAL_REFERENCE_OUTLIER"
    )


def test_spot_reference_prefers_parity_over_a_nearer_cluster_estimate():
    raw_df = pd.DataFrame(
        [
            {"Option_Type": "EUU", "Contract_Month": "JUL26", "Strike": 1.14, "Settle": 0.01, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.15, "Settle": 0.02, "OI": 100, "Is_Call": True},
            {"Option_Type": "EUU", "Contract_Month": "AUG26", "Strike": 1.15, "Settle": 0.01, "OI": 100, "Is_Call": False},
        ]
    )

    spot, _, _, diagnostics = detect_spot_and_classify(
        raw_df, "EUR", include_diagnostics=True
    )

    assert spot == pytest.approx(1.16)
    assert diagnostics["reference_month"] == "AUG26"
    assert diagnostics["global_source"] == "PUT_CALL_PARITY"


def test_mixed_eur_rows_are_classified_by_parity_and_delta():
    raw_df = pd.DataFrame(
        [
            {"Strike": 1.1300, "Settle": 0.0255, "Delta": 0.95, "OI": 10, "Is_Call": None, "Contract_Month": "AUG26", "Option_Type": "2EU"},
            {"Strike": 1.1300, "Settle": 0.0005, "Delta": 0.05, "OI": 100, "Is_Call": None, "Contract_Month": "AUG26", "Option_Type": "2EU"},
            # Duplicate text-layer row with point-change misread as delta.
            {"Strike": 1.1300, "Settle": 0.0255000000001, "Delta": 0.0077, "OI": 10, "Is_Call": None, "Contract_Month": "AUG26", "Option_Type": "2EU"},
            {"Strike": 1.1700, "Settle": 0.0010, "Delta": 0.20, "OI": 80, "Is_Call": None, "Contract_Month": "AUG26", "Option_Type": "2EU"},
            {"Strike": 1.1700, "Settle": 0.0160, "Delta": 0.80, "OI": 20, "Is_Call": None, "Contract_Month": "AUG26", "Option_Type": "2EU"},
        ]
    )

    spot, spots_per_month, classified = detect_spot_and_classify(raw_df, "EUR")

    assert len(classified) == 4
    assert spot == pytest.approx(1.1550, abs=1e-6)
    assert spots_per_month["AUG26"] == pytest.approx(1.1550, abs=1e-6)
    low_strike = classified[classified["Strike"] == 1.1300].sort_values("Settle")
    high_strike = classified[classified["Strike"] == 1.1700].sort_values("Settle")
    assert low_strike["Is_Call"].tolist() == [False, True]
    assert high_strike["Is_Call"].tolist() == [True, False]


def test_expiry_day_intrinsic_rows_infer_forward_without_premium_pairs():
    raw_df = pd.DataFrame(
        [
            {"Strike": 1.1400, "Settle": 0.0142, "Delta": 1.0, "OI": 10, "Is_Call": None, "Contract_Month": "JUL26", "Option_Type": "SEC"},
            {"Strike": 1.1450, "Settle": 0.0092, "Delta": 1.0, "OI": 20, "Is_Call": None, "Contract_Month": "JUL26", "Option_Type": "SEC"},
            {"Strike": 1.1500, "Settle": 0.0042, "Delta": 1.0, "OI": 30, "Is_Call": None, "Contract_Month": "JUL26", "Option_Type": "SEC"},
            {"Strike": 1.1600, "Settle": 0.0058, "Delta": 1.0, "OI": 40, "Is_Call": None, "Contract_Month": "JUL26", "Option_Type": "SEC"},
        ]
    )

    spot, _, classified = detect_spot_and_classify(raw_df, "EUR")

    assert spot == pytest.approx(1.1542, abs=1e-6)
    assert classified.sort_values("Strike")["Is_Call"].tolist() == [True, True, True, False]


def test_atm_iv_estimate_prefers_liquid_near_atm_series():
    # Same ATM area, but the low-OI put has an inflated settlement mark. The
    # range calculation should follow the liquid monthly series instead.
    option_df = pd.DataFrame(
        [
            {"Strike": 4150.0, "Settle": 31.1, "OI": 178, "Is_Call": True},
            {"Strike": 4150.0, "Settle": 31.7, "OI": 1077, "Is_Call": False},
            {"Strike": 4150.0, "Settle": 110.1, "OI": 2, "Is_Call": False},
            {"Strike": 4140.0, "Settle": 35.0, "OI": 400, "Is_Call": True},
            {"Strike": 4160.0, "Settle": 35.0, "OI": 350, "Is_Call": False},
        ]
    )

    iv_atm = estimate_atm_iv(option_df, "XAU", 4149.4, 1.0 / 252.0, 0.0, 0.03)

    assert 0.20 < iv_atm < 0.45


def test_atm_iv_estimate_uses_nearest_strikes_not_wide_smile_window():
    option_df = pd.DataFrame(
        [
            {"Strike": 1.1400, "Settle": 0.0040, "OI": 3800, "Is_Call": True},
            {"Strike": 1.1375, "Settle": 0.0031, "OI": 862, "Is_Call": False},
            {"Strike": 1.1425, "Settle": 0.0037, "OI": 200, "Is_Call": True},
            {"Strike": 1.1600, "Settle": 0.0100, "OI": 100000, "Is_Call": True},
            {"Strike": 1.1800, "Settle": 0.0200, "OI": 100000, "Is_Call": True},
        ]
    )

    iv_atm = estimate_atm_iv(option_df, "EUR", 1.1400, 7.0 / 252.0, 0.0, 0.02)

    assert 0.04 < iv_atm < 0.07


def test_atm_iv_static_fallback_has_explicit_diagnostics():
    empty = pd.DataFrame(columns=["Strike", "Settle", "OI", "Is_Call"])

    iv, diagnostics = resolve_atm_iv_reference(
        empty, "EUR", 1.14, 7.0 / 252.0, 0.0, 0.02
    )

    assert iv == 0.07
    assert diagnostics["source"] == "STATIC_FALLBACK"
    assert diagnostics["fallback_reason"] == "NO_VALID_OPTION_ROWS"


def test_pipeline_excludes_expired_rows_and_marks_static_iv_degraded(
    tmp_path, monkeypatch
):
    raw_df = pd.DataFrame(
        [
            {"Option_Type": "BTC", "Contract_Month": "JUL26", "Strike": 100000.0, "Settle": 0.01, "OI": 10, "Is_Call": True},
            {"Option_Type": "BTC", "Contract_Month": "JUL26", "Strike": 100000.0, "Settle": 0.01, "OI": 10, "Is_Call": False},
            {"Option_Type": "BTC", "Contract_Month": "AUG26", "Strike": 63000.0, "Settle": 0.01, "OI": 10, "Is_Call": True},
            {"Option_Type": "BTC", "Contract_Month": "AUG26", "Strike": 63000.0, "Settle": 0.01, "OI": 10, "Is_Call": False},
        ]
    )
    monkeypatch.setattr(main_module, "copy_csv_to_mt5", lambda *_args, **_kwargs: None)

    main_module.calculate_gex_pipeline(
        raw_df, "BTC", str(tmp_path), datetime.date(2026, 8, 3)
    )

    output = pd.read_csv(tmp_path / "GEX_BTCUSD_2026-08-03.csv")
    metadata = output.iloc[0]
    assert metadata["Futures_Spot"] == pytest.approx(63000.0)
    assert metadata["Excluded_Expired_Rows"] == 2
    assert metadata["IV_Source"] == "STATIC_FALLBACK"
    assert metadata["Quality_Status"] == "DEGRADED"
    assert "IV_STATIC_FALLBACK" in metadata["Quality_Reasons"]


def test_iv_month_rollover_skips_all_near_expiry_months():
    selected_month, selected_dte, old_month, old_dte = select_iv_month(
        ["JUN26", "JUL26", "AUG26"],
        "XAU",
        datetime.date(2026, 6, 24),
    )

    assert old_month == "JUN26"
    assert old_dte < 5
    assert selected_month == "AUG26"
    assert selected_dte >= 5
