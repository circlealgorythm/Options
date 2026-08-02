import csv
import datetime
import json
import threading
import urllib.error
import urllib.request

import pytest

from Dashboard import run_dashboard


@pytest.fixture
def dashboard_server(tmp_path, monkeypatch):
    monkeypatch.setattr(run_dashboard, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(run_dashboard, "ANALYSIS_PATH", str(tmp_path / "analysis.json"))
    monkeypatch.setattr(run_dashboard, "INDICATOR_LEVELS_DIR", str(tmp_path / "indicator-levels"))
    monkeypatch.setattr(run_dashboard, "schedule_today_files_sync", lambda: False)
    server = run_dashboard.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        run_dashboard.DashboardHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_api_rejects_unknown_currency_with_json_error(dashboard_server):
    base_url, _ = dashboard_server

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(
            f"{base_url}/api/data?currency=..%2F..%2Ftmp&date=2026-08-02"
        )

    payload = json.loads(exc_info.value.read().decode("utf-8"))
    assert exc_info.value.code == 400
    assert payload["error"]["code"] == "INVALID_CURRENCY"
    assert payload["error"]["request_id"]


def test_api_exposes_anomaly_and_fail_closed_xau_basis(dashboard_server):
    base_url, data_dir = dashboard_server
    selected_date = datetime.date.today().isoformat()
    path = data_dir / f"GEX_XAUUSD_{selected_date}.csv"
    fieldnames = [
        "Currency",
        "Strike",
        "Total_GEX",
        "Total_Abs_Gamma",
        "Daily_Call_Settle",
        "Daily_Call_OI",
        "Daily_Put_Settle",
        "Daily_Put_OI",
        "Global_Call_OI",
        "Global_Put_OI",
        "Futures_Spot",
        "R68_High",
        "R68_Low",
        "R95_High",
        "R95_Low",
        "Anomaly_Status",
        "Anomaly_Codes",
        "Anomaly_Details",
        "Anomaly_Baseline_Date",
    ]
    row = {
        "Currency": "XAU",
        "Strike": 4100.0,
        "Total_GEX": 12.0,
        "Total_Abs_Gamma": 3.0,
        "Daily_Call_Settle": 10.0,
        "Daily_Call_OI": 20,
        "Daily_Put_Settle": 11.0,
        "Daily_Put_OI": 21,
        "Global_Call_OI": 30,
        "Global_Put_OI": 31,
        "Futures_Spot": 4100.0,
        "R68_High": 4140.0,
        "R68_Low": 4060.0,
        "R95_High": 4180.0,
        "R95_Low": 4020.0,
        "Anomaly_Status": "WARN",
        "Anomaly_Codes": "IV_SHIFT",
        "Anomaly_Details": "R68 IV proxy changed",
        "Anomaly_Baseline_Date": "2026-08-01",
    }
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    with urllib.request.urlopen(
        f"{base_url}/api/data?currency=XAU&date={selected_date}"
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))

    metadata = payload["metadata"]
    assert metadata["anomaly_status"] == "WARN"
    assert metadata["anomaly_codes"] == "IV_SHIFT"
    assert metadata["basis_available"] is False
    assert metadata["basis_reason"] == "NO_SYNCHRONIZED_XAU_REFERENCE"
    assert metadata["live_spot"] is None
    assert metadata["live_offset"] == 0.0


