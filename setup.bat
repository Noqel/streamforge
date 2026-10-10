@echo off
echo ===================================
echo   			   Setup
echo ===================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden.
    echo Bitte installiere Python 3.10+ von https://www.python.org/downloads/
    echo Wichtig: "Add Python to PATH" beim Installieren anhaken!
    pause
    exit /b 1
)

echo [1/3] Erstelle virtuelle Umgebung...
python -m venv venv
if errorlevel 1 (
    echo [FEHLER] venv konnte nicht erstellt werden.
    pause
    exit /b 1
)

echo [2/3] Installiere Abhaengigkeiten...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [FEHLER] pip install fehlgeschlagen.
    pause
    exit /b 1
)

echo [3/3] Pruefe PoW-Modul...
venv\Scripts\python.exe -c "from pow_cython import er; print('  OK:', er('test', 8))"
if errorlevel 1 (
    echo [WARNUNG] pow_cython nicht ladbar.
    echo Das Modul wurde fuer Python 3.12 / Windows 64-bit gebaut.
    pause
    exit /b 1
)

echo.
echo ===================================
echo   Setup abgeschlossen!
echo   Starte mit: run.bat
echo ===================================
pause