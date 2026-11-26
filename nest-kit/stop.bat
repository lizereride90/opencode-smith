@echo off
setlocal EnableDelayedExpansion
set "KIT=%~dp0"
if "%KIT:~-1%"=="\" set "KIT=%KIT:~0,-1%"
if not exist "%KIT%\web\server.py" set "KIT=%LOCALAPPDATA%\nest-kit"

echo ==^> stopping nest
for %%F in (web watchdog) do (
  set "PIDFILE=%KIT%\logs\%%F.pid"
  if exist "!PIDFILE!" (
    set /p PID=<!PIDFILE!
    if defined PID (
      powershell -NoProfile -Command "try { Stop-Process -Id !PID! -ErrorAction Stop; Write-Host '  [+] stopped %%F' } catch { Write-Host '  [!] %%F already stopped' }"
    )
    del /Q "!PIDFILE!" >nul 2>&1
  ) else (
    echo   [!] %%F was not running
  )
)
endlocal
