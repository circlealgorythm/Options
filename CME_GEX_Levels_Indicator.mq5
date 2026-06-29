//+------------------------------------------------------------------+
//|                                    CME_GEX_Levels_Indicator.mq5  |
//|                                  Copyright 2026, circlealgorythm |
//|                                  https://github.com/circlealgorythm |

//+------------------------------------------------------------------+

#property copyright "Copyright 2026, circlealgorythm"

#property link      "https://github.com/circlealgorythm/Options"

#property version   "1.05"

#property description "Indicator to fetch CME GEX options levels and plot premium boundaries, MDD, AG, and volatility zones."

#property indicator_chart_window

#property indicator_buffers 0

#property indicator_plots 0
//--- Inputs

input group "--- GitHub Configuration ---"

input string   InpGithubUser  = "circlealgorythm"; // GitHub Username

input string   InpGithubRepo  = "Options";         // GitHub Repository Name

input string   InpGithubToken = "";                // GitHub PAT (leave empty if repo is public)

input group "--- Display Settings ---"

input int      InpHistoryDays = 14;                // Days of history to load

input double   InpMinGexFilter = 1000.0;           // Minimum absolute GEX to display (filter noise)

input double   InpMinGexPercent = 15.0;            // Minimum GEX percent of max to display (noise threshold %)

input int      InpMaxVisibleGexLevels = 0;         // Max visible GEX strike rows (0 = auto per asset)

input double   InpMaxStrikeDistancePercent = 0.0;  // Max non-key strike distance from spot/futures % (0 = auto)

input double   InpMaxKeyDistancePercent = 0.0;     // Max key strike distance from spot/futures % (0 = auto)

input int      InpBaseLineWidth = 1;               // Base Line Width (for all lines)

input bool     InpUseDynamicWidth = true;          // Scale GEX line widths dynamically based on volume

input int      InpForwardPoints = 0;               // Forward Point (Manual Shift in points)

input bool     InpAutoSpotAdjust= true;            // Auto-adjust to Spot Price (Overrides Manual)

input color    InpColorCall   = clrMediumSeaGreen; // Positive GEX Color (Support)

input color    InpColorPut    = clrCrimson;        // Negative GEX Color (Resistance)

input color    InpColorGamma  = clrDeepSkyBlue;    // Max Absolute Gamma Color

input int      InpRefreshHours= 4;                 // Refresh rate in hours

input group "--- Market Boundaries (1st Order) ---"

input color    InpColorCallMarket = C'0,0,255';        // Call 1st Order (Market Boundary) Color (Blue)

input color    InpColorPutMarket  = C'255,141,0';      // Put 1st Order (Market Boundary) Color (Orange)

input int      InpWidthMarket     = 5;                 // 1st Order Line Width

input group "--- Absolute Gamma (AG) Lines ---"

input color    InpColorAGLine = C'0,191,255';      // AG Line Color (DeepSkyBlue / Light Blue)

input group "--- Risk Premiums (2nd Order - MDD) ---"

input color    InpColorMDDCall= clrRoyalBlue;      // Call MDD (Breakeven) Color

input color    InpColorMDDPut = clrOrangeRed;      // Put MDD (Breakeven) Color

input int      InpWidthDailyMDD   = 2;             // Daily MDD Line Width (Dash-Dot style)

input group "--- Option Month Settings ---"

input bool     InpDrawMonthLines  = true;              // Draw option month separator lines

input color    InpColorNewMonth   = clrMediumOrchid;   // Option Month Line Color

input int      InpWidthNewMonth   = 2;                 // Option Month Line Width

input ENUM_LINE_STYLE InpStyleNewMonth = STYLE_DASH;   // Option Month Line Style

input group "--- Volatility Zones ---"

input bool     InpDrawZones   = true;              // Draw volatility zones R68/R95

input bool     InpFillZones   = true;              // Fill volatility zones with color (false = draw borders only)

input color    InpColorR68    = C'35,20,20';       // R68 Zone Color (68% probability)

input color    InpColorR95    = C'20,30,20';       // R95 Zone Color (95% probability)

input group "--- Zero Gamma ---"

input color    InpColorZeroGamma = C'255,215,0';       // Zero Gamma Level Color (Gold)

input int      InpWidthZeroGamma = 3;                  // Zero Gamma Line Width

input ENUM_LINE_STYLE InpStyleZeroGamma = STYLE_SOLID; // Zero Gamma Line Style
//--- Global Variables
datetime       g_last_update = 0;
string         g_base_currency = "";
string         g_obj_prefix = "CMEGEX_";

bool           g_show_gex = true;

bool           g_show_ag  = true;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |

//+------------------------------------------------------------------+

int OnInit()
{
   string symbol = Symbol();
   StringToUpper(symbol);
   if(StringFind(symbol, "EUR") >= 0)
      g_base_currency = "EUR";
   else if(StringFind(symbol, "GBP") >= 0)
      g_base_currency = "GBP";
   else if(StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "GOLD") >= 0)
      g_base_currency = "XAU";
   else if(StringFind(symbol, "NAS") >= 0 || StringFind(symbol, "US100") >= 0 || StringFind(symbol, "USTEC") >= 0 || StringFind(symbol, "NQ") >= 0)
      g_base_currency = "NAS";
   else if(StringFind(symbol, "BTC") >= 0)
      g_base_currency = "BTC";
   else if(StringFind(symbol, "CAD") >= 0)
      g_base_currency = "CAD";
   else if(StringFind(symbol, "SPX") >= 0 || StringFind(symbol, "SP500") >= 0 || StringFind(symbol, "US500") >= 0 || StringFind(symbol, "ES") >= 0 || StringFind(symbol, "S&P500") >= 0)
      g_base_currency = "SPX";
   else
   {
      Alert("Symbol ", symbol, " is not supported. Supported: EUR, GBP, XAU/GOLD, NAS100, SPX500, BTCUSD, USDCAD.");
      return(INIT_FAILED);
   }
   Print("CME GEX Indicator initialized for ", g_base_currency, "USD. Loading historical levels...");
   string gv_gex = "CMEGEX_GEX_" + IntegerToString(ChartID());
   string gv_ag  = "CMEGEX_AG_" + IntegerToString(ChartID());
   if(GlobalVariableCheck(gv_gex))
      g_show_gex = (bool)GlobalVariableGet(gv_gex);
   if(GlobalVariableCheck(gv_ag))
      g_show_ag = (bool)GlobalVariableGet(gv_ag);
   CreateButtons();
   EventSetTimer(3600); // Trigger timer event every hour
   bool history_desynced = false;
   string gv_desync = "CMEGEX_Desync_" + IntegerToString(ChartID());
   if(GlobalVariableCheck(gv_desync))
      history_desynced = (GlobalVariableGet(gv_desync) > 0.0);
   UpdateLevels();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |

//+------------------------------------------------------------------+

