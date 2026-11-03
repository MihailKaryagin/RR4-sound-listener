@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Установи Python 3.12 с python.org с компонентом Tcl/Tk и Python Launcher.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Не удалось установить зависимости. Проверь интернет.
    pause
    exit /b 1
)
echo Готово. Запускай start.bat.
pause
