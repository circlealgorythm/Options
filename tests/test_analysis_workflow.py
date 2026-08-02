import copy
import datetime as dt
import json

import pytest

from Dashboard.analysis_store import load_analysis_payload
from Dashboard.analysis_workflow import (
    AnalysisWorkflowError,
    build_analysis_context,
    save_daily_report,
)
from Dashboard.indicator_levels_store import manifest_filename
from tests.test_indicator_levels_store import valid_manifest


def make_manifest(
    report_date,
    *,
    daily_expiry,
    global_expiry,
    quality_status="PASS",
    anomaly_status="OK",
    offset_status="mt5_d1_open",
    total_gex=5000.0,
):
    payload = valid_manifest("EUR", report_date)
    payload["generated_at"] = f"{report_date}T09:00:00+03:00"
    payload["expiries"].update({
        "daily_expiry": daily_expiry,
        "global_expiry": global_expiry,
    })
    payload["quality"]["quality_status"] = quality_status
    payload["quality"]["anomaly_status"] = anomaly_status
    payload["market"]["fw_offset_status"] = offset_status
    payload["visible_strikes"][0]["total_gex"] = total_gex
    return payload


def write_manifest(directory, payload):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / manifest_filename(payload["asset"], payload["report_date"])
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_context_compares_only_matching_daily_global_and_full_profiles(tmp_path):
    today = dt.date.today()
    current_date = today.isoformat()
    previous_date = (today - dt.timedelta(days=1)).isoformat()
    older_date = (today - dt.timedelta(days=2)).isoformat()
    daily_expiry = (today + dt.timedelta(days=3)).isoformat()
    global_expiry = (today + dt.timedelta(days=30)).isoformat()

    current = make_manifest(
        current_date,
        daily_expiry=daily_expiry,
        global_expiry=global_expiry,
        total_gex=6500.0,
    )
    previous = make_manifest(
        previous_date,
        daily_expiry=daily_expiry,
        global_expiry=global_expiry,
        total_gex=5000.0,
    )
    previous["key_levels"]["daily_call_mdd"]["oi"] = 80.0
    older = make_manifest(
        older_date,
        daily_expiry=(today + dt.timedelta(days=2)).isoformat(),
        global_expiry=global_expiry,
    )
    for payload in (current, previous, older):
        write_manifest(tmp_path, payload)

    context = build_analysis_context(tmp_path, "eur", current_date)

    assert context["schema_version"] == 1
    assert len(context["context_id"]) == 64
    assert context["quality_gate"] == {"report_mode": "full", "reasons": []}
    assert context["rollover"]["daily"]["changed"] is False
    assert context["rollover"]["global"]["changed"] is False
    comparison = context["comparison"]
    assert comparison["immediate_previous"]["report_date"] == previous_date
    assert comparison["same_daily_expiry"]["previous"]["report_date"] == previous_date
    assert comparison["same_global_expiry"]["previous"]["report_date"] == previous_date
    assert comparison["same_full_profile"]["previous"]["report_date"] == previous_date
    first_row = comparison["same_full_profile"]["visible_strike_changes"][1]
    assert first_row["strike"] == pytest.approx(1.155)
    assert first_row["deltas"]["total_gex"] == pytest.approx(1500.0)
    daily_call = next(
        change
        for change in comparison["same_daily_expiry"]["key_level_changes"]
        if change["level"] == "daily_call_mdd"
    )
    assert daily_call["deltas"]["oi"] == pytest.approx(20.0)


def test_context_marks_rollover_and_does_not_mix_nonmatching_cycles(tmp_path):
    today = dt.date.today()
    current_date = today.isoformat()
    previous_date = (today - dt.timedelta(days=1)).isoformat()
    current = make_manifest(
        current_date,
        daily_expiry=(today + dt.timedelta(days=4)).isoformat(),
        global_expiry=(today + dt.timedelta(days=60)).isoformat(),
    )
    previous = make_manifest(
        previous_date,
        daily_expiry=(today + dt.timedelta(days=1)).isoformat(),
        global_expiry=(today + dt.timedelta(days=30)).isoformat(),
    )
    write_manifest(tmp_path, current)
    write_manifest(tmp_path, previous)

    context = build_analysis_context(tmp_path, "EUR", current_date)

    assert context["rollover"]["daily"]["changed"] is True
    assert context["rollover"]["global"]["changed"] is True
    assert context["comparison"]["same_daily_expiry"] is None
    assert context["comparison"]["same_global_expiry"] is None
    assert context["comparison"]["same_full_profile"] is None


def test_context_skips_corrupt_history_and_marks_unknown_rollover(tmp_path):
    today = dt.date.today()
    report_date = today.isoformat()
    current = make_manifest(
        report_date,
        daily_expiry=(today + dt.timedelta(days=3)).isoformat(),
        global_expiry=(today + dt.timedelta(days=30)).isoformat(),
    )
    write_manifest(tmp_path, current)
    corrupt_date = (today - dt.timedelta(days=1)).isoformat()
    (tmp_path / manifest_filename("EUR", corrupt_date)).write_text(
        "{broken",
        encoding="utf-8",
    )

    context = build_analysis_context(tmp_path, "EUR", report_date)

    assert context["comparison"]["immediate_previous"] is None
    assert context["comparison"]["warnings"][0]["date"] == corrupt_date
    assert context["rollover"]["daily"]["status"] == "unknown_no_previous"
    assert context["rollover"]["daily"]["changed"] is None


