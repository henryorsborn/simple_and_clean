@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "TOOL=%SCRIPT_DIR%cicd_setup.py"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%TOOL%" %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%TOOL%" %*
  exit /b %errorlevel%
)

echo Python 3 was not found. Install Python 3 to run the CI/CD setup tool.
exit /b 1
