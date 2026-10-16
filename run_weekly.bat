@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo [%date% %time%] weekly check >> logs\weekly.log
python src\main.py --weekly-only >> logs\weekly.log 2>&1
echo [%date% %time%] weekly done, exit=%errorlevel% >> logs\weekly.log
