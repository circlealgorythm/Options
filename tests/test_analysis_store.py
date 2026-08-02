import datetime as dt

import pytest

from Dashboard.analysis_store import (
    AnalysisStoreError,
    migrate_legacy_payload,
    prune_analysis_payload,
    resolve_analysis_report,
)


def test_legacy_weekdays_are_archived_by_report_date_not_weekday():
    legacy = {
        "updated_at": "27.07.2026, 06:00:00",
        "EUR": {
            "weekly": "# EURUSD — обзор недели 27.07.2026 – 31.07.2026\nТекст",
            "monday": "# EURUSD — Понедельник: План торгов (27.07.2026)\nТекст",
            "tuesday": "",
        },
    }

    migrated = migrate_legacy_payload(legacy)

    assert migrated["schema_version"] == 2
    assert set(migrated["assets"]["EUR"]["daily"]) == {"2026-07-27"}
    assert set(migrated["assets"]["EUR"]["weekly"]) == {"2026-07-27"}
    assert resolve_analysis_report(legacy, "EUR", "2026-08-03", "daily") is None


def test_daily_and_weekly_resolution_requires_exact_period_key():
    payload = {
        "schema_version": 2,
        "assets": {
            "EUR": {
                "daily": {
                    "2026-07-27": {
                        "report_date": "2026-07-27",
                        "content": "Дневной отчёт",
                    }
                },
                "weekly": {
                    "2026-07-27": {
                        "week_start": "2026-07-27",
                        "week_end": "2026-07-31",
                        "content": "Недельный отчёт",
                    }
                },
            }
        },
    }

    daily = resolve_analysis_report(payload, "EUR", "2026-07-27", "daily")
    weekly = resolve_analysis_report(payload, "EUR", "2026-07-29", "weekly")

    assert daily["content"] == "Дневной отчёт"
    assert weekly["content"] == "Недельный отчёт"
    assert resolve_analysis_report(payload, "EUR", "2026-08-03", "daily") is None
    assert resolve_analysis_report(payload, "EUR", "2026-08-03", "weekly") is None


def test_prune_removes_only_reports_older_than_seven_days():
    payload = {
        "schema_version": 2,
        "assets": {
            "EUR": {
                "daily": {
                    "2026-07-26": {"content": "старше семи дней"},
                    "2026-07-27": {"content": "ровно семь дней"},
                    "2026-08-03": {"content": "сегодня"},
                },
                "weekly": {
                    "2026-07-20": {"content": "старая неделя"},
                    "2026-07-27": {"content": "текущая сохранённая неделя"},
                },
            }
        },
    }

    pruned, removed = prune_analysis_payload(
        payload,
        reference_date=dt.date(2026, 8, 3),
    )

    assert removed == 2
    assert set(pruned["assets"]["EUR"]["daily"]) == {
        "2026-07-27",
        "2026-08-03",
    }
    assert set(pruned["assets"]["EUR"]["weekly"]) == {"2026-07-27"}


def test_report_identity_mismatch_is_rejected():
    payload = {
        "schema_version": 2,
        "assets": {
            "EUR": {
                "daily": {
                    "2026-08-03": {
                        "report_date": "2026-08-04",
                        "content": "Неверная дата",
                    }
                },
                "weekly": {},
            }
        },
    }

    with pytest.raises(AnalysisStoreError, match="identity mismatch"):
        resolve_analysis_report(payload, "EUR", "2026-08-03", "daily")
