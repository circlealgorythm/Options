from dataclasses import dataclass, field
from typing import Mapping


def _numbered(prefix, count=5):
    return frozenset(f"{prefix}{number}" for number in range(1, count + 1))


def _leading_numbered(suffix, count=5):
    return frozenset(f"{number}{suffix}" for number in range(1, count + 1))


@dataclass(frozen=True)
class ProductConfig:
    default_contract_size: float
    monthly_codes: frozenset[str] = frozenset()
    eom_codes: frozenset[str] = frozenset()
    numbered_weekly_codes: frozenset[str] = frozenset()
    rolling_weekdays: Mapping[str, int] = field(default_factory=dict)
    fixed_occurrence_weekdays: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    global_codes: frozenset[str] = frozenset()
    daily_codes: frozenset[str] = frozenset()
    contract_size_overrides: Mapping[str, float] = field(default_factory=dict)

    @property
    def supported_codes(self):
        return frozenset(
            set(self.monthly_codes)
            | set(self.eom_codes)
            | set(self.numbered_weekly_codes)
            | set(self.rolling_weekdays)
            | set(self.fixed_occurrence_weekdays)
        )


EUR_NUMBERED = (
    _leading_numbered("EU")
    | _numbered("MO")
    | _numbered("TU")
    | _numbered("WE")
    | _numbered("SU")
)
EUR_ROLLING = {
    "MEM": 0,
    "TEC": 1,
    "WEC": 2,
    # The daily bulletin's SEC aggregate maps to Thursday weekly series.
    "SEC": 3,
    "FRC": 4,
}

GBP_NUMBERED = (
    _leading_numbered("BP")
    | _numbered("MB")
    | _numbered("TG")
    | _numbered("WG")
    | _numbered("SB")
)
GBP_ROLLING = {
    "MGB": 0,
    "MGM": 0,
    "TGB": 1,
    "WGB": 2,
    "SBP": 3,
    "FGB": 4,
}

CAD_NUMBERED = (
    _leading_numbered("CD")
    | _numbered("MD")
    | _numbered("TL")
    | _numbered("WD")
    | _numbered("SD")
)
CAD_ROLLING = {"MCM": 0, "TCD": 1, "WCD": 2, "SCD": 3}

GOLD_STANDARD_NUMBERED = (
    _numbered("OG")
    | frozenset(
        f"G{number}{suffix}"
        for number in range(1, 6)
        for suffix in ("M", "T", "W", "R")
    )
)
GOLD_MICRO_NUMBERED = (
    _leading_numbered("MG")
    | _leading_numbered("WG")
    | _leading_numbered("FG")
)
GOLD_ROLLING = {
    "GMW": 0,
    "GWT": 1,
    "GWW": 2,
    "GWR": 3,
    "MMG": 0,
    "FMG": 4,
}
GOLD_MICRO_CODES = frozenset({"OMG", "MMG", "FMG"}) | GOLD_MICRO_NUMBERED

NAS_NUMBERED = frozenset(
    f"Q{number}{suffix}"
    for number in range(1, 6)
    for suffix in ("A", "B", "C", "D")
) | _numbered("QN")
NAS_MICRO_NUMBERED = frozenset(
    f"MN{number}{suffix}"
    for number in range(1, 6)
    for suffix in ("A", "B", "C", "D", "E")
)
NAS_ROLLING = {
    "QMW": 0,
    "DMQ": 0,
    "QTW": 1,
    "DTQ": 1,
    "QWW": 2,
    "DWQ": 2,
    "QRW": 3,
    "DRQ": 3,
    # Daily-bulletin aliases for Micro E-mini Nasdaq weekday options.
    "MN1": 0,
    "MN2": 1,
    "MN3": 2,
    "MN4": 3,
    "MN5": 4,
}
NAS_MICRO_CODES = frozenset(NAS_ROLLING.keys()) & _numbered("MN") | NAS_MICRO_NUMBERED
NAS_DAILY = NAS_NUMBERED | NAS_MICRO_NUMBERED | frozenset(NAS_ROLLING) | {"QN"}

