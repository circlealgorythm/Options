from pathlib import Path


INDICATOR_PATH = Path(__file__).resolve().parents[1] / "CME_GEX_Levels_Indicator.mq5"


def test_missing_today_is_not_filled_with_historical_levels():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert "TryParseLocalCSV(local_file_path, today_str" not in source
    assert "TryParseLocalCSV(local_file_path, latest_available_date" in source
    assert 'status = StringFormat("GEX today MISSING: %s | latest: %s"' in source