def test_quality_gate_is_limited_or_blocked_and_context_id_tracks_manifest(tmp_path):
    today = dt.date.today()
    report_date = today.isoformat()
    expiry = (today + dt.timedelta(days=7)).isoformat()
    current = make_manifest(
        report_date,
        daily_expiry=expiry,
        global_expiry=(today + dt.timedelta(days=30)).isoformat(),
        quality_status="WARN",
        anomaly_status="WARN",
        offset_status="fallback",
    )
    path = write_manifest(tmp_path, current)

    limited = build_analysis_context(tmp_path, "EUR", report_date)
    assert limited["quality_gate"]["report_mode"] == "limited"
    assert len(limited["quality_gate"]["reasons"]) == 3

    changed = copy.deepcopy(current)
    changed["visible_strikes"][0]["total_gex"] = 6000.0
    path.write_text(json.dumps(changed), encoding="utf-8")
    changed_context = build_analysis_context(tmp_path, "EUR", report_date)
    assert changed_context["context_id"] != limited["context_id"]

    changed["quality"]["quality_status"] = "FAIL"
    path.write_text(json.dumps(changed), encoding="utf-8")
    blocked = build_analysis_context(tmp_path, "EUR", report_date)
    assert blocked["quality_gate"]["report_mode"] == "blocked"


def test_future_manifest_is_diagnostic_only_and_cannot_be_saved(tmp_path):
    today = dt.date.today()
    future = today + dt.timedelta(days=1)
    report_date = future.isoformat()
    manifest = make_manifest(
        report_date,
        daily_expiry=(future + dt.timedelta(days=3)).isoformat(),
        global_expiry=(future + dt.timedelta(days=30)).isoformat(),
    )
    write_manifest(tmp_path / "levels", manifest)
    now = dt.datetime.combine(today, dt.time(12, 0), tzinfo=dt.timezone.utc)

    context = build_analysis_context(
        tmp_path / "levels",
        "EUR",
        report_date,
        now=now,
    )
    assert context["quality_gate"]["report_mode"] == "blocked"
    assert "FUTURE_REPORT_DATE" in context["quality_gate"]["reasons"]

    with pytest.raises(AnalysisWorkflowError, match="future date"):
        save_daily_report(
            tmp_path / "analysis.json",
            tmp_path / "levels",
            "EUR",
            report_date,
            f"# EUR {report_date}",
            context["context_id"],
            now=now,
        )


def test_save_daily_report_rejects_stale_context_and_preserves_archive(tmp_path):
    today = dt.date.today()
    report_date = today.isoformat()
    expiry = (today + dt.timedelta(days=7)).isoformat()
    manifest = make_manifest(
        report_date,
        daily_expiry=expiry,
        global_expiry=(today + dt.timedelta(days=30)).isoformat(),
    )
    manifest_path = write_manifest(tmp_path / "levels", manifest)
    context = build_analysis_context(tmp_path / "levels", "EUR", report_date)
    analysis_path = tmp_path / "analysis.json"
    kept_date = (today - dt.timedelta(days=1)).isoformat()
    expired_date = (today - dt.timedelta(days=8)).isoformat()
    analysis_path.write_text(json.dumps({
        "schema_version": 2,
        "generation_mode": "on_demand",
        "retention_days": 7,
        "assets": {
            "GBP": {
                "daily": {
                    kept_date: {
                        "report_date": kept_date,
                        "content": "keep",
                    },
                    expired_date: {
                        "report_date": expired_date,
                        "content": "remove",
                    },
                },
                "weekly": {},
            }
        },
    }), encoding="utf-8")

    changed = copy.deepcopy(manifest)
    changed["visible_strikes"][0]["total_gex"] = 6000.0
    manifest_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(AnalysisWorkflowError, match="context changed"):
        save_daily_report(
            analysis_path,
            tmp_path / "levels",
            "EUR",
            report_date,
            f"# EUR — план на {report_date}",
            context["context_id"],
        )

    current_context = build_analysis_context(tmp_path / "levels", "EUR", report_date)
    result = save_daily_report(
        analysis_path,
        tmp_path / "levels",
        "EUR",
        report_date,
        f"# EUR — план на {today.strftime('%d.%m.%Y')}\n\nГотовый отчёт.",
        current_context["context_id"],
    )

    payload = load_analysis_payload(analysis_path)
    entry = payload["assets"]["EUR"]["daily"][report_date]
    assert result["removed_reports"] == 1
    assert entry["context_id"] == current_context["context_id"]
    assert entry["report_mode"] == "full"
    assert entry["source"] == "on_demand_indicator_manifest_v1"
    assert entry["content"].startswith("<!-- indicator_context_id:")
    assert kept_date in payload["assets"]["GBP"]["daily"]
    assert expired_date not in payload["assets"]["GBP"]["daily"]


def test_save_daily_report_rejects_blocked_or_wrong_date_content(tmp_path):
    today = dt.date.today()
    report_date = today.isoformat()
    manifest = make_manifest(
        report_date,
        daily_expiry=(today + dt.timedelta(days=3)).isoformat(),
        global_expiry=(today + dt.timedelta(days=30)).isoformat(),
        quality_status="FAIL",
    )
    write_manifest(tmp_path / "levels", manifest)
    context = build_analysis_context(tmp_path / "levels", "EUR", report_date)

    with pytest.raises(AnalysisWorkflowError, match="exact report date"):
        save_daily_report(
            tmp_path / "analysis.json",
            tmp_path / "levels",
            "EUR",
            report_date,
            "# Отчёт без даты",
            context["context_id"],
        )
    with pytest.raises(AnalysisWorkflowError, match="Analysis is blocked"):
        save_daily_report(
            tmp_path / "analysis.json",
            tmp_path / "levels",
            "EUR",
            report_date,
            f"# Отчёт {report_date}",
            context["context_id"],
        )
