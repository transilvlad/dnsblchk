@echo off
REM DNS Block List Checker local runner for Windows.
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "MAIN_PY=%SCRIPT_DIR%\main.py"
set "DEFAULT_CONFIG=%SCRIPT_DIR%\config\config-local.yaml"
set "EXTENDED_CONFIG=%SCRIPT_DIR%\config\config-local-extended.yaml"
set "USE_EXTENDED=false"
set "CUSTOM_CONFIG="

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="-e" set "USE_EXTENDED=true" & shift & goto parse_args
if /i "%~1"=="--extended" set "USE_EXTENDED=true" & shift & goto parse_args
if /i "%~1"=="-c" set "CUSTOM_CONFIG=%~2" & shift & shift & goto parse_args
if /i "%~1"=="--config" set "CUSTOM_CONFIG=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-h" call :show_help & exit /b 0
if /i "%~1"=="--help" call :show_help & exit /b 0
if /i "%~1"=="-v" shift & goto parse_args
if /i "%~1"=="--verbose" shift & goto parse_args
echo [ERROR] Unknown option: %~1
call :show_help
exit /b 1

:args_done
call :main
exit /b %errorlevel%

:show_help
echo.
echo DNS Block List Checker - Local Runner
echo.
echo USAGE:
echo   run.bat [OPTIONS]
echo.
echo OPTIONS:
echo   -e, --extended       Use config\config-local-extended.yaml
echo   -c, --config PATH    Use a custom config file
echo   -v, --verbose        Show verbose runner output
echo   -h, --help           Show this help message
echo.
exit /b 0

:main
echo.
echo ^>^>^> Starting dnsblchk Local Runner

if not exist "%MAIN_PY%" (
    echo [ERROR] main.py not found: %MAIN_PY%
    exit /b 1
)

if not "%CUSTOM_CONFIG%"=="" (
    set "CONFIG_FILE=%CUSTOM_CONFIG%"
    if not exist "!CONFIG_FILE!" set "CONFIG_FILE=%SCRIPT_DIR%\%CUSTOM_CONFIG%"
) else if "%USE_EXTENDED%"=="true" (
    set "CONFIG_FILE=%EXTENDED_CONFIG%"
) else (
    set "CONFIG_FILE=%DEFAULT_CONFIG%"
)

if not exist "!CONFIG_FILE!" (
    echo [ERROR] Config file not found: !CONFIG_FILE!
    echo Restore config\config-local.yaml or pass --config PATH.
    exit /b 1
)

set "PYTHON_EXE="
for %%p in (python3.exe python.exe) do (
    if "!PYTHON_EXE!"=="" (
        where /q %%p
        if !errorlevel! equ 0 (
            for /f "delims=" %%i in ('where %%p') do if "!PYTHON_EXE!"=="" set "PYTHON_EXE=%%i"
        )
    )
)
if "!PYTHON_EXE!"=="" if defined VIRTUAL_ENV if exist "!VIRTUAL_ENV!\Scripts\python.exe" set "PYTHON_EXE=!VIRTUAL_ENV!\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%\.venv\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%\venv\Scripts\python.exe"

if "!PYTHON_EXE!"=="" (
    echo [ERROR] Python 3.10+ not found in PATH or virtual environments
    exit /b 1
)

echo [INFO] Python: !PYTHON_EXE!
echo [INFO] Config file: !CONFIG_FILE!

cd /d "%SCRIPT_DIR%"
"!PYTHON_EXE!" "%MAIN_PY%" "!CONFIG_FILE!"
exit /b %errorlevel%
