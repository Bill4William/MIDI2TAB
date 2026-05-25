@echo off
setlocal
cd /d "%~dp0.."

echo ==================================================
echo   MIDI2TAB Build Script
echo ==================================================
echo.

rem --- Python detection ---
rem Use --version as the test to avoid cmd variable-expansion timing
rem issues and zero-byte Microsoft Store stub executables.

set "PY=C:\Users\Cygnet\AppData\Local\Python\bin\python.exe"
"%PY%" --version >nul 2>&1
if not errorlevel 1 goto :found_python

rem Fallback: any "python" on PATH that actually runs
set "PY=python"
"%PY%" --version >nul 2>&1
if not errorlevel 1 goto :found_python

echo ERROR: Python not found.
echo Expected: C:\Users\Cygnet\AppData\Local\Python\bin\python.exe
goto :fail

:found_python
echo Using Python: %PY%
echo.

rem --- Step 1: Generate icon ---
echo [1/3] Generating icon...
"%PY%" assets\create_icon.py
if errorlevel 1 (
    echo ERROR: Icon generation failed.
    goto :fail
)
echo.

rem --- Step 2: PyInstaller ---
echo [2/3] Bundling application with PyInstaller...
"%PY%" -m PyInstaller build\MIDI2TAB.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    goto :fail
)
echo.

rem --- Step 3: Inno Setup ---
echo [3/3] Looking for Inno Setup...
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo  Inno Setup is not installed.
    echo  The bundled app is ready in:  dist\MIDI2TAB\
    echo.
    echo  To create the Windows installer:
    echo    1. Download Inno Setup 6 ^(free^) from https://jrsoftware.org/isinfo.php
    echo    2. Install it
    echo    3. Re-run this script, or compile manually:
    echo       "C:\Program Files ^(x86^)\Inno Setup 6\ISCC.exe" build\installer.iss
    echo.
    goto :success_no_installer
)

echo    Found: %ISCC%
if not exist "installer_output" mkdir installer_output
"%ISCC%" build\installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    goto :fail
)

echo.
echo ==================================================
echo   SUCCESS
echo   Installer: installer_output\MIDI2TAB_Setup_v1.0.0.exe
echo ==================================================
goto :done

:success_no_installer
echo ==================================================
echo   BUILD COMPLETE  ^(no installer -- see above^)
echo   App folder: dist\MIDI2TAB\
echo ==================================================
goto :done

:fail
echo.
echo ==================================================
echo   BUILD FAILED
echo ==================================================
pause
exit /b 1

:done
pause
