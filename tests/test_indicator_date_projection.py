from pathlib import Path


INDICATOR_PATH = Path(__file__).resolve().parents[1] / "CME_GEX_Levels_Indicator.mq5"


def test_missing_today_is_not_filled_with_historical_levels():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert "TryParseLocalCSV(local_file_path, today_str" not in source
    assert "TryParseLocalCSV(local_file_path, latest_available_date" in source
    assert 'status = StringFormat("GEX %s | NO DATA | LAST %s"' in source


def test_visual_overlap_handling_preserves_the_existing_level_selection():
    source = INDICATOR_PATH.read_text(encoding="utf-8")
    overlap_block = source.split("int label_lane[];", 1)[1].split(
        'PrintFormat("CME GEX display pruning', 1
    )[0]

    assert "label_lane" in overlap_block
    assert "draw_labels" not in source
    assert "draw_rows[i] =" not in overlap_block
    assert "draw_rows[j] =" not in overlap_block
    assert "input double   InpMinGexPercent = 15.0;" in source
    assert "input int      InpMaxVisibleGexLevels = 0;" in source


def test_visual_controls_and_compact_status_are_present():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert 'ObjectCreate(0, "Btn_ShowZones", OBJ_BUTTON' in source
    assert 'ObjectCreate(0, "Btn_ShowLabels", OBJ_BUTTON' in source
    assert 'StringFormat("GEX %s | READY"' in source
    assert 'StringFormat("%s%s%s · G%d · A%d"' in source


def test_labels_start_near_lines_and_collisions_use_opposite_sides():
    source = INDICATOR_PATH.read_text(encoding="utf-8")

    assert "ArrayInitialize(used_lanes, false);" in source
    assert "while(free_lane < valid_rows && used_lanes[free_lane])" in source
    assert "label_lane[i] = free_lane;" in source
    assert "label_on_right ? (time_end - 1200) : (time_start + 1200)" in source
    assert "ANCHOR_RIGHT_LOWER : ANCHOR_RIGHT_UPPER" in source
    assert "ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER" in source
    assert "AllocateSpecialLabelLane" in source
    assert "ResolveLabelPlacement(zero_gamma_label_lane" in source
    assert "ResolveLabelPlacement(daily_call_mdd_label_lane" in source
    assert "ResolveLabelPlacement(daily_put_mdd_label_lane" in source
    assert "if(!used_lanes[2]) return 2;" in source


def test_fw_offset_uses_exact_calendar_day_and_reports_real_source():
    source = INDICATOR_PATH.read_text(encoding="utf-8")
    reference_block = source.split("double GetDailySpotReferenceWithRetry", 1)[1].split(
        "//| Parse CSV contents and draw levels", 1
    )[0]

    assert "CopyRates(symbol, PERIOD_D1, day_start, day_end" in reference_block
    assert "CopyRates(symbol, _Period, day_start, day_end" in reference_block
    assert "intraday_rates[i].time >= day_start" in reference_block
    assert "iBarShift(symbol, _Period, time_val)" not in reference_block
    assert 'out_source = "mt5_d1_open";' in reference_block
    assert 'out_source = "mt5_intraday_open_fallback";' in reference_block
    assert 'out_source = "mt5_live_bid_fallback";' in reference_block
    assert "fw_offset_status = spot_reference_source;" in source


def test_indicator_exports_the_final_visible_mt5_level_selection():
    source = INDICATOR_PATH.read_text(encoding="utf-8")
    export_block = source.split("void ExportIndicatorLevelsManifest", 1)[1].split(
        "//+------------------------------------------------------------------+", 1
    )[0]

    assert "input bool     InpExportIndicatorLevels = true;" in source
    assert "if(!draw_rows[i])" in export_block
    assert '"coordinate_system\\\":\\\"MT5_SPOT' in export_block
    assert "context.fw_offset" in export_block
    assert "context.daily_call_strike + context.fw_offset + daily_call_settle" in export_block
    assert "context.daily_put_strike + context.fw_offset - daily_put_settle" in export_block
    assert "ExportIndicatorLevelsManifest(date_str, rows, draw_rows" in source
    assert source.index("ExportIndicatorLevelsManifest(date_str, rows, draw_rows") > source.index(
        "while(visible_rows < max_visible_rows)"
    )
