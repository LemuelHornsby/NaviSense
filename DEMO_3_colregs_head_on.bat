@echo off
title NaviSense - Step 5 - COLREGS head-on
cd /d "%~dp0"
echo === Step 5 - COLREGS head-on ===
"%~dp0.venv\Scripts\python.exe" run_colregs.py --head-on
echo.
echo Exit code: %ERRORLEVEL%
pause
