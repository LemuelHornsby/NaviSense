@echo off
title NaviSense - Step 5 - COLREGS overtaking
cd /d "%~dp0"
echo === Step 5 - COLREGS overtaking ===
"%~dp0.venv\Scripts\python.exe" run_colregs.py --overtaking
echo.
echo Exit code: %ERRORLEVEL%
pause
