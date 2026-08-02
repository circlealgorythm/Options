import calendar
import datetime
import re

from src.product_config import get_product_config


MONTH_MAP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def parse_contract_month(month_code):
    if not isinstance(month_code, str) or len(month_code) < 5:
        return None
    month = MONTH_MAP.get(month_code[:3].upper())
    try:
        year = 2000 + int(month_code[3:5])
    except (TypeError, ValueError):
        return None
    if month is None:
        return None
    return year, month


def nth_weekday(year, month, weekday, occurrence):
    days = [
        week[weekday]
        for week in calendar.monthcalendar(year, month)
        if week[weekday] != 0
    ]
    occurrence = int(occurrence)
    if not days or occurrence < 1 or occurrence > len(days):
        return None
    return datetime.date(year, month, days[occurrence - 1])


def next_weekday_on_or_after(value, weekday):
    return value + datetime.timedelta(days=(weekday - value.weekday()) % 7)


def _easter_sunday(year):
    """Gregorian Easter using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def _observed_fixed_holiday(year, month, day):
    holiday = datetime.date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - datetime.timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + datetime.timedelta(days=1)
    return holiday


def _last_weekday(year, month, weekday):
    last_day = calendar.monthrange(year, month)[1]
    value = datetime.date(year, month, last_day)
    return value - datetime.timedelta(days=(value.weekday() - weekday) % 7)


def _last_cme_trading_day(year, month):
    last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
    return previous_cme_trading_day(last_day)


def cme_full_close_holidays(year):
    """CME/US market holidays used for expiry adjustment and trading-day DTE."""
    holidays = {
        _observed_fixed_holiday(year, 1, 1),
        nth_weekday(year, 1, calendar.MONDAY, 3),
        nth_weekday(year, 2, calendar.MONDAY, 3),
        _easter_sunday(year) - datetime.timedelta(days=2),
        _last_weekday(year, 5, calendar.MONDAY),
        _observed_fixed_holiday(year, 6, 19),
        _observed_fixed_holiday(year, 7, 4),
        nth_weekday(year, 9, calendar.MONDAY, 1),
        nth_weekday(year, 11, calendar.THURSDAY, 4),
        _observed_fixed_holiday(year, 12, 25),
    }
    # New Year's Day can be observed in the preceding calendar year.
    holidays.add(_observed_fixed_holiday(year + 1, 1, 1))
    return holidays


def is_cme_trading_day(value):
    return value.weekday() < 5 and value not in cme_full_close_holidays(value.year)


def previous_cme_trading_day(value):
    result = value
    while not is_cme_trading_day(result):
        result -= datetime.timedelta(days=1)
    return result


def next_cme_trading_day(value):
    result = value
    while not is_cme_trading_day(result):
        result += datetime.timedelta(days=1)
    return result


def _adjust_weekly_expiry(value, option_type):
    if is_cme_trading_day(value):
        return value
    # All weekly candidates that land on Monday are Monday series by
    # construction. CME moves their holiday expiry forward; the other weekly
    # expiries move back to the preceding trading day.
    if value.weekday() == calendar.MONDAY:
        return next_cme_trading_day(value)
    return previous_cme_trading_day(value)


def _monthly_expiry(month_code, currency):
    parsed = parse_contract_month(month_code)
    if parsed is None:
        return None
    year, month = parsed
    currency = str(currency or "").upper()

    if currency in {"EUR", "GBP", "CAD", "USDCAD"}:
        third_wednesday = nth_weekday(year, month, calendar.WEDNESDAY, 3)
        return previous_cme_trading_day(third_wednesday - datetime.timedelta(days=12))

    if currency == "BTC":
        return previous_cme_trading_day(_last_weekday(year, month, calendar.FRIDAY))

    if currency == "XAU":
        if month == 1:
            prior_year, prior_month = year - 1, 12
        else:
            prior_year, prior_month = year, month - 1
        last_day = calendar.monthrange(prior_year, prior_month)[1]
        month_end = datetime.date(prior_year, prior_month, last_day)
        # Rule 115 counts four business days *prior to* month-end, so the
        # month-end business day itself is not part of the four-day count.
        cursor = month_end - datetime.timedelta(days=1)
        business_days = 0
        while business_days < 4:
            if is_cme_trading_day(cursor):
                business_days += 1
                if business_days == 4:
                    expiry = cursor
                    break
            cursor -= datetime.timedelta(days=1)

        # COMEX additionally moves a Friday expiry, or an expiry immediately
        # preceding an Exchange holiday, to the preceding business day.
        next_day_is_holiday = (
            expiry + datetime.timedelta(days=1)
        ) in cme_full_close_holidays(expiry.year)
        if expiry.weekday() == calendar.FRIDAY or next_day_is_holiday:
            expiry = previous_cme_trading_day(expiry - datetime.timedelta(days=1))
        return expiry

    return previous_cme_trading_day(nth_weekday(year, month, calendar.FRIDAY, 3))


def _rolling_weekday_expiry(as_of_date, parsed_month, weekday, option_type):
    expiry = next_weekday_on_or_after(as_of_date, weekday)
    if parsed_month is not None:
        year, month = parsed_month
        contract_key = (year, month)
        as_of_key = (as_of_date.year, as_of_date.month)
        expiry_key = (expiry.year, expiry.month)
        # A just-expired alias remains in the next bulletin. If advancing to
        # the next weekday leaves its own contract month, keep the final
        # matching weekday in that month so the row can be excluded as stale.
        if contract_key <= as_of_key and expiry_key > contract_key:
            expiry = _last_weekday(year, month, weekday)
    return _adjust_weekly_expiry(expiry, option_type)


def resolve_option_expiry(option_type, contract_month, currency, as_of_date=None):
    """Resolve an explicitly supported option series; unknown codes fail closed."""
    if as_of_date is None:
        as_of_date = datetime.date.today()
    option_type = str(option_type or "").upper()
    parsed = parse_contract_month(contract_month)
    config = get_product_config(currency)

    # Backward-compatible monthly helper used by month_to_expiry_date(). The
    # production pipeline always supplies an explicit option type.
    if not option_type:
        return _monthly_expiry(contract_month, currency)
    if config is None or option_type not in config.supported_codes:
        return None

    if option_type in config.monthly_codes:
        return _monthly_expiry(contract_month, currency)

    if option_type in config.eom_codes:
        if parsed is None:
            return None
        return _last_cme_trading_day(*parsed)

    if option_type in config.rolling_weekdays:
        return _rolling_weekday_expiry(
            as_of_date, parsed, config.rolling_weekdays[option_type], option_type
        )

    if option_type in config.fixed_occurrence_weekdays:
        if parsed is None:
            return None
        weekday, occurrence = config.fixed_occurrence_weekdays[option_type]
        expiry = nth_weekday(parsed[0], parsed[1], weekday, occurrence)
        return _adjust_weekly_expiry(expiry, option_type) if expiry else None

    if parsed is not None:
        year, month = parsed
        weekly_patterns = (
            (r"^([1-5])(?:EU|BP|CD)$", calendar.FRIDAY),
            (r"^(?:MO|MB|MD)([1-5])$", calendar.MONDAY),
            (r"^(?:TU|TG|TL)([1-5])$", calendar.TUESDAY),
            (r"^(?:WE|WG|WD)([1-5])$", calendar.WEDNESDAY),
            (r"^(?:SU|SB|SD)([1-5])$", calendar.THURSDAY),
            (r"^OG([1-5])$", calendar.FRIDAY),
            (r"^([1-5])MG$", calendar.MONDAY),
            (r"^([1-5])WG$", calendar.WEDNESDAY),
            (r"^([1-5])FG$", calendar.FRIDAY),
            (r"^G([1-5])M$", calendar.MONDAY),
            (r"^G([1-5])T$", calendar.TUESDAY),
            (r"^G([1-5])W$", calendar.WEDNESDAY),
            (r"^G([1-5])R$", calendar.THURSDAY),
            (r"^Q([1-5])A$", calendar.MONDAY),
            (r"^Q([1-5])B$", calendar.TUESDAY),
            (r"^Q([1-5])C$", calendar.WEDNESDAY),
            (r"^Q([1-5])D$", calendar.THURSDAY),
            (r"^QN([1-5])$", calendar.FRIDAY),
            (r"^EOW([1-5])$", calendar.FRIDAY),
            (r"^E([1-5])A$", calendar.MONDAY),
            (r"^E([1-5])B$", calendar.TUESDAY),
            (r"^E([1-5])C$", calendar.WEDNESDAY),
            (r"^E([1-5])D$", calendar.THURSDAY),
        )
        for pattern, weekday in weekly_patterns:
            match = re.match(pattern, option_type)
            if match:
                expiry = nth_weekday(year, month, weekday, int(match.group(1)))
                if expiry is None:
                    return None
                return _adjust_weekly_expiry(expiry, option_type)

        micro_nas_match = re.match(r"^MN([1-5])([A-E])$", option_type)
        if micro_nas_match:
            weekday = {
                "A": calendar.MONDAY,
                "B": calendar.TUESDAY,
                "C": calendar.WEDNESDAY,
                "D": calendar.THURSDAY,
                "E": calendar.FRIDAY,
            }[micro_nas_match.group(2)]
            expiry = nth_weekday(year, month, weekday, int(micro_nas_match.group(1)))
            return _adjust_weekly_expiry(expiry, option_type) if expiry else None

    return None


def trading_days_to_expiry(as_of_date, expiry_date):
    if expiry_date is None:
        return None
    if expiry_date <= as_of_date:
        return 0
    count = 0
    cursor = as_of_date + datetime.timedelta(days=1)
    while cursor <= expiry_date:
        if is_cme_trading_day(cursor):
            count += 1
        cursor += datetime.timedelta(days=1)
    return count