SPX_NUMBERED = (
    _numbered("EOW")
    | frozenset(
        f"E{number}{suffix}"
        for number in range(1, 6)
        for suffix in ("A", "B", "C", "D")
    )
)
SPX_ROLLING = {
    "MMW": 0,
    "MTW": 1,
    "MDW": 2,
    "MRW": 3,
    "XMS": 0,
    "XTS": 1,
    "XWS": 2,
    "XRS": 3,
}


PRODUCT_CONFIGS = {
    "EUR": ProductConfig(
        default_contract_size=125_000,
        monthly_codes=frozenset({"EUU"}),
        numbered_weekly_codes=EUR_NUMBERED,
        rolling_weekdays=EUR_ROLLING,
        global_codes=frozenset({"EUU"}),
        daily_codes=EUR_NUMBERED | frozenset(EUR_ROLLING),
    ),
    "GBP": ProductConfig(
        default_contract_size=62_500,
        monthly_codes=frozenset({"GBU"}),
        numbered_weekly_codes=GBP_NUMBERED,
        rolling_weekdays=GBP_ROLLING,
        global_codes=frozenset({"GBU"}),
        daily_codes=GBP_NUMBERED | frozenset(GBP_ROLLING),
    ),
    "USDCAD": ProductConfig(
        default_contract_size=100_000,
        monthly_codes=frozenset({"CAU"}),
        numbered_weekly_codes=CAD_NUMBERED,
        rolling_weekdays=CAD_ROLLING,
        global_codes=frozenset({"CAU"}),
        daily_codes=CAD_NUMBERED | frozenset(CAD_ROLLING),
    ),
    "XAU": ProductConfig(
        default_contract_size=100,
        monthly_codes=frozenset({"OG", "OMG"}),
        numbered_weekly_codes=GOLD_STANDARD_NUMBERED | GOLD_MICRO_NUMBERED,
        rolling_weekdays=GOLD_ROLLING,
        global_codes=frozenset({"OG"}),
        daily_codes=GOLD_STANDARD_NUMBERED | GOLD_MICRO_NUMBERED | frozenset(GOLD_ROLLING),
        contract_size_overrides={code: 10 for code in GOLD_MICRO_CODES},
    ),
    "NAS": ProductConfig(
        default_contract_size=20,
        monthly_codes=frozenset({"EMINI"}),
        eom_codes=frozenset({"MINI"}),
        numbered_weekly_codes=NAS_NUMBERED | NAS_MICRO_NUMBERED,
        rolling_weekdays=NAS_ROLLING,
        fixed_occurrence_weekdays={"QN": (4, 3)},
        global_codes=frozenset({"EMINI"}),
        daily_codes=frozenset(NAS_DAILY) | {"MINI"},
        contract_size_overrides={code: 2 for code in NAS_MICRO_CODES},
    ),
    "SPX": ProductConfig(
        default_contract_size=50,
        monthly_codes=frozenset({"EMINI"}),
        eom_codes=frozenset({"EOM", "SME"}),
        numbered_weekly_codes=SPX_NUMBERED,
        rolling_weekdays=SPX_ROLLING,
        global_codes=frozenset({"EMINI"}),
        daily_codes=SPX_NUMBERED | frozenset(SPX_ROLLING) | {"EOM", "SME"},
        contract_size_overrides={"SME": 100},
    ),
    "BTC": ProductConfig(
        default_contract_size=5,
        monthly_codes=frozenset({"BTC"}),
        global_codes=frozenset({"BTC"}),
        daily_codes=frozenset({"BTC"}),
    ),
}


CATALOG_VERSION = "2026-08-02.2"


def normalize_product_key(currency):
    key = str(currency or "").upper()
    return "USDCAD" if key == "CAD" else key


def get_product_config(currency):
    return PRODUCT_CONFIGS.get(normalize_product_key(currency))


def is_supported_series(currency, option_type):
    config = get_product_config(currency)
    code = str(option_type or "").upper()
    return bool(config and code in config.supported_codes)


def contract_size_for(currency, option_type):
    config = get_product_config(currency)
    if config is None:
        raise KeyError(f"Unsupported product: {currency}")
    code = str(option_type or "").upper()
    return float(config.contract_size_overrides.get(code, config.default_contract_size))
