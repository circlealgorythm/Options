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
