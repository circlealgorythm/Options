//+------------------------------------------------------------------+
//|                                           CME_GEX_Levels_EA.mq5  |
//|                                  Copyright 2026, circlealgorythm |
//|                                  https://github.com/circlealgorythm |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, circlealgorythm"
#property link      "https://github.com/circlealgorythm/Options"
#property version   "1.05"
#property description "Expert Advisor to fetch CME GEX options levels and plot premium boundaries, MDD, AG, and volatility zones."

//--- Inputs
input group "--- GitHub Configuration ---"
input string   InpGithubUser  = "circlealgorythm"; // GitHub Username
input string   InpGithubRepo  = "Options";         // GitHub Repository Name
input string   InpGithubToken = "";                // GitHub PAT (leave empty if repo is public)

input group "--- Display Settings ---"
input int      InpHistoryDays = 30;                // Days of history to load
input double   InpMinGexFilter = 1000.0;           // Minimum absolute GEX to display (filter noise)
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
input int      InpWidthGlobalMDD  = 3;             // Global MDD Line Width (Solid style)

input group "--- Option Month Settings ---"
input bool     InpDrawMonthLines  = true;              // Draw option month separator lines
input color    InpColorNewMonth   = clrMediumOrchid;   // Option Month Line Color
input int      InpWidthNewMonth   = 2;                 // Option Month Line Width
input ENUM_LINE_STYLE InpStyleNewMonth = STYLE_DASH;   // Option Month Line Style

input group "--- Volatility Zones ---"
input bool     InpDrawZones   = true;              // Draw volatility zones R68/R95
input bool     InpFillZones   = true;              // Fill volatility zones with color (false = draw borders only)
input color    InpColorR68    = C'244,224,224';    // R68 Zone Color (68% probability)
input color    InpColorR95    = C'248,255,248';    // R95 Zone Color (95% probability)

//--- Global Variables
datetime       g_last_update = 0;
string         g_base_currency = "";
string         g_obj_prefix = "CMEGEX_";
bool           g_show_gex = true;
bool           g_show_ag  = true;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   string symbol = Symbol();
   if(StringFind(symbol, "EUR") >= 0)
      g_base_currency = "EUR";
   else if(StringFind(symbol, "GBP") >= 0)
      g_base_currency = "GBP";
   else
   {
      Alert("Symbol ", symbol, " is not supported. Only EUR and GBP pairs are supported.");
      return(INIT_FAILED);
   }

   Print("CME GEX EA initialized for ", g_base_currency, "USD. Loading historical levels...");
   
   CreateButtons();
   EventSetTimer(3600); // Trigger timer event every hour
   
   UpdateLevels();
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   DeleteButtons();
   CleanUpObjects();
   Print("CME GEX EA deinitialized and objects cleaned up.");
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
         bool is_mdd_r_zones = (StringFind(name, "_R68") >= 0 || StringFind(name, "_R95") >= 0 || StringFind(name, "CMD") >= 0 || StringFind(name, "PMD") >= 0);
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
      if(sparam == "Btn_ShowGEX")
      {
         g_show_gex = !g_show_gex;
         UpdateToggleButton("Btn_ShowGEX", "GEX", g_show_gex);
         UpdateVisibility();
         ObjectSetInteger(0, "Btn_ShowGEX", OBJPROP_STATE, false); // Reset button state
      }
      else if(sparam == "Btn_ShowAG")
      {
         g_show_ag = !g_show_ag;
         UpdateToggleButton("Btn_ShowAG", "AG", g_show_ag);
         UpdateVisibility();
         ObjectSetInteger(0, "Btn_ShowAG", OBJPROP_STATE, false); // Reset button state
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
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
   
   Print("Fetching option levels...");
   g_last_update = TimeCurrent();
   
   datetime current_time = TimeCurrent();
   int success_count = 0;
   MqlDateTime current_dt;
   TimeToStruct(current_time, current_dt);
   string today_str = StringFormat("%04d-%02d-%02d", current_dt.year, current_dt.mon, current_dt.day);
   bool today_loaded = false;
   
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
   
   UpdateVisibility();
   DrawUpdateStatus(today_str, today_loaded, success_count);
   ChartRedraw(0);
   Print("Levels update completed. Successfully loaded data for ", success_count, " days.");
   
   // --- DEBUG BLOCK ---
   int cme_obj_count = 0;
   int total_obj = ObjectsTotal(0);
   for(int j = total_obj - 1; j >= 0; j--)
   {
      string name = ObjectName(0, j);
      if(StringSubstr(name, 0, StringLen(g_obj_prefix)) == g_obj_prefix)
      {
         cme_obj_count++;
         if(cme_obj_count <= 10)
         {
            double price1 = ObjectGetDouble(0, name, OBJPROP_PRICE, 0);
            datetime time1 = (datetime)ObjectGetInteger(0, name, OBJPROP_TIME, 0);
            PrintFormat("Debug Obj: %s | Type: %d | Time: %s | Price: %.5f", name, (int)ObjectGetInteger(0, name, OBJPROP_TYPE), TimeToString(time1), price1);
         }
      }
   }
   PrintFormat("Debug Total Objects with Prefix '%s': %d (out of %d total chart objects)", g_obj_prefix, cme_obj_count, total_obj);
}

