import os
import sys
import csv
import json
import glob
import time
import datetime
import math
import socket
import tempfile
import threading
import urllib.request
import urllib.error
import subprocess
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

try:
    from .analysis_store import (
        AnalysisStoreError,
        load_analysis_payload,
        prune_analysis_payload,
        resolve_analysis_report,
        week_start_for,
        write_analysis_payload,
    )
except ImportError:  # Direct execution: python Dashboard/run_dashboard.py
    from analysis_store import (
        AnalysisStoreError,
        load_analysis_payload,
        prune_analysis_payload,
        resolve_analysis_report,
        week_start_for,
        write_analysis_payload,
    )

PORT = 8080
HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
ANALYSIS_PATH = os.path.join(BASE_DIR, "analysis.json")
DEFAULT_MT5_GEX_DIR = r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX"
SUPPORTED_CURRENCIES = frozenset({"EUR", "GBP", "XAU", "NAS", "SPX", "BTC", "USDCAD"})
ANALYSIS_STORE_LOCK = threading.Lock()

LAST_SYNC_ATTEMPT = 0.0
SYNC_THROTTLE_SECONDS = 900  # 15 minutes throttle
SYNC_IN_PROGRESS = False
SYNC_STATE_LOCK = threading.Lock()

# Synchronized spot/futures cache (TTL = 60s for live data)
MARKET_PRICE_CACHE = {}
MARKET_PRICE_CACHE_LOCK = threading.Lock()
CACHE_TTL = 60.0
LIVE_STALE_CACHE_SECONDS = 300.0
HTTP_TIMEOUT_SECONDS = 5
HTTP_RETRY_ATTEMPTS = 3
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024

YAHOO_MARKETS = {
    "EUR": {"spot": "EURUSD=X", "futures": "6E=F", "max_basis_pct": 0.05},
    "GBP": {"spot": "GBPUSD=X", "futures": "6B=F", "max_basis_pct": 0.05},
    # Yahoo exposes GC futures but no reliable XAU/USD spot series. Leaving
    # XAU unmapped deliberately prevents a stale or cross-instrument offset.
    "NAS": {"spot": "^NDX", "futures": "NQ=F", "max_basis_pct": 0.10},
    "SPX": {"spot": "^SPX", "futures": "ES=F", "max_basis_pct": 0.10},
    "BTC": {"spot": "BTC-USD", "futures": "BTC=F", "max_basis_pct": 0.20},
    "USDCAD": {
        "spot": "USDCAD=X",
        "futures": "6C=F",
        "invert_futures": True,
        "max_basis_pct": 0.05,
    },
}


