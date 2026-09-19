@echo off
REM Construit la base locale de l'univers d'investissement.
REM Cree l'environnement Python au premier lancement, puis recharge les fiches.

setlocal
cd /d "%~dp0"

REM Selon l'installation, Python repond a "python" ou seulement au lanceur "py".
set PYTHON=python
where python >nul 2>&1 || set PYTHON=py
%PYTHON% --version >nul 2>&1 || goto :sanspython

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python...
    %PYTHON% -m venv .venv || goto :erreur
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :erreur
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :erreur
)

".venv\Scripts\python.exe" tools\construire_base.py
if errorlevel 1 (
    echo.
    echo La construction a signale des ecarts bloquants. Voir la table anomalie.
    pause
    exit /b 1
)

echo.
echo Base construite : data\reference.db
pause
exit /b 0

:sanspython
echo.
echo Python est introuvable. Installez-le depuis https://www.python.org/downloads/
echo en cochant "Add python.exe to PATH", puis relancez ce fichier.
pause
exit /b 1

:erreur
echo Echec de l'installation de l'environnement Python.
pause
exit /b 1