//+------------------------------------------------------------------+
//| Draw data freshness status                                       |
//+------------------------------------------------------------------+
void DrawUpdateStatus(string today_str, bool today_loaded, int success_count)
{
   string name = g_obj_prefix + "UpdateStatus";
   ObjectDelete(0, name);
   
   if(ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0))
   {
      string status = today_loaded ? "GEX today OK: " : "GEX today MISSING: ";
      status += today_str + StringFormat(" | loaded days: %d", success_count);
      
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 56);
      ObjectSetString(0, name, OBJPROP_TEXT, status);
      ObjectSetInteger(0, name, OBJPROP_COLOR, today_loaded ? clrSeaGreen : clrCrimson);
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
   string local_file_path = "GEX\\GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   if(!prefer_remote && FileIsExist(local_file_path))
   {
      if(TryParseLocalCSV(local_file_path, date_str, out_month, "Loaded levels locally from"))
         return true;

      Print("Local CSV has an unsupported or stale schema, trying WebRequest fallback: Files\\", local_file_path);
      ResetLastError();
      FileDelete(local_file_path);
   }
   
   // 2. Fallback to GitHub WebRequest if local file is not found
   string url;
   string headers = "User-Agent: MetaTrader5\r\n";
   
   if(StringLen(InpGithubToken) > 0)
   {
      url = "https://api.github.com/repos/" + InpGithubUser + "/" + InpGithubRepo + 
            "/contents/data/GEX_" + g_base_currency + "USD_" + date_str + ".csv";
            
      headers += "Authorization: Bearer " + InpGithubToken + "\r\n";
      headers += "Accept: application/vnd.github.v3.raw\r\n";
      headers += "X-GitHub-Api-Version: 2022-11-28\r\n";
   }
   else
   {
      url = "https://raw.githubusercontent.com/" + InpGithubUser + "/" + InpGithubRepo + 
            "/main/data/GEX_" + g_base_currency + "USD_" + date_str + ".csv";
   }
                 
   char post[], result_data[];
   string result_headers;
   int timeout = 5000; // 5 seconds
   
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

       // Save downloaded CSV locally to prevent redundant WebRequests on timeframe switches
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
      if(err == 4014)
         Print("WebRequest failed (4014). Allow URL 'https://api.github.com' in Tools -> Options -> Expert Advisors.");
      else
         PrintFormat("WebRequest error for %s. HTTP Code: %d, MT5 Error: %d", date_str, res, err);

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
   double global_call_settle;
   double global_call_oi;
   double global_put_settle;
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
   else
      return StringFormat("%s%.0f", sign, abs_val);
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
   
   PrintFormat("ParseCSV Debug: Line 0 (Header) = '%s'", lines[0]);
   if(total_lines > 1)
      PrintFormat("ParseCSV Debug: Line 1 (First data row) = '%s'", lines[1]);

   if(StringFind(lines[0], "Daily_Call_Settle") < 0 || StringFind(lines[0], "Global_Call_Settle") < 0)
   {
      Print("Unsupported CSV schema. Expected Daily/Global MDD columns, got: ", lines[0]);
      return false;
   }
      
   double max_abs_gex = 0.0;
   double max_abs_gamma = 0.0;
   double max_gamma_strike = 0.0;
   
   double max_daily_call_oi = -1.0;
   double max_daily_call_oi_strike = 0.0;
   double max_daily_put_oi = -1.0;
   double max_daily_put_oi_strike = 0.0;
   
   double max_global_call_oi = -1.0;
   double max_global_call_oi_strike = 0.0;
   double max_global_put_oi = -1.0;
   double max_global_put_oi_strike = 0.0;
   
   double r68_high = 0.0;
   double r68_low = 0.0;
   double r95_high = 0.0;
   double r95_low = 0.0;
   
   OptionRow rows[];
   if(ArrayResize(rows, total_lines) == -1)
   {
      Print("Error: Failed to allocate memory for CSV parsing.");
      return false;
   }
   
   int valid_rows = 0;
   
   // First pass: extract data, find maximums and volatility zones
   for(int i = 1; i < total_lines; i++)
   {
      string line = lines[i];
      StringTrimLeft(line);
      StringTrimRight(line);
      
      if(StringLen(line) == 0)
         continue;
         
      string columns[];
      int total_cols = StringSplit(line, ',', columns);
      
      // Structure: Currency,Strike,Total_GEX,Total_Abs_Gamma,Daily_Call_Settle,Daily_Call_OI,Daily_Put_Settle,Daily_Put_OI,Global_Call_Settle,Global_Call_OI,Global_Put_Settle,Global_Put_OI,R68_High,R68_Low,R95_High,R95_Low,Global_Month,Daily_Month
      if(total_cols < 18)
         continue;
         
      double strike = StringToDouble(columns[1]);
      double total_gex = StringToDouble(columns[2]);
      double total_abs_gamma = StringToDouble(columns[3]);
      
      double d_call_settle = StringToDouble(columns[4]);
      double d_call_oi = StringToDouble(columns[5]);
      double d_put_settle = StringToDouble(columns[6]);
      double d_put_oi = StringToDouble(columns[7]);
      
      double g_call_settle = StringToDouble(columns[8]);
      double g_call_oi = StringToDouble(columns[9]);
      double g_put_settle = StringToDouble(columns[10]);
      double g_put_oi = StringToDouble(columns[11]);
      
      // Read volatility zones and months from the first matching row
      if(total_cols >= 16 && r68_high == 0.0)
      {
         r68_high = StringToDouble(columns[12]);
         r68_low = StringToDouble(columns[13]);
         r95_high = StringToDouble(columns[14]);
         r95_low = StringToDouble(columns[15]);
         if(total_cols >= 18)
         {
            out_global_month = columns[16];
         }
      }
      
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
      
      if(g_call_oi > max_global_call_oi && g_call_settle > 0.0)
      {
         max_global_call_oi = g_call_oi;
         max_global_call_oi_strike = strike;
      }
      
      if(g_put_oi > max_global_put_oi && g_put_settle > 0.0)
      {
         max_global_put_oi = g_put_oi;
         max_global_put_oi_strike = strike;
      }
      
      bool has_mdd_data = ((d_call_oi > 0.0 && d_call_settle > 0.0) ||
                           (d_put_oi > 0.0 && d_put_settle > 0.0) ||
                           (g_call_oi > 0.0 && g_call_settle > 0.0) ||
                           (g_put_oi > 0.0 && g_put_settle > 0.0));
      
      if(MathAbs(total_gex) >= InpMinGexFilter || has_mdd_data)
      {
         rows[valid_rows].strike = strike;
         rows[valid_rows].total_gex = total_gex;
         rows[valid_rows].total_abs_gamma = total_abs_gamma;
         rows[valid_rows].daily_call_settle = d_call_settle;
         rows[valid_rows].daily_call_oi = d_call_oi;
         rows[valid_rows].daily_put_settle = d_put_settle;
         rows[valid_rows].daily_put_oi = d_put_oi;
         rows[valid_rows].global_call_settle = g_call_settle;
         rows[valid_rows].global_call_oi = g_call_oi;
         rows[valid_rows].global_put_settle = g_put_settle;
         rows[valid_rows].global_put_oi = g_put_oi;
         
         double abs_gex = MathAbs(total_gex);
         if(abs_gex > max_abs_gex)
            max_abs_gex = abs_gex;
            
         if(total_abs_gamma > max_abs_gamma)
         {
            max_abs_gamma = total_abs_gamma;
            max_gamma_strike = strike;
         }
         
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
   
   if(InpAutoSpotAdjust && r68_high > 0.0 && r68_low > 0.0)
   {
      double futures_price = (r68_high + r68_low) / 2.0;
      int shift = iBarShift(Symbol(), PERIOD_D1, time_start);
      if(shift >= 0)
      {
         double spot_price = iClose(Symbol(), PERIOD_D1, shift);
         if(spot_price > 0)
         {
            fw_offset = spot_price - futures_price;
         }
      }
   }
   
   // Draw volatility zones first (so they are in the background)
   if(InpDrawZones && r68_high > 0.0 && r68_low > 0.0)
   {
      double chart_r95_high = r95_high + fw_offset;
      double chart_r95_low = r95_low + fw_offset;
      double chart_r68_high = r68_high + fw_offset;
      double chart_r68_low = r68_low + fw_offset;
      
      string r95_name = StringFormat("%s%s_%s_R95", g_obj_prefix, g_base_currency, date_str);
      ObjectDelete(0, r95_name);
      if(ObjectCreate(0, r95_name, OBJ_RECTANGLE, 0, time_start, chart_r95_high, time_end, chart_r95_low))
      {
         ObjectSetInteger(0, r95_name, OBJPROP_COLOR, InpColorR95);
         ObjectSetInteger(0, r95_name, OBJPROP_FILL, InpFillZones);
         ObjectSetInteger(0, r95_name, OBJPROP_BACK, true);
         ObjectSetInteger(0, r95_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, r95_name, OBJPROP_HIDDEN, true);
         ObjectSetString(0, r95_name, OBJPROP_TOOLTIP,
                         StringFormat("Date: %s | R95 Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                      date_str, chart_r95_low, chart_r95_high, r95_low, r95_high));
      }
      
      string r68_name = StringFormat("%s%s_%s_R68", g_obj_prefix, g_base_currency, date_str);
      ObjectDelete(0, r68_name);
      if(ObjectCreate(0, r68_name, OBJ_RECTANGLE, 0, time_start, chart_r68_high, time_end, chart_r68_low))
      {
         ObjectSetInteger(0, r68_name, OBJPROP_COLOR, InpColorR68);
         ObjectSetInteger(0, r68_name, OBJPROP_FILL, InpFillZones);
         ObjectSetInteger(0, r68_name, OBJPROP_BACK, true);
         ObjectSetInteger(0, r68_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, r68_name, OBJPROP_HIDDEN, true);
         ObjectSetString(0, r68_name, OBJPROP_TOOLTIP,
                         StringFormat("Date: %s | R68 Zone chart/spot [%.5f - %.5f] | futures [%.5f - %.5f]",
                                      date_str, chart_r68_low, chart_r68_high, r68_low, r68_high));
      }
   }
   
   // Second pass: Draw the levels & labels
   for(int i = 0; i < valid_rows; i++)
   {
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
         line_width = InpBaseLineWidth + (int)MathRound(gex_ratio * 3.0); // Maps [0, 1] width offset
      }
      else
      {
         line_width = InpBaseLineWidth;
      }
      
      datetime gex_line_end = time_start + (int)((time_end - time_start) * MathMax(0.2, gex_ratio));
      datetime ag_line_end = time_start + (int)((time_end - time_start) * MathMax(0.2, ag_ratio));
      
      string type_prefix = "";
      
      // Global CALL Market Boundary (1st Order)
      if(strike == max_global_call_oi_strike && max_global_call_oi > 0)
      {
         line_color = InpColorCallMarket;
         line_width = InpWidthMarket;
         type_prefix = "[GLOB CALL] ";
      }
      // Global PUT Market Boundary (1st Order)
      else if(strike == max_global_put_oi_strike && max_global_put_oi > 0)
      {
         line_color = InpColorPutMarket;
         line_width = InpWidthMarket;
         type_prefix = "[GLOB PUT] ";
      }
      // Daily CALL Market Boundary
      else if(strike == max_daily_call_oi_strike && max_daily_call_oi > 0)
      {
         line_color = InpColorCallMarket;
         line_width = 2;
         type_prefix = "[DLY CALL] ";
      }
      // Daily PUT Market Boundary
      else if(strike == max_daily_put_oi_strike && max_daily_put_oi > 0)
      {
         line_color = InpColorPutMarket;
         line_width = 2;
         type_prefix = "[DLY PUT] ";
      }
      // Highlight absolute maximum gamma level if it's not a market boundary
      else if(strike == max_gamma_strike && max_abs_gamma > 0)
      {
         line_color = InpColorGamma;
         line_width = 4;
         type_prefix = "[MAX AG] ";
      }
      
      string obj_name = StringFormat("%s%s_%s_%.4f", g_obj_prefix, g_base_currency, date_str, strike);
      
      // Draw horizontal bounded trendline for GEX Wall
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
      
      // Draw horizontal bounded trendline for Absolute Gamma (AG) with a micro-offset below the GEX line
      double ag_chart_price = chart_price - 2.0 * Point();
      string ag_line_name = obj_name + "_AGL";
      ObjectDelete(0, ag_line_name);
      if(ObjectCreate(0, ag_line_name, OBJ_TREND, 0, time_start, ag_chart_price, ag_line_end, ag_chart_price))
      {
         ObjectSetInteger(0, ag_line_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_COLOR, InpColorAGLine);
         ObjectSetInteger(0, ag_line_name, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, ag_line_name, OBJPROP_STYLE, STYLE_DOT); // Dotted line
         ObjectSetInteger(0, ag_line_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, ag_line_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, ag_line_name, OBJPROP_BACK, true);
      }
      
      // Calculate percentages for labels
      int gex_pct = (int)MathRound(gex_ratio * 100.0);
      int ag_pct = (int)MathRound(ag_ratio * 100.0);
      
      // Draw text label on the left side of the level (slightly offset to the right by 1 hour / 3600 seconds)
      string text_obj_name = obj_name + "_TXT";
      ObjectDelete(0, text_obj_name);
      if(ObjectCreate(0, text_obj_name, OBJ_TEXT, 0, time_start + 3600, chart_price))
      {
         string sign = (gex >= 0) ? "+" : "";
         string text_val = StringFormat("%sGEX %s%s (%d%%) | AG %s (%d%%)", 
                                        type_prefix, sign, FormatVolume(gex), gex_pct, FormatVolume(ag), ag_pct);
         ObjectSetString(0, text_obj_name, OBJPROP_TEXT, text_val);
         ObjectSetInteger(0, text_obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, text_obj_name, OBJPROP_FONTSIZE, 8);
         ObjectSetString(0, text_obj_name, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, text_obj_name, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
         ObjectSetInteger(0, text_obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, text_obj_name, OBJPROP_HIDDEN, true);
      }
      
      // Daily Call MDD
      if(strike == max_daily_call_oi_strike && rows[i].daily_call_settle > 0.0)
      {
         double settle = rows[i].daily_call_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = strike + settle;
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
            ObjectCreate(0, txt, OBJ_TEXT, 0, time_start + 5400, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, clrBlack);
            ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, txt, OBJPROP_HIDDEN, true);
         }
      }
      
      // Global Call MDD
      if(strike == max_global_call_oi_strike && rows[i].global_call_settle > 0.0)
      {
         double settle = rows[i].global_call_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = chart_price + settle;
         string name = obj_name + "_GCMD";
         ObjectDelete(0, name);
         if(ObjectCreate(0, name, OBJ_TREND, 0, time_start, mdd, time_end, mdd))
         {
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorMDDCall);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, InpWidthGlobalMDD);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, name, OBJPROP_BACK, false);
            ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("Global Call MDD Premium: %.4f", settle));
            
            string txt = name + "_TXT";
            ObjectDelete(0, txt);
            ObjectCreate(0, txt, OBJ_TEXT, 0, time_start + 9000, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "G_CALL");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, InpColorMDDCall);
            ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, txt, OBJPROP_HIDDEN, true);
         }
      }

      // Daily Put MDD
      if(strike == max_daily_put_oi_strike && rows[i].daily_put_settle > 0.0)
      {
         double settle = rows[i].daily_put_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = strike - settle;
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
            ObjectCreate(0, txt, OBJ_TEXT, 0, time_start + 5400, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, clrBlack);
            ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, txt, OBJPROP_HIDDEN, true);
         }
      }
      
      // Global Put MDD
      if(strike == max_global_put_oi_strike && rows[i].global_put_settle > 0.0)
      {
         double settle = rows[i].global_put_settle;
         if(g_base_currency == "GBP" && settle > 1.0) settle /= 100.0;
         double mdd = chart_price - settle;
         string name = obj_name + "_GPMD";
         ObjectDelete(0, name);
         if(ObjectCreate(0, name, OBJ_TREND, 0, time_start, mdd, time_end, mdd))
         {
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorMDDPut);
            ObjectSetInteger(0, name, OBJPROP_WIDTH, InpWidthGlobalMDD);
            ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, name, OBJPROP_BACK, false);
            ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("Global Put MDD Premium: %.4f", settle));
            
            string txt = name + "_TXT";
            ObjectDelete(0, txt);
            ObjectCreate(0, txt, OBJ_TEXT, 0, time_start + 9000, mdd);
            ObjectSetString(0, txt, OBJPROP_TEXT, "G_PUT");
            ObjectSetInteger(0, txt, OBJPROP_COLOR, InpColorMDDPut);
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
//+------------------------------------------------------------------+
