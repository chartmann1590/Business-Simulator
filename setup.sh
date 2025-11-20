#!/bin/bash

echo "Setting up Autonomous Office Simulation..."
echo ""

echo "Creating Python virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment"
    exit 1
fi

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Installing Python dependencies..."
pip install -r backend/requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies"
    exit 1
fi

echo ""
echo "Seeding database..."
cd backend
python seed.py
cd ..

echo ""
echo "Setup complete!"
echo ""
echo "To start the simulation:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run: cd backend && python main.py"
echo "  3. Open http://localhost:8000 in your browser"
echo ""






