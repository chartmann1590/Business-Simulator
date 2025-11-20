#!/usr/bin/env python
"""Test script to start backend and see errors"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing main...")
    from main import app
    print("App imported successfully!")
    print("Starting uvicorn...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)


