@echo off
echo Setting up Autonomous Office Simulation...
echo.

echo Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo Failed to create virtual environment
    exit /b 1
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing Python dependencies...
pip install -r backend\requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    exit /b 1
)

echo.
echo Seeding database...
cd backend
python seed.py
cd ..

echo.
echo Setup complete!
echo.
echo To start the simulation:
echo   1. Activate the virtual environment: venv\Scripts\activate.bat
echo   2. Run: cd backend && python main.py
echo   3. Open http://localhost:8000 in your browser
echo.

pause


