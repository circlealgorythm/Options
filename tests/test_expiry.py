import datetime

from src.expiry import resolve_option_expiry, trading_days_to_expiry


def test_week_number_codes_resolve_to_distinct_expiries():
    as_of = datetime.date(2026, 7, 1)

    assert resolve_option_expiry("EOW1", "JUL26", "SPX", as_of) == datetime.date(2026, 7, 2)
    assert resolve_option_expiry("EOW4", "JUL26", "SPX", as_of) == datetime.date(2026, 7, 24)
    assert resolve_option_expiry("EOW5", "JUL26", "SPX", as_of) == datetime.date(2026, 7, 31)


def test_nas_weekday_and_week_number_are_both_used():
    as_of = datetime.date(2026, 6, 1)

    assert resolve_option_expiry("Q1C", "JUN26", "NAS", as_of) == datetime.date(2026, 6, 3)
    assert resolve_option_expiry("Q4C", "JUN26", "NAS", as_of) == datetime.date(2026, 6, 24)


def test_generic_daily_code_uses_next_matching_session():
    as_of = datetime.date(2026, 6, 23)

    assert resolve_option_expiry("WEC", "SEP26", "EUR", as_of) == datetime.date(2026, 6, 24)


def test_good_friday_expiry_moves_to_previous_trading_day():
    as_of = datetime.date(2026, 4, 1)

    assert resolve_option_expiry("1EU", "APR26", "EUR", as_of) == datetime.date(2026, 4, 2)


def test_same_day_expiry_has_zero_full_trading_days_remaining():
    value = datetime.date(2026, 7, 31)

    assert trading_days_to_expiry(value, value) == 0


def test_gold_monthly_expiry_excludes_month_end_from_four_day_count():
    as_of = datetime.date(2026, 7, 31)

    assert resolve_option_expiry("OG", "DEC26", "XAU", as_of) == datetime.date(2026, 11, 23)


def test_gold_monthly_expiry_matches_published_december_2009_date():
    as_of = datetime.date(2009, 10, 1)

    assert resolve_option_expiry("OG", "DEC09", "XAU", as_of) == datetime.date(2009, 11, 23)
