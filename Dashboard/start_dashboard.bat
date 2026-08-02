@echo off
title CME GEX Dashboard
cd /d "%~dp0"
echo Starting Option Levels Dashboard...
start "" "http://127.0.0.1:8080"
python run_dashboard.py
