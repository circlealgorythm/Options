import pandas as pd

from main import filter_supported_option_series
from src.product_config import contract_size_for, get_product_config


def test_contract_sizes_distinguish_standard_micro_and_month_end_products():
    assert contract_size_for("NAS", "EMINI") == 20
    assert contract_size_for("NAS", "MN1") == 2
    assert contract_size_for("XAU", "OG") == 100
    assert contract_size_for("XAU", "OMG") == 10
    assert contract_size_for("SPX", "EMINI") == 50
    assert contract_size_for("SPX", "SME") == 100


def test_global_series_are_monthly_not_weekly_aliases():
    assert get_product_config("NAS").global_codes == {"EMINI"}
    assert get_product_config("SPX").global_codes == {"EMINI"}


def test_unknown_and_cross_product_codes_are_excluded_fail_closed():
    raw = pd.DataFrame(
        [
            {"Option_Type": "EMINI", "Strike": 28000},
            {"Option_Type": "RTM", "Strike": 2900},
            {"Option_Type": "FUTURE_NEW_CODE", "Strike": 28000},
        ]
    )

    supported, unknown_codes, unknown_rows = filter_supported_option_series(raw, "NAS")

    assert supported["Option_Type"].tolist() == ["EMINI"]
    assert unknown_codes == ["FUTURE_NEW_CODE", "RTM"]
    assert unknown_rows == 2
