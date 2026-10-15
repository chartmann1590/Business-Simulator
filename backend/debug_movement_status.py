import asyncio
import logging
import sys
from sqlalchemy import select
from database.database import async_session_maker
from database.models import Employee

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_movement_status():
    print("--- DEBUGGING MOVEMENT STATUS ---")
    async with async_session_maker() as db:
        # Get all active employees
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        
        print(f"Total Active Employees: {len(employees)}")
        
        # Count by activity state
        state_counts = {}
        for emp in employees:
            state = emp.activity_state or "None"
            state_counts[state] = state_counts.get(state, 0) + 1
            
        print("\nActivity State Breakdown:")
        for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {state}: {count}")
            
        # Show some walking employees
        walking_employees = [emp for emp in employees if emp.activity_state == "walking"]
        print(f"\nWalking Employees: {len(walking_employees)}")
        
        if walking_employees:
            print("Sample Walking Employees (first 10):")
            for emp in walking_employees[:10]:
                print(f"  {emp.name}: {emp.current_room} -> {emp.target_room}")
        else:
            print("NO WALKING EMPLOYEES FOUND!")
            
        # Check for employees without current_room
        no_room = [emp for emp in employees if not emp.current_room]
        print(f"\nEmployees without current_room: {len(no_room)}")
        if no_room and len(no_room) <= 10:
            for emp in no_room:
                print(f"  {emp.name}: State={emp.activity_state}, Target={emp.target_room}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_movement_status())
