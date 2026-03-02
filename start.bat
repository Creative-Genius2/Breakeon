@echo off
REM =====================================================
REM  BREAKEON - Start script for Windows
REM
REM  This does two things:
REM    1. Starts the local server (serves your ROM + handles hooks)
REM    2. Opens your browser to localhost:3000
REM
REM  The server runs until you close this window or hit Ctrl+C.
REM =====================================================

echo.
echo   ____                 _                    
echo  ^| __ ) _ __ ___  __ _^| ^|_ ___  ___  _ __  
echo  ^|  _ \^| '__/ _ \/ _` ^| ^|/ / _ \/ _ \^| '_ \ 
echo  ^| ^|_) ^| ^| ^|  __/ (_^| ^|   ^<  __/ (_) ^| ^| ^| ^|
echo  ^|____/^|_^|  \___^|\__,_^|_^|\_\___^|\___/^|_^| ^|_^|
echo.
echo  Play games while Claude thinks.
echo  Close this window to stop.
echo.

REM Navigate to project directory
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.9+ from python.org
    pause
    exit /b 1
)

REM Open browser after a short delay (give server time to start)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:3000"

REM Start the server (this blocks until Ctrl+C)
python server.py
