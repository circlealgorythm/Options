import calendar
import datetime
import re


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
    option_type = str(option_type or "").upper()
    monday_series = bool(
        re.match(r"^(Q[1-5]A|E[1-5]A|XMS|QMW|DMQ|SEC|MGB|MCM|G[1-5]M|GMW)$", option_type)
    )
    if value.weekday() == 0 and monday_series:
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


_GENERIC_WEEKDAY_CODES = {
    "SEC": calendar.MONDAY,
    "TEC": calendar.TUESDAY,
    "WEC": calendar.WEDNESDAY,
    "THC": calendar.THURSDAY,
    "FRC": calendar.FRIDAY,
    "MGB": calendar.MONDAY,
    "MGM": calendar.MONDAY,
    "TGB": calendar.TUESDAY,
    "WGB": calendar.WEDNESDAY,
    "SBP": calendar.THURSDAY,
    "FGB": calendar.FRIDAY,
    "MCM": calendar.MONDAY,
    "TCD": calendar.TUESDAY,
    "WCD": calendar.WEDNESDAY,
    "SCD": calendar.THURSDAY,
    "XMS": calendar.MONDAY,
    "XTS": calendar.TUESDAY,
    "XWS": calendar.WEDNESDAY,
    "XRS": calendar.THURSDAY,
    "QMW": calendar.MONDAY,
    "DMQ": calendar.MONDAY,
    "QTW": calendar.TUESDAY,
    "DTQ": calendar.TUESDAY,
    "QWW": calendar.WEDNESDAY,
    "DWQ": calendar.WEDNESDAY,
    "QRW": calendar.THURSDAY,
    "DRQ": calendar.THURSDAY,
    "GMW": calendar.MONDAY,
    "GWT": calendar.TUESDAY,
    "GWW": calendar.WEDNESDAY,
    "GWR": calendar.THURSDAY,
}


def resolve_option_expiry(option_type, contract_month, currency, as_of_date=None):
    """Resolve the actual option expiry, including weekday/week-number series."""
    if as_of_date is None:
        as_of_date = datetime.date.today()
    option_type = str(option_type or "").upper()
    parsed = parse_contract_month(contract_month)

    if option_type in _GENERIC_WEEKDAY_CODES:
        expiry = next_weekday_on_or_after(as_of_date, _GENERIC_WEEKDAY_CODES[option_type])
        return _adjust_weekly_expiry(expiry, option_type)

    if parsed is not None:
        year, month = parsed
        weekly_patterns = (
            (r"^([1-5])(?:EU|BP|CD)$", calendar.FRIDAY),
            (r"^OG([1-5])$", calendar.FRIDAY),
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

    return _monthly_expiry(contract_month, currency)


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
