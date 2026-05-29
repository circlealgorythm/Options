# MT5 Deployment Note

When changing `CME_GEX_Levels_EA`, use these paths:

- Edit the project source in:
  `C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_EA.mq5`
- Compile/deploy the `.ex5` used by the active terminal to:
  `C:\Program Files\Wizense Global MT5 Terminal\MQL5\Experts`
- Copy refreshed CSV files to:
  `C:\Program Files\Wizense Global MT5 Terminal\MQL5\Files\GEX`

Do not rely on the `AppData\Roaming\MetaQuotes\Terminal\...\MQL5` copy for this terminal. The active MT5 instance is using the portable `Program Files\Wizense Global MT5 Terminal` tree.
