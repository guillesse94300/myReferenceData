@echo off
REM Ouvre l'interface de consultation de l'univers d'investissement.
REM Construit la base et charge les cotations au prealable si besoin.

setlocal
cd /d "%~dp0"
call "_preparer.bat" || exit /b 1

if not exist "data\reference.db" (
    echo Base absente, construction en cours...
    ".venv\Scripts\python.exe" tools\construire_base.py || goto :erreur
)

REM La migration est sans effet si elle a deja eu lieu. Elle est appelee a
REM chaque lancement parce qu'un "git pull" peut faire avancer le schema d'une
REM base qui, elle, ne se reconstruit pas.
".venv\Scripts\python.exe" tools\migrer_cotations.py || goto :erreur

REM Cotations : chargees depuis les captures tant que le collecteur n'existe pas.
if not exist "data\cotations.db" (
    echo Chargement des valeurs liquidatives...
    ".venv\Scripts\python.exe" tools\charger_cotations.py || goto :erreur
)

echo Ouverture de l'interface dans le navigateur, Ctrl+C pour arreter...
".venv\Scripts\python.exe" -m streamlit run app\univers.py
exit /b 0

:erreur
echo.
echo Echec de la preparation. Relisez les messages ci-dessus.
pause
exit /b 1
