@echo off
title Stop CME GEX Dashboard
echo Stopping GEX Dashboard server...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' AND CommandLine LIKE '%%run_dashboard.py%%'\" | Invoke-CimMethod -MethodName Terminate"
echo Dashboard stopped successfully.
timeout /t 2 >nul
