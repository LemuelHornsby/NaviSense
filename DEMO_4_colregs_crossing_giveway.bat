@echo off
title NaviSense - Step 5 - COLREGS crossing give-way
cd /d "%~dp0"
echo === Step 5 - COLREGS crossing give-way ===
"%~dp0.venv\Scripts\python.exe" run_colregs.py --crossing-giveway
echo.
echo Exit code: %ERRORLEVEL%
pause
