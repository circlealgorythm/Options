"""Fail-visible quality checks for generated GEX summaries."""

from dataclasses import dataclass
import datetime
import math
from pathlib import Path
import re

import pandas as pd


@dataclass(frozen=True)
class AnomalyReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    details: tuple[str, ...]

    @property
    def status(self):
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "WARN"
        return "OK"

    @property
    def codes(self):
        return self.errors + self.warnings


DRIFT_LIMITS = {
    "EUR": {"spot": 0.08, "gamma_flip": 0.25, "iv_ratio": 2.0},
    "GBP": {"spot": 0.08, "gamma_flip": 0.25, "iv_ratio": 2.0},
    "CAD": {"spot": 0.08, "gamma_flip": 0.25, "iv_ratio": 2.0},
    "USDCAD": {"spot": 0.08, "gamma_flip": 0.25, "iv_ratio": 2.0},
    "XAU": {"spot": 0.15, "gamma_flip": 0.30, "iv_ratio": 2.0},
    "NAS": {"spot": 0.15, "gamma_flip": 0.30, "iv_ratio": 2.0},
    "SPX": {"spot": 0.15, "gamma_flip": 0.30, "iv_ratio": 2.0},
    "BTC": {"spot": 0.25, "gamma_flip": 0.40, "iv_ratio": 2.5},
}


def _first_number(frame, column):
    if frame is None or frame.empty or column not in frame.columns:
        return None
    value = pd.to_numeric(frame[column], errors="coerce").iloc[0]
    if pd.isna(value) or not math.isfinite(float(value)):
        return None
    return float(value)


def _add_issue(codes, details, code, detail):
    if code not in codes:
        codes.append(code)
        details.append(detail)


def load_previous_summary(output_dir, currency, as_of_date, max_age_days=7):
    """Load the newest earlier summary suitable for drift comparison."""
    output_path = Path(output_dir)
    prefix = "GEX_USDCAD_" if currency == "USDCAD" else f"GEX_{currency}USD_"
    filename_pattern = re.compile(
        rf"^{re.escape(prefix)}(\d{{4}}-\d{{2}}-\d{{2}})\.csv$"
    )
    candidates = []
    for path in output_path.glob(f"{prefix}*.csv"):
        match = filename_pattern.match(path.name)
        if not match:
            continue
        try:
            candidate_date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        age_days = (as_of_date - candidate_date).days
        if 0 < age_days <= max_age_days:
            candidates.append((candidate_date, path))

    if not candidates:
        return None, None, None

    baseline_date, baseline_path = max(candidates, key=lambda item: item[0])
    try:
        baseline = pd.read_csv(baseline_path)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return baseline_date, None, "BASELINE_READ_ERROR"
    if baseline.empty:
        return baseline_date, None, "BASELINE_EMPTY"
    return baseline_date, baseline, None


