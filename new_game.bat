@echo off
echo ========================================
echo NEW GAME / SIMULATION SETUP
echo ========================================
echo.
echo This will:
echo   1. Optionally backup your current database
echo   2. Wipe all existing data
echo   3. Generate a new company with random name, product, and team
echo   4. Seed the database with the new company
echo.

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment
    echo Please run setup.bat first to create the virtual environment
    pause
    exit /b 1
)

echo.
echo Running new game script...
cd backend
python new_game.py
cd ..

echo.
echo Done!
echo.
pause

