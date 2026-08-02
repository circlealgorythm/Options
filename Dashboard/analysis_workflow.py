"""Build expiry-safe analysis context and persist on-demand daily reports."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

try:
    from .analysis_store import (
        AnalysisStoreError,
        DEFAULT_RETENTION_DAYS,
        load_analysis_payload,
        prune_analysis_payload,
        write_analysis_payload,
    )
    from .indicator_levels_store import (
        DEFAULT_INDICATOR_LEVELS_DIR,
        IndicatorLevelsError,
        SUPPORTED_ASSETS,
        load_indicator_manifest,
        manifest_filename,
        parse_iso_date,
    )
except ImportError:  # Direct execution: python Dashboard/analysis_workflow.py
    from analysis_store import (
        AnalysisStoreError,
        DEFAULT_RETENTION_DAYS,
        load_analysis_payload,
        prune_analysis_payload,
        write_analysis_payload,
    )
    from indicator_levels_store import (
        DEFAULT_INDICATOR_LEVELS_DIR,
        IndicatorLevelsError,
        SUPPORTED_ASSETS,
        load_indicator_manifest,
        manifest_filename,
        parse_iso_date,
    )


CONTEXT_SCHEMA_VERSION = 1
REPORT_SOURCE = "on_demand_indicator_manifest_v1"
DAILY_LEVEL_KEYS = (
    "spot_reference",
    "zero_gamma",
    "daily_call_mdd",
    "daily_put_mdd",
    "r68_high",
    "r68_low",
    "r95_high",
    "r95_low",
)
GLOBAL_LEVEL_KEYS = ("global_call", "global_put", "max_abs_gamma")
_LEVEL_NUMERIC_FIELDS = ("chart_price", "strike", "settle", "oi", "abs_gamma")
_ROW_NUMERIC_FIELDS = (
    "chart_price",
    "total_gex",
    "total_abs_gamma",
    "gex_strength_percent",
    "ag_strength_percent",
)


class AnalysisWorkflowError(ValueError):
    """Raised when an analysis context or report cannot be handled safely."""


def _now_local(now: dt.datetime | None = None) -> dt.datetime:
    value = now or dt.datetime.now().astimezone()
    if value.tzinfo is None:
        value = value.astimezone()
    return value


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_dates(
    directory: str | os.PathLike[str],
    asset: str,
    before: dt.date,
) -> list[dt.date]:
    prefix = f"GEX_{asset.upper()}_"
    result: set[dt.date] = set()
    for path in Path(directory).glob(f"{prefix}*.json"):
        name = path.name
        if not name.startswith(prefix):
            continue
        date_text = name[len(prefix):-5]
        try:
            candidate = dt.date.fromisoformat(date_text)
        except ValueError:
            continue
        if candidate < before:
            result.add(candidate)
    return sorted(result, reverse=True)


def _load_previous_manifests(
    directory: str | os.PathLike[str],
    asset: str,
    report_date: dt.date,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    manifests: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for candidate in _candidate_dates(directory, asset, report_date):
        date_text = candidate.isoformat()
        try:
            manifests.append(load_indicator_manifest(directory, asset, date_text))
        except (FileNotFoundError, IndicatorLevelsError) as exc:
            warnings.append({
                "date": date_text,
                "code": "INVALID_PREVIOUS_MANIFEST",
                "message": str(exc),
            })
    return manifests, warnings


def _find_previous(
    manifests: Iterable[dict[str, Any]],
    *,
    daily_expiry: str | None = None,
    global_expiry: str | None = None,
) -> dict[str, Any] | None:
    for manifest in manifests:
        expiries = manifest["expiries"]
        if daily_expiry is not None and expiries["daily_expiry"] != daily_expiry:
            continue
        if global_expiry is not None and expiries["global_expiry"] != global_expiry:
            continue
        return manifest
    return None


def _is_comparable_expiry(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def _rollover_scope(
    immediate: dict[str, Any] | None,
    current_expiry: str,
    field: str,
) -> dict[str, Any]:
    previous_expiry = immediate["expiries"][field] if immediate else None
    if immediate is None:
        status = "unknown_no_previous"
        changed = None
    elif not _is_comparable_expiry(previous_expiry) or not _is_comparable_expiry(current_expiry):
        status = "unknown_expiry"
        changed = None
    elif previous_expiry != current_expiry:
        status = "changed"
        changed = True
    else:
        status = "unchanged"
        changed = False
    return {
        "status": status,
        "changed": changed,
        "from_expiry": previous_expiry,
        "to_expiry": current_expiry,
    }


def _level_change(
    name: str,
    current: dict[str, Any] | None,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    if current is None and previous is None:
        status = "absent"
    elif previous is None:
        status = "added"
    elif current is None:
        status = "removed"
    elif current == previous:
        status = "unchanged"
    else:
        status = "changed"

    deltas: dict[str, float] = {}
    if current is not None and previous is not None:
        for field in _LEVEL_NUMERIC_FIELDS:
            if field in current and field in previous:
                deltas[field] = float(current[field]) - float(previous[field])
    return {
        "level": name,
        "status": status,
        "current": copy.deepcopy(current),
        "previous": copy.deepcopy(previous),
        "deltas": deltas,
    }


def _compare_key_levels(
    current: dict[str, Any],
    previous: dict[str, Any],
    keys: Iterable[str],
) -> list[dict[str, Any]]:
    current_levels = current["key_levels"]
    previous_levels = previous["key_levels"]
    return [
        _level_change(key, current_levels.get(key), previous_levels.get(key))
        for key in keys
    ]


def _compare_visible_strikes(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    current_rows = {float(row["strike"]): row for row in current["visible_strikes"]}
    previous_rows = {float(row["strike"]): row for row in previous["visible_strikes"]}
    changes: list[dict[str, Any]] = []
    for strike in sorted(current_rows.keys() | previous_rows.keys()):
        current_row = current_rows.get(strike)
        previous_row = previous_rows.get(strike)
        if current_row is None:
            status = "removed"
        elif previous_row is None:
            status = "added"
        elif current_row == previous_row:
            status = "unchanged"
        else:
            status = "changed"

        deltas: dict[str, float] = {}
        roles_added: list[str] = []
        roles_removed: list[str] = []
        if current_row is not None and previous_row is None:
            roles_added = sorted(current_row["roles"])
        elif current_row is None and previous_row is not None:
            roles_removed = sorted(previous_row["roles"])
        elif current_row is not None and previous_row is not None:
            for field in _ROW_NUMERIC_FIELDS:
                deltas[field] = float(current_row[field]) - float(previous_row[field])
            current_roles = set(current_row["roles"])
            previous_roles = set(previous_row["roles"])
            roles_added = sorted(current_roles - previous_roles)
            roles_removed = sorted(previous_roles - current_roles)
        changes.append({
            "strike": strike,
            "status": status,
            "current": copy.deepcopy(current_row),
            "previous": copy.deepcopy(previous_row),
            "deltas": deltas,
            "roles_added": roles_added,
            "roles_removed": roles_removed,
        })
    return changes


def _comparison_identity(manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if manifest is None:
        return None
    return {
        "report_date": manifest["report_date"],
        "generated_at": manifest["generated_at"],
        "manifest_sha256": _canonical_hash(manifest),
        "daily_expiry": manifest["expiries"]["daily_expiry"],
        "global_expiry": manifest["expiries"]["global_expiry"],
    }


def _scoped_comparison(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    keys: Iterable[str],
) -> dict[str, Any] | None:
    if previous is None:
        return None
    return {
        "previous": _comparison_identity(previous),
        "key_level_changes": _compare_key_levels(current, previous, keys),
    }


def _quality_gate(
    manifest: dict[str, Any],
    report_date: dt.date,
    reference_date: dt.date,
) -> dict[str, Any]:
    quality = manifest["quality"]
    market = manifest["market"]
    quality_status = quality["quality_status"].strip().upper()
    anomaly_status = quality["anomaly_status"].strip().upper()
    offset_status = market["fw_offset_status"].strip().lower()
    reasons: list[str] = []

    if report_date > reference_date:
        reasons.append("FUTURE_REPORT_DATE")
    if quality_status == "FAIL":
        reasons.append(f"QUALITY_FAIL: {quality['quality_reasons']}")
    elif quality_status not in {"PASS", "OK"}:
        reasons.append(
            f"QUALITY_{quality_status or 'UNKNOWN'}: {quality['quality_reasons']}"
        )
    if anomaly_status not in {"PASS", "OK", "NONE"}:
        reasons.append(
            f"ANOMALY_{anomaly_status or 'UNKNOWN'}: {quality['anomaly_codes']}"
        )
    if offset_status != "mt5_d1_open":
        reasons.append(f"FW_OFFSET_STATUS: {market['fw_offset_status']}")

    if report_date > reference_date or quality_status == "FAIL":
        report_mode = "blocked"
    elif reasons:
        report_mode = "limited"
    else:
        report_mode = "full"
    return {"report_mode": report_mode, "reasons": reasons}


def build_analysis_context(
    levels_directory: str | os.PathLike[str],
    asset: str,
    report_date: str,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Build an immutable, expiry-aware input contract for one daily report."""
    normalized_asset = asset.upper()
    if normalized_asset not in SUPPORTED_ASSETS:
        raise AnalysisWorkflowError(f"Unsupported analysis asset: {asset}")
    parsed_date = parse_iso_date(report_date)
    current = load_indicator_manifest(levels_directory, normalized_asset, report_date)
    previous_manifests, warnings = _load_previous_manifests(
        levels_directory,
        normalized_asset,
        parsed_date,
    )

    daily_expiry = current["expiries"]["daily_expiry"]
    global_expiry = current["expiries"]["global_expiry"]
    immediate = previous_manifests[0] if previous_manifests else None
    same_daily = (
        _find_previous(previous_manifests, daily_expiry=daily_expiry)
        if _is_comparable_expiry(daily_expiry)
        else None
    )
    same_global = (
        _find_previous(previous_manifests, global_expiry=global_expiry)
        if _is_comparable_expiry(global_expiry)
        else None
    )
    same_profile = (
        _find_previous(
            previous_manifests,
            daily_expiry=daily_expiry,
            global_expiry=global_expiry,
        )
        if _is_comparable_expiry(daily_expiry)
        and _is_comparable_expiry(global_expiry)
        else None
    )
    generated = _now_local(now)

    rollover = {
        "previous_date": immediate["report_date"] if immediate else None,
        "daily": _rollover_scope(immediate, daily_expiry, "daily_expiry"),
        "global": _rollover_scope(immediate, global_expiry, "global_expiry"),
    }
    profile_comparison = None
    if same_profile is not None:
        profile_comparison = {
            "previous": _comparison_identity(same_profile),
            "visible_strike_changes": _compare_visible_strikes(current, same_profile),
        }

    core = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "asset": normalized_asset,
        "report_date": report_date,
        "coordinate_system": current["coordinate_system"],
        "quality_gate": _quality_gate(current, parsed_date, generated.date()),
        "rollover": rollover,
        "comparison": {
            "immediate_previous": _comparison_identity(immediate),
            "same_daily_expiry": _scoped_comparison(
                current,
                same_daily,
                DAILY_LEVEL_KEYS,
            ),
            "same_global_expiry": _scoped_comparison(
                current,
                same_global,
                GLOBAL_LEVEL_KEYS,
            ),
            "same_full_profile": profile_comparison,
            "warnings": warnings,
        },
        "indicator_levels": current,
    }
    return {
        **core,
        "context_id": _canonical_hash(core),
        "generated_at": generated.isoformat(timespec="seconds"),
    }


