@echo off
REM Resout un interpreteur Python et prepare .venv. Appele par les autres
REM scripts : la detection vivait en double dans lancer.bat et construire.bat,
REM et un troisieme script en aurait fait une troisieme copie.
REM
REM Les appelants utilisent ensuite ".venv\Scripts\python.exe" directement.

cd /d "%~dp0"

REM Le lanceur "py" est essaye en premier : il est installe dans C:\Windows avec
REM Python et ne depend pas du PATH. "python" vient ensuite, mais Windows 11
REM place un raccourci factice vers le Microsoft Store a ce nom : chaque
REM candidat est donc reellement execute, et non simplement cherche sur le PATH.
set "PYTHON="
py -3 -c "" >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (py -c "" >nul 2>&1 && set "PYTHON=py")
if not defined PYTHON (python -c "" >nul 2>&1 && set "PYTHON=python")
if not defined PYTHON (python3 -c "" >nul 2>&1 && set "PYTHON=python3")
if not defined PYTHON goto :sanspython

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python avec "%PYTHON%"...
    %PYTHON% -m venv .venv || goto :erreur
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :erreur
)

REM Les dependances ne sont reinstallees que si la liste a change depuis la
REM derniere fois : sans cette comparaison, une dependance ajoutee par un
REM "git pull" resterait absente et le script echouerait a l'import.
set "REINSTALLER="
if not exist ".venv\requirements-installees.txt" set "REINSTALLER=1"
if not defined REINSTALLER (
    fc /b requirements.txt ".venv\requirements-installees.txt" >nul 2>&1 || set "REINSTALLER=1"
)
if defined REINSTALLER (
    echo Installation des dependances, quelques minutes au premier lancement...
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :erreur
    copy /y requirements.txt ".venv\requirements-installees.txt" >nul
)
exit /b 0

:sanspython
echo.
echo Aucun interpreteur Python utilisable n'a repondu.
echo Les commandes essayees sont : py -3, py, python, python3.
echo.
echo Installez Python depuis https://www.python.org/downloads/ en cochant
echo "Add python.exe to PATH", puis relancez ce fichier.
echo.
echo Si Python est deja installe, ouvrez une invite de commandes et lancez
echo   py --version
echo puis envoyez le resultat.
pause
exit /b 1

:erreur
echo.
echo Echec de la preparation de l'environnement Python.
echo Relisez les messages ci-dessus : ils indiquent l'etape en cause.
pause
exit /b 1
