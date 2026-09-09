@echo off
REM servicectl doctor — Windows shortcut launcher
REM
REM Double-click this file to run servicectl doctor against the
REM current directory. The --pause flag keeps the window open so
REM you can read the output before it closes.

cd /d "%~dp0"
python -m servicectl doctor . --pause
