//+------------------------------------------------------------------+
//|                                           CME_GEX_Levels_EA.mq5  |
//|                                  Copyright 2026, circlealgorythm |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, circlealgorythm"
#property link      "https://github.com/circlealgorythm/Options"
#property version   "1.01"
#property description "Expert Advisor to fetch CME GEX options levels from GitHub and plot them."

//--- Inputs
input group "--- GitHub Configuration ---"
input string   InpGithubUser  = "circlealgorythm"; // GitHub Username
input string   InpGithubRepo  = "Options";         // GitHub Repository Name
input string   InpGithubToken = "";                // GitHub PAT (leave empty if repo is public)

input group "--- Display Settings ---"
input int      InpHistoryDays = 30;                // Days of history to load
input double   InpMinGexFilter = 1000.0;           // Minimum absolute GEX to display (filter noise)
input color    InpColorCall   = clrMediumSeaGreen; // Positive GEX Color (Support)
input color    InpColorPut    = clrCrimson;        // Negative GEX Color (Resistance)
input color    InpColorGamma  = clrDeepSkyBlue;    // Max Absolute Gamma Color
input int      InpRefreshHours= 4;                 // Refresh rate in hours

//--- Global Variables
datetime       g_last_update = 0;
string         g_base_currency = "";
string         g_obj_prefix = "CMEGEX_";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Identify base currency (EUR or GBP)
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
   
   // Create a timer to refresh data periodically
   EventSetTimer(3600); // Trigger timer event every hour
   
   // Initial data load
   UpdateLevels();
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   CleanUpObjects();
   Print("CME GEX EA deinitialized and objects cleaned up.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // We update on timer, no need to run WebRequest on every tick
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
   
   Print("Fetching option levels from GitHub...");
   g_last_update = TimeCurrent();
   
   datetime current_time = TimeCurrent();
   int success_count = 0;
   
   for(int i = 0; i < InpHistoryDays; i++)
   {
      datetime target_date = current_time - i * 86400;
      MqlDateTime dt;
      TimeToStruct(target_date, dt);
      
      // Skip weekends since CME options don't update
      if(dt.day_of_week == 0 || dt.day_of_week == 6)
         continue;
         
      string date_str = StringFormat("%04d-%02d-%02d", dt.year, dt.mon, dt.day);
      if(FetchAndParseDate(date_str))
      {
         success_count++;
      }
   }
   
   ChartRedraw(0);
   Print("Levels update completed. Successfully loaded data for ", success_count, " days.");
}

//+------------------------------------------------------------------+
//| Download and parse CSV file for a specific date                  |
//+------------------------------------------------------------------+
bool FetchAndParseDate(string date_str)
{
   string url = "https://raw.githubusercontent.com/" + InpGithubUser + "/" + InpGithubRepo + 
                "/main/data/GEX_" + g_base_currency + "USD_" + date_str + ".csv";
                
   string headers = "User-Agent: MetaTrader5\r\n";
   if(StringLen(InpGithubToken) > 0)
   {
      headers += "Authorization: token " + InpGithubToken + "\r\n";
   }
   
   char post[], result_data[];
   string result_headers;
   int timeout = 5000; // 5 seconds
   
   ResetLastError();
   int res = WebRequest("GET", url, headers, timeout, post, result_data, result_headers);
   
   if(res == 200)
   {
      string csv_data = CharArrayToString(result_data, 0, WHOLE_ARRAY, CP_UTF8);
      ParseCSV(csv_data, date_str);
      return true;
   }
   else if(res == 404)
   {
      // 404 is normal for days with no bulletin data (e.g. holidays or today's data before update)
      return false;
   }
   else
   {
      int err = GetLastError();
      if(err == 4014) // ERR_FUNCTION_NOT_ALLOWED
         Print("WebRequest failed (4014). Allow URL 'https://raw.githubusercontent.com' in Tools -> Options -> Expert Advisors.");
      else
         PrintFormat("WebRequest error for %s. HTTP Code: %d, MT5 Error: %d", date_str, res, err);
         
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
};

//+------------------------------------------------------------------+
//| Parse CSV contents and draw levels                               |
//+------------------------------------------------------------------+
void ParseCSV(const string &csv_data, string date_str)
{
   // Strip carriage returns to ensure clean splitting
   string clean_csv = csv_data;
   StringReplace(clean_csv, "\r", "");
   
   string lines[];
   int total_lines = StringSplit(clean_csv, '\n', lines);
   if(total_lines <= 1)
      return;
      
   double max_abs_gex = 0.0;
   double max_abs_gamma = 0.0;
   double max_gamma_strike = 0.0;
   
   OptionRow rows[];
   if(ArrayResize(rows, total_lines) == -1)
   {
      Print("Error: Failed to allocate memory for CSV parsing.");
      return;
   }
   
   int valid_rows = 0;
   
   // First pass: extract data and find maximums
   for(int i = 1; i < total_lines; i++)
   {
      string line = lines[i];
      StringTrimLeft(line);
      StringTrimRight(line);
      
      if(StringLen(line) == 0)
         continue;
         
      string columns[];
      int total_cols = StringSplit(line, ',', columns);
      
      // Expected minimum 4 columns: Currency,Strike,Total_GEX,Total_Abs_Gamma
      if(total_cols < 4)
         continue;
         
      double strike = StringToDouble(columns[1]);
      double total_gex = StringToDouble(columns[2]);
      double total_abs_gamma = StringToDouble(columns[3]);
      
      if(MathAbs(total_gex) >= InpMinGexFilter)
      {
         rows[valid_rows].strike = strike;
         rows[valid_rows].total_gex = total_gex;
         rows[valid_rows].total_abs_gamma = total_abs_gamma;
         
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
   
   if(valid_rows == 0)
      return;
      
   // Calculate time bounds for the specific day (strictly horizontal bounds)
   datetime time_start = StringToTime(date_str + " 00:00:00");
   datetime time_end = StringToTime(date_str + " 23:59:59");
   
   // Second pass: Draw the levels
   for(int i = 0; i < valid_rows; i++)
   {
      double strike = rows[i].strike;
      double gex = rows[i].total_gex;
      
      color line_color = (gex >= 0) ? InpColorCall : InpColorPut;
      
      // Scale thickness between 1 and 4 based on max GEX
      int line_width = 1;
      if(max_abs_gex > 0)
      {
         double ratio = MathAbs(gex) / max_abs_gex;
         line_width = 1 + (int)MathRound(ratio * 3.0); // Maps [0, 1] to [1, 4]
      }
      
      // Highlight absolute maximum gamma level
      if(strike == max_gamma_strike && max_abs_gamma > 0)
      {
         line_color = InpColorGamma;
         line_width = 4;
      }
      
      string obj_name = StringFormat("%s%s_%s_%.4f", g_obj_prefix, g_base_currency, date_str, strike);
      
      // Draw daily horizontal bounded trendline
      if(ObjectCreate(0, obj_name, OBJ_TREND, 0, time_start, strike, time_end, strike))
      {
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_LEFT, false); // Crucial for bounded line
         ObjectSetInteger(0, obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, obj_name, OBJPROP_WIDTH, line_width);
         ObjectSetInteger(0, obj_name, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true); // Keep object list clean
         ObjectSetInteger(0, obj_name, OBJPROP_BACK, true); // Behind candlesticks
         
         string tooltip = StringFormat("Date: %s | Strike: %.4f | GEX: %.0f | Abs Gamma: %.0f", 
                                       date_str, strike, gex, rows[i].total_abs_gamma);
         ObjectSetString(0, obj_name, OBJPROP_TOOLTIP, tooltip);
      }
   }
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
