import datetime

import pandas as pd

from main import copy_csv_to_mt5, select_daily_contracts, select_near_spot_mdd_settle, validate_mdd_summary
from src.parser import parse_bulletin_date_from_text


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


def test_validate_mdd_summary_rejects_missing_daily_levels():
    summary = pd.DataFrame(
        [
            {
                "Daily_Call_OI": 0.0,
                "Daily_Call_Settle": 0.0,
                "Daily_Put_OI": 0.0,
                "Daily_Put_Settle": 0.0,
                "Global_Call_OI": 10.0,
                "Global_Call_Settle": 0.001,
                "Global_Put_OI": 20.0,
                "Global_Put_Settle": 0.002,
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
