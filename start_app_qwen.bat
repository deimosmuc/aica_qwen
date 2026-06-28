@echo off
REM ===================================================================
REM  AI Circuit Architect - Start with REAL Qwen agents (Live Mode)
REM  Doppelklick genuegt. Das Skript erledigt alles selbst:
REM    - wechselt ins Projektverzeichnis
REM    - legt bei Bedarf die venv an und installiert die Abhaengigkeiten
REM    - prueft, ob ein echter QWEN_API_KEY in .env steht (Live vs. Mock)
REM    - oeffnet den Browser
REM    - startet den Server
REM ===================================================================
setlocal enabledelayedexpansion
title AI Circuit Architect - Qwen Live

REM --- immer relativ zum Speicherort dieser .bat arbeiten ---
cd /d "%~dp0"

echo.
echo  ===============================================
echo   AI Circuit Architect  -  Qwen Live Mode
echo  ===============================================
echo.

REM --- 1) venv sicherstellen ---
if not exist ".venv\Scripts\python.exe" (
    echo  [setup] Keine venv gefunden - lege eine an...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo  [FEHLER] Konnte keine venv anlegen. Ist Python installiert und im PATH?
        echo.
        pause
        exit /b 1
    )
    echo  [setup] Installiere Abhaengigkeiten ^(einmalig, kann ein paar Minuten dauern^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [FEHLER] pip install ist fehlgeschlagen. Bitte Ausgabe oben pruefen.
        echo.
        pause
        exit /b 1
    )
)

REM --- 2) Live- vs. Mock-Mode anzeigen ---
set "LIVE=0"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /i "%%A"=="QWEN_API_KEY" if not "%%B"=="" set "LIVE=1"
    )
)
if "!LIVE!"=="1" (
    echo  [ok] QWEN_API_KEY gefunden  -^>  LIVE MODE ^(echte Qwen-Agents^)
) else (
    echo  [hinweis] Kein QWEN_API_KEY in .env  -^>  MOCK MODE ^(Demo-Daten^)
    echo            Key in .env eintragen, um die echten Agents zu nutzen.
)
echo.

REM --- 3) Browser oeffnen (leicht verzoegert, damit der Server bereit ist) ---
echo  [start] Oeffne http://localhost:8000 ...
start "" /b cmd /c "timeout /t 3 >nul & start "" http://localhost:8000"

REM --- 4) Server starten (laeuft in diesem Fenster; mit STRG+C beenden) ---
echo  [start] Starte Server  -  zum Beenden dieses Fenster schliessen oder STRG+C.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo  Server beendet.
pause
