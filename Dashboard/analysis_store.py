"""Versioned storage and safe lookup for on-demand GEX analysis reports."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
DEFAULT_RETENTION_DAYS = 7
SUPPORTED_PERIODS = frozenset({"daily", "weekly"})
_DATE_PATTERN = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
_WEEK_RANGE_PATTERN = re.compile(
    r"\b(\d{2}\.\d{2}\.\d{4})\s*[-–—]\s*(\d{2}\.\d{2}\.\d{4})\b"
)


class AnalysisStoreError(ValueError):
    """Raised when the analysis store is malformed or cannot be resolved safely."""


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisStoreError(f"Invalid analysis date: {value}") from exc


def week_start_for(value: dt.date) -> dt.date:
    return value - dt.timedelta(days=value.weekday())


def _parse_legacy_date(value: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(value, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


def _legacy_daily_date(content: str) -> dt.date | None:
    first_line = content.splitlines()[0] if content else ""
    match = _DATE_PATTERN.search(first_line)
    return _parse_legacy_date(match.group(1)) if match else None


def _legacy_week_range(content: str) -> tuple[dt.date, dt.date] | None:
    first_line = content.splitlines()[0] if content else ""
    match = _WEEK_RANGE_PATTERN.search(first_line)
    if not match:
        return None
    start = _parse_legacy_date(match.group(1))
    end = _parse_legacy_date(match.group(2))
    if start is None or end is None or end < start:
        return None
    return start, end


def _normalize_generated_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "UNKNOWN"
    stripped = value.strip()
    try:
        return dt.datetime.fromisoformat(stripped).isoformat()
    except ValueError:
        pass
    try:
        parsed = dt.datetime.strptime(stripped, "%d.%m.%Y, %H:%M:%S")
        return parsed.isoformat()
    except ValueError:
        return stripped


def migrate_legacy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert weekday-keyed v1 data into a lossless date-keyed v2 archive."""
    if payload.get("schema_version") == SCHEMA_VERSION and isinstance(payload.get("assets"), dict):
        return payload

    generated_at = _normalize_generated_at(payload.get("updated_at"))
    assets: dict[str, Any] = {}
    for asset, legacy_data in payload.items():
        if asset == "updated_at" or not isinstance(legacy_data, dict):
            continue

        daily_reports: dict[str, Any] = {}
        weekly_reports: dict[str, Any] = {}
        for key, raw_content in legacy_data.items():
            if not isinstance(raw_content, str) or not raw_content.strip():
                continue
            content = raw_content.strip()
            if key == "weekly":
                week_range = _legacy_week_range(content)
                if week_range is None:
                    continue
                week_start, week_end = week_range
                weekly_reports[week_start.isoformat()] = {
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "generated_at": generated_at,
                    "source": "legacy_weekday_v1",
                    "content": content,
                }
                continue

            report_date = _legacy_daily_date(content)
            if report_date is None:
                continue
            daily_reports[report_date.isoformat()] = {
                "report_date": report_date.isoformat(),
                "generated_at": generated_at,
                "source": "legacy_weekday_v1",
                "content": content,
            }

        assets[asset] = {"daily": daily_reports, "weekly": weekly_reports}

    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": generated_at,
        "generation_mode": "on_demand",
        "retention_days": DEFAULT_RETENTION_DAYS,
        "assets": assets,
    }


def load_analysis_payload(path: str | os.PathLike[str]) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AnalysisStoreError(f"Unable to read analysis store: {exc}") from exc
    if not isinstance(payload, dict):
        raise AnalysisStoreError("Analysis store root must be a JSON object")
    return payload


def resolve_analysis_report(
    payload: dict[str, Any],
    currency: str,
    selected_date: str,
    period: str = "daily",
) -> dict[str, Any] | None:
    """Resolve only the exact selected day or its exact Monday-based week."""
    if period not in SUPPORTED_PERIODS:
        raise AnalysisStoreError(f"Unsupported analysis period: {period}")
    selected = parse_iso_date(selected_date)
    normalized = migrate_legacy_payload(payload)
    assets = normalized.get("assets")
    if not isinstance(assets, dict):
        raise AnalysisStoreError("Analysis store is missing the assets object")
    asset_data = assets.get(currency.upper())
    if not isinstance(asset_data, dict):
        return None

    if period == "daily":
        period_key = selected.isoformat()
        report_map = asset_data.get("daily", {})
        identity_field = "report_date"
    else:
        period_key = week_start_for(selected).isoformat()
        report_map = asset_data.get("weekly", {})
        identity_field = "week_start"

    if not isinstance(report_map, dict):
        raise AnalysisStoreError(f"Analysis {period} store for {currency} must be an object")
    entry = report_map.get(period_key)
    if entry is None:
        return None
    if isinstance(entry, str):
        entry = {identity_field: period_key, "content": entry}
    if not isinstance(entry, dict):
        raise AnalysisStoreError(f"Analysis entry {currency}/{period_key} must be an object")
    if entry.get(identity_field, period_key) != period_key:
        raise AnalysisStoreError(
            f"Analysis entry identity mismatch for {currency}/{period_key}"
        )
    content = entry.get("content")
    if not isinstance(content, str) or not content.strip():
        return None

    resolved = dict(entry)
    resolved[identity_field] = period_key
    resolved["period"] = period
    resolved["period_key"] = period_key
    resolved["content"] = content.strip()
    return resolved


def prune_analysis_payload(
    payload: dict[str, Any],
    reference_date: dt.date | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> tuple[dict[str, Any], int]:
    """Remove reports more than retention_days older than their period key."""
    if retention_days < 0:
        raise AnalysisStoreError("Analysis retention days cannot be negative")
    reference_date = reference_date or dt.date.today()
    cutoff = reference_date - dt.timedelta(days=retention_days)
    normalized = copy.deepcopy(migrate_legacy_payload(payload))
    normalized["retention_days"] = retention_days
    assets = normalized.get("assets")
    if not isinstance(assets, dict):
        raise AnalysisStoreError("Analysis store is missing the assets object")

    removed = 0
    for asset, asset_data in assets.items():
        if not isinstance(asset_data, dict):
            raise AnalysisStoreError(f"Analysis store for {asset} must be an object")
        for period in SUPPORTED_PERIODS:
            report_map = asset_data.get(period, {})
            if not isinstance(report_map, dict):
                raise AnalysisStoreError(
                    f"Analysis {period} store for {asset} must be an object"
                )
            for period_key in list(report_map):
                report_date = parse_iso_date(period_key)
                if report_date < cutoff:
                    del report_map[period_key]
                    removed += 1
            asset_data[period] = report_map
    return normalized, removed


def write_analysis_payload(path: str | os.PathLike[str], payload: dict[str, Any]) -> None:
    destination = Path(path)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate GEX analysis.json to schema v2")
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--keep-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="Delete reports older than this many calendar days (default: 7)",
    )
    args = parser.parse_args()
    payload = load_analysis_payload(args.path)
    migrated, removed = prune_analysis_payload(
        payload,
        retention_days=args.keep_days,
    )
    write_analysis_payload(args.path, migrated)
    print(
        f"Migrated {args.path} to analysis schema v{SCHEMA_VERSION}; "
        f"removed {removed} expired reports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
