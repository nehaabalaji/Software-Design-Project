@echo off
REM One-time local setup for QueueSmart (Windows).
REM Creates a virtual environment and installs Python dependencies.

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo Error: python is not installed or not on PATH. Install Python 3, then run this again.
  exit /b 1
)

echo Creating virtual environment in .venv ...
python -m venv .venv
if errorlevel 1 exit /b 1

echo Installing dependencies from requirements.txt ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Setup complete.
echo Next steps:
echo   1. Activate the environment:  .venv\Scripts\activate.bat
echo   2. Set up MySQL (one-time):    see BACKEND.md section 1a, then: flask db upgrade
echo   3. Start the API:              python run.py
echo   4. Run tests ^(optional^):     pytest -v
echo.
echo API will be at http://127.0.0.1:5000
echo Open the HTML files in a browser for the frontend ^(login.html, etc.^).
echo.
echo Note: .venv is local to your machine and is not committed to GitHub.
