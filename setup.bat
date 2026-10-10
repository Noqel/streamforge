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
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         Make sure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)

:: --- 2. venv anlegen (falls noch nicht vorhanden) ---
echo [1/4] Creating virtual environment...
if exist "venv\Scripts\python.exe" (
    echo       venv already exists, skipping.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

:: --- 3. Dependencies installieren ---
echo [2/4] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

:: --- 4. pow_cython mit zig cc kompilieren ---
echo [3/4] Compiling pow_cython with zig cc...

venv\Scripts\python.exe setup.py build_ext --inplace --force
if errorlevel 1 (
    echo.
    echo [ERROR] Cython build failed. See output above.
    pause
    exit /b 1
)

:: --- 5. Verifizieren ---
echo [4/4] Verifying pow_cython...
venv\Scripts\python.exe -c "from pow_cython import er; print('  OK:', er('test', 8))"
if errorlevel 1 (
    echo [ERROR] pow_cython could not be imported after build.
    echo         Check that the .pyd file was created in the project folder.
    pause
    exit /b 1
)

echo.
echo ===================================
echo   Setup complete. Run run.bat to start.
echo ===================================
pause
endlocal