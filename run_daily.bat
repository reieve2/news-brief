@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo [%date% %time%] start >> logs\scheduler.log
python src\main.py >> logs\scheduler.log 2>&1
echo [%date% %time%] done, exit=%errorlevel% >> logs\scheduler.log
