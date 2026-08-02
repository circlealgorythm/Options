import datetime
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import main
from src.parser import parse_cme_pdf


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "cme"
GOLDEN_PATH = FIXTURE_DIR / "btc_2026-07-30_golden.json"


def test_real_btc_bulletin_matches_golden_levels(tmp_path, monkeypatch):
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    fixture_path = FIXTURE_DIR / golden["fixture"]

    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == golden["sha256"]

    raw = parse_cme_pdf(str(fixture_path), "BTC", is_call_only=None)
    assert len(raw) == golden["raw_rows"]
    assert sorted(raw["Option_Type"].dropna().unique()) == golden["option_types"]
    assert sorted(raw["Contract_Month"].dropna().unique()) == golden["contract_months"]

    monkeypatch.setattr(main, "copy_csv_to_mt5", lambda _: None)
    as_of_date = datetime.date.fromisoformat(golden["as_of_date"])
    main.calculate_gex_pipeline(raw, "BTC", str(tmp_path), as_of_date)

    output_path = tmp_path / f"GEX_BTCUSD_{golden['as_of_date']}.csv"
    summary = pd.read_csv(output_path, keep_default_na=False)
    assert len(summary) == golden["output_rows"]
    first = summary.iloc[0]

    for column, expected in golden["levels"].items():
        assert first[column] == pytest.approx(expected, rel=1e-9, abs=1e-9)

    assert summary["Total_GEX"].sum() == pytest.approx(
        golden["totals"]["Total_GEX"], rel=1e-8, abs=1e-3
    )
    assert summary["Total_Abs_Gamma"].sum() == pytest.approx(
        golden["totals"]["Total_Abs_Gamma"], rel=1e-8, abs=1e-10
    )

    for column, expected in golden["metadata"].items():
        actual = first[column]
        if isinstance(expected, int):
            assert int(actual) == expected
        else:
            assert str(actual) == expected

    for prefix, expected in golden["mdd"].items():
        oi_column = f"{prefix}_OI"
        selected = summary.loc[summary[oi_column].idxmax()]
        assert selected["Strike"] == pytest.approx(expected["Strike"])
        assert selected[oi_column] == pytest.approx(expected["OI"])
        settle_column = f"{prefix}_Settle"
        if "Settle" in expected:
            assert selected[settle_column] == pytest.approx(expected["Settle"])
