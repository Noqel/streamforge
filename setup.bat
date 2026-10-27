@echo off
setlocal
cd /d "%~dp0"

echo ===================================
echo   StreamForge Setup
echo ===================================
echo.

:: --- 1. Python pruefen ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         Make sure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)

:: --- 2. venv anlegen ---
echo [1/5] Creating virtual environment...
if exist "venv\Scripts\python.exe" (
    echo       venv already exists, skipping.
) else (
    python -m venv venv
    if errorlevel 1 ( echo [ERROR] venv failed. & pause & exit /b 1 )
)

:: --- 3. Dependencies installieren ---
echo [2/5] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install "setuptools>=68" wheel "cython>=3.0" "setuptools-zig>=0.5" "ziglang<0.16"
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )

:: --- 4. Package + Extension bauen ---
echo [3/5] Compiling pow_cython...
venv\Scripts\python.exe -m pip install --no-build-isolation -e .
if errorlevel 1 ( echo [ERROR] Build failed. & pause & exit /b 1 )

:: --- 5. Verifizieren ---
echo [4/5] Verifying installation...
venv\Scripts\python.exe -c "from streamforge.pow import er; print('  pow OK:', er('test', 8))"
if errorlevel 1 ( echo [ERROR] streamforge.pow not importable. & pause & exit /b 1 )

venv\Scripts\python.exe -c "import streamforge.cli; print('  cli OK')"
if errorlevel 1 ( echo [ERROR] streamforge.cli not importable. & pause & exit /b 1 )

:: --- 6. Optional: mpv + Anime4K ---
echo.
echo [5/5] Optional: Install mpv and Anime4K
echo.
set /p INSTALL_MPV="Download mpv and install Anime4K? [y/N]: "
if /i not "%INSTALL_MPV%"=="y" goto :skip_mpv

echo.
echo Which GPU tier do you have?
echo   [1] Low-end  (GTX 980, 1060, RX 570)
echo   [2] High-end (GTX 1080, RTX 2070, 3060, RX 590, Vega 56)
set /p A4K_TIER="Choose [1/2] (default 1): "
if "%A4K_TIER%"=="2" (
    set "A4K_VARIANT=high"
) else (
    set "A4K_VARIANT=low"
)

echo.
echo Installing mpv and Anime4K...
venv\Scripts\python.exe -m streamforge.player_setup --variant %A4K_VARIANT% --target portable
if errorlevel 1 (
    echo.
    echo [WARNUNG] mpv/Anime4K-Installation fehlgeschlagen.
    echo Manuell nachholen:
    echo   venv\Scripts\python.exe -m streamforge.player_setup --variant %A4K_VARIANT%
)

:skip_mpv

:: --- 7. Build-Artefakte aufraeumen ---
echo.
echo Cleaning up build artifacts...
if exist build rmdir /s /q build
if exist src\streamforge\pow\pow_cython.c del /q src\streamforge\pow\pow_cython.c
if exist src\streamforge\__pycache__ rmdir /s /q src\streamforge\__pycache__

echo Removing build-only libraries...
venv\Scripts\python.exe -m pip uninstall -y cython setuptools-zig ziglang >nul 2>&1

echo.
echo ===================================
echo   Setup complete.
echo   Start with: run.bat
echo ===================================
pause
endlocal
