@echo off
chcp 65001 > nul
title פלאפון כשר חכם v1.0

echo  פלאפון כשר חכם v1.0 - Smart Kosher Phone
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 ( echo Python לא מותקן - https://python.org & pause & exit /b 1 )

python -c "import PyQt6"     > nul 2>&1 || ( echo מתקין PyQt6...     & pip install PyQt6 --quiet )
python -c "import bleak"       > nul 2>&1 || ( echo מתקין bleak...       & pip install bleak --quiet )
python -c "import sounddevice" > nul 2>&1 || ( echo מתקין sounddevice... & pip install sounddevice --quiet )

echo מפעיל...
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 ( echo שגיאה & pause )