void OnDeinit(const int reason)
{
   EventKillTimer();
   DeleteButtons();
   if(reason != REASON_CHARTCHANGE)
   {
      CleanUpObjects();
      string gv_gex = "CMEGEX_GEX_" + IntegerToString(ChartID());
      string gv_ag  = "CMEGEX_AG_" + IntegerToString(ChartID());
      string gv_desync = "CMEGEX_Desync_" + IntegerToString(ChartID());
      GlobalVariableDel(gv_gex);
      GlobalVariableDel(gv_ag);
      GlobalVariableDel(gv_desync);
      Print("CME GEX Indicator deinitialized and objects cleaned up.");
   }
}

//+------------------------------------------------------------------+
//| Check if objects exist for current symbol                        |

//+------------------------------------------------------------------+

bool ObjectsExistForCurrentSymbol()
{
   string prefix = g_obj_prefix + g_base_currency + "_";
   int total_objects = ObjectsTotal(0);
   for(int i = 0; i < total_objects; i++)
   {
      string name = ObjectName(0, i);
      if(StringSubstr(name, 0, StringLen(prefix)) == prefix)
      {
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |

//+------------------------------------------------------------------+

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   // Indicators use OnCalculate instead of OnTick. We don't need tick-by-tick updates
   // for drawing historical levels, as the timer handles scheduled updates.
   return(rates_total);
}

//+------------------------------------------------------------------+
//| UI Buttons Creation                                              |

//+------------------------------------------------------------------+

void CreateButtons()
{
   ObjectCreate(0, "Btn_ShowGEX", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_YDISTANCE, 42);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_XSIZE, 54);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_YSIZE, 24);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_CORNER, CORNER_LEFT_LOWER);
   ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_HIDDEN, true);
   ObjectCreate(0, "Btn_ShowAG", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_XDISTANCE, 70);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_YDISTANCE, 42);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_XSIZE, 42);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_YSIZE, 24);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_CORNER, CORNER_LEFT_LOWER);
   ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_HIDDEN, true);
   UpdateToggleButton("Btn_ShowGEX", "GEX", g_show_gex);
   UpdateToggleButton("Btn_ShowAG", "AG", g_show_ag);
   ChartRedraw(0);
}

void UpdateToggleButton(string name, string label, bool enabled)
{
   ObjectSetString(0, name, OBJPROP_TEXT, label);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrBlack);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, enabled ? C'220,242,224' : C'246,220,220');
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, enabled ? C'100,170,110' : C'190,105,105');
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
}

//+------------------------------------------------------------------+
//| UI Buttons Deletion                                              |

//+------------------------------------------------------------------+

void DeleteButtons()
{
   ObjectDelete(0, "Btn_ShowGEX");
   ObjectDelete(0, "Btn_ShowAG");
}

//+------------------------------------------------------------------+
//| Visibility Toggling                                              |

//+------------------------------------------------------------------+

void UpdateVisibility()
{
   int total_objects = ObjectsTotal(0);
   for(int i = 0; i < total_objects; i++)
   {
      string name = ObjectName(0, i);
      if(StringSubstr(name, 0, StringLen(g_obj_prefix)) == g_obj_prefix)
      {
         bool is_ag = (StringFind(name, "_AGL") >= 0);
         bool is_mdd_r_zones = (StringFind(name, "_R68") >= 0 || StringFind(name, "_R95") >= 0 || StringFind(name, "CMD") >= 0 || StringFind(name, "PMD") >= 0 || StringFind(name, "ZeroGamma") >= 0);
         bool is_status = (StringFind(name, "UpdateStatus") >= 0);
         if(is_status)
         {
            ObjectSetInteger(0, name, OBJPROP_TIMEFRAMES, OBJ_ALL_PERIODS);
         }
         else if(is_ag)
         {
            ObjectSetInteger(0, name, OBJPROP_TIMEFRAMES, g_show_ag ? OBJ_ALL_PERIODS : OBJ_NO_PERIODS);
         }
         else if(!is_mdd_r_zones)
         {
            // Apply to all other GEX lines and text labels
            ObjectSetInteger(0, name, OBJPROP_TIMEFRAMES, g_show_gex ? OBJ_ALL_PERIODS : OBJ_NO_PERIODS);
         }
      }
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Chart Event Handler                                              |

//+------------------------------------------------------------------+

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      string gv_gex = "CMEGEX_GEX_" + IntegerToString(ChartID());
      string gv_ag  = "CMEGEX_AG_" + IntegerToString(ChartID());
      if(sparam == "Btn_ShowGEX")
      {
         g_show_gex = !g_show_gex;
         GlobalVariableSet(gv_gex, g_show_gex);
         UpdateToggleButton("Btn_ShowGEX", "GEX", g_show_gex);
         UpdateVisibility();
         ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_STATE, false); // Reset button state
      }
      else if(sparam == "Btn_ShowAG")
      {
         g_show_ag = !g_show_ag;
         GlobalVariableSet(gv_ag, g_show_ag);
         UpdateToggleButton("Btn_ShowAG", "AG", g_show_ag);
         UpdateVisibility();
         ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_STATE, false); // Reset button state
      }
   }
}

//+------------------------------------------------------------------+
//| Timer function                                                   |

//+------------------------------------------------------------------+

void OnTimer()
{
   datetime now = TimeCurrent();
   if(now - g_last_update >= InpRefreshHours * 3600)
   {
      Print("Timer triggered update...");
      UpdateLevels();
   }
}

//+------------------------------------------------------------------+
//| Fetch and draw levels                                            |

//+------------------------------------------------------------------+

