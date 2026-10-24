@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Math Modeling Paper Review - Launcher
rem ============================================================
rem  One-click launcher: build frontend if needed, start FastAPI,
rem  then open the workbench in the default browser.
rem
rem  Usage:
rem    start-workbench.cmd                   default port 8000
rem    start-workbench.cmd /port 8010        pick a port
rem    start-workbench.cmd /dev              dev mode (uvicorn --reload, skip build check)
rem    start-workbench.cmd /rebuild          rebuild frontend even if dist exists
rem ============================================================

cd /d "%~dp0"
set "PORT=8000"
set "DEV=0"
set "REBUILD=0"

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="/port" goto set_port
if /i "%~1"=="/dev" goto set_dev
if /i "%~1"=="/rebuild" goto set_rebuild
echo [Error] Unknown argument: %~1
goto usage
:set_port
if "%~2"=="" goto usage
set "PORT=%~2"
shift
shift
goto parse
:set_dev
set "DEV=1"
shift
goto parse
:set_rebuild
set "REBUILD=1"
shift
goto parse
:parsed

if exist ".venv\Scripts\python.exe" goto venv_ok
echo [Error] Virtual env .venv not found. Install dependencies first:
echo        py -m venv .venv
echo        .venv\Scripts\python.exe -m pip install -r requirements.txt
pause
exit /b 1
:venv_ok

if "%DEV%"=="1" goto start_server

if exist "frontend\dist\index.html" goto check_rebuild
echo [Info] Frontend build not found, building now...
call :build_frontend
if errorlevel 1 goto build_fail
goto start_server

:check_rebuild
if not "%REBUILD%"=="1" goto use_existing
echo [Info] /rebuild given, rebuilding frontend...
call :build_frontend
if errorlevel 1 goto build_fail
goto start_server
:use_existing
echo [Info] Using existing build at frontend\dist (add /rebuild to force rebuild).

:start_server
echo.
echo ============================================================
echo   Starting FastAPI  http://127.0.0.1:%PORT%/#/overview
echo   Close this window or press Ctrl+C to stop.
echo ============================================================
echo.

rem Delay 2s so uvicorn is listening before opening the browser.
start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:%PORT%/#/overview"

if "%DEV%"=="1" goto run_dev
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port %PORT%
goto run_end
:run_dev
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port %PORT%

:run_end
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Server exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:build_fail
echo.
echo [Error] Frontend build failed. Check npm / node and retry.
pause
exit /b 1

:build_frontend
if not exist "frontend\package.json" goto bf_no_package
if not exist "frontend\node_modules" goto bf_install
goto bf_build
:bf_no_package
echo [Error] frontend\package.json missing; project layout looks wrong.
exit /b 1
:bf_install
echo [Info] node_modules not found, running npm install...
call npm install --prefix frontend
if errorlevel 1 exit /b 1
:bf_build
call npm run build --prefix frontend
exit /b %ERRORLEVEL%

:usage
echo Usage: start-workbench.cmd [/port PORT] [/dev] [/rebuild]
exit /b 1