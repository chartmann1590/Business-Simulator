#!/bin/bash

echo "Starting Autonomous Office Simulation..."
echo ""

echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Starting backend server..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

echo ""
echo "Waiting for backend to start..."
sleep 3

echo ""
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Both servers are starting..."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait

