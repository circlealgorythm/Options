import os
import sys
import json
import glob
import time
import datetime
import urllib.request
import urllib.error
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DEFAULT_MT5_GEX_DIR = r"C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX"

LAST_SYNC_ATTEMPT = 0.0
SYNC_THROTTLE_SECONDS = 900  # 15 minutes throttle

def sync_today_files_from_github():
    global LAST_SYNC_ATTEMPT
    
    # Check if we should throttle
    now = time.time()
    if now - LAST_SYNC_ATTEMPT < SYNC_THROTTLE_SECONDS:
        return
        
    LAST_SYNC_ATTEMPT = now
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    currencies = ["EUR", "GBP", "XAU", "NAS", "SPX", "BTC", "ETH", "USDCAD"]
    
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
            req = urllib.request.Request(
                github_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read()
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
                print(f"[Sync] Successfully downloaded and saved {filename} to local data/")
                
                # Copy to MT5
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


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialize SimpleHTTPRequestHandler to serve from BASE_DIR (Dashboard/)
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        # Add CORS headers for developer convenience
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Prevent browser caching of any files/endpoints in dashboard
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/dates':
            self.handle_get_dates(parsed_url.query)
        elif path == '/api/data':
            self.handle_get_data(parsed_url.query)
        elif path == '/api/status':
            self.handle_get_status()
        else:
            # Fallback to serving static files
            super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/update':
            self.handle_post_update()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_dates(self, query_str):
        try:
            sync_today_files_from_github()
        except Exception as se:
            print(f"[Sync] Error running automatic sync: {se}")

        try:
            params = parse_qs(query_str)
            currency = params.get('currency', [None])[0]
            
            if currency:
                curr_upper = currency.upper()
                if curr_upper == "USDCAD":
                    search_pattern = os.path.join(DATA_DIR, "GEX_USDCAD_*.csv")
                else:
                    search_pattern = os.path.join(DATA_DIR, f"GEX_{curr_upper}USD_*.csv")
            else:
                search_pattern = os.path.join(DATA_DIR, "GEX_*_*.csv")
                
            files = glob.glob(search_pattern)
            
            dates = set()
            for file_path in files:
                # Filename format: GEX_CURRENCY_YYYY-MM-DD.csv
                basename = os.path.basename(file_path)
                parts = basename.replace(".csv", "").split("_")
                if len(parts) >= 3:
                    # YYYY-MM-DD is the last part
                    dates.add(parts[-1])
            
            # Sort dates descending (latest first)
            sorted_dates = sorted(list(dates), reverse=True)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"dates": sorted_dates}).encode('utf-8'))
        except Exception as e:
            self.send_error_json(500, f"Error listing dates: {str(e)}")

    def handle_get_data(self, query_str):
        try:
            sync_today_files_from_github()
        except Exception as se:
            print(f"[Sync] Error running automatic sync: {se}")

        try:
            params = parse_qs(query_str)
            currency = params.get('currency', ['GBP'])[0].upper()
            selected_date = params.get('date', [None])[0]

            # If no date, find the latest available date for this currency
            if not selected_date:
                if currency == "USDCAD":
                    search_pattern = os.path.join(DATA_DIR, "GEX_USDCAD_*.csv")
                else:
                    search_pattern = os.path.join(DATA_DIR, f"GEX_{currency}USD_*.csv")
                files = glob.glob(search_pattern)
                if not files:
                    self.send_error_json(404, f"No files found for currency {currency}")
                    return
                # Extract dates and find the latest
                file_dates = []
                for f in files:
                    parts = os.path.basename(f).replace(".csv", "").split("_")
                    if len(parts) >= 3:
                        file_dates.append(parts[-1])
                if not file_dates:
                    self.send_error_json(404, f"Could not extract dates for currency {currency}")
                    return
                selected_date = sorted(file_dates, reverse=True)[0]

            if currency == "USDCAD":
                csv_name = f"GEX_USDCAD_{selected_date}.csv"
            else:
                csv_name = f"GEX_{currency}USD_{selected_date}.csv"
            csv_path = os.path.join(DATA_DIR, csv_name)

            if not os.path.exists(csv_path):
                self.send_error_json(404, f"File {csv_name} not found")
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
                "daily_month": "UNKNOWN"
            }

            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    self.send_error_json(500, "Empty data file")
                    return
                
                # Parse headers
                headers = [h.strip() for h in lines[0].split(',')]
                
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
                except ValueError as ve:
                    self.send_error_json(500, f"Missing required column in GEX CSV: {str(ve)}")
                    return

                # Read rows
                first_row = True
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split(',')]
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

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "metadata": metadata,
                "levels": levels
            }).encode('utf-8'))

        except Exception as e:
            self.send_error_json(500, f"Error reading GEX CSV: {str(e)}")

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
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "mt5_directory": mt5_dir,
                "exists": exists,
                "sync_files_count": len(files),
                "sync_files": sorted(files, reverse=True)[:5] # top 5 files
            }).encode('utf-8'))
        except Exception as e:
            self.send_error_json(500, f"Error getting status: {str(e)}")

    def handle_post_update(self):
        try:
            parent_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
            main_py_path = os.path.join(parent_dir, "main.py")
            
            if not os.path.exists(main_py_path):
                self.send_error_json(404, "main.py not found in parent directory")
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

            success = (process.returncode == 0)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": success,
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }).encode('utf-8'))
            
        except subprocess.TimeoutExpired:
            self.send_error_json(504, "CME Update pipeline timed out (took longer than 120s)")
        except Exception as e:
            self.send_error_json(500, f"Error executing CME update pipeline: {str(e)}")

    def send_error_json(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=DashboardHandler, port=PORT):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Option Levels Dashboard server running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
