//+------------------------------------------------------------------+
//|                                           CME_GEX_Levels_EA.mq5  |
//|                                  Copyright 2026, circlealgorythm |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, circlealgorythm"
#property link      "https://github.com/circlealgorythm/Options"
#property version   "1.02"
#property description "Expert Advisor to fetch CME GEX options levels from GitHub and plot GEX walls & MDD levels."

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
input color    InpColorMDDCall= clrRoyalBlue;      // Call MDD (Breakeven) Color
input color    InpColorMDDPut = clrOrangeRed;      // Put MDD (Breakeven) Color
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
   CleanUpObjects();
   Print("CME GEX EA deinitialized and objects cleaned up.");
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
   
   Print("Fetching option levels from GitHub...");
   g_last_update = TimeCurrent();
   
   datetime current_time = TimeCurrent();
   int success_count = 0;
   
   for(int i = 0; i < InpHistoryDays; i++)
   {
      datetime target_date = current_time - i * 86400;
      MqlDateTime dt;
      TimeToStruct(target_date, dt);
      
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
      ParseCSV(csv_data, date_str);
      return true;
   }
   else if(res == 404)
   {
      return false;
   }
   else
   {
      int err = GetLastError();
      if(err == 4014)
         Print("WebRequest failed (4014). Allow URL 'https://api.github.com' in Tools -> Options -> Expert Advisors.");
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
   double call_settle;
   double put_settle;
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
void ParseCSV(const string &csv_data, string date_str)
{
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
      
      // Structure: Currency,Strike,Total_GEX,Total_Abs_Gamma,Call_OI,Put_OI,Call_Settle,Put_Settle
      if(total_cols < 4)
         continue;
         
      double strike = StringToDouble(columns[1]);
      double total_gex = StringToDouble(columns[2]);
      double total_abs_gamma = StringToDouble(columns[3]);
      double call_settle = (total_cols >= 7) ? StringToDouble(columns[6]) : 0.0;
      double put_settle = (total_cols >= 8) ? StringToDouble(columns[7]) : 0.0;
      
      if(MathAbs(total_gex) >= InpMinGexFilter)
      {
         rows[valid_rows].strike = strike;
         rows[valid_rows].total_gex = total_gex;
         rows[valid_rows].total_abs_gamma = total_abs_gamma;
         rows[valid_rows].call_settle = call_settle;
         rows[valid_rows].put_settle = put_settle;
         
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
      
   datetime time_start = StringToTime(date_str + " 00:00:00");
   datetime time_end = StringToTime(date_str + " 23:59:59");
   
   // Second pass: Draw the levels & labels
   for(int i = 0; i < valid_rows; i++)
   {
      double strike = rows[i].strike;
      double gex = rows[i].total_gex;
      double ag = rows[i].total_abs_gamma;
      
      color line_color = (gex >= 0) ? InpColorCall : InpColorPut;
      
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
      
      // Draw horizontal bounded trendline for GEX Wall
      if(ObjectCreate(0, obj_name, OBJ_TREND, 0, time_start, strike, time_end, strike))
      {
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, obj_name, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, obj_name, OBJPROP_WIDTH, line_width);
         ObjectSetInteger(0, obj_name, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, obj_name, OBJPROP_BACK, true);
         
         string tooltip = StringFormat("Date: %s | Strike: %.4f | GEX: %.0f | Abs Gamma: %.0f", 
                                       date_str, strike, gex, ag);
         ObjectSetString(0, obj_name, OBJPROP_TOOLTIP, tooltip);
      }
      
      // Calculate percentages for labels
      int gex_pct = (max_abs_gex > 0) ? (int)MathRound((MathAbs(gex) / max_abs_gex) * 100.0) : 0;
      int ag_pct = (max_abs_gamma > 0) ? (int)MathRound((ag / max_abs_gamma) * 100.0) : 0;
      
      // Draw text label on the left side of the level
      string text_obj_name = obj_name + "_TXT";
      if(ObjectCreate(0, text_obj_name, OBJ_TEXT, 0, time_start, strike))
      {
         string text_val = StringFormat("GEX %s %d%%\nAG %s %d%%", FormatVolume(gex), gex_pct, FormatVolume(ag), ag_pct);
         ObjectSetString(0, text_obj_name, OBJPROP_TEXT, text_val);
         ObjectSetInteger(0, text_obj_name, OBJPROP_COLOR, line_color);
         ObjectSetInteger(0, text_obj_name, OBJPROP_FONTSIZE, 8);
         ObjectSetString(0, text_obj_name, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, text_obj_name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
         ObjectSetInteger(0, text_obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, text_obj_name, OBJPROP_HIDDEN, true);
      }
      
      // Draw Call MDD (Breakeven) if settlement premium exists
      if(rows[i].call_settle > 0.0)
      {
         double call_mdd = strike + rows[i].call_settle;
         string mdd_call_name = obj_name + "_CMD";
         if(ObjectCreate(0, mdd_call_name, OBJ_TREND, 0, time_start, call_mdd, time_end, call_mdd))
         {
            ObjectSetInteger(0, mdd_call_name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_COLOR, InpColorMDDCall);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_STYLE, STYLE_DOT); // Dotted line
            ObjectSetInteger(0, mdd_call_name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, mdd_call_name, OBJPROP_BACK, true);
         }
         
         // Label for Call MDD
         string mdd_call_txt = mdd_call_name + "_TXT";
         if(ObjectCreate(0, mdd_call_txt, OBJ_TEXT, 0, time_start + 7200, call_mdd)) // Offset slightly to right
         {
            ObjectSetString(0, mdd_call_txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, mdd_call_txt, OBJPROP_COLOR, InpColorMDDCall);
            ObjectSetInteger(0, mdd_call_txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, mdd_call_txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, mdd_call_txt, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
            ObjectSetInteger(0, mdd_call_txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, mdd_call_txt, OBJPROP_HIDDEN, true);
         }
      }
      
      // Draw Put MDD (Breakeven) if settlement premium exists
      if(rows[i].put_settle > 0.0)
      {
         double put_mdd = strike - rows[i].put_settle;
         string mdd_put_name = obj_name + "_PMD";
         if(ObjectCreate(0, mdd_put_name, OBJ_TREND, 0, time_start, put_mdd, time_end, put_mdd))
         {
            ObjectSetInteger(0, mdd_put_name, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_RAY_LEFT, false);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_COLOR, InpColorMDDPut);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_STYLE, STYLE_DOT); // Dotted line
            ObjectSetInteger(0, mdd_put_name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, mdd_put_name, OBJPROP_BACK, true);
         }
         
         // Label for Put MDD
         string mdd_put_txt = mdd_put_name + "_TXT";
         if(ObjectCreate(0, mdd_put_txt, OBJ_TEXT, 0, time_start + 7200, put_mdd)) // Offset slightly to right
         {
            ObjectSetString(0, mdd_put_txt, OBJPROP_TEXT, "MDD");
            ObjectSetInteger(0, mdd_put_txt, OBJPROP_COLOR, InpColorMDDPut);
            ObjectSetInteger(0, mdd_put_txt, OBJPROP_FONTSIZE, 8);
            ObjectSetString(0, mdd_put_txt, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, mdd_put_txt, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
            ObjectSetInteger(0, mdd_put_txt, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, mdd_put_txt, OBJPROP_HIDDEN, true);
         }
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
