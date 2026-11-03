@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Сначала запусти install.bat.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.11,<7"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --onedir --name RF4Notifier --collect-all pyaudiowpatch main.py
if errorlevel 1 (
    pause
    exit /b 1
)
copy /y "INSTALL_RU.txt" "dist\RF4Notifier\INSTALL_RU.txt" >nul
if errorlevel 1 (
    echo Не удалось скопировать инструкцию в папку сборки.
    pause
    exit /b 1
)
echo Готово: dist\RF4Notifier\RF4Notifier.exe. Инструкция: INSTALL_RU.txt.
echo Переноси всю папку RF4Notifier.
pause
