#!/bin/bash

echo "========================================"
echo "NEW GAME / SIMULATION SETUP"
echo "========================================"
echo ""
echo "This will:"
echo "  1. Optionally backup your current database"
echo "  2. Wipe all existing data"
echo "  3. Generate a new company with random name, product, and team"
echo "  4. Seed the database with the new company"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run setup.sh first to create the virtual environment"
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment"
    exit 1
fi

echo ""
echo "Running new game script..."
cd backend
python new_game.py
cd ..

echo ""
echo "Done!"

