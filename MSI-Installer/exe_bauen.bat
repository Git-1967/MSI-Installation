@echo off
REM ====================================================================
REM  EXE bauen fuer den MSI Batch-Installer
REM  --------------------------------------------------------------------
REM  Dieses Skript muss neben "msi_installer_admin.py" liegen.
REM  Einfach doppelklicken - es installiert PyInstaller (falls noetig)
REM  und erzeugt die fertige EXE im Unterordner "dist".
REM ====================================================================

echo.
echo === MSI Batch-Installer  -  EXE erstellen ===
echo.

REM In das Verzeichnis dieses Skripts wechseln
cd /d "%~dp0"

REM Pruefen, ob die Quelldatei vorhanden ist
if not exist "msi_installer_admin.py" (
    echo FEHLER: "msi_installer_admin.py" wurde nicht gefunden.
    echo Bitte dieses Skript in denselben Ordner wie die .py-Datei legen.
    echo.
    pause
    exit /b 1
)

REM Pruefen, ob Python erreichbar ist
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python wurde nicht gefunden.
    echo Bitte Python installieren und beim Setup "Add to PATH" aktivieren.
    echo.
    pause
    exit /b 1
)

echo Schritt 1/2: PyInstaller installieren bzw. aktualisieren ...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo FEHLER: PyInstaller konnte nicht installiert werden.
    echo.
    pause
    exit /b 1
)

echo.
echo Schritt 2/2: EXE wird gebaut ...
echo.

REM  --onefile     : alles in eine einzige EXE
REM  --windowed    : kein schwarzes Konsolenfenster
REM  --uac-admin   : EXE fordert beim Start Admin-Rechte an (UAC-Abfrage)
REM  --clean       : Reste frueherer Builds entfernen
python -m PyInstaller --onefile --windowed --uac-admin --clean ^
    --name "MSI-Batch-Installer" msi_installer_admin.py

if errorlevel 1 (
    echo.
    echo FEHLER: Der Build ist fehlgeschlagen.
    echo.
    pause
    exit /b 1
)

echo.
echo === FERTIG ===
echo Die EXE liegt hier:
echo   %~dp0dist\MSI-Batch-Installer.exe
echo.
pause
