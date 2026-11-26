@echo off
setlocal EnableDelayedExpansion
set "KIT=%~dp0"
if "%KIT:~-1%"=="\" set "KIT=%KIT:~0,-1%"
set "CONFIG=%APPDATA%\opencode"
if "%CONFIG%"=="" set "CONFIG=%USERPROFILE%\.config\opencode"
set "PY="
set "ANSWER="

echo(
echo ==> nest // 4080
echo   kit: %KIT%
echo   config: %CONFIG%

REM ---------------------------------------------------------------- python
echo(
echo ==> python
where python >nul 2>&1
if %errorlevel%==0 (
  set "PY=python"
) else (
  where py >nul 2>&1
  if !errorlevel!==0 set "PY=py -3"
)
if defined PY (
  for /f "tokens=*" %%v in ('%PY% --version 2^>^&1') do echo   [+] %%v
) else (
  echo   [!] python not found - config helper, watchdog and UI need it
)

REM ---------------------------------------------------------------- opencode
echo(
echo ==> opencode
where opencode >nul 2>&1
if %errorlevel%==0 (
  echo   [+] opencode already on PATH
) else (
  echo   installing from opencode.ai
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://opencode.ai/install.ps1 | iex"
)
where opencode >nul 2>&1
if %errorlevel%==0 (
  for /f "tokens=*" %%v in ('opencode --version 2^>^&1') do echo   [+] %%v
) else (
  echo   [!] opencode cli not found yet
)

REM ---------------------------------------------------------------- unlimited
echo(
echo ==> opencode unlimited
set "UNLIMITED_DIR="
if exist "%USERPROFILE%\OpenCode-Unlimited\install.ps1" set "UNLIMITED_DIR=%USERPROFILE%\OpenCode-Unlimited"
if not defined UNLIMITED_DIR if exist "%KIT%\..\OpenCode-Unlimited\install.ps1" set "UNLIMITED_DIR=%KIT%\..\OpenCode-Unlimited"
if not defined UNLIMITED_DIR (
  where git >nul 2>&1
  if !errorlevel!==0 (
    echo   cloning Tazmyan/OpenCode-Unlimited
    git clone --depth 1 https://github.com/Tazmyan/OpenCode-Unlimited.git "%USERPROFILE%\OpenCode-Unlimited"
    if exist "%USERPROFILE%\OpenCode-Unlimited\install.ps1" set "UNLIMITED_DIR=%USERPROFILE%\OpenCode-Unlimited"
  ) else (
    echo   [!] git missing - cannot clone Unlimited
  )
)
if defined UNLIMITED_DIR (
  echo   [+] source: !UNLIMITED_DIR!
  powershell -NoProfile -ExecutionPolicy Bypass -File "!UNLIMITED_DIR!\install.ps1"
  set "PATH=!UNLIMITED_DIR!\bin;%PATH%"
) else (
  echo   [!] unlimited not installed; quota resets may be unavailable
)

REM ---------------------------------------------------------------- agent
echo(
echo ==> lowkeyy agent
if not exist "%CONFIG%\agents" mkdir "%CONFIG%\agents"
if exist "%KIT%\assets\lowkeyy.md" (
  copy /Y "%KIT%\assets\lowkeyy.md" "%CONFIG%\agents\lowkeyy.md" >nul
  echo   [+] agent installed: %CONFIG%\agents\lowkeyy.md
) else (
  echo   [!] assets\lowkeyy.md missing
)

if defined PY (
  if exist "%KIT%\lib\configure.py" (
    %PY% "%KIT%\lib\configure.py" --all
    %PY% "%KIT%\lib\configure.py" --show
  )
)

REM ---------------------------------------------------------------- skill
echo(
echo ==> jailbreak-smith skill
if not exist "%CONFIG%\skills" mkdir "%CONFIG%\skills"
if exist "%KIT%\assets\jailbreak-smith.zip" (
  if exist "%TEMP%\nest-skill" rmdir /S /Q "%TEMP%\nest-skill"
  mkdir "%TEMP%\nest-skill"
  powershell -NoProfile -Command "Expand-Archive -LiteralPath '%KIT%\assets\jailbreak-smith.zip' -DestinationPath '%TEMP%\nest-skill' -Force"
  if exist "%CONFIG%\skills\jailbreak-smith" rmdir /S /Q "%CONFIG%\skills\jailbreak-smith"
  xcopy /E /I /Y /Q "%TEMP%\nest-skill\jailbreak-smith\skill" "%CONFIG%\skills\jailbreak-smith" >nul
  echo   [+] skill installed: %CONFIG%\skills\jailbreak-smith
) else (
  echo   [!] assets\jailbreak-smith.zip missing
)

REM ---------------------------------------------------------------- watchdog
echo(
echo ==> quota watchdog
if not exist "%KIT%\logs" mkdir "%KIT%\logs"
if defined PY (
  if exist "%KIT%\lib\watchdog.py" (
    start /b "" %PY% "%KIT%\lib\watchdog.py" >> "%KIT%\logs\watchdog.out" 2>&1
    echo   [+] watchdog started
  )
) else (
  echo   [!] watchdog not started
)

REM ---------------------------------------------------------------- ui choice
echo(
echo ==> web interface
set /p "ANSWER=  Install the localhost web interface? [y/N] "
if /I "%ANSWER%"=="y" goto INSTALLUI
if /I "%ANSWER%"=="yes" goto INSTALLUI
echo   [+] setup complete - terminal only
goto TUTORIAL

:INSTALLUI
if not defined PY (
  echo   [!] python missing - UI cannot start
  goto TUTORIAL
)
set "PORT=8787"
if not "%NEST_UI_PORT%"=="" set "PORT=%NEST_UI_PORT%"
start /b "" %PY% "%KIT%\web\server.py" --host 127.0.0.1 --port %PORT% >> "%KIT%\logs\web.out" 2>&1
echo   [+] web UI on http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"

:TUTORIAL
echo(
echo ==> how to use it
echo   1. Open a terminal and run:  opencode
echo   2. lowkeyy is the default agent. Use /model to switch models.
echo   3. Big Pickle is under the OpenCode provider.
echo   4. The watchdog watches the log and rotates the project id on a limit.
echo   5. Manual reset:   opencode-unlimited reset
echo   6. Skill CLI:
echo        python %%USERPROFILE%%\.config\opencode\skills\jailbreak-smith\scripts\smith.py targets
echo        python %%USERPROFILE%%\.config\opencode\skills\jailbreak-smith\scripts\smith.py payloads
echo   7. Web UI: http://127.0.0.1:8787
echo(
echo   [+] nest is warm. go gnaw.
echo(
endlocal
