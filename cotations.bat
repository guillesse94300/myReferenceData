@echo off
REM Met a jour la base des valeurs liquidatives.
REM
REM Sans argument : migration si besoin, chargement des captures, puis
REM SIMULATION de l'import des releves de data\raw\vl. Rien n'est ecrit par
REM l'import -- une base qui s'accumule ne se reconstruit pas, on regarde avant.
REM
REM   cotations.bat            simule l'import des releves
REM   cotations.bat --ecrire   ecrit

setlocal
cd /d "%~dp0"
call "_preparer.bat" || exit /b 1

if not exist "data\reference.db" (
    echo Base de reference absente, construction en cours...
    ".venv\Scripts\python.exe" tools\construire_base.py || goto :erreur
)

".venv\Scripts\python.exe" tools\migrer_cotations.py || goto :erreur
echo.
".venv\Scripts\python.exe" tools\charger_cotations.py || goto :erreur
echo.
".venv\Scripts\python.exe" tools\importer_vl.py %* || goto :erreur

if "%~1"=="" (
    echo.
    echo SIMULATION : rien n'a ete ecrit par l'import des releves.
    echo Relancez avec   cotations.bat --ecrire   pour ecrire.
)
pause
exit /b 0

:erreur
echo.
echo Echec. Relisez les messages ci-dessus.
pause
exit /b 1
