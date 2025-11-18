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
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from datetime import datetime, timedelta
from config import now as local_now

# Create simulator instance (will be initialized in lifespan)
simulator = OfficeSimulator()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
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
                
                # Generate birthday party meetings for upcoming birthdays (next 90 days)
                print("Generating birthday party meetings for calendar...")
                try:
                    from business.birthday_manager import BirthdayManager
                    birthday_manager = BirthdayManager(db)
                    meetings_created = await birthday_manager.generate_birthday_party_meetings(days_ahead=90)
                    if meetings_created > 0:
                        print(f"✅ Generated {meetings_created} birthday party meetings for the calendar.")
                    else:
                        print("✅ Birthday party meetings check complete (all parties already scheduled).")
                except Exception as birthday_error:
                    print(f"❌ Warning: Could not generate birthday meetings: {birthday_error}")
                    import traceback
                    traceback.print_exc()
                
                # Generate initial customer reviews for existing completed projects
                print("Generating initial customer reviews for completed projects...")
                try:
                    from business.customer_review_manager import CustomerReviewManager
                    from database.models import Project
                    from sqlalchemy import select
                    
                    # Get all completed projects
                    result = await db.execute(select(Project).where(Project.status == "completed"))
                    completed_projects = result.scalars().all()
                    
                    if completed_projects:
                        customer_review_manager = CustomerReviewManager(db)
                        # Generate reviews for all completed projects (ignore hours_since_completion for initial generation)
                        # We'll call the method with 0 hours to generate for all completed projects
                        reviews_created = await customer_review_manager.generate_reviews_for_completed_projects(
                            hours_since_completion=0.0  # 0 means generate for all completed projects
                        )
                        if reviews_created:
                            print(f"⭐ Generated {len(reviews_created)} initial customer review(s) for {len(completed_projects)} completed project(s)")
                        else:
                            print(f"ℹ️  No new reviews needed (projects may already have reviews)")
                    else:
                        print("ℹ️  No completed projects found for initial review generation")
                except Exception as review_error:
                    print(f"Warning: Could not generate initial customer reviews: {review_error}")
                    import traceback
                    traceback.print_exc()
                
                # Generate initial meetings for the day and past week
                print("Generating initial meetings for today and last week...")
                try:
                    from business.meeting_manager import MeetingManager
                    from database.models import Meeting
                    from sqlalchemy import select
                    
                    meeting_manager = MeetingManager(db)
                    now = local_now()
                    
                    # Generate meetings for last week (7 days ago to today)
                    last_week_start = now - timedelta(days=7)
                    last_week_start = last_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    tomorrow_start = today_start + timedelta(days=1)
                    
                    # Check existing meetings in this range
                    result = await db.execute(
                        select(Meeting).where(
                            Meeting.start_time >= last_week_start,
                            Meeting.start_time < tomorrow_start
                        )
                    )
                    existing_meetings = result.scalars().all()
                    
                    if len(existing_meetings) == 0:
                        # Generate meetings for last week
                        print("Generating meetings for the past week...")
                        past_meetings = await meeting_manager.generate_meetings_for_date_range(
                            last_week_start, today_start
                        )
                        print(f"📅 Generated {past_meetings} meetings for the past week")
                        
                        # Generate meetings for today
                        print("Generating meetings for today...")
                        today_meetings = await meeting_manager.generate_meetings()
                        print(f"📅 Generated {today_meetings} meetings for today")
                    else:
                        print(f"ℹ️  {len(existing_meetings)} meetings already exist in the date range")
                    
                    # Always generate an in-progress meeting if one doesn't exist
                    result = await db.execute(
                        select(Meeting).where(Meeting.status == "in_progress")
                    )
                    in_progress_meetings = result.scalars().all()
                    
                    if len(in_progress_meetings) == 0:
                        print("Generating an in-progress meeting...")
                        in_progress_meeting = await meeting_manager.generate_in_progress_meeting()
                        if in_progress_meeting:
                            print(f"📅 Generated in-progress meeting: {in_progress_meeting.title}")
                        else:
                            print("ℹ️  Could not generate in-progress meeting (may need more employees)")
                    else:
                        print(f"ℹ️  {len(in_progress_meetings)} in-progress meeting(s) already exist")
                        
                except Exception as meeting_error:
                    print(f"Warning: Could not generate initial meetings: {meeting_error}")
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
        print("Office simulation started...")
    except Exception as e:
        print(f"Warning: Could not start simulation: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Shutdown
    simulator.stop()
    print("Office simulation stopped.")

app = FastAPI(title="Autonomous Office Simulation", lifespan=lifespan)

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

@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await websocket_endpoint(websocket, simulator)

@app.get("/")
async def root():
    return {"message": "Autonomous Office Simulation API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

