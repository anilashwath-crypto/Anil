@echo off
rem FOD Guard - install Windows auto-start (run once, from the fod folder or anywhere)
rem Usage:  install_windows.bat <camera-ip> <camera-user> <camera-password> [port]
rem Creates start_fod.bat next to this file and a Task Scheduler entry "FOD Guard"
rem that runs it at every logon, then starts it immediately.
rem NOTE: start_fod.bat contains the camera password in plain text - keep this PC's
rem Windows account protected.
setlocal
if "%~3"=="" (
  echo Usage: %~nx0 ^<camera-ip^> ^<camera-user^> ^<camera-password^> [port]
  exit /b 1
)
set "PORT=%~4"
if "%PORT%"=="" set "PORT=8010"
set "HERE=%~dp0"

> "%HERE%start_fod.bat" (
  echo @echo off
  echo title FOD Guard server
  echo cd /d "%HERE%.."
  echo set FOD_PORT=%PORT%
  echo python fod\home_server.py %~1 %~2 %~3
  echo pause
)

schtasks /Create /F /TN "FOD Guard" /SC ONLOGON /TR "\"%HERE%start_fod.bat\""
if errorlevel 1 (
  echo Could not create the scheduled task - run this window as the normal logged-in user.
  exit /b 1
)
schtasks /Run /TN "FOD Guard"
echo.
echo FOD Guard installed: it now starts automatically at every Windows logon.
echo App on this PC:   http://localhost:%PORT%/fod/index.html
echo To remove later:  schtasks /Delete /F /TN "FOD Guard"
endlocal
