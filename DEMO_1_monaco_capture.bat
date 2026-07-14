@echo off
title NaviSense - Step 1 - run_demo monaco_capture (start, then press Play in UE)
cd /d "%~dp0"
echo === Step 1 - run_demo monaco_capture (start, then press Play in UE) ===
"%~dp0.venv\Scripts\python.exe" run_demo.py --scenario monaco_capture
echo.
echo Exit code: %ERRORLEVEL%
pause
