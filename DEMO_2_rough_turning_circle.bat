@echo off
title NaviSense - Step 1b - run_demo rough_turning_circle SS5 (D2 wave-ride)
cd /d "%~dp0"
echo === Step 1b - run_demo rough_turning_circle SS5 (D2 wave-ride) ===
"%~dp0.venv\Scripts\python.exe" run_demo.py --scenario rough_turning_circle
echo.
echo Exit code: %ERRORLEVEL%
pause