def evaluate_summary_anomalies(
    summary,
    currency,
    previous_summary=None,
    baseline_warning=None,
):
    """Validate current invariants and flag implausible inter-day changes."""
    errors = []
    warnings = []
    details = []

    if summary is None or summary.empty:
        return AnomalyReport(
            errors=("EMPTY_SUMMARY",),
            warnings=(),
            details=("Generated summary has no rows",),
        )

    required_numeric = (
        "Strike",
        "Total_GEX",
        "Total_Abs_Gamma",
        "R68_High",
        "R68_Low",
        "R95_High",
        "R95_Low",
        "Futures_Spot",
        "Gamma_Flip",
    )
    for column in required_numeric:
        if column not in summary.columns:
            _add_issue(
                errors,
                details,
                "MISSING_NUMERIC_COLUMN",
                f"Required numeric column is missing: {column}",
            )
            continue
        values = pd.to_numeric(summary[column], errors="coerce")
        if values.isna().any() or not values.map(math.isfinite).all():
            _add_issue(
                errors,
                details,
                "NONFINITE_NUMERIC_VALUE",
                f"Column contains a non-finite value: {column}",
            )

    spot = _first_number(summary, "Futures_Spot")
    r68_high = _first_number(summary, "R68_High")
    r68_low = _first_number(summary, "R68_Low")
    r95_high = _first_number(summary, "R95_High")
    r95_low = _first_number(summary, "R95_Low")
    gamma_flip = _first_number(summary, "Gamma_Flip")

    if spot is None or spot <= 0.0:
        _add_issue(errors, details, "INVALID_SPOT", "Futures spot must be positive")
    elif None not in (r68_high, r68_low, r95_high, r95_low):
        if not (r95_low < r68_low < spot < r68_high < r95_high):
            _add_issue(
                errors,
                details,
                "INVALID_RANGE_ORDER",
                "Expected R95_Low < R68_Low < spot < R68_High < R95_High",
            )
        tolerance = max(abs(spot) * 1e-9, 1e-12)
        if not math.isclose(r68_high - spot, spot - r68_low, abs_tol=tolerance):
            _add_issue(
                errors,
                details,
                "ASYMMETRIC_R68",
                "R68 volatility band is not symmetric around spot",
            )
        if not math.isclose(r95_high - spot, spot - r95_low, abs_tol=tolerance):
            _add_issue(
                errors,
                details,
                "ASYMMETRIC_R95",
                "R95 volatility band is not symmetric around spot",
            )

    if "Total_Abs_Gamma" in summary.columns:
        total_abs_gamma = pd.to_numeric(
            summary["Total_Abs_Gamma"], errors="coerce"
        ).fillna(0.0).sum()
        if total_abs_gamma <= 0.0:
            _add_issue(
                warnings,
                details,
                "NO_POSITIVE_GAMMA",
                "All absolute gamma values are zero",
            )

    gamma_status = (
        str(summary["Gamma_Flip_Status"].iloc[0])
        if "Gamma_Flip_Status" in summary.columns
        else "UNKNOWN"
    )
    if gamma_status == "FOUND":
        if spot and (gamma_flip is None or not 0.5 * spot <= gamma_flip <= 1.5 * spot):
            _add_issue(
                errors,
                details,
                "INVALID_GAMMA_FLIP",
                "Found Gamma Flip lies outside the validated spot range",
            )
    elif gamma_status == "NO_CROSSING" and gamma_flip not in (None, 0.0):
        _add_issue(
            errors,
            details,
            "INCONSISTENT_GAMMA_STATUS",
            "NO_CROSSING status must store Gamma Flip as zero",
        )

    if "Quality_Status" in summary.columns:
        quality_status = str(summary["Quality_Status"].iloc[0])
        spot_source = str(summary.get("Spot_Source", pd.Series(["NONE"])).iloc[0])
        iv_source = str(summary.get("IV_Source", pd.Series(["NONE"])).iloc[0])
        fallback_details = str(
            summary.get("Spot_Fallback_Details", pd.Series(["NONE"])).iloc[0]
        )
        fallback_used = (
            spot_source == "STATIC_FALLBACK"
            or iv_source == "STATIC_FALLBACK"
            or fallback_details not in ("", "NONE", "nan")
        )
        if fallback_used and quality_status != "DEGRADED":
            _add_issue(
                errors,
                details,
                "HIDDEN_MARKET_FALLBACK",
                "Fallback market data must set Quality_Status to DEGRADED",
            )

    if baseline_warning:
        _add_issue(
            warnings,
            details,
            baseline_warning,
            "Previous summary could not be used as an anomaly baseline",
        )

    if previous_summary is not None and not previous_summary.empty and spot and spot > 0.0:
        limits = DRIFT_LIMITS.get(
            str(currency).upper(),
            {"spot": 0.15, "gamma_flip": 0.30, "iv_ratio": 2.0},
        )
        previous_spot = _first_number(previous_summary, "Futures_Spot")
        if previous_spot and previous_spot > 0.0:
            spot_change = abs(spot / previous_spot - 1.0)
            if spot_change > limits["spot"]:
                _add_issue(
                    warnings,
                    details,
                    "SPOT_SHIFT",
                    f"Spot changed by {spot_change:.1%} versus the previous summary",
                )

            previous_r68_high = _first_number(previous_summary, "R68_High")
            previous_r68_low = _first_number(previous_summary, "R68_Low")
            if None not in (r68_high, r68_low, previous_r68_high, previous_r68_low):
                current_iv_proxy = (r68_high - r68_low) / (2.0 * spot)
                previous_iv_proxy = (
                    (previous_r68_high - previous_r68_low) / (2.0 * previous_spot)
                )
                if current_iv_proxy > 0.0 and previous_iv_proxy > 0.0:
                    iv_ratio = current_iv_proxy / previous_iv_proxy
                    ratio_limit = limits["iv_ratio"]
                    if iv_ratio > ratio_limit or iv_ratio < 1.0 / ratio_limit:
                        _add_issue(
                            warnings,
                            details,
                            "IV_SHIFT",
                            f"R68 IV proxy changed by a factor of {iv_ratio:.2f}",
                        )

        previous_gamma_flip = _first_number(previous_summary, "Gamma_Flip")
        if gamma_flip and gamma_flip > 0.0 and previous_gamma_flip and previous_gamma_flip > 0.0:
            gamma_change = abs(gamma_flip / previous_gamma_flip - 1.0)
            if gamma_change > limits["gamma_flip"]:
                _add_issue(
                    warnings,
                    details,
                    "GAMMA_FLIP_SHIFT",
                    f"Gamma Flip changed by {gamma_change:.1%} versus the previous summary",
                )

    return AnomalyReport(
        errors=tuple(errors),
        warnings=tuple(warnings),
        details=tuple(details),
    )