void UpdateLevels()
{
   CleanUpObjects();
   GlobalVariableSet("CMEGEX_Desync_" + IntegerToString(ChartID()), 0.0);
   Print("Fetching option levels...");
   g_last_update = TimeCurrent();
   datetime current_time = TimeCurrent();
   int success_count = 0;
   MqlDateTime current_dt;
   TimeToStruct(current_time, current_dt);
   string today_str = StringFormat("%04d-%02d-%02d", current_dt.year, current_dt.mon, current_dt.day);
   bool today_loaded = false;
   string latest_available_date = "";
   string prev_month = "";
   datetime prev_date_time = 0;
   for(int i = 0; i < InpHistoryDays; i++)
   {
      datetime target_date = current_time - i * 86400;
      MqlDateTime dt;
      TimeToStruct(target_date, dt);
      if(dt.day_of_week == 0 || dt.day_of_week == 6)
         continue;
      string date_str = StringFormat("%04d-%02d-%02d", dt.year, dt.mon, dt.day);
      string current_month = "";
      if(FetchAndParseDate(date_str, current_month))
      {
         success_count++;
         if(date_str == today_str)
            today_loaded = true;
         if(latest_available_date == "")
            latest_available_date = date_str;
         datetime time_start = StringToTime(date_str + " 00:00:00");
         // If we detect a month transition between chronologically adjacent days (scanned backward)
         if(InpDrawMonthLines && prev_month != "" && current_month != "" && current_month != "UNKNOWN" && prev_month != "UNKNOWN" && current_month != prev_month)
         {
            // Transition happened going back in time. Chronologically, prev_date_time is the first day of the new month (prev_month).
            string line_name = g_obj_prefix + "Month_Separator_" + TimeToString(prev_date_time, TIME_DATE);
            ObjectDelete(0, line_name);
            if(ObjectCreate(0, line_name, OBJ_VLINE, 0, prev_date_time, 0))
            {
               ObjectSetInteger(0, line_name, OBJPROP_COLOR, InpColorNewMonth);
               ObjectSetInteger(0, line_name, OBJPROP_WIDTH, InpWidthNewMonth);
               ObjectSetInteger(0, line_name, OBJPROP_STYLE, InpStyleNewMonth);
               ObjectSetInteger(0, line_name, OBJPROP_SELECTABLE, false);
               ObjectSetInteger(0, line_name, OBJPROP_HIDDEN, true);
               ObjectSetInteger(0, line_name, OBJPROP_BACK, true);
               ObjectSetString(0, line_name, OBJPROP_TOOLTIP, "New Option Month: " + prev_month);
               // Draw text label on the chart for the new option month
               string label_name = line_name + "_TXT";
               ObjectDelete(0, label_name);
               if(ObjectCreate(0, label_name, OBJ_TEXT, 0, prev_date_time, SymbolInfoDouble(Symbol(), SYMBOL_ASK)))
               {
                  ObjectSetString(0, label_name, OBJPROP_TEXT, " " + prev_month);
                  ObjectSetInteger(0, label_name, OBJPROP_COLOR, InpColorNewMonth);
                  ObjectSetInteger(0, label_name, OBJPROP_FONTSIZE, 9);
                  ObjectSetString(0, label_name, OBJPROP_FONT, "Consolas");
                  ObjectSetInteger(0, label_name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
                  ObjectSetInteger(0, label_name, OBJPROP_SELECTABLE, false);
                  ObjectSetInteger(0, label_name, OBJPROP_HIDDEN, true);
               }
            }
         }
         if(current_month != "" && current_month != "UNKNOWN")
         {
            prev_month = current_month;
            prev_date_time = time_start;
         }
      }
   }
   // Fallback: if today's GEX data is missing, load and plot the latest available GEX data on today's chart column
   bool fallback_loaded = false;
   if(!today_loaded && latest_available_date != "")
   {
      string local_file_path = "GEX\\";
      if(g_base_currency == "XAU")
         local_file_path += "XAU\\GEX_" + g_base_currency + "USD_" + latest_available_date + ".csv";
      else if(g_base_currency == "NAS" || g_base_currency == "SPX")
         local_file_path += "NAS100\\GEX_" + g_base_currency + "USD_" + latest_available_date + ".csv";
      else if(g_base_currency == "BTC" || g_base_currency == "ETH")
         local_file_path += "Crypto\\GEX_" + g_base_currency + "USD_" + latest_available_date + ".csv";
      else if(g_base_currency == "CAD")
         local_file_path += "USDCAD\\GEX_USDCAD_" + latest_available_date + ".csv";
      else
         local_file_path += "GEX_" + g_base_currency + "USD_" + latest_available_date + ".csv";
      string dummy_month = "";
      if(TryParseLocalCSV(local_file_path, today_str, dummy_month, "Fallback loaded from latest " + latest_available_date))
      {
         fallback_loaded = true;
         Print("Successfully loaded fallback levels for today (", today_str, ") from latest available file (", latest_available_date, ")");
      }
   }
   UpdateVisibility();
   DrawUpdateStatus(today_str, today_loaded, fallback_loaded, latest_available_date, success_count);
   ChartRedraw(0);
   Print("Levels update completed. Successfully loaded data for ", success_count, " days.");
}

//+------------------------------------------------------------------+
//| Draw data freshness status                                       |

//+------------------------------------------------------------------+

void DrawUpdateStatus(string today_str, bool today_loaded, bool fallback_loaded, string latest_date, int success_count)
{
   string name = g_obj_prefix + "UpdateStatus";
   ObjectDelete(0, name);
   if(ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0))
   {
      string status = "";
      color status_color = clrCrimson;
      if(today_loaded)
      {
         status = "GEX today OK: " + today_str;
         status_color = clrSeaGreen;
      }
      else if(fallback_loaded)
      {
         status = StringFormat("GEX today OK (Fallback %s): %s", latest_date, today_str);
         status_color = clrGoldenrod; // Warm gold color for fallback
      }
      else
      {
         status = "GEX today MISSING: " + today_str;
         status_color = clrCrimson;
      }
      status += StringFormat(" | loaded days: %d", success_count);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 56);
      ObjectSetString(0, name, OBJPROP_TEXT, status);
      ObjectSetInteger(0, name, OBJPROP_COLOR, status_color);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   }
}

//+------------------------------------------------------------------+
//| Download and parse CSV file for a specific date                  |

//+------------------------------------------------------------------+

bool TryParseLocalCSV(string local_file_path, string date_str, string &out_month, string reason)
{
   ResetLastError();
   int file_handle = FileOpen(local_file_path, FILE_READ|FILE_TXT|FILE_ANSI);
   if(file_handle == INVALID_HANDLE)
      return false;
   string csv_data = "";
   while(!FileIsEnding(file_handle))
   {
      csv_data += FileReadString(file_handle) + "\n";
   }
   FileClose(file_handle);
   Print(reason, ": Files\\", local_file_path);
   return ParseCSV(csv_data, date_str, out_month);
}

