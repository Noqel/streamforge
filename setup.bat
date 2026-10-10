@echo off
setlocal
cd /d "%~dp0"

echo ===================================
echo   StreamForge Setup
echo ===================================
echo.

:: --- 1. Python prüfen ---
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

:: --- 3. Runtime + Build-Tools installieren ---
echo [2/4] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install "setuptools>=68" wheel "cython>=3.0" "setuptools-zig>=0.5" "ziglang<0.16"
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )

:: --- 4. pow_cython kompilieren ---
echo [3/4] Compiling pow_cython...
venv\Scripts\python.exe -m pip install --no-build-isolation -e .
if errorlevel 1 ( echo [ERROR] Build failed. & pause & exit /b 1 )

:: --- 5. Verifizieren ---
echo [4/4] Verifying pow_cython...
venv\Scripts\python.exe -c "from pow_cython import er; print('  OK:', er('test', 8))"
if errorlevel 1 ( echo [ERROR] pow_cython not importable. & pause & exit /b 1 )

:: --- 6. Build-Artefakte aufräumen ---
echo.
echo Cleaning up build artifacts...
if exist build rmdir /s /q build
if exist pow_cython.c del /q pow_cython.c
if exist __pycache__ rmdir /s /q __pycache__

:: --- 7. Build-Bibliotheken aus der venv entfernen (spart ~60 MB) ---
echo Removing build-only libraries...
venv\Scripts\python.exe -m pip uninstall -y cython setuptools-zig ziglang >nul 2>&1

echo.
echo ===================================
echo   Setup complete. Run run.bat to start.
echo ===================================
pause
endlocal
