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
    pause
    exit /b 1
)

:: --- 2. venv anlegen ---
echo [1/4] Creating virtual environment...
if exist "venv\Scripts\python.exe" (
    echo       venv already exists, skipping.
) else (
    python -m venv venv
    if errorlevel 1 ( echo [ERROR] venv failed. & pause & exit /b 1 )
)

:: --- 3. Dependencies + Build-Tools ---
echo [2/4] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install "setuptools>=68" wheel "cython>=3.0" "setuptools-zig>=0.5" "ziglang<0.16"
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )

:: --- 4. Package + Extension bauen ---
echo [3/4] Compiling pow_cython...
venv\Scripts\python.exe -m pip install --no-build-isolation -e .
if errorlevel 1 ( echo [ERROR] Build failed. & pause & exit /b 1 )

:: --- 5. Verifizieren ---
echo [4/4] Verifying installation...
venv\Scripts\python.exe -c "from streamforge.pow import er; print('  pow OK:', er('test', 8))"
if errorlevel 1 ( echo [ERROR] streamforge.pow not importable. & pause & exit /b 1 )

venv\Scripts\python.exe -c "import streamforge.cli; print('  cli OK')"
if errorlevel 1 ( echo [ERROR] streamforge.cli not importable. & pause & exit /b 1 )

:: --- 6. Build-Artefakte aufraeumen ---
echo.
echo Cleaning up build artifacts...
if exist build rmdir /s /q build
if exist src\streamforge\pow\pow_cython.c del /q src\streamforge\pow\pow_cython.c
if exist src\streamforge\__pycache__ rmdir /s /q src\streamforge\__pycache__

echo Removing build-only libraries...
venv\Scripts\python.exe -m pip uninstall -y cython setuptools-zig ziglang >nul 2>&1

echo.
echo ===================================
echo   Setup complete. Run run.bat to start.
echo ===================================
pause
endlocal