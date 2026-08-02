from src.parser import (
    canonicalize_option_header_code,
    extract_delta,
    infer_nas_option_type_after_total,
)


def test_delta_skips_integer_point_change_in_native_quote_row():
    parts = "11300 ---- ---- ---- ---- 25.80+ 77 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953


def test_delta_skips_decimal_point_change_in_duplicate_quote_row():
    parts = "11300 ---- ---- ---- ---- .02580 +0.00770 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953


def test_delta_handles_split_change_sign_and_magnitude():
    parts = "11300 ---- ---- ---- ---- .02580 + .00770 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953


def test_gold_bulletin_alias_preserves_week_number():
    assert canonicalize_option_header_code(
        "XAU", "GMW", "GMW MON GOLD WEEKLY MONDAY OPTION WEEK3"
    ) == "G3M"
    assert canonicalize_option_header_code(
        "XAU", "FMG", "FMG OPT MICRO GOLD WEEKLY FRI OPTION WEEK5"
    ) == "5FG"


def test_nas_unlabeled_quarterly_put_transition_after_qn4_total():
    assert infer_nas_option_type_after_total(
        "NAS", "QN4", False, True, ["SEP26"]
    ) == "EMINI"
    assert infer_nas_option_type_after_total(
        "NAS", "QN4", True, True, ["SEP26"]
    ) == "QN4"
