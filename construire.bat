@echo off
REM Construit la base locale de l'univers d'investissement.

setlocal
cd /d "%~dp0"
call "_preparer.bat" || exit /b 1

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