def _empty_analysis_payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "updated_at": "UNKNOWN",
        "generation_mode": "on_demand",
        "retention_days": DEFAULT_RETENTION_DAYS,
        "assets": {},
    }


def save_daily_report(
    analysis_path: str | os.PathLike[str],
    levels_directory: str | os.PathLike[str],
    asset: str,
    report_date: str,
    content: str,
    expected_context_id: str,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Persist one exact daily report only if its indicator context is current."""
    if not isinstance(content, str) or not content.strip():
        raise AnalysisWorkflowError("Daily analysis content cannot be empty")
    generated = _now_local(now)
    parsed_date = parse_iso_date(report_date)
    if parsed_date > generated.date():
        raise AnalysisWorkflowError("Cannot save an analysis report for a future date")
    cutoff = generated.date() - dt.timedelta(days=DEFAULT_RETENTION_DAYS)
    if parsed_date < cutoff:
        raise AnalysisWorkflowError(
            f"Cannot save a report older than the {DEFAULT_RETENTION_DAYS}-day retention window"
        )
    localized_date = parsed_date.strftime("%d.%m.%Y")
    if report_date not in content and localized_date not in content:
        raise AnalysisWorkflowError(
            "Daily analysis content must contain its exact report date"
        )

    context = build_analysis_context(
        levels_directory,
        asset,
        report_date,
        now=generated,
    )
    if not isinstance(expected_context_id, str) or expected_context_id != context["context_id"]:
        raise AnalysisWorkflowError(
            "Indicator context changed; rebuild the context before saving the report"
        )
    if context["quality_gate"]["report_mode"] == "blocked":
        raise AnalysisWorkflowError(
            "Analysis is blocked: " + "; ".join(context["quality_gate"]["reasons"])
        )

    destination = Path(analysis_path)
    source_payload = (
        load_analysis_payload(destination)
        if destination.is_file()
        else _empty_analysis_payload()
    )
    payload, removed = prune_analysis_payload(
        source_payload,
        reference_date=generated.date(),
        retention_days=DEFAULT_RETENTION_DAYS,
    )
    normalized_asset = asset.upper()
    assets = payload.setdefault("assets", {})
    asset_store = assets.setdefault(normalized_asset, {"daily": {}, "weekly": {}})
    daily_store = asset_store.setdefault("daily", {})
    asset_store.setdefault("weekly", {})
    clean_content = content.strip()
    stored_content = (
        f"<!-- indicator_context_id: {context['context_id']} -->\n"
        f"<!-- analysis_date: {report_date} -->\n"
        f"{clean_content}"
    )
    entry = {
        "report_date": report_date,
        "generated_at": generated.isoformat(timespec="seconds"),
        "source": REPORT_SOURCE,
        "context_id": context["context_id"],
        "indicator_generated_at": context["indicator_levels"]["generated_at"],
        "report_mode": context["quality_gate"]["report_mode"],
        "quality_reasons": list(context["quality_gate"]["reasons"]),
        "content": stored_content,
    }
    daily_store[report_date] = entry
    payload["schema_version"] = 2
    payload["updated_at"] = generated.isoformat(timespec="seconds")
    payload["generation_mode"] = "on_demand"
    payload["retention_days"] = DEFAULT_RETENTION_DAYS
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_analysis_payload(destination, payload)
    return {
        "entry": copy.deepcopy(entry),
        "removed_reports": removed,
        "analysis_path": str(destination),
    }


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and safely store on-demand GEX analysis"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    context_parser = subparsers.add_parser(
        "context",
        help="Build an exact, expiry-aware analysis context",
    )
    context_parser.add_argument("asset", choices=sorted(SUPPORTED_ASSETS))
    context_parser.add_argument("date", help="Exact report date in YYYY-MM-DD format")
    context_parser.add_argument(
        "--levels-directory",
        type=Path,
        default=DEFAULT_INDICATOR_LEVELS_DIR,
    )
    context_parser.add_argument("--output", type=Path)

    save_parser = subparsers.add_parser(
        "save",
        help="Save a report only while its context ID is still current",
    )
    save_parser.add_argument("asset", choices=sorted(SUPPORTED_ASSETS))
    save_parser.add_argument("date", help="Exact report date in YYYY-MM-DD format")
    save_parser.add_argument("report", type=Path, help="UTF-8 Markdown report")
    save_parser.add_argument("--context-id", required=True)
    save_parser.add_argument(
        "--levels-directory",
        type=Path,
        default=DEFAULT_INDICATOR_LEVELS_DIR,
    )
    save_parser.add_argument(
        "--analysis-path",
        type=Path,
        default=Path(__file__).with_name("analysis.json"),
    )
    args = parser.parse_args()

    try:
        if args.command == "context":
            context = build_analysis_context(
                args.levels_directory,
                args.asset,
                args.date,
            )
            if args.output:
                _write_json_atomically(args.output, context)
                print(args.output)
            else:
                print(json.dumps(context, ensure_ascii=False, indent=2))
            return 0

        content = args.report.read_text(encoding="utf-8-sig")
        result = save_daily_report(
            args.analysis_path,
            args.levels_directory,
            args.asset,
            args.date,
            content,
            args.context_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (
        OSError,
        UnicodeError,
        AnalysisStoreError,
        IndicatorLevelsError,
        AnalysisWorkflowError,
    ) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