def test_analysis_api_never_substitutes_an_old_report_for_selected_date(
    dashboard_server,
):
    base_url, data_dir = dashboard_server
    today = datetime.date.today()
    old_date = today - datetime.timedelta(days=1)
    analysis_path = data_dir / "analysis.json"
    analysis_path.write_text(
        json.dumps({
            "schema_version": 2,
            "generation_mode": "on_demand",
            "assets": {
                "EUR": {
                    "daily": {
                        old_date.isoformat(): {
                            "report_date": old_date.isoformat(),
                            "generated_at": f"{old_date.isoformat()}T09:00:00+03:00",
                            "content": "Старый дневной отчёт",
                        }
                    },
                    "weekly": {},
                }
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    with urllib.request.urlopen(
        f"{base_url}/api/analysis?currency=EUR&date={today.isoformat()}&period=daily"
    ) as response:
        missing_payload = json.loads(response.read().decode("utf-8"))
    with urllib.request.urlopen(
        f"{base_url}/api/analysis?currency=EUR&date={old_date.isoformat()}&period=daily"
    ) as response:
        exact_payload = json.loads(response.read().decode("utf-8"))

    assert missing_payload["period_key"] == today.isoformat()
    assert missing_payload["report"] is None
    assert exact_payload["report"] == "Старый дневной отчёт"
    assert exact_payload["report_date"] == old_date.isoformat()


def test_analysis_api_rejects_unknown_period(dashboard_server):
    base_url, _ = dashboard_server

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(
            f"{base_url}/api/analysis?currency=EUR&date="
            f"{datetime.date.today().isoformat()}&period=monday"
        )

    payload = json.loads(exc_info.value.read().decode("utf-8"))
    assert exc_info.value.code == 400
    assert payload["error"]["code"] == "INVALID_ANALYSIS_PERIOD"


def test_indicator_levels_api_returns_only_exact_mt5_manifest(dashboard_server):
    base_url, data_dir = dashboard_server
    manifest_dir = data_dir / "indicator-levels"
    manifest_dir.mkdir()
    report_date = datetime.date.today().isoformat()
    payload = {
        "schema_version": 1,
        "producer": "CME_GEX_Levels_Indicator",
        "asset": "XAU",
        "report_date": report_date,
        "generated_at": f"{report_date}T09:00:00",
        "source_csv": f"GEX_XAUUSD_{report_date}.csv",
        "coordinate_system": "MT5_SPOT",
        "selection": {
            "filter_mode": "absolute",
            "min_gex_filter": 1000.0,
            "active_gex_filter": 1000.0,
            "filter_reference_abs_gex": 5000.0,
            "min_gex_percent": 15.0,
            "max_visible_rows": 32,
            "max_strike_distance_percent": 12.0,
            "max_key_distance_percent": 18.0,
            "visible_count": 1,
        },
        "market": {
            "futures_spot": 4100.0,
            "mt5_spot_reference": 4098.0,
            "fw_offset": -2.0,
            "fw_offset_status": "mt5_d1_open",
        },
        "expiries": {
            "daily_month": "AUG26",
            "daily_expiry": report_date,
            "global_month": "DEC26",
            "global_expiry": "2026-11-23",
        },
        "quality": {
            "quality_status": "WARN",
            "quality_reasons": "ESTIMATED_EXPIRY_ALIAS",
            "anomaly_status": "OK",
            "anomaly_codes": "NONE",
            "anomaly_details": "NONE",
            "anomaly_baseline_date": "NONE",
            "gamma_flip_status": "FOUND",
        },
        "diagnostics": {
            "spot_source": "PUT_CALL_PARITY",
            "iv_source": "WEIGHTED_ATM",
            "iv_expiry": report_date,
            "iv_dte": 0,
            "estimated_expiry_types": "MM1",
        },
        "key_levels": {
            "spot_reference": {"chart_price": 4098.0},
            "zero_gamma": {"chart_price": 4075.0},
            "daily_call_mdd": {
                "chart_price": 4120.0,
                "strike": 4100.0,
                "settle": 22.0,
                "oi": 10.0,
            },
            "daily_put_mdd": {
                "chart_price": 4076.0,
                "strike": 4100.0,
                "settle": 22.0,
                "oi": 11.0,
            },
            "global_call": None,
            "global_put": None,
            "max_abs_gamma": {"chart_price": 4098.0, "strike": 4100.0, "abs_gamma": 9.0},
            "r68_high": {"chart_price": 4140.0},
            "r68_low": {"chart_price": 4056.0},
            "r95_high": {"chart_price": 4182.0},
            "r95_low": {"chart_price": 4014.0},
        },
        "visible_strikes": [{
            "strike": 4100.0,
            "chart_price": 4098.0,
            "total_gex": 100.0,
            "total_abs_gamma": 9.0,
            "gex_strength_percent": 100,
            "ag_strength_percent": 100,
            "roles": ["daily_call", "daily_put", "max_abs_gamma"],
        }],
    }
    (manifest_dir / f"GEX_XAU_{report_date}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with urllib.request.urlopen(
        f"{base_url}/api/indicator-levels?currency=XAU&date={report_date}"
    ) as response:
        exact = json.loads(response.read().decode("utf-8"))

    assert exact["coordinate_system"] == "MT5_SPOT"
    assert exact["market"]["fw_offset"] == -2.0
    missing_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(
            f"{base_url}/api/indicator-levels?currency=XAU&date={missing_date}"
        )
    missing = json.loads(exc_info.value.read().decode("utf-8"))
    assert exc_info.value.code == 404
    assert missing["error"]["code"] == "INDICATOR_LEVELS_NOT_FOUND"
