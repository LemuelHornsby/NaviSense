@echo off
title NaviSense - Step 6 - verify_demo_session closeout
cd /d "%~dp0"
echo === Step 6 - verify_demo_session closeout ===
"%~dp0.venv\Scripts\python.exe" python/verify_demo_session.py
echo.
echo Exit code: %ERRORLEVEL%
pause