def _fetch_bytes(url, timeout=HTTP_TIMEOUT_SECONDS, attempts=HTTP_RETRY_ATTEMPTS):
    """Fetch a bounded response with verified TLS and transient retries."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CME-GEX-Dashboard/1.0"},
    )
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read(MAX_DOWNLOAD_BYTES + 1)
                if len(content) > MAX_DOWNLOAD_BYTES:
                    raise ValueError("HTTP response exceeds the configured size limit")
                return content
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
        time.sleep(0.2 * (2 ** attempt))
    raise last_error


def _fetch_yahoo_reference(ticker, selected_date=None):
    cache_key = (ticker, selected_date.isoformat() if selected_date else "live")
    now = time.time()
    with MARKET_PRICE_CACHE_LOCK:
        cached = MARKET_PRICE_CACHE.get(cache_key)
    cache_ttl = 86400.0 if selected_date else CACHE_TTL
    if cached and now - cached["timestamp"] < cache_ttl:
        return cached["price"]

    encoded_ticker = quote(ticker, safe="")
    if selected_date:
        period1 = int(datetime.datetime.combine(selected_date, datetime.time.min, datetime.timezone.utc).timestamp())
        period2 = int((datetime.datetime.combine(selected_date, datetime.time.min, datetime.timezone.utc) + datetime.timedelta(days=2)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?period1={period1}&period2={period2}&interval=1d"
    else:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}"

    try:
        result = json.loads(_fetch_bytes(url).decode("utf-8"))["chart"]["result"][0]
        if selected_date:
            opens = result.get("indicators", {}).get("quote", [{}])[0].get("open", [])
            price = next((float(value) for value in opens if value is not None and value > 0.0), None)
        else:
            price = result.get("meta", {}).get("regularMarketPrice")
        if price is not None and float(price) > 0.0:
            price = float(price)
            with MARKET_PRICE_CACHE_LOCK:
                MARKET_PRICE_CACHE[cache_key] = {"price": price, "timestamp": now}
            return price
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"[MarketReference] Error fetching {ticker}: {exc}")
        cache_age = now - cached["timestamp"] if cached else None
        if cached and (selected_date or cache_age <= LIVE_STALE_CACHE_SECONDS):
            return cached["price"]
    return None


def get_market_basis(currency, selected_date=None):
    config = YAHOO_MARKETS.get(currency.upper())
    if not config:
        return None

    spot = _fetch_yahoo_reference(config["spot"], selected_date)
    futures = _fetch_yahoo_reference(config["futures"], selected_date)
    if futures and config.get("invert_futures"):
        futures = 1.0 / futures
    if not spot or not futures:
        return None
    offset = spot - futures
    offset_pct = abs(offset) / abs(futures)
    if offset_pct > config["max_basis_pct"]:
        print(
            f"[MarketReference] Rejected {currency} basis {offset_pct:.2%}: "
            "spot/futures references are not comparable"
        )
        return None
    return {
        "spot": spot,
        "futures": futures,
        "offset": offset,
        "offset_pct": offset_pct,
        "source": "historical_open" if selected_date else "live_synchronized",
    }


def attach_market_basis(metadata, currency, selected_date, today=None):
    """Attach only a synchronized, bounded spot/futures basis to API metadata."""
    today = today or datetime.date.today()
    basis_date = None if selected_date == today else selected_date
    basis = get_market_basis(currency, basis_date)
    if basis is None:
        metadata.update({
            "live_spot": None,
            "live_futures": None,
            "live_offset": 0.0,
            "basis_available": False,
            "basis_reason": (
                "NO_SYNCHRONIZED_XAU_REFERENCE"
                if currency == "XAU"
                else "REFERENCE_UNAVAILABLE"
            ),
            "offset_status": "unavailable",
        })
        return metadata

    metadata.update({
        "live_spot": basis["spot"],
        "live_futures": basis["futures"],
        "live_offset": basis["offset"],
        "basis_available": True,
        "basis_reason": "NONE",
        "offset_status": basis["source"],
    })
    return metadata


def _validate_gex_csv(content, expected_currency):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Downloaded GEX file is not valid UTF-8") from exc
    reader = csv.DictReader(text.splitlines())
    required = {
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
    }
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Downloaded GEX file has an unsupported schema")
    row_count = 0
    numeric_columns = required - {"Currency"}
    for row in reader:
        row_count += 1
        if row.get("Currency", "").upper() != expected_currency:
            raise ValueError("Downloaded GEX file contains the wrong product")
        try:
            numeric_values = [float(row[column]) for column in numeric_columns]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Downloaded GEX file contains an invalid numeric value") from exc
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("Downloaded GEX file contains a non-finite numeric value")
    if row_count == 0:
        raise ValueError("Downloaded GEX file contains no rows")


def _write_file_atomically(destination, content):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=os.path.basename(destination) + ".",
        suffix=".tmp",
        dir=os.path.dirname(destination),
    )
    try:
        with os.fdopen(fd, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def _perform_today_files_sync():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    currencies = ["EUR", "GBP", "XAU", "NAS", "SPX", "BTC", "USDCAD"]
    
    missing_files = []
    for currency in currencies:
        if currency == "USDCAD":
            filename = f"GEX_USDCAD_{today_str}.csv"
        else:
            filename = f"GEX_{currency}USD_{today_str}.csv"
        
        local_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(local_path):
            missing_files.append((currency, filename, local_path))
            
    if not missing_files:
        print(f"[Sync] All today's files ({today_str}) are already present locally. No download needed.")
        return
        
    print(f"[Sync] Found {len(missing_files)} missing files for today ({today_str}). Checking GitHub...")
    
    copy_fn = None
    try:
        parent_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        from main import copy_csv_to_mt5
        copy_fn = copy_csv_to_mt5
    except Exception as e:
        print(f"[Sync] Warning: Could not import copy_csv_to_mt5 from main.py: {e}")
        
    mt5_dir = os.environ.get("MT5_GEX_DIR") or DEFAULT_MT5_GEX_DIR
    
    for currency, filename, local_path in missing_files:
        github_url = f"https://raw.githubusercontent.com/circlealgorythm/Options/main/data/{filename}"
        print(f"[Sync] Fetching {filename} from {github_url} ...")
        try:
            content = _fetch_bytes(github_url)
            _validate_gex_csv(content, currency)
            _write_file_atomically(local_path, content)
            print(f"[Sync] Successfully downloaded and saved {filename} to local data/")

            # Copy to MT5 only after a validated atomic local write.
            if copy_fn:
                copied = copy_fn(local_path, mt5_gex_dir=mt5_dir)
                if copied:
                    print(f"[Sync] Copied {filename} to MT5: {copied}")
                else:
                    print(f"[Sync] Warning: copy_csv_to_mt5 returned None for {filename}")
            else:
                print(f"[Sync] Warning: Skipping copy of {filename} to MT5 (copy function not loaded)")
        except urllib.error.HTTPError as he:
            if he.code == 404:
                print(f"[Sync] File {filename} not yet available on GitHub (404).")
            else:
                print(f"[Sync] HTTP error downloading {filename}: {he.code} {he.reason}")
        except Exception as e:
            print(f"[Sync] Error downloading {filename}: {e}")


def _finish_reserved_sync():
    global SYNC_IN_PROGRESS
    try:
        _perform_today_files_sync()
    except Exception as exc:
        print(f"[Sync] Background synchronization failed: {exc}")
    finally:
        with SYNC_STATE_LOCK:
            SYNC_IN_PROGRESS = False


def schedule_today_files_sync():
    """Start one throttled background sync without delaying an API request."""
    global LAST_SYNC_ATTEMPT, SYNC_IN_PROGRESS
    now = time.monotonic()
    with SYNC_STATE_LOCK:
        if SYNC_IN_PROGRESS or (
            LAST_SYNC_ATTEMPT > 0.0
            and now - LAST_SYNC_ATTEMPT < SYNC_THROTTLE_SECONDS
        ):
            return False
        previous_attempt = LAST_SYNC_ATTEMPT
        LAST_SYNC_ATTEMPT = now
        SYNC_IN_PROGRESS = True

    thread = threading.Thread(
        target=_finish_reserved_sync,
        name="gex-github-sync",
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        with SYNC_STATE_LOCK:
            SYNC_IN_PROGRESS = False
            LAST_SYNC_ATTEMPT = previous_attempt
        raise
    return True


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialize SimpleHTTPRequestHandler to serve from BASE_DIR (Dashboard/)
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        allowed_origin = os.environ.get("DASHBOARD_ALLOWED_ORIGIN")
        if allowed_origin:
            self.send_header('Access-Control-Allow-Origin', allowed_origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if hasattr(self, "request_id"):
            self.send_header("X-Request-ID", self.request_id)
        # Prevent browser caching of any files/endpoints in dashboard
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.request_id = uuid.uuid4().hex[:12]
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        self.request_id = uuid.uuid4().hex[:12]
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/dates':
            self.handle_get_dates(parsed_url.query)
        elif path == '/api/data':
            self.handle_get_data(parsed_url.query)
        elif path == '/api/analysis':
            self.handle_get_analysis(parsed_url.query)
        elif path == '/api/status':
            self.handle_get_status()
        elif path.startswith('/api/'):
            self.send_error_json(404, "ENDPOINT_NOT_FOUND", "API endpoint not found")
        else:
            # Fallback to serving static files
            super().do_GET()

    def do_POST(self):
        self.request_id = uuid.uuid4().hex[:12]
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/update':
            self.handle_post_update()
        else:
            self.send_error_json(404, "ENDPOINT_NOT_FOUND", "API endpoint not found")

    def handle_get_dates(self, query_str):
        try:
            schedule_today_files_sync()
        except Exception as se:
            print(f"[Sync] Error running automatic sync: {se}")

        try:
            params = parse_qs(query_str)
            currency = params.get('currency', [None])[0]
            
            if currency:
                curr_upper = currency.upper()
                if curr_upper not in SUPPORTED_CURRENCIES:
                    self.send_error_json(
                        400,
                        "INVALID_CURRENCY",
                        f"Unsupported currency: {currency}",
                    )
                    return
                if curr_upper == "USDCAD":
                    search_pattern = os.path.join(DATA_DIR, "GEX_USDCAD_*.csv")
                else:
                    search_pattern = os.path.join(DATA_DIR, f"GEX_{curr_upper}USD_*.csv")
            else:
                search_pattern = os.path.join(DATA_DIR, "GEX_*_*.csv")
                
            files = glob.glob(search_pattern)
            
            dates = set()
            today = datetime.date.today()
            limit = today - datetime.timedelta(days=14)
            
            for file_path in files:
                # Filename format: GEX_CURRENCY_YYYY-MM-DD.csv
                basename = os.path.basename(file_path)
                parts = basename.replace(".csv", "").split("_")
                if len(parts) >= 3:
                    # YYYY-MM-DD is the last part
                    date_part = parts[-1]
                    try:
                        file_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
                        if file_date >= limit:
                            dates.add(date_part)
                    except ValueError:
                        continue
            
            # Sort dates descending (latest first)
            sorted_dates = sorted(list(dates), reverse=True)
            
            self.send_json(200, {"dates": sorted_dates})
        except Exception as e:
            self.log_error("[request_id=%s] Error listing dates: %s", self.request_id, e)
            self.send_error_json(500, "DATES_READ_FAILED", "Unable to list GEX dates")

    def handle_get_data(self, query_str):
        try:
            schedule_today_files_sync()
        except Exception as se:
            print(f"[Sync] Error running automatic sync: {se}")

        try:
            params = parse_qs(query_str)
            currency = params.get('currency', ['EUR'])[0].upper()
            selected_date = params.get('date', [None])[0]

            if currency not in SUPPORTED_CURRENCIES:
                self.send_error_json(
                    400,
                    "INVALID_CURRENCY",
                    f"Unsupported currency: {currency}",
                )
                return

            today = datetime.date.today()
            limit = today - datetime.timedelta(days=14)

            if selected_date:
                try:
                    req_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d").date()
                    if req_date < limit:
                        self.send_error_json(
                            400,
                            "DATE_OUT_OF_RANGE",
                            f"Requested date {selected_date} is older than the 14-day limit",
                        )
                        return
                except ValueError:
                    self.send_error_json(
                        400,
                        "INVALID_DATE",
                        f"Invalid date format: {selected_date}",
                    )
                    return

            # If no date, find the latest available date for this currency
            if not selected_date:
                if currency == "USDCAD":
                    search_pattern = os.path.join(DATA_DIR, "GEX_USDCAD_*.csv")
                else:
                    search_pattern = os.path.join(DATA_DIR, f"GEX_{currency}USD_*.csv")
                files = glob.glob(search_pattern)
                if not files:
                    self.send_error_json(
                        404,
                        "GEX_DATA_NOT_FOUND",
                        f"No files found for currency {currency}",
                    )
                    return
                # Extract dates and find the latest within 14 days limit
                file_dates = []
                for f in files:
                    parts = os.path.basename(f).replace(".csv", "").split("_")
                    if len(parts) >= 3:
                        date_part = parts[-1]
                        try:
                            file_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
                            if file_date >= limit:
                                file_dates.append(date_part)
                        except ValueError:
                            continue
                if not file_dates:
                    self.send_error_json(
                        404,
                        "GEX_DATA_NOT_FOUND",
                        f"No GEX data found within the last 14 days for {currency}",
                    )
                    return
                selected_date = sorted(file_dates, reverse=True)[0]

            if currency == "USDCAD":
                csv_name = f"GEX_USDCAD_{selected_date}.csv"
            else:
                csv_name = f"GEX_{currency}USD_{selected_date}.csv"
            csv_path = os.path.join(DATA_DIR, csv_name)

            if not os.path.exists(csv_path):
                self.send_error_json(
                    404,
                    "GEX_DATA_NOT_FOUND",
                    f"File {csv_name} not found",
                )
                return

            # Read and parse CSV manually to avoid dependencies
            levels = []
            metadata = {
                "currency": currency,
                "date": selected_date,
                "spot": 0.0,
                "r68_high": 0.0,
                "r68_low": 0.0,
                "r95_high": 0.0,
                "r95_low": 0.0,
                "global_month": "UNKNOWN",
                "daily_month": "UNKNOWN",
                "daily_expiry": "UNKNOWN",
                "global_expiry": "UNKNOWN",
                "gamma_flip": 0.0,
                "gamma_flip_status": "UNKNOWN",
                "quality_status": "UNKNOWN",
                "quality_reasons": "NONE",
                "catalog_version": "UNKNOWN",
                "spot_source": "UNKNOWN",
                "spot_reference_month": "UNKNOWN",
                "spot_fallback_details": "NONE",
                "iv_source": "UNKNOWN",
                "iv_expiry": "UNKNOWN",
                "iv_dte": 0,
                "iv_fallback_reason": "NONE",
                "unknown_option_types": "NONE",
                "estimated_expiry_types": "NONE",
                "anomaly_status": "UNKNOWN",
                "anomaly_codes": "NONE",
                "anomaly_details": "NONE",
                "anomaly_baseline_date": "NONE",
            }

            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    self.send_error_json(
                        500,
                        "INVALID_GEX_FILE",
                        "GEX data file is empty",
                    )
                    return
                headers = [header.strip() for header in headers]
                
                # Check required headers
                try:
                    strike_idx = headers.index("Strike")
                    gex_idx = headers.index("Total_GEX")
                    gamma_idx = headers.index("Total_Abs_Gamma")
                    call_settle_idx = headers.index("Daily_Call_Settle")
                    call_oi_idx = headers.index("Daily_Call_OI")
                    put_settle_idx = headers.index("Daily_Put_Settle")
                    put_oi_idx = headers.index("Daily_Put_OI")
                    glob_call_oi_idx = headers.index("Global_Call_OI")
                    glob_put_oi_idx = headers.index("Global_Put_OI")
                    
                    # Optional/meta columns
                    spot_idx = headers.index("Futures_Spot") if "Futures_Spot" in headers else -1
                    r68_h_idx = headers.index("R68_High") if "R68_High" in headers else -1
                    r68_l_idx = headers.index("R68_Low") if "R68_Low" in headers else -1
                    r95_h_idx = headers.index("R95_High") if "R95_High" in headers else -1
                    r95_l_idx = headers.index("R95_Low") if "R95_Low" in headers else -1
                    g_month_idx = headers.index("Global_Month") if "Global_Month" in headers else -1
                    d_month_idx = headers.index("Daily_Month") if "Daily_Month" in headers else -1
                    d_expiry_idx = headers.index("Daily_Expiry") if "Daily_Expiry" in headers else -1
                    g_expiry_idx = headers.index("Global_Expiry") if "Global_Expiry" in headers else -1
                    gamma_flip_idx = headers.index("Gamma_Flip") if "Gamma_Flip" in headers else -1
                    gamma_status_idx = headers.index("Gamma_Flip_Status") if "Gamma_Flip_Status" in headers else -1
                    quality_status_idx = headers.index("Quality_Status") if "Quality_Status" in headers else -1
                    quality_reasons_idx = headers.index("Quality_Reasons") if "Quality_Reasons" in headers else -1
                    catalog_version_idx = headers.index("Series_Catalog_Version") if "Series_Catalog_Version" in headers else -1
                    spot_source_idx = headers.index("Spot_Source") if "Spot_Source" in headers else -1
                    spot_reference_month_idx = headers.index("Spot_Reference_Month") if "Spot_Reference_Month" in headers else -1
                    spot_fallback_idx = headers.index("Spot_Fallback_Details") if "Spot_Fallback_Details" in headers else -1
                    iv_source_idx = headers.index("IV_Source") if "IV_Source" in headers else -1
                    iv_expiry_idx = headers.index("IV_Expiry") if "IV_Expiry" in headers else -1
                    iv_dte_idx = headers.index("IV_DTE") if "IV_DTE" in headers else -1
                    iv_fallback_idx = headers.index("IV_Fallback_Reason") if "IV_Fallback_Reason" in headers else -1
                    unknown_types_idx = headers.index("Unknown_Option_Types") if "Unknown_Option_Types" in headers else -1
                    estimated_types_idx = headers.index("Estimated_Expiry_Types") if "Estimated_Expiry_Types" in headers else -1
                    anomaly_status_idx = headers.index("Anomaly_Status") if "Anomaly_Status" in headers else -1
                    anomaly_codes_idx = headers.index("Anomaly_Codes") if "Anomaly_Codes" in headers else -1
                    anomaly_details_idx = headers.index("Anomaly_Details") if "Anomaly_Details" in headers else -1
                    anomaly_baseline_idx = headers.index("Anomaly_Baseline_Date") if "Anomaly_Baseline_Date" in headers else -1
                except ValueError as ve:
                    self.log_error(
                        "[request_id=%s] Invalid GEX schema in %s: %s",
                        self.request_id,
                        csv_name,
                        ve,
                    )
                    self.send_error_json(
                        500,
                        "INVALID_GEX_SCHEMA",
                        "GEX data file is missing a required column",
                    )
                    return
 
                # Read rows
                first_row = True
                for parts in reader:
                    if not parts or not any(part.strip() for part in parts):
                        continue
                    parts = [part.strip() for part in parts]
                    if len(parts) < len(headers):
                        continue
 
                    # Extract metadata from the first row
                    if first_row:
                        first_row = False
                        if spot_idx != -1: metadata["spot"] = float(parts[spot_idx])
                        if r68_h_idx != -1: metadata["r68_high"] = float(parts[r68_h_idx])
                        if r68_l_idx != -1: metadata["r68_low"] = float(parts[r68_l_idx])
                        if r95_h_idx != -1: metadata["r95_high"] = float(parts[r95_h_idx])
                        if r95_l_idx != -1: metadata["r95_low"] = float(parts[r95_l_idx])
                        if g_month_idx != -1: metadata["global_month"] = parts[g_month_idx]
                        if d_month_idx != -1: metadata["daily_month"] = parts[d_month_idx]
                        if d_expiry_idx != -1: metadata["daily_expiry"] = parts[d_expiry_idx]
                        if g_expiry_idx != -1: metadata["global_expiry"] = parts[g_expiry_idx]
                        if gamma_flip_idx != -1 and gamma_flip_idx < len(parts):
                            metadata["gamma_flip"] = float(parts[gamma_flip_idx])
                        if gamma_status_idx != -1: metadata["gamma_flip_status"] = parts[gamma_status_idx]
                        if quality_status_idx != -1: metadata["quality_status"] = parts[quality_status_idx]
                        if quality_reasons_idx != -1: metadata["quality_reasons"] = parts[quality_reasons_idx]
                        if catalog_version_idx != -1: metadata["catalog_version"] = parts[catalog_version_idx]
                        if spot_source_idx != -1: metadata["spot_source"] = parts[spot_source_idx]
                        if spot_reference_month_idx != -1: metadata["spot_reference_month"] = parts[spot_reference_month_idx]
                        if spot_fallback_idx != -1: metadata["spot_fallback_details"] = parts[spot_fallback_idx]
                        if iv_source_idx != -1: metadata["iv_source"] = parts[iv_source_idx]
                        if iv_expiry_idx != -1: metadata["iv_expiry"] = parts[iv_expiry_idx]
                        if iv_dte_idx != -1: metadata["iv_dte"] = int(float(parts[iv_dte_idx]))
                        if iv_fallback_idx != -1: metadata["iv_fallback_reason"] = parts[iv_fallback_idx]
                        if unknown_types_idx != -1: metadata["unknown_option_types"] = parts[unknown_types_idx]
                        if estimated_types_idx != -1: metadata["estimated_expiry_types"] = parts[estimated_types_idx]
                        if anomaly_status_idx != -1: metadata["anomaly_status"] = parts[anomaly_status_idx]
                        if anomaly_codes_idx != -1: metadata["anomaly_codes"] = parts[anomaly_codes_idx]
                        if anomaly_details_idx != -1: metadata["anomaly_details"] = parts[anomaly_details_idx]
                        if anomaly_baseline_idx != -1: metadata["anomaly_baseline_date"] = parts[anomaly_baseline_idx]

                    levels.append({
                        "strike": float(parts[strike_idx]),
                        "gex": float(parts[gex_idx]),
                        "gamma": float(parts[gamma_idx]),
                        "daily_call_settle": float(parts[call_settle_idx]),
                        "daily_call_oi": float(parts[call_oi_idx]),
                        "daily_put_settle": float(parts[put_settle_idx]),
                        "daily_put_oi": float(parts[put_oi_idx]),
                        "global_call_oi": float(parts[glob_call_oi_idx]),
                        "global_put_oi": float(parts[glob_put_oi_idx]),
                    })

                if first_row:
                    self.send_error_json(
                        500,
                        "INVALID_GEX_FILE",
                        "GEX data file contains no level rows",
                    )
                    return

            # Convert futures strikes to spot using synchronized references.
            # Historical files use same-day opens; today's file uses two live
            # quotes. Never subtract a live spot from a stale CSV future.
            selected_date_value = datetime.date.fromisoformat(selected_date)
            attach_market_basis(metadata, currency, selected_date_value)

            self.send_json(200, {
                "metadata": metadata,
                "levels": levels
            })

        except Exception as e:
            self.log_error(
                "[request_id=%s] Error reading GEX CSV: %s",
                self.request_id,
                e,
            )
            self.send_error_json(
                500,
                "GEX_DATA_READ_FAILED",
                "Unable to read the GEX data file",
            )

    def handle_get_analysis(self, query_str):
        params = parse_qs(query_str)
        currency = params.get("currency", ["EUR"])[0].upper()
        selected_date = params.get("date", [None])[0]
        period = params.get("period", ["daily"])[0].lower()

        if currency not in SUPPORTED_CURRENCIES:
            self.send_error_json(
                400,
                "INVALID_CURRENCY",
                f"Unsupported currency: {currency}",
            )
            return
        if selected_date is None:
            self.send_error_json(
                400,
                "ANALYSIS_DATE_REQUIRED",
                "Analysis date is required",
            )
            return
        try:
            selected_date_value = datetime.date.fromisoformat(selected_date)
        except ValueError:
            self.send_error_json(
                400,
                "INVALID_DATE",
                f"Invalid date format: {selected_date}",
            )
            return
        if period not in {"daily", "weekly"}:
            self.send_error_json(
                400,
                "INVALID_ANALYSIS_PERIOD",
                f"Unsupported analysis period: {period}",
            )
            return

        try:
            with ANALYSIS_STORE_LOCK:
                if os.path.exists(ANALYSIS_PATH):
                    source_payload = load_analysis_payload(ANALYSIS_PATH)
                else:
                    source_payload = {
                        "schema_version": 2,
                        "generation_mode": "on_demand",
                        "retention_days": 7,
                        "assets": {},
                    }
                payload, removed = prune_analysis_payload(source_payload)
                if removed or payload != source_payload:
                    write_analysis_payload(ANALYSIS_PATH, payload)
                report = resolve_analysis_report(
                    payload,
                    currency,
                    selected_date,
                    period,
                )
        except AnalysisStoreError as exc:
            self.log_error(
                "[request_id=%s] Invalid analysis store: %s",
                self.request_id,
                exc,
            )
            self.send_error_json(
                500,
                "INVALID_ANALYSIS_STORE",
                "Unable to read the analysis archive safely",
            )
            return

        period_key = (
            selected_date
            if period == "daily"
            else week_start_for(selected_date_value).isoformat()
        )
        response = {
            "schema_version": payload.get("schema_version", 1),
            "generation_mode": payload.get("generation_mode", "on_demand"),
            "retention_days": payload.get("retention_days", 7),
            "currency": currency,
            "selected_date": selected_date,
            "period": period,
            "period_key": period_key,
            "updated_at": payload.get("updated_at", "UNKNOWN"),
            "report": None,
            "generated_at": None,
            "source": None,
        }
        if report is not None:
            response.update({
                "period_key": report["period_key"],
                "report": report["content"],
                "generated_at": report.get("generated_at"),
                "source": report.get("source"),
                "report_date": report.get("report_date"),
                "week_start": report.get("week_start"),
                "week_end": report.get("week_end"),
            })
        self.send_json(200, response)

    def handle_get_status(self):
        try:
            mt5_dir = os.environ.get("MT5_GEX_DIR") or DEFAULT_MT5_GEX_DIR
            exists = os.path.exists(mt5_dir)
            files = []
            if exists:
                root_files = glob.glob(os.path.join(mt5_dir, "GEX_*.csv"))
                xau_files = glob.glob(os.path.join(mt5_dir, "XAU", "GEX_*.csv"))
                nas_files = glob.glob(os.path.join(mt5_dir, "NAS100", "GEX_*.csv"))
                crypto_files = glob.glob(os.path.join(mt5_dir, "Crypto", "GEX_*.csv"))
                usdcad_files = glob.glob(os.path.join(mt5_dir, "USDCAD", "GEX_*.csv"))
                all_paths = root_files + xau_files + nas_files + crypto_files + usdcad_files
                files = [os.path.basename(f) for f in all_paths]
            
            self.send_json(200, {
                "mt5_directory": mt5_dir,
                "exists": exists,
                "sync_files_count": len(files),
                "sync_files": sorted(files, reverse=True)[:5] # top 5 files
            })
        except Exception as e:
            self.log_error(
                "[request_id=%s] Error getting MT5 status: %s",
                self.request_id,
                e,
            )
            self.send_error_json(
                500,
                "MT5_STATUS_FAILED",
                "Unable to read MT5 synchronization status",
            )

    def handle_post_update(self):
        try:
            parent_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
            main_py_path = os.path.join(parent_dir, "main.py")
            
            if not os.path.exists(main_py_path):
                self.send_error_json(
                    500,
                    "PIPELINE_NOT_FOUND",
                    "CME update pipeline is not available",
                )
                return

            print(f"Triggering CME update pipeline: {sys.executable} {main_py_path} in {parent_dir}")
            
            # Execute python main.py
            process = subprocess.run(
                [sys.executable, "main.py"],
                cwd=parent_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            payload = {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
            if process.returncode == 0:
                self.send_json(200, payload)
            else:
                self.send_error_json(
                    500,
                    "PIPELINE_FAILED",
                    "CME update pipeline exited with an error",
                    extra=payload,
                )
            
        except subprocess.TimeoutExpired:
            self.send_error_json(
                504,
                "PIPELINE_TIMEOUT",
                "CME update pipeline exceeded the 120-second timeout",
                retryable=True,
            )
        except Exception as e:
            self.log_error(
                "[request_id=%s] Error executing CME pipeline: %s",
                self.request_id,
                e,
            )
            self.send_error_json(
                500,
                "PIPELINE_EXECUTION_FAILED",
                "Unable to execute the CME update pipeline",
            )

    def send_json(self, status_code, payload):
        content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_error_json(
        self,
        status_code,
        code,
        message,
        retryable=False,
        extra=None,
    ):
        payload = dict(extra or {})
        payload["error"] = {
            "code": code,
            "message": message,
            "request_id": self.request_id,
            "retryable": retryable,
        }
        self.send_json(status_code, payload)

def run(server_class=ThreadingHTTPServer, handler_class=DashboardHandler, port=PORT, host=HOST):
    server_address = (host, port)
    httpd = server_class(server_address, handler_class)
    print(f"Option Levels Dashboard server running at http://{host}:{port}/")
    
    # Trigger an immediate sync check on startup
    try:
        print("[Sync] Running initial startup sync check...")
        schedule_today_files_sync()
    except Exception as e:
        print(f"[Sync] Error during startup sync check: {e}")
        
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
