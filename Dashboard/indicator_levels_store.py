"""Strict access to indicator-exported MT5 level manifests."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PRODUCER = "CME_GEX_Levels_Indicator"
COORDINATE_SYSTEM = "MT5_SPOT"
SUPPORTED_ASSETS = frozenset({"EUR", "GBP", "XAU", "NAS", "SPX", "BTC", "USDCAD"})
SUPPORTED_ROLES = frozenset({
    "daily_call",
    "daily_put",
    "global_call",
    "global_put",
    "max_abs_gamma",
})
REQUIRED_KEY_LEVELS = frozenset({
    "spot_reference",
    "zero_gamma",
    "daily_call_mdd",
    "daily_put_mdd",
    "global_call",
    "global_put",
    "max_abs_gamma",
    "r68_high",
    "r68_low",
    "r95_high",
    "r95_low",
})
DEFAULT_INDICATOR_LEVELS_DIR = Path(
    r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX\IndicatorLevels"
)


class IndicatorLevelsError(ValueError):
    """Raised when an indicator-level manifest violates its contract."""


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise IndicatorLevelsError(f"Invalid indicator-level date: {value}") from exc


def manifest_filename(asset: str, report_date: str) -> str:
    normalized_asset = asset.upper()
    if normalized_asset not in SUPPORTED_ASSETS:
        raise IndicatorLevelsError(f"Unsupported indicator-level asset: {asset}")
    parse_iso_date(report_date)
    return f"GEX_{normalized_asset}_{report_date}.json"


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IndicatorLevelsError(f"{field} must be an object")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IndicatorLevelsError(f"{field} must be a non-empty string")
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IndicatorLevelsError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise IndicatorLevelsError(f"{field} must be finite")
    if positive and numeric <= 0.0:
        raise IndicatorLevelsError(f"{field} must be positive")
    return numeric


def _require_close(actual: float, expected: float, field: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-8):
        raise IndicatorLevelsError(
            f"{field} does not match the exported MT5 formula: "
            f"expected {expected}, got {actual}"
        )


def _validate_key_level(value: Any, field: str, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise IndicatorLevelsError(f"key_levels.{field} is required")
        return
    level = _object(value, f"key_levels.{field}")
    _number(level.get("chart_price"), f"key_levels.{field}.chart_price", positive=True)
    if "strike" in level:
        _number(level["strike"], f"key_levels.{field}.strike", positive=True)
    if "settle" in level:
        _number(level["settle"], f"key_levels.{field}.settle")
    if "oi" in level:
        _number(level["oi"], f"key_levels.{field}.oi")
    if "abs_gamma" in level:
        _number(level["abs_gamma"], f"key_levels.{field}.abs_gamma")


def validate_indicator_manifest(
    payload: dict[str, Any],
    *,
    expected_asset: str | None = None,
    expected_date: str | None = None,
) -> dict[str, Any]:
    """Validate identity, coordinates, selection counts, and numeric safety."""
    root = _object(payload, "manifest")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise IndicatorLevelsError(
            f"Unsupported indicator-level schema: {root.get('schema_version')}"
        )
    if root.get("producer") != PRODUCER:
        raise IndicatorLevelsError(f"Unexpected indicator-level producer: {root.get('producer')}")
    if root.get("coordinate_system") != COORDINATE_SYSTEM:
        raise IndicatorLevelsError(
            f"Unexpected coordinate system: {root.get('coordinate_system')}"
        )

    asset = _string(root.get("asset"), "asset").upper()
    if asset not in SUPPORTED_ASSETS:
        raise IndicatorLevelsError(f"Unsupported indicator-level asset: {asset}")
    report_date = _string(root.get("report_date"), "report_date")
    parse_iso_date(report_date)
    if expected_asset is not None and asset != expected_asset.upper():
        raise IndicatorLevelsError(
            f"Indicator-level asset mismatch: expected {expected_asset}, got {asset}"
        )
    if expected_date is not None and report_date != expected_date:
        raise IndicatorLevelsError(
            f"Indicator-level date mismatch: expected {expected_date}, got {report_date}"
        )
    generated_at = _string(root.get("generated_at"), "generated_at")
    try:
        dt.datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise IndicatorLevelsError("generated_at must be an ISO timestamp") from exc
    source_csv = _string(root.get("source_csv"), "source_csv")
    expected_source = (
        f"GEX_USDCAD_{report_date}.csv"
        if asset == "USDCAD"
        else f"GEX_{asset}USD_{report_date}.csv"
    )
    if source_csv != expected_source:
        raise IndicatorLevelsError(
            f"Indicator-level source mismatch: expected {expected_source}, got {source_csv}"
        )

    selection = _object(root.get("selection"), "selection")
    visible_count = selection.get("visible_count")
    if isinstance(visible_count, bool) or not isinstance(visible_count, int):
        raise IndicatorLevelsError("selection.visible_count must be an integer")
    if visible_count < 0:
        raise IndicatorLevelsError("selection.visible_count cannot be negative")
    if selection.get("filter_mode") not in {"absolute", "relative_percent"}:
        raise IndicatorLevelsError("selection.filter_mode is unsupported")
    for field in (
        "min_gex_filter",
        "active_gex_filter",
        "filter_reference_abs_gex",
        "min_gex_percent",
        "max_strike_distance_percent",
        "max_key_distance_percent",
    ):
        _number(selection.get(field), f"selection.{field}")
    maximum = selection.get("max_visible_rows")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise IndicatorLevelsError("selection.max_visible_rows must be a positive integer")
    market = _object(root.get("market"), "market")
    futures_spot = _number(market.get("futures_spot"), "market.futures_spot")
    mt5_spot = _number(
        market.get("mt5_spot_reference"),
        "market.mt5_spot_reference",
        positive=True,
    )
    fw_offset = _number(market.get("fw_offset"), "market.fw_offset")
    _string(market.get("fw_offset_status"), "market.fw_offset_status")
    if futures_spot > 0.0:
        _require_close(mt5_spot, futures_spot + fw_offset, "market.mt5_spot_reference")

    expiries = _object(root.get("expiries"), "expiries")
    for field in ("daily_month", "daily_expiry", "global_month", "global_expiry"):
        _string(expiries.get(field), f"expiries.{field}")

    quality = _object(root.get("quality"), "quality")
    for field in (
        "quality_status",
        "quality_reasons",
        "anomaly_status",
        "anomaly_codes",
        "anomaly_details",
        "anomaly_baseline_date",
        "gamma_flip_status",
    ):
        _string(quality.get(field), f"quality.{field}")

    diagnostics = _object(root.get("diagnostics"), "diagnostics")
    for field in ("spot_source", "iv_source", "iv_expiry", "estimated_expiry_types"):
        _string(diagnostics.get(field), f"diagnostics.{field}")
    iv_dte = diagnostics.get("iv_dte")
    if isinstance(iv_dte, bool) or not isinstance(iv_dte, int) or iv_dte < 0:
        raise IndicatorLevelsError("diagnostics.iv_dte must be a non-negative integer")

    key_levels = _object(root.get("key_levels"), "key_levels")
    missing_keys = REQUIRED_KEY_LEVELS - key_levels.keys()
    if missing_keys:
        raise IndicatorLevelsError(
            f"key_levels is missing: {', '.join(sorted(missing_keys))}"
        )
    _validate_key_level(key_levels["spot_reference"], "spot_reference", required=True)
    _validate_key_level(key_levels["daily_call_mdd"], "daily_call_mdd", required=True)
    _validate_key_level(key_levels["daily_put_mdd"], "daily_put_mdd", required=True)
    for field in REQUIRED_KEY_LEVELS - {"spot_reference", "daily_call_mdd", "daily_put_mdd"}:
        _validate_key_level(key_levels[field], field)

    daily_call = key_levels["daily_call_mdd"]
    daily_put = key_levels["daily_put_mdd"]
    _require_close(
        float(daily_call["chart_price"]),
        float(daily_call["strike"]) + fw_offset + float(daily_call["settle"]),
        "key_levels.daily_call_mdd.chart_price",
    )
    _require_close(
        float(daily_put["chart_price"]),
        float(daily_put["strike"]) + fw_offset - float(daily_put["settle"]),
        "key_levels.daily_put_mdd.chart_price",
    )
    for field in ("global_call", "global_put", "max_abs_gamma"):
        level = key_levels[field]
        if level is not None:
            _require_close(
                float(level["chart_price"]),
                float(level["strike"]) + fw_offset,
                f"key_levels.{field}.chart_price",
            )

    rows = root.get("visible_strikes")
    if not isinstance(rows, list):
        raise IndicatorLevelsError("visible_strikes must be an array")
    if len(rows) != visible_count:
        raise IndicatorLevelsError(
            "selection.visible_count does not match visible_strikes length"
        )
    seen_strikes: set[float] = set()
    rows_by_strike: dict[float, dict[str, Any]] = {}
    for index, raw_row in enumerate(rows):
        row = _object(raw_row, f"visible_strikes[{index}]")
        strike = _number(row.get("strike"), f"visible_strikes[{index}].strike", positive=True)
        if strike in seen_strikes:
            raise IndicatorLevelsError(f"Duplicate visible strike: {strike}")
        seen_strikes.add(strike)
        chart_price = _number(
            row.get("chart_price"),
            f"visible_strikes[{index}].chart_price",
            positive=True,
        )
        _require_close(
            chart_price,
            strike + fw_offset,
            f"visible_strikes[{index}].chart_price",
        )
        _number(row.get("total_gex"), f"visible_strikes[{index}].total_gex")
        gamma = _number(row.get("total_abs_gamma"), f"visible_strikes[{index}].total_abs_gamma")
        if gamma < 0.0:
            raise IndicatorLevelsError(
                f"visible_strikes[{index}].total_abs_gamma cannot be negative"
            )
        for strength_field in ("gex_strength_percent", "ag_strength_percent"):
            strength = _number(
                row.get(strength_field),
                f"visible_strikes[{index}].{strength_field}",
            )
            if strength < 0.0 or strength > 100.0:
                raise IndicatorLevelsError(
                    f"visible_strikes[{index}].{strength_field} must be between 0 and 100"
                )
        roles = row.get("roles")
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise IndicatorLevelsError(f"visible_strikes[{index}].roles must be a string array")
        unknown_roles = set(roles) - SUPPORTED_ROLES
        if unknown_roles:
            raise IndicatorLevelsError(
                f"visible_strikes[{index}] has unsupported roles: "
                f"{', '.join(sorted(unknown_roles))}"
            )
        rows_by_strike[strike] = row

    role_by_level = {
        "daily_call_mdd": "daily_call",
        "daily_put_mdd": "daily_put",
        "global_call": "global_call",
        "global_put": "global_put",
        "max_abs_gamma": "max_abs_gamma",
    }
    for level_name, role in role_by_level.items():
        level = key_levels[level_name]
        if level is None:
            continue
        strike = float(level["strike"])
        row = rows_by_strike.get(strike)
        if row is None or role not in row["roles"]:
            raise IndicatorLevelsError(
                f"key_levels.{level_name} is not linked to a visible strike role"
            )

    return root


def load_indicator_manifest(
    directory: str | os.PathLike[str],
    asset: str,
    report_date: str,
    *,
    attempts: int = 3,
) -> dict[str, Any]:
    """Load only the exact requested manifest; never substitute an older date."""
    filename = manifest_filename(asset, report_date)
    path = Path(directory) / filename
    if not path.is_file():
        raise FileNotFoundError(path)

    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            return validate_indicator_manifest(
                payload,
                expected_asset=asset,
                expected_date=report_date,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, IndicatorLevelsError) as exc:
            last_error = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.05)
    if isinstance(last_error, IndicatorLevelsError):
        raise last_error
    raise IndicatorLevelsError(f"Unable to read indicator-level manifest: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read an exact MT5 indicator-level manifest"
    )
    parser.add_argument("asset", choices=sorted(SUPPORTED_ASSETS))
    parser.add_argument("date", help="Exact report date in YYYY-MM-DD format")
    parser.add_argument(
        "--directory",
        type=Path,
        default=DEFAULT_INDICATOR_LEVELS_DIR,
    )
    args = parser.parse_args()
    payload = load_indicator_manifest(args.directory, args.asset, args.date)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
