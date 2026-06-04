@echo off
title CME GEX Dashboard
cd /d "c:\Users\circlealgorythm\.antigravity\bot_grid\Dashboard"
echo Starting Option Levels Dashboard...
start "" "http://localhost:8080"
python run_dashboard.py
