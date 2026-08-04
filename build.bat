@echo off
chcp 65001 > nul
title Build - Smart Kosher Phone v1.0

echo  Smart Kosher Phone v1.0 - Build
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 ( echo Python לא מותקן & pause & exit /b 1 )

echo בחר סוג קומפיל:
echo   1  קובץ EXE בודד (הכל כלול, ~70MB)
echo   2  תיקיית standalone (EXE קטן + קבצי משנה)
echo.
set /p CHOICE=הכנס 1 או 2: 

pip install nuitka zstandard ordered-set PyQt6 bleak sounddevice vosk --quiet

if "%CHOICE%"=="1" goto :onefile
if "%CHOICE%"=="2" goto :onedir
goto :onefile

:onefile
echo [קובץ אחד] מקמפל...
python -m nuitka ^
  --standalone --onefile ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=app\resources\icon.ico ^
  --output-filename=SmartKosherPhone.exe ^
  --output-dir=dist ^
  --include-package=app --include-package=bleak --include-package=vosk ^
  --include-data-dir=app\resources=app\resources ^
  --include-data-files=app\style_light.qss=app\style_light.qss ^
  --include-data-files=app\style_dark.qss=app\style_dark.qss ^
  --plugin-enable=pyqt6 ^
  --windows-product-name="Smart Kosher Phone" ^
  --windows-product-version=1.0.0.0 ^
  --windows-company-name="Smart Kosher Phone Project" ^
  --windows-file-description="פלאפון כשר חכם v1.0" ^
  main.py
if %errorlevel% equ 0 ( echo הצלחה: dist\SmartKosherPhone.exe ) else ( goto :pyi_onefile )
goto :done

:onedir
echo [תיקיה] מקמפל...
python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=app\resources\icon.ico ^
  --output-filename=SmartKosherPhone.exe ^
  --output-dir=dist_dir ^
  --include-package=app --include-package=bleak --include-package=vosk ^
  --include-data-dir=app\resources=app\resources ^
  --include-data-files=app\style_light.qss=app\style_light.qss ^
  --include-data-files=app\style_dark.qss=app\style_dark.qss ^
  --plugin-enable=pyqt6 ^
  main.py
if %errorlevel% equ 0 ( echo הצלחה: dist_dir\SmartKosherPhone.dist\ ) else ( goto :pyi_onedir )
goto :done

:pyi_onefile
echo Nuitka נכשל, מנסה PyInstaller (קובץ אחד)...
pip install pyinstaller --quiet
pyinstaller --onefile --windowed --name SmartKosherPhone --distpath dist ^
  --add-data "app\style_light.qss;app" --add-data "app\style_dark.qss;app" ^
  --add-data "app\resources;app\resources" ^
  --hidden-import bleak --hidden-import bleak.backends.winrt ^
  --hidden-import vosk --hidden-import sounddevice ^
  --hidden-import PyQt6.QtMultimedia main.py
goto :done

:pyi_onedir
echo Nuitka נכשל, מנסה PyInstaller (תיקיה)...
pip install pyinstaller --quiet
pyinstaller --onedir --windowed --name SmartKosherPhone --distpath dist_dir ^
  --add-data "app\style_light.qss;app" --add-data "app\style_dark.qss;app" ^
  --add-data "app\resources;app\resources" ^
  --hidden-import bleak --hidden-import bleak.backends.winrt ^
  --hidden-import vosk --hidden-import sounddevice ^
  --hidden-import PyQt6.QtMultimedia main.py

:done
echo.
pause
