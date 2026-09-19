@echo off
REM Ouvre l'interface de consultation de l'univers d'investissement.
REM Construit la base au prealable si elle n'existe pas encore.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python...
    python -m venv .venv || goto :erreur
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :erreur
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :erreur
)

if not exist "data\reference.db" (
    echo Base absente, construction en cours...
    ".venv\Scripts\python.exe" tools\construire_base.py || goto :erreur
)

echo Ouverture de l'interface dans le navigateur...
".venv\Scripts\python.exe" -m streamlit run app\univers.py
exit /b 0

:erreur
echo.
echo Echec de la preparation de l'environnement.
pause
exit /b 1
