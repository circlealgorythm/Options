from pathlib import Path


INDICATOR_PATH = Path(__file__).resolve().parents[1] / "CME_GEX_Levels_Indicator.mq5"


def test_missing_today_is_not_filled_with_historical_levels():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert "TryParseLocalCSV(local_file_path, today_str" not in source
    assert "TryParseLocalCSV(local_file_path, latest_available_date" in source
    assert 'status = StringFormat("GEX %s | NO DATA | LAST %s"' in source


def test_visual_overlap_handling_preserves_the_existing_level_selection():
    source = INDICATOR_PATH.read_text(encoding="utf-8")
    overlap_block = source.split("if(InpPreventLabelOverlap", 1)[1].split(
        'PrintFormat("CME GEX display pruning', 1
    )[0]

    assert "draw_labels" in overlap_block
    assert "draw_rows[" not in overlap_block
    assert "input double   InpMinGexPercent = 15.0;" in source
    assert "input int      InpMaxVisibleGexLevels = 0;" in source


def test_visual_controls_and_compact_status_are_present():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert 'ObjectCreate(0, "Btn_ShowZones", OBJ_BUTTON' in source
    assert 'ObjectCreate(0, "Btn_ShowLabels", OBJ_BUTTON' in source
    assert 'StringFormat("GEX %s | READY"' in source
    assert 'StringFormat("%s%s%s · G%d · A%d"' in source
