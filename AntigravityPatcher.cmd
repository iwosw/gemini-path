@echo off
where pyw.exe >nul 2>&1
if errorlevel 1 goto fallback
start "" pyw.exe -3 "%~dp0antigravity_gui.py"
exit /b 0

:fallback
py.exe -3 "%~dp0antigravity_gui.py"
if errorlevel 1 (
    echo Python 3 with Tkinter is required. See README.md.
    pause
)