bool FetchAndParseDate(string date_str, string &out_month)
{
   out_month = "UNKNOWN";
   MqlDateTime now_dt;
   TimeToStruct(TimeCurrent(), now_dt);
   string today_str = StringFormat("%04d-%02d-%02d", now_dt.year, now_dt.mon, now_dt.day);
   bool prefer_remote = (date_str == today_str);
   // For today's file, prefer the remote CSV so the 08:00 MSK automation is picked up.
   // Older dates are loaded from the local MT5 cache first.
   string local_file_path = "GEX\\";
   if(g_base_currency == "XAU")
      local_file_path += "XAU\\GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   else if(g_base_currency == "NAS" || g_base_currency == "SPX")
      local_file_path += "NAS100\\GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   else if(g_base_currency == "BTC" || g_base_currency == "ETH")
      local_file_path += "Crypto\\GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   else if(g_base_currency == "CAD")
      local_file_path += "USDCAD\\GEX_USDCAD_" + date_str + ".csv";
   else
      local_file_path += "GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   if(!prefer_remote && FileIsExist(local_file_path))
   {
      if(TryParseLocalCSV(local_file_path, date_str, out_month, "Loaded levels locally from"))
         return true;
      Print("Local CSV has an unsupported or stale schema, trying WebRequest fallback: Files\\", local_file_path);
      ResetLastError();
      FileDelete(local_file_path);
   }
   // Note: WebRequest is restricted inside MT5 Indicators on the UI thread.
   // We skip remote fetch in Indicators to prevent blocking the GUI thread (error 4014).
   // Data is expected to be generated locally by Python (main.py) directly into Files/GEX/.
   if(MQLInfoInteger(MQL_PROGRAM_TYPE) == PROGRAM_INDICATOR)
   {
      // Fallback directly to local file for Indicator mode
      return TryParseLocalCSV(local_file_path, date_str, out_month, "Indicator Mode - Loaded locally from");
   }
   // WebRequest logic kept for reference/compilation consistency, but bypassed in indicator mode.
   string url;
   string headers = "User-Agent: MetaTrader5\r\n";
   string filename = "GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   if(g_base_currency == "CAD")
      filename = "GEX_USDCAD_" + date_str + ".csv";
   if(StringLen(InpGithubToken) > 0)
   {
      url = "https://api.github.com/repos/" + InpGithubUser + "/" + InpGithubRepo + 
            "/contents/data/" + filename;
      headers += "Authorization: Bearer " + InpGithubToken + "\r\n";
      headers += "Accept: application/vnd.github.v3.raw\r\n";
      headers += "X-GitHub-Api-Version: 2022-11-28\r\n";
   }
   else
   {
      url = "https://raw.githubusercontent.com/" + InpGithubUser + "/" + InpGithubRepo + 
            "/main/data/" + filename;
   }
   char post[], result_data[];
   string result_headers;
   int timeout = 5000;
   ResetLastError();
   int res = WebRequest("GET", url, headers, timeout, post, result_data, result_headers);
   if(res == 200)
   {
      string csv_data = CharArrayToString(result_data, 0, WHOLE_ARRAY, CP_UTF8);
      if(!ParseCSV(csv_data, date_str, out_month))
      {
         Print("Downloaded CSV has an unsupported schema or no drawable rows: ", date_str);
         if(prefer_remote && TryParseLocalCSV(local_file_path, date_str, out_month, "Downloaded CSV failed, using local fallback"))
            return true;
         return false;
      }
      int write_handle = FileOpen(local_file_path, FILE_WRITE|FILE_TXT|FILE_ANSI);
      if(write_handle != INVALID_HANDLE)
      {
         FileWriteString(write_handle, csv_data);
         FileClose(write_handle);
         Print("Saved downloaded levels locally to: Files\\", local_file_path);
      }
      return true;
   }
   else if(res == 404)
   {
      if(prefer_remote && TryParseLocalCSV(local_file_path, date_str, out_month, "Remote CSV not found, using local fallback"))
         return true;
      return false;
   }
   else
   {
      int err = GetLastError();
      if(prefer_remote && TryParseLocalCSV(local_file_path, date_str, out_month, "WebRequest failed, using local fallback"))
         return true;
      return false;
   }
}

//+------------------------------------------------------------------+
//| Struct for parsed rows                                           |

//+------------------------------------------------------------------+

struct OptionRow {
   double strike;
   double total_gex;
   double total_abs_gamma;
   double daily_call_settle;
   double daily_call_oi;
   double daily_put_settle;
   double daily_put_oi;
   double global_call_oi;
   double global_put_oi;
};

//+------------------------------------------------------------------+
//| Format volume numbers to K/M format                              |

//+------------------------------------------------------------------+
string FormatVolume(double value)
{
   double abs_val = MathAbs(value);
   string sign = (value < 0) ? "-" : "";
   if(abs_val >= 1000000.0)
      return StringFormat("%s%.2fM", sign, abs_val / 1000000.0);
   else if(abs_val >= 1000.0)
      return StringFormat("%s%.0fk", sign, abs_val / 1000.0);
   else if(abs_val > 0.0 && abs_val < 1.0)
      return StringFormat("%s%.4f", sign, abs_val);
   else if(abs_val > 0.0 && abs_val < 10.0)
      return StringFormat("%s%.2f", sign, abs_val);
   else
      return StringFormat("%s%.0f", sign, abs_val);
}

//+------------------------------------------------------------------+
//| Asset-specific display pruning defaults                          |

//+------------------------------------------------------------------+

int GetMaxVisibleGexLevels()
{
   if(InpMaxVisibleGexLevels > 0)
      return InpMaxVisibleGexLevels;
   if(g_base_currency == "NAS" || g_base_currency == "SPX")
      return 28;
   if(g_base_currency == "XAU")
      return 32;
   return 24;
}

double GetMaxStrikeDistancePercent()
{
   if(InpMaxStrikeDistancePercent > 0.0)
      return InpMaxStrikeDistancePercent;
   if(g_base_currency == "BTC")
      return 25.0;
   if(g_base_currency == "XAU")
      return 12.0;
   if(g_base_currency == "NAS" || g_base_currency == "SPX")
      return 8.0;
   return 6.0;
}

double GetMaxKeyDistancePercent()
{
   if(InpMaxKeyDistancePercent > 0.0)
      return InpMaxKeyDistancePercent;
   if(g_base_currency == "BTC")
      return 35.0;
   if(g_base_currency == "XAU")
      return 18.0;
   if(g_base_currency == "NAS" || g_base_currency == "SPX")
      return 12.0;
   return 12.0;
}

//+------------------------------------------------------------------+
//| Blend a tint color into the current chart background             |

//+------------------------------------------------------------------+
color BlendWithChartBackground(color tint, int tint_pct)
{
   long bg_value = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   int pct = MathMax(0, MathMin(100, tint_pct));
   int tint_r = (int)(tint & 0xFF);
   int tint_g = (int)((tint >> 8) & 0xFF);
   int tint_b = (int)((tint >> 16) & 0xFF);
   int bg_r = (int)(bg_value & 0xFF);
   int bg_g = (int)((bg_value >> 8) & 0xFF);
   int bg_b = (int)((bg_value >> 16) & 0xFF);
   int r = (bg_r * (100 - pct) + tint_r * pct) / 100;
   int g = (bg_g * (100 - pct) + tint_g * pct) / 100;
   int b = (bg_b * (100 - pct) + tint_b * pct) / 100;
   return (color)(r | (g << 8) | (b << 16));
}

//+------------------------------------------------------------------+
//| Get fixed daily spot reference with retry                        |

//+------------------------------------------------------------------+

double GetDailySpotReferenceWithRetry(string symbol, datetime time_val, bool is_today, int &out_shift)
{
   out_shift = -1;
   double spot_reference = 0.0;
   for(int r = 0; r < 20; r++)
   {
      ResetLastError();
      int shift = iBarShift(symbol, PERIOD_D1, time_val);
      if(shift >= 0)
      {
         spot_reference = iOpen(symbol, PERIOD_D1, shift);
         if(spot_reference > 0.0)
         {
            out_shift = shift;
            return spot_reference;
         }
      }
      // Request daily history loading for this specific date, to pull the bar into terminal cache
      datetime temp[];
      CopyTime(symbol, PERIOD_D1, time_val, 1, temp);
      Sleep(20);
   }
   // Fallback using chart timeframe (_Period) if D1 history is not synchronized.
   // This is robust for both historical days and today.
   if(spot_reference <= 0.0)
   {
      int fallback_shift = iBarShift(symbol, _Period, time_val);
      if(fallback_shift >= 0)
      {
         spot_reference = iOpen(symbol, _Period, fallback_shift);
         if(spot_reference > 0.0)
         {
            out_shift = fallback_shift;
         }
      }
      // Ultimate fallback to Bid for today
      if(spot_reference <= 0.0 && is_today)
      {
         spot_reference = SymbolInfoDouble(symbol, SYMBOL_BID);
         GlobalVariableSet("CMEGEX_Desync_" + IntegerToString(ChartID()), 1.0);
      }
      if(spot_reference > 0.0)
      {
         PrintFormat("Warning: D1 history for %s (%s) not synchronized after retries. Using fallback spot reference %.5f.", symbol, TimeToString(time_val, TIME_DATE), spot_reference);
      }
      else
      {
         PrintFormat("Error: Failed to find any spot reference for %s on %s.", symbol, TimeToString(time_val, TIME_DATE));
      }
   }
   return spot_reference;
}

