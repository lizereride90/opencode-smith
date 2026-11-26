@echo off
setlocal EnableDelayedExpansion
set "KIT=%~dp0"
if "%KIT:~-1%"=="\" set "KIT=%KIT:~0,-1%"
if not exist "%KIT%\web\server.py" set "KIT=%LOCALAPPDATA%\nest-kit"

echo ==^> starting nest
if not exist "%KIT%\logs" mkdir "%KIT%\logs"

set "PY=python"
where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if !errorlevel!==0 set "PY=py -3"
)

powershell -NoProfile -Command ^
  "$p = Start-Process -FilePath '%PY%' -ArgumentList '\"%KIT%\lib\watchdog.py\"' -PassThru -WindowStyle Hidden; $p.Id | Out-File -FilePath '%KIT%\logs\watchdog.pid' -Encoding ascii"
echo   [+] watchdog started

powershell -NoProfile -Command ^
  "$p = Start-Process -FilePath '%PY%' -ArgumentList '\"%KIT%\web\server.py\"','--host','127.0.0.1','--port','8787' -PassThru -WindowStyle Hidden; $p.Id | Out-File -FilePath '%KIT%\logs\web.pid' -Encoding ascii"
echo   [+] chat UI on http://127.0.0.1:8787
endlocal
