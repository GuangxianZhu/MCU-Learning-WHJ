@echo off
rem ============================================================
rem  MCU 3D Classroom - one-click launcher for Windows
rem  Double-click this file. It will:
rem    1. find Python 3.8-3.13 (install Python 3.12 silently if missing)
rem    2. create a private environment in .venv
rem    3. install / check the packages in requirements.txt
rem    4. start the course
rem  Messages are in English on purpose: Chinese text inside .bat
rem  files breaks on some Windows language settings.
rem ============================================================
setlocal EnableExtensions DisableDelayedExpansion
title MCU 3D Classroom
cd /d "%~dp0"

set "PYVER=3.12.7"
set "VENV=%~dp0.venv"
set "VPY=%~dp0.venv\Scripts\python.exe"
set "STAMP=%~dp0.venv\requirements.stamp"
set "PIPUSER="
set "MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"

echo ============================================
echo    MCU 3D Classroom - one-click launcher
echo ============================================
echo.

rem ---------- 1. reuse an existing, working .venv ----------
if not exist "%VPY%" goto :need_python
"%VPY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto :deps
echo [..] The old .venv folder is broken, rebuilding it...
rmdir /s /q "%VENV%" >nul 2>&1

:need_python
call :find_python
if defined PY goto :make_venv
echo [..] Python 3.8-3.13 was not found on this computer.
echo [..] Installing Python %PYVER% automatically, please wait (a few minutes)...
call :install_python
call :find_python
if defined PY goto :make_venv
echo [x] Python could not be installed automatically.
echo     Please install Python 3.12 from https://www.python.org/downloads/
echo     ^(tick "Add python.exe to PATH"^), then double-click this file again.
goto :fail

:make_venv
echo [ok] Python found: %PY%
echo [..] Creating the private environment .venv ...
"%PY%" -m venv "%VENV%" >nul 2>&1
if exist "%VPY%" goto :deps
echo [!] Could not create .venv, using Python directly instead.
set "VPY=%PY%"
set "STAMP=%TEMP%\mcu3d_requirements.stamp"
set "PIPUSER=--user"

rem ---------- 2. check / install requirements ----------
:deps
if not exist "%STAMP%" goto :install_deps
fc /b "requirements.txt" "%STAMP%" >nul 2>&1
if errorlevel 1 goto :install_deps
"%VPY%" -c "import panda3d" >nul 2>&1
if errorlevel 1 goto :install_deps
echo [ok] Packages are already installed.
goto :run

:install_deps
echo [..] Installing packages from requirements.txt ...
"%VPY%" -m pip install --disable-pip-version-check %PIPUSER% -r requirements.txt
if not errorlevel 1 goto :deps_ok
echo [..] Download failed, retrying with a mirror server...
"%VPY%" -m pip install --disable-pip-version-check %PIPUSER% -r requirements.txt -i %MIRROR%
if not errorlevel 1 goto :deps_ok
"%VPY%" -c "import panda3d" >nul 2>&1
if errorlevel 1 goto :deps_fail
echo [!] Could not update packages ^(offline?^), starting with what is installed.
goto :run

:deps_ok
copy /y "requirements.txt" "%STAMP%" >nul 2>&1
echo [ok] Packages are ready.
goto :run

:deps_fail
echo [x] Installing packages failed. Please check the internet connection
echo     and double-click this file again.
goto :fail

rem ---------- 3. start ----------
:run
echo [..] Starting MCU 3D Classroom...
echo.
"%VPY%" -m mcu3d
if errorlevel 1 goto :run_fail
exit /b 0

:run_fail
echo.
echo [x] The program stopped with an error ^(see the messages above^).
goto :fail

:fail
echo.
echo Press any key to close this window.
pause >nul
exit /b 1


rem ============================================================
rem  Subroutines
rem ============================================================

rem Sets PY to the full path of a usable python.exe, or leaves it empty.
:find_python
set "PY="
for %%V in (3.12 3.11 3.13 3.10 3.9 3.8) do if not defined PY call :try_py py -%%V
if not defined PY call :try_py python
if not defined PY call :try_py python3
for %%D in ("%LocalAppData%\Programs\Python\Python312" "%LocalAppData%\Programs\Python\Python311" "%ProgramFiles%\Python312" "%ProgramFiles%\Python311") do if not defined PY if exist "%%~D\python.exe" call :try_py "%%~D\python.exe"
exit /b 0

rem Runs the given command and accepts it if it is Python 3.8-3.13.
rem (The fake "python" from the Microsoft Store prints nothing, so it is skipped.)
:try_py
set "CAND="
set "PYTMP=%TEMP%\mcu3d_python_path.txt"
del "%PYTMP%" >nul 2>&1
%* -c "import sys; v=sys.version_info[:2]; print(sys.executable) if (3,8)<=v<=(3,13) else None" >"%PYTMP%" 2>nul
if exist "%PYTMP%" set /p CAND=<"%PYTMP%"
del "%PYTMP%" >nul 2>&1
if not defined CAND exit /b 0
if exist "%CAND%" set "PY=%CAND%"
exit /b 0

rem Installs Python silently for the current user (no admin rights needed).
:install_python
where winget >nul 2>&1
if errorlevel 1 goto :download_python
echo [..] Trying winget...
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
call :find_python
if defined PY exit /b 0

:download_python
set "PYARCH=-amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 set "PYARCH="
set "PYFILE=python-%PYVER%%PYARCH%.exe"
set "PYINST=%TEMP%\%PYFILE%"
echo [..] Downloading %PYFILE% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $urls=@('https://www.python.org/ftp/python/%PYVER%/%PYFILE%','https://registry.npmmirror.com/-/binary/python/%PYVER%/%PYFILE%'); foreach($u in $urls){ try { Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $env:PYINST; exit 0 } catch {} }; exit 1"
if errorlevel 1 exit /b 1
if not exist "%PYINST%" exit /b 1
echo [..] Installing Python %PYVER% ...
"%PYINST%" /quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Shortcuts=0
del "%PYINST%" >nul 2>&1
exit /b 0
