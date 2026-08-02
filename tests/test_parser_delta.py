from src.parser import extract_delta


def test_delta_skips_integer_point_change_in_native_quote_row():
    parts = "11300 ---- ---- ---- ---- 25.80+ 77 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953


def test_delta_skips_decimal_point_change_in_duplicate_quote_row():
    parts = "11300 ---- ---- ---- ---- .02580 +0.00770 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953


def test_delta_handles_split_change_sign_and_magnitude():
    parts = "11300 ---- ---- ---- ---- .02580 + .00770 .953 ---- ---- 3 UNCH".split()

    assert extract_delta(parts, 5) == 0.953
