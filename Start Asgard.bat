@echo off
setlocal enabledelayedexpansion

:: Check if FastAPI backend is already running on port 8000
netstat -ano | findstr "LISTENING" | findstr ":8000" >nul
if %errorlevel% equ 0 (
    start http://localhost:8000
    exit /b
)

:: Not running — start it
:MENU
cls
title Asgard Trading Launcher
color 0B
echo ===================================================
echo             ASGARD INTELLIGENCE LAUNCHER
echo ===================================================
echo.
echo Backend is not running on port 8000.
echo.
echo [1] Start Asgard (Python Backend)
echo [2] Start using Docker Compose
echo [3] Just open browser on http://localhost:8000
echo [4] Exit
echo.
set /p choice="Choose an option (1-4): "

if "%choice%"=="1" goto START_LOCAL
if "%choice%"=="2" goto START_DOCKER
if "%choice%"=="3" goto OPEN_BROWSER
if "%choice%"=="4" goto EXIT

echo Invalid option. Please try again.
timeout /t 2 >nul
goto MENU

:START_LOCAL
echo.
echo Starting Asgard Backend...
start "Asgard Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --reload --port 8000"
echo Waiting for backend to initialize...
timeout /t 5 >nul
start http://localhost:8000
exit /b

:START_DOCKER
echo.
echo Starting Docker containers...
start "Asgard Docker" cmd /k "cd /d "%~dp0" && docker-compose up"
echo Waiting for containers to start...
timeout /t 8 >nul
start http://localhost:8000
exit /b

:OPEN_BROWSER
start http://localhost:8000
exit /b

:EXIT
exit /b