//+------------------------------------------------------------------+
//| Parse CSV contents and draw levels                               |

//+------------------------------------------------------------------+

bool ParseCSV(const string &csv_data, string date_str, string &out_global_month)
{
   out_global_month = "UNKNOWN";
   string clean_csv = csv_data;
   StringReplace(clean_csv, "\r", "");
   string lines[];
   int total_lines = StringSplit(clean_csv, '\n', lines);
   PrintFormat("ParseCSV Debug: date_str=%s | csv_data length=%d | total_lines=%d", date_str, StringLen(csv_data), total_lines);
   if(total_lines <= 1)
   {
      Print("ParseCSV Debug Error: total_lines <= 1, aborting.");
      return false;
   }
   if(StringFind(lines[0], "Daily_Call_Settle") < 0 || StringFind(lines[0], "Global_Call_OI") < 0)
   {
      Print("Unsupported CSV schema. Expected Daily MDD and Global OI columns, got: ", lines[0]);
      return false;
   }
   // Find maximum values in the CSV data first (1st pass) to adapt the noise filter and pre-identify key strikes
   double file_max_abs_gex = 0.0;
   double gex_array[];
   int gex_count = 0;
   double max_daily_call_oi = -1.0;
   double max_daily_call_oi_strike = 0.0;
   double max_daily_put_oi = -1.0;
   double max_daily_put_oi_strike = 0.0;
   double max_global_call_oi = -1.0;
   double max_global_call_oi_strike = 0.0;
   double max_global_put_oi = -1.0;
   double max_global_put_oi_strike = 0.0;
   double max_abs_gamma = 0.0;
   double max_gamma_strike = 0.0;
   for(int i = 1; i < total_lines; i++)
   {
      string line = lines[i];
      StringTrimLeft(line);
      StringTrimRight(line);
      if(StringLen(line) == 0)
         continue;
      string columns[];
      int total_cols = StringSplit(line, ',', columns);
      if(total_cols < 10) // Must have at least strike, gex, abs_gamma, d_call_settle, d_call_oi, d_put_settle, d_put_oi, g_call_oi, g_put_oi
         continue;
      double strike = StringToDouble(columns[1]);
      double total_gex = StringToDouble(columns[2]);
      double abs_gex = MathAbs(total_gex);
      if(abs_gex > file_max_abs_gex)
         file_max_abs_gex = abs_gex;
      double total_abs_gamma = StringToDouble(columns[3]);
      if(total_abs_gamma > max_abs_gamma)
      {
         max_abs_gamma = total_abs_gamma;
         max_gamma_strike = strike;
      }
      if(abs_gex > 0.0)
      {
         ArrayResize(gex_array, gex_count + 1);
         gex_array[gex_count] = abs_gex;
         gex_count++;
      }
      double d_call_settle = StringToDouble(columns[4]);
      double d_call_oi = StringToDouble(columns[5]);
      double d_put_settle = StringToDouble(columns[6]);
      double d_put_oi = StringToDouble(columns[7]);
      double g_call_oi = StringToDouble(columns[8]);
      double g_put_oi = StringToDouble(columns[9]);
      if(d_call_oi > max_daily_call_oi && d_call_settle > 0.0)
      {
         max_daily_call_oi = d_call_oi;
         max_daily_call_oi_strike = strike;
      }
      if(d_put_oi > max_daily_put_oi && d_put_settle > 0.0)
      {
         max_daily_put_oi = d_put_oi;
         max_daily_put_oi_strike = strike;
      }
      if(g_call_oi > max_global_call_oi)
      {
         max_global_call_oi = g_call_oi;
         max_global_call_oi_strike = strike;
      }
      if(g_put_oi > max_global_put_oi)
      {
         max_global_put_oi = g_put_oi;
         max_global_put_oi_strike = strike;
      }
   }
   double filter_reference_abs_gex = file_max_abs_gex;
   if(gex_count >= 20)
   {
      ArraySort(gex_array);
      int idx = (int)MathFloor((gex_count - 1) * 0.99); // ignore single-strike outliers
      if(idx < 0) idx = 0;
      if(idx >= gex_count) idx = gex_count - 1;
      if(gex_array[idx] > 0.0)
         filter_reference_abs_gex = gex_array[idx];
   }
   double active_filter = InpMinGexFilter;
   if(InpMinGexFilter <= 0.0 || file_max_abs_gex <= InpMinGexFilter)
   {
      active_filter = filter_reference_abs_gex * (InpMinGexPercent / 100.0); // relative % of robust max GEX
      PrintFormat("CME GEX: file_max_abs_gex (%.4f), filter_reference_abs_gex (%.4f), InpMinGexFilter (%.4f). Using relative noise filter (%.1f%%): %.6f", 
                  file_max_abs_gex, filter_reference_abs_gex, InpMinGexFilter, InpMinGexPercent, active_filter);
   }
   else
   {
      PrintFormat("CME GEX: Using absolute noise filter: %.6f", active_filter);
   }
   double max_abs_gex = 0.0;
   double r68_high = 0.0;
   double r68_low = 0.0;
   double r95_high = 0.0;
   double r95_low = 0.0;
   double futures_spot = 0.0;
   double gamma_flip = 0.0;
   OptionRow rows[];
   if(ArrayResize(rows, total_lines) == -1)
   {
      Print("Error: Failed to allocate memory for CSV parsing.");
      return false;
   }
   int valid_rows = 0;
   for(int i = 1; i < total_lines; i++)
   {
      string line = lines[i];
      StringTrimLeft(line);
      StringTrimRight(line);
      if(StringLen(line) == 0)
         continue;
      string columns[];
      int total_cols = StringSplit(line, ',', columns);
      if(total_cols < 10)
         continue;
      double strike = StringToDouble(columns[1]);
      double total_gex = StringToDouble(columns[2]);
      double total_abs_gamma = StringToDouble(columns[3]);
      double d_call_settle = StringToDouble(columns[4]);
      double d_call_oi = StringToDouble(columns[5]);
      double d_put_settle = StringToDouble(columns[6]);
      double d_put_oi = StringToDouble(columns[7]);
      double g_call_oi = StringToDouble(columns[8]);
      double g_put_oi = StringToDouble(columns[9]);
      if(total_cols >= 14 && r68_high == 0.0)
      {
         r68_high = StringToDouble(columns[10]);
         r68_low = StringToDouble(columns[11]);
         r95_high = StringToDouble(columns[12]);
         r95_low = StringToDouble(columns[13]);
         if(total_cols >= 16)
         {
            out_global_month = columns[14];
         }
         if(total_cols >= 17)
         {
            futures_spot = StringToDouble(columns[16]);
         }
         if(total_cols >= 18)
         {
            gamma_flip = StringToDouble(columns[17]);
         }
      }
      // Check if this is a key level that must always be shown
      bool is_key_strike = (strike == max_daily_call_oi_strike && max_daily_call_oi > 0.0) ||
                           (strike == max_daily_put_oi_strike && max_daily_put_oi > 0.0) ||
                           (strike == max_global_call_oi_strike && max_global_call_oi > 0.0) ||
                           (strike == max_global_put_oi_strike && max_global_put_oi > 0.0) ||
                           (strike == max_gamma_strike && max_abs_gamma > 0.0);
      if(MathAbs(total_gex) >= active_filter || is_key_strike)
      {
         rows[valid_rows].strike = strike;
         rows[valid_rows].total_gex = total_gex;
         rows[valid_rows].total_abs_gamma = total_abs_gamma;
         rows[valid_rows].daily_call_settle = d_call_settle;
         rows[valid_rows].daily_call_oi = d_call_oi;
         rows[valid_rows].daily_put_settle = d_put_settle;
         rows[valid_rows].daily_put_oi = d_put_oi;
         rows[valid_rows].global_call_oi = g_call_oi;
         rows[valid_rows].global_put_oi = g_put_oi;
         double abs_gex = MathAbs(total_gex);
         if(abs_gex > max_abs_gex)
            max_abs_gex = abs_gex;
         valid_rows++;
      }
   }
   PrintFormat("ParseCSV Debug: finished loop, valid_rows count = %d", valid_rows);
   if(valid_rows == 0)
   {
      Print("ParseCSV Debug: valid_rows is 0, aborting drawing.");
      return false;
   }
   if(max_daily_call_oi <= 0.0 || max_daily_put_oi <= 0.0)
   {
      PrintFormat("CSV is missing Daily MDD rows for %s. DailyCallOI=%.2f, DailyPutOI=%.2f",
                  date_str, max_daily_call_oi, max_daily_put_oi);
      return false;
   }
   datetime time_start = StringToTime(date_str + " 00:00:00");
   datetime time_end = StringToTime(date_str + " 23:59:59");
   double fw_offset = InpForwardPoints * Point();
   if(InpAutoSpotAdjust && futures_spot > 0.0)
   {
      int shift = -1;
      MqlDateTime now_dt;
      TimeToStruct(TimeCurrent(), now_dt);
      string today_str = StringFormat("%04d-%02d-%02d", now_dt.year, now_dt.mon, now_dt.day);
      bool is_today = (date_str == today_str);
      double spot_price = GetDailySpotReferenceWithRetry(Symbol(), time_start, is_today, shift);
      if(spot_price > 0.0)
      {
         fw_offset = spot_price - futures_spot;
      }
      else
      {
         PrintFormat("Warning: Failed to calculate fw_offset for %s. shift=%d, spot_price=%.5f, futures_spot=%.5f. Using default fw_offset = %.5f", 
                     date_str, shift, spot_price, futures_spot, fw_offset);
      }
   }
   bool draw_rows[];
   ArrayResize(draw_rows, valid_rows);
   for(int i = 0; i < valid_rows; i++)
      draw_rows[i] = false;
   int max_visible_rows = GetMaxVisibleGexLevels();
   double max_distance_pct = GetMaxStrikeDistancePercent();
   double max_key_distance_pct = GetMaxKeyDistancePercent();
   double reference_spot = futures_spot;
   if(reference_spot <= 0.0)
      reference_spot = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   int visible_rows = 0;
   if(reference_spot > 0.0 && max_visible_rows > 0)
   {
      for(int i = 0; i < valid_rows; i++)
      {
         double strike = rows[i].strike;
         double distance_pct = MathAbs(strike - reference_spot) / reference_spot * 100.0;
         bool is_global_call = (strike == max_global_call_oi_strike && max_global_call_oi > 0);
         bool is_global_put = (strike == max_global_put_oi_strike && max_global_put_oi > 0);
         bool is_daily_call = (strike == max_daily_call_oi_strike && max_daily_call_oi > 0);
         bool is_daily_put = (strike == max_daily_put_oi_strike && max_daily_put_oi > 0);
         bool is_max_ag = (strike == max_gamma_strike && max_abs_gamma > 0);
         // Daily MDD anchors are selected near spot in the Python pipeline, so keep them.
         // Other key levels are useful only while they remain reasonably close to the traded area.
         if(is_daily_call || is_daily_put || ((is_global_call || is_global_put || is_max_ag) && distance_pct <= max_key_distance_pct))
         {
            draw_rows[i] = true;
            visible_rows++;
         }
      }
      while(visible_rows < max_visible_rows)
      {
         int best_idx = -1;
         double best_abs_gex = -1.0;
         for(int i = 0; i < valid_rows; i++)
         {
            if(draw_rows[i])
               continue;
            double strike = rows[i].strike;
            double distance_pct = MathAbs(strike - reference_spot) / reference_spot * 100.0;
            if(distance_pct > max_distance_pct)
               continue;
            double abs_gex = MathAbs(rows[i].total_gex);
            if(abs_gex > best_abs_gex)
            {
               best_abs_gex = abs_gex;
               best_idx = i;
            }
         }
         if(best_idx < 0)
            break;
         draw_rows[best_idx] = true;
         visible_rows++;
      }
   }
   else
   {
      for(int i = 0; i < valid_rows; i++)
      {
         draw_rows[i] = true;
         visible_rows++;
      }
   }
   double label_max_abs_gex = filter_reference_abs_gex;
   if(label_max_abs_gex <= 0.0)
      label_max_abs_gex = max_abs_gex;
   double label_max_abs_gamma = max_abs_gamma;
   double display_max_abs_gex = 0.0;
   double display_max_abs_gamma = 0.0;
   for(int i = 0; i < valid_rows; i++)
   {
      if(!draw_rows[i])
         continue;
      display_max_abs_gex = MathMax(display_max_abs_gex, MathAbs(rows[i].total_gex));
      display_max_abs_gamma = MathMax(display_max_abs_gamma, rows[i].total_abs_gamma);
   }
   if(display_max_abs_gex > 0.0)
      max_abs_gex = display_max_abs_gex;
   if(display_max_abs_gamma > 0.0)
      max_abs_gamma = display_max_abs_gamma;
   PrintFormat("CME GEX display pruning %s %s: drawable rows %d -> %d | max rows=%d | distance %.1f%% | key distance %.1f%%",
               g_base_currency, date_str, valid_rows, visible_rows, max_visible_rows, max_distance_pct, max_key_distance_pct);
   if(InpDrawZones && r68_high > 0.0 && r68_low > 0.0)
   {
      double chart_r95_high = r95_high + fw_offset;
      double chart_r95_low = r95_low + fw_offset;
      double chart_r68_high = r68_high + fw_offset;
      double chart_r68_low = r68_low + fw_offset;
      color zone_r95_color = InpColorR95;
      color zone_r68_color = InpColorR68;
      string r95_name = StringFormat("%s%s_%s_R95", g_obj_prefix, g_base_currency, date_str);
      string r95_name_upper = StringFormat("%s%s_%s_R95_U", g_obj_prefix, g_base_currency, date_str);
      string r95_name_lower = StringFormat("%s%s_%s_R95_L", g_obj_prefix, g_base_currency, date_str);
      if(InpFillZones)
      {
         ObjectDelete(0, r95_name);
         ObjectDelete(0, r95_name_upper);
         if(ObjectCreate(0, r95_name_upper, OBJ_RECTANGLE, 0, time_start, chart_r95_high, time_end, chart_r68_high))
         {
            ObjectSetInteger(0, r95_name_upper, OBJPROP_COLOR, zone_r95_color);
            ObjectSetInteger(0, r95_name_upper, OBJPROP_FILL, true);
            ObjectSetInteger(0, r95_name_upper, OBJPROP_BACK, true);
            ObjectSetInteger(0, r95_name_upper, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, r95_name_upper, OBJPROP_HIDDEN, true);
            ObjectSetString(0, r95_name_upper, OBJPROP_TOOLTIP,
                            StringFormat("Date: %s | R95 Upper Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                         date_str, chart_r68_high, chart_r95_high, r68_high, r95_high));
         }
         ObjectDelete(0, r95_name_lower);
         if(ObjectCreate(0, r95_name_lower, OBJ_RECTANGLE, 0, time_start, chart_r68_low, time_end, chart_r95_low))
         {
            ObjectSetInteger(0, r95_name_lower, OBJPROP_COLOR, zone_r95_color);
            ObjectSetInteger(0, r95_name_lower, OBJPROP_FILL, true);
            ObjectSetInteger(0, r95_name_lower, OBJPROP_BACK, true);
            ObjectSetInteger(0, r95_name_lower, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, r95_name_lower, OBJPROP_HIDDEN, true);
            ObjectSetString(0, r95_name_lower, OBJPROP_TOOLTIP,
                            StringFormat("Date: %s | R95 Lower Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                         date_str, chart_r95_low, chart_r68_low, r95_low, r68_low));
         }
      }
      else
      {
         ObjectDelete(0, r95_name_upper);
         ObjectDelete(0, r95_name_lower);
         ObjectDelete(0, r95_name);
         if(ObjectCreate(0, r95_name, OBJ_RECTANGLE, 0, time_start, chart_r95_high, time_end, chart_r95_low))
         {
            ObjectSetInteger(0, r95_name, OBJPROP_COLOR, zone_r95_color);
            ObjectSetInteger(0, r95_name, OBJPROP_FILL, false);
            ObjectSetInteger(0, r95_name, OBJPROP_BACK, true);
            ObjectSetInteger(0, r95_name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, r95_name, OBJPROP_HIDDEN, true);
            ObjectSetString(0, r95_name, OBJPROP_TOOLTIP,
                            StringFormat("Date: %s | R95 Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                         date_str, chart_r95_low, chart_r95_high, r95_low, r95_high));
         }
      }
      string r68_name = StringFormat("%s%s_%s_R68", g_obj_prefix, g_base_currency, date_str);
      ObjectDelete(0, r68_name);
      if(ObjectCreate(0, r68_name, OBJ_RECTANGLE, 0, time_start, chart_r68_high, time_end, chart_r68_low))
      {
         ObjectSetInteger(0, r68_name, OBJPROP_COLOR, zone_r68_color);
         ObjectSetInteger(0, r68_name, OBJPROP_FILL, InpFillZones);
         ObjectSetInteger(0, r68_name, OBJPROP_BACK, true);
         ObjectSetInteger(0, r68_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, r68_name, OBJPROP_HIDDEN, true);
         ObjectSetString(0, r68_name, OBJPROP_TOOLTIP,
                         StringFormat("Date: %s | R68 Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                      date_str, chart_r68_low, chart_r68_high, r68_low, r68_high));
      }
   }
   // Draw Zero Gamma level
   if(gamma_flip > 0.0)
   {
      double chart_gamma_flip = gamma_flip + fw_offset;
      string flip_name = StringFormat("%s%s_%s_ZeroGamma", g_obj_prefix, g_base_currency, date_str);
      ObjectDelete(0, flip_name);
      if(ObjectCreate(0, flip_name, OBJ_TREND, 0, time_start, chart_gamma_flip, time_end, chart_gamma_flip))
      {
         ObjectSetInteger(0, flip_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, flip_name, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, flip_name, OBJPROP_COLOR, InpColorZeroGamma);
         ObjectSetInteger(0, flip_name, OBJPROP_WIDTH, InpWidthZeroGamma);
         ObjectSetInteger(0, flip_name, OBJPROP_STYLE, InpStyleZeroGamma);
         ObjectSetInteger(0, flip_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, flip_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, flip_name, OBJPROP_BACK, false);
         ObjectSetString(0, flip_name, OBJPROP_TOOLTIP, 
                         StringFormat("Date: %s | Zero Gamma level chart/spot: %.5f | futures: %.5f", 
                                      date_str, chart_gamma_flip, gamma_flip));
         // Text label next to the line
         string flip_txt = flip_name + "_TXT";
         ObjectDelete(0, flip_txt);
         datetime flip_txt_time = time_start + 3600;
         if(ObjectCreate(0, flip_txt, OBJ_TEXT, 0, flip_txt_time, chart_gamma_flip))
         {
            ObjectSetString(0, flip_txt, OBJPROP_TEXT, "Zero Gamma");
            ObjectSetInteger(0, flip_txt, OBJPROP_COLOR, InpColorZeroGamma);
            ObjectSetInteger(0, flip_txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, flip_txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, flip_txt, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
            ObjectSetInteger(0, flip_txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, flip_txt, OBJPROP_HIDDEN, true);
         }
      }
   }
   datetime label_time = time_start + 3600;
   for(int i = 0; i < valid_rows; i++)
   {
      if(!draw_rows[i])
         continue;
      double strike = rows[i].strike;
      double gex = rows[i].total_gex;
      double ag = rows[i].total_abs_gamma;
      double chart_price = strike + fw_offset;
      color line_color = (gex >= 0) ? InpColorCall : InpColorPut;
      int line_width = InpBaseLineWidth;
      int line_style = STYLE_SOLID;
      double gex_ratio = (max_abs_gex > 0) ? (MathAbs(gex) / max_abs_gex) : 1.0;
      double ag_ratio = (max_abs_gamma > 0) ? (ag / max_abs_gamma) : 1.0;
      if(InpUseDynamicWidth && max_abs_gex > 0)
      {
         line_width = InpBaseLineWidth + (int)MathRound(gex_ratio * 3.0);
      }
      else
      {
         line_width = InpBaseLineWidth;
      }
      datetime gex_line_end = time_start + (int)((time_end - time_start) * MathMax(0.2, gex_ratio));
      datetime ag_line_end = time_start + (int)((time_end - time_start) * MathMax(0.2, ag_ratio));
      string type_prefix = "";
      bool is_global_call = (strike == max_global_call_oi_strike && max_global_call_oi > 0);
      bool is_global_put = (strike == max_global_put_oi_strike && max_global_put_oi > 0);
      bool is_daily_call = (strike == max_daily_call_oi_strike && max_daily_call_oi > 0);
      bool is_daily_put = (strike == max_daily_put_oi_strike && max_daily_put_oi > 0);
      bool is_max_ag = (strike == max_gamma_strike && max_abs_gamma > 0);
      if(is_global_call && is_global_put)
         type_prefix += "GLOB CALL/PUT ";
      else if(is_global_call)
         type_prefix += "GLOB CALL ";
      else if(is_global_put)
         type_prefix += "GLOB PUT ";
      if(is_daily_call && is_daily_put)
         type_prefix += "DLY CALL/PUT ";
      else if(is_daily_call)
         type_prefix += "DLY CALL ";
      else if(is_daily_put)
         type_prefix += "DLY PUT ";
      if(is_max_ag)
         type_prefix += "MAX AG ";
      if(is_global_call && is_global_put)
      {
         line_color = (max_global_put_oi >= max_global_call_oi) ? InpColorPutMarket : InpColorCallMarket;
         line_width = InpWidthMarket;
      }
      else if(is_global_call)
      {
         line_color = InpColorCallMarket;
         line_width = InpWidthMarket;
      }
      else if(is_global_put)
      {
         line_color = InpColorPutMarket;
         line_width = InpWidthMarket;
      }
      else if(is_daily_call && is_daily_put)
      {
         line_color = (max_daily_put_oi >= max_daily_call_oi) ? InpColorPutMarket : InpColorCallMarket;
         line_width = 2;
      }
      else if(is_daily_call)
      {
         line_color = InpColorCallMarket;
         line_width = 2;
      }
      else if(is_daily_put)
      {
         line_color = InpColorPutMarket;
         line_width = 2;
      }
      else if(is_max_ag)
      {
         line_color = InpColorGamma;
         line_width = 4;
      }
      string obj_name = StringFormat("%s%s_%s_%.4f", g_obj_prefix, g_base_currency, date_str, strike);
      ObjectDelete(0, obj_name);
      if(ObjectCreate(0, obj_name, OBJ_TREND, 0, time_start, chart_price, gex_line_end, chart_price))
      {
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, obj_name, OBJPROP_WIDTH, line_width);
         ObjectSetInteger(0, obj_name, OBJPROP_STYLE, line_style);
         ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, obj_name, OBJPROP_BACK, true);
         string tooltip = StringFormat("Date: %s | Strike: %.4f | Chart Price: %.5f | GEX: %.0f | Abs Gamma: %.0f | D_Call_OI: %.0f | D_Put_OI: %.0f | G_Call_OI: %.0f | G_Put_OI: %.0f", 
                                       date_str, strike, chart_price, gex, ag, rows[i].daily_call_oi, rows[i].daily_put_oi, rows[i].global_call_oi, rows[i].global_put_oi);
         ObjectSetString(0, obj_name, OBJPROP_TOOLTIP, tooltip);
      }
      double ag_chart_price = chart_price - 2.0 * Point();
      string ag_line_name = obj_name + "_AGL";
      ObjectDelete(0, ag_line_name);
      if(ObjectCreate(0, ag_line_name, OBJ_TREND, 0, time_start, ag_chart_price, ag_line_end, ag_chart_price))
      {
         ObjectSetInteger(0, ag_line_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_COLOR, InpColorAGLine);
         ObjectSetInteger(0, ag_line_name, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, ag_line_name, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, ag_line_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, ag_line_name, OBJPROP_BACK, true);
      }
      double label_gex_ratio = (label_max_abs_gex > 0) ? (MathAbs(gex) / label_max_abs_gex) : gex_ratio;
      if(label_gex_ratio > 1.0)
         label_gex_ratio = 1.0;
      double label_ag_ratio = (label_max_abs_gamma > 0) ? (ag / label_max_abs_gamma) : ag_ratio;
      int gex_pct = (int)MathRound(label_gex_ratio * 100.0);
      int ag_pct = (int)MathRound(label_ag_ratio * 100.0);
      string text_obj_name = obj_name + "_TXT";
      ObjectDelete(0, text_obj_name);
      if(ObjectCreate(0, text_obj_name, OBJ_TEXT, 0, label_time, chart_price))
      {
         string sign = (gex >= 0) ? "+" : "";
         string text_val = StringFormat("%sGEX %s%s (%d%%) | AG (%d%%)", 
                                        type_prefix, sign, FormatVolume(gex), gex_pct, ag_pct);
         ObjectSetString(0, text_obj_name, OBJPROP_TEXT, text_val);
         ObjectSetInteger(0, text_obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, text_obj_name, OBJPROP_FONTSIZE, 8);
         ObjectSetString(0, text_obj_name, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, text_obj_name, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
         ObjectSetInteger(0, text_obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, text_obj_name, OBJPROP_HIDDEN, true);
      }
      if(strike == max_daily_call_oi_strike && rows[i].daily_call_settle > 0.0)
      {
         double settle = rows[i].daily_call_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = chart_price + settle;
         string name = obj_name + "_DCMD";
         ObjectDelete(0, name);
         if(ObjectCreate(0, name, OBJ_TREND, 0, time_start, mdd, time_end, mdd))
         {
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorMDDCall);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, InpWidthDailyMDD);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, name, OBJPROP_BACK, false);
            ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("Daily Call MDD Premium: %.4f", settle));
            string txt = name + "_TXT";
            ObjectDelete(0, txt);
            ObjectCreate(0, txt, OBJ_TEXT, 0, label_time, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, clrBlack);
            ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, txt, OBJPROP_HIDDEN, true);
         }
      }
      if(strike == max_daily_put_oi_strike && rows[i].daily_put_settle > 0.0)
      {
         double settle = rows[i].daily_put_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = chart_price - settle;
         string name = obj_name + "_DPMD";
         ObjectDelete(0, name);
         if(ObjectCreate(0, name, OBJ_TREND, 0, time_start, mdd, time_end, mdd))
         {
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorMDDPut);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, InpWidthDailyMDD);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, name, OBJPROP_BACK, false);
            ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("Daily Put MDD Premium: %.4f", settle));
            string txt = name + "_TXT";
            ObjectDelete(0, txt);
            ObjectCreate(0, txt, OBJ_TEXT, 0, label_time, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, clrBlack);
            ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, txt, OBJPROP_HIDDEN, true);
         }
      }
   }
   return true;
}

//+------------------------------------------------------------------+
//| Clean up all custom objects                                      |

//+------------------------------------------------------------------+

void CleanUpObjects()
{
   int total_objects = ObjectsTotal(0);
   for(int i = total_objects - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringSubstr(name, 0, StringLen(g_obj_prefix)) == g_obj_prefix)
      {
         ObjectDelete(0, name);
      }
   }
}