@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo [%date% %time%] fallback check >> logs\fallback.log
python tools\local_fallback.py >> logs\fallback.log 2>&1
echo [%date% %time%] fallback done, exit=%errorlevel% >> logs\fallback.log
