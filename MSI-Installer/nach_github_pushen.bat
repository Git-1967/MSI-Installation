@echo off
REM ====================================================================
REM  Projekt nach GitHub pushen  -  MSI Batch-Installer
REM  --------------------------------------------------------------------
REM  Dieses Skript in den Projektordner legen und doppelklicken.
REM  Es laedt die Quelldateien zu GitHub hoch. Die .gitignore sorgt
REM  dafuer, dass EXE, Build-Reste und Logs NICHT mitgeladen werden.
REM
REM  Voraussetzung: Git ist installiert und der Ordner ist bereits
REM  ein Git-Repository (mit GitHub verbunden).
REM ====================================================================

echo.
echo === MSI Batch-Installer  -  nach GitHub pushen ===
echo.

cd /d "%~dp0"

REM --- Pruefen, ob Git verfuegbar ist ---
git --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Git wurde nicht gefunden.
    echo Bitte Git installieren: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

REM --- Pruefen, ob dies ein Git-Repository ist ---
if not exist ".git" (
    echo Dieser Ordner ist noch kein Git-Repository.
    echo.
    set /p ANTWORT="Jetzt ein neues Repository hier anlegen? (j/n): "
    if /i not "%ANTWORT%"=="j" (
        echo Abgebrochen.
        pause
        exit /b 0
    )
    git init
    echo.
    echo Repository angelegt. Bitte spaeter noch die GitHub-Adresse setzen:
    echo   git remote add origin https://github.com/DEIN-NAME/DEIN-REPO.git
    echo.
)

REM --- Aktuellen Stand zeigen ---
echo Geaenderte Dateien:
git status --short
echo.

REM --- Commit-Beschreibung abfragen ---
set "BESCHREIBUNG="
set /p BESCHREIBUNG="Beschreibung der Aenderung (Enter = Standardtext): "
if "%BESCHREIBUNG%"=="" set "BESCHREIBUNG=MSI-Installer aktualisiert"

REM --- Dateien aufnehmen, einchecken, hochladen ---
echo.
echo Dateien werden aufgenommen ...
git add .

echo Commit wird erstellt ...
git commit -m "%BESCHREIBUNG%"
if errorlevel 1 (
    echo.
    echo Hinweis: Es gab nichts Neues zum Einchecken
    echo          oder der Commit ist fehlgeschlagen.
    echo.
    pause
    exit /b 0
)

echo.
echo Hochladen zu GitHub ...
git push
if errorlevel 1 (
    echo.
    echo FEHLER beim Hochladen.
    echo Moegliche Ursachen:
    echo  - Es ist noch keine GitHub-Adresse gesetzt (git remote add origin ...)
    echo  - Beim ersten Push ggf. noetig: git push -u origin main
    echo  - Anmeldung bei GitHub erforderlich
    echo.
    pause
    exit /b 1
)

echo.
echo === FERTIG - alles wurde zu GitHub hochgeladen ===
echo.
pause
