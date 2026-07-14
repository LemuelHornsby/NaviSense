@echo off
title NaviSense - Step 5 - COLREGS crossing stand-on
cd /d "%~dp0"
echo === Step 5 - COLREGS crossing stand-on ===
"%~dp0.venv\Scripts\python.exe" run_colregs.py --crossing-standon
echo.
echo Exit code: %ERRORLEVEL%
pause
