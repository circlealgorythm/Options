import urllib.error

import pytest

from Dashboard import run_dashboard


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        return self.content


def test_fetch_bytes_retries_transient_errors_with_default_tls(monkeypatch):
    calls = []

    def fake_urlopen(request, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise urllib.error.URLError("temporary failure")
        return FakeResponse(b"ok")

    monkeypatch.setattr(run_dashboard.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_dashboard.time, "sleep", lambda _seconds: None)

    assert run_dashboard._fetch_bytes("https://example.test/data") == b"ok"
    assert len(calls) == 2
    assert all("context" not in kwargs for kwargs in calls)
    assert all(kwargs["timeout"] == run_dashboard.HTTP_TIMEOUT_SECONDS for kwargs in calls)


@pytest.mark.parametrize(
    "content, expected_message",
    [
        (b"<html>not csv</html>", "unsupported schema"),
        (
            b"Currency,Strike,Total_GEX,Total_Abs_Gamma,Daily_Call_Settle,"
            b"Daily_Call_OI,Daily_Put_Settle,Daily_Put_OI,Global_Call_OI,"
            b"Global_Put_OI,Futures_Spot\nEUR,1.1,2.0,3.0,0.1,10,0.1,10,"
            b"20,20,1.1\n",
            "wrong product",
        ),
    ],
)
def test_downloaded_csv_is_validated_before_write(content, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        run_dashboard._validate_gex_csv(content, "BTC")


def test_valid_downloaded_csv_passes_validation():
    content = (
        b"Currency,Strike,Total_GEX,Total_Abs_Gamma,Daily_Call_Settle,"
        b"Daily_Call_OI,Daily_Put_Settle,Daily_Put_OI,Global_Call_OI,"
        b"Global_Put_OI,Futures_Spot\nBTC,65000,2.0,3.0,250,8,340,12,"
        b"63,74,64775\n"
    )

    run_dashboard._validate_gex_csv(content, "BTC")


def test_atomic_file_write_replaces_destination(tmp_path):
    destination = tmp_path / "GEX_BTCUSD_2026-08-02.csv"
    destination.write_bytes(b"old")

    run_dashboard._write_file_atomically(str(destination), b"new")

    assert destination.read_bytes() == b"new"
    assert list(tmp_path.glob("*.tmp")) == []


def test_background_sync_is_non_blocking_and_throttled(monkeypatch):
    started_threads = []
    sync_calls = []

    class DeferredThread:
        def __init__(self, target, **_kwargs):
            self.target = target

        def start(self):
            started_threads.append(self)

    monkeypatch.setattr(run_dashboard.threading, "Thread", DeferredThread)
    # A first attempt must run even during the first 15 minutes after boot.
    monkeypatch.setattr(run_dashboard.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(run_dashboard, "LAST_SYNC_ATTEMPT", 0.0)
    monkeypatch.setattr(run_dashboard, "SYNC_IN_PROGRESS", False)
    monkeypatch.setattr(
        run_dashboard,
        "_perform_today_files_sync",
        lambda: sync_calls.append("done"),
    )

    assert run_dashboard.schedule_today_files_sync() is True
    assert run_dashboard.SYNC_IN_PROGRESS is True
    assert run_dashboard.schedule_today_files_sync() is False
    assert sync_calls == []

    started_threads[0].target()
    assert sync_calls == ["done"]
    assert run_dashboard.SYNC_IN_PROGRESS is False


def test_api_error_shape_has_stable_code_and_request_id():
    handler = object.__new__(run_dashboard.DashboardHandler)
    handler.request_id = "request-123"
    captured = {}
    handler.send_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )

    handler.send_error_json(
        504,
        "DEPENDENCY_TIMEOUT",
        "Dependency timed out",
        retryable=True,
    )

    assert captured["status"] == 504
    assert captured["payload"]["error"] == {
        "code": "DEPENDENCY_TIMEOUT",
        "message": "Dependency timed out",
        "request_id": "request-123",
        "retryable": True,
    }
