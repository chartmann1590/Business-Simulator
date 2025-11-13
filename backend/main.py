import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import router
from api.websocket import websocket_endpoint
from engine.office_simulator import OfficeSimulator
from database.database import init_db
import asyncio
import uvicorn

app = FastAPI(title="Autonomous Office Simulation")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve static files for avatars
avatars_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatars")
if os.path.exists(avatars_path):
    app.mount("/avatars", StaticFiles(directory=avatars_path), name="avatars")

# Serve static files for office layouts
office_layout_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "office_layout")
if os.path.exists(office_layout_path):
    app.mount("/office_layout", StaticFiles(directory=office_layout_path), name="office_layout")

# Create simulator instance
simulator = OfficeSimulator()

@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await websocket_endpoint(websocket, simulator)

@app.on_event("startup")
async def startup_event():
    """Initialize database and start simulation."""
    print("Initializing database...")
    try:
        await init_db()
        print("Database initialized.")
        
        # Auto-seed if database is empty
        from database.database import async_session_maker
        from database.models import Employee
        from sqlalchemy import select
        
        async with async_session_maker() as db:
            result = await db.execute(select(Employee))
            employees = result.scalars().all()
            if not employees:
                print("Database is empty. Seeding initial data...")
                try:
                    from seed import seed_database
                    await seed_database()
                    print("Database seeded successfully!")
                except Exception as seed_error:
                    print(f"Warning: Could not seed database: {seed_error}")
                    import traceback
                    traceback.print_exc()
            else:
                # Assign rooms to existing employees that don't have them
                print("Assigning rooms to existing employees...")
                try:
                    from employees.room_assigner import assign_rooms_to_existing_employees
                    await assign_rooms_to_existing_employees(db)
                    print("Room assignment completed.")
                except Exception as room_error:
                    print(f"Warning: Could not assign rooms: {room_error}")
                    import traceback
                    traceback.print_exc()
                
                # Check if we need to hire employees to meet minimum staffing (15 employees)
                result = await db.execute(select(Employee).where(Employee.status == "active"))
                active_employees = result.scalars().all()
                active_count = len(active_employees)
                MIN_EMPLOYEES = 15
                
                if active_count < MIN_EMPLOYEES:
                    employees_needed = MIN_EMPLOYEES - active_count
                    print(f"Office needs minimum {MIN_EMPLOYEES} employees to run. Current: {active_count}. Hiring {employees_needed} employees...")
                    try:
                        from engine.office_simulator import OfficeSimulator
                        temp_simulator = OfficeSimulator()
                        business_context = await temp_simulator.get_business_context(db)
                        
                        # Hire employees in batches (up to 5 at a time on startup)
                        hires_needed = min(employees_needed, 5)
                        for i in range(hires_needed):
                            await temp_simulator._hire_employee(db, business_context)
                            print(f"Hired employee {i+1}/{hires_needed}")
                        
                        print(f"Startup hiring complete. Active employees: {active_count + hires_needed}")
                    except Exception as hire_error:
                        print(f"Warning: Could not hire employees on startup: {hire_error}")
                        import traceback
                        traceback.print_exc()
    except Exception as e:
        print(f"Warning: Database initialization had issues: {e}")
        import traceback
        traceback.print_exc()
        # Continue anyway - tables might already exist
    
    # Start simulation in background
    try:
        asyncio.create_task(simulator.run())
        print("Simulation started.")
    except Exception as e:
        print(f"Warning: Could not start simulation: {e}")
        import traceback
        traceback.print_exc()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop simulation on shutdown."""
    simulator.stop()

@app.get("/")
async def root():
    return {"message": "Autonomous Office Simulation API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

