@echo off
echo Starting Autonomous Office Simulation...
echo.

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting backend server...
start "Backend Server" cmd /k "cd backend && python main.py"

echo.
echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo.
echo Starting frontend...
cd frontend
start "Frontend Server" cmd /k "npm run dev"

echo.
echo Both servers are starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to exit...
pause >nul

