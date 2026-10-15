import asyncio
import logging
import sys
from sqlalchemy import select
from database.database import async_session_maker
from database.models import Employee

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def reset_all_to_home_rooms():
    """
    NUCLEAR OPTION: Force all employees to return to their home rooms.
    Ignores capacity constraints - just gets everyone moving to where they belong.
    """
    print("=" * 60)
    print("FORCE RESET: MOVING ALL EMPLOYEES TO HOME ROOMS")
    print("=" * 60)
    
    async with async_session_maker() as db:
        # Get all active employees
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        
        total_employees = len(employees)
        moved_count = 0
        no_home_count = 0
        already_home_count = 0
        
        print(f"\nProcessing {total_employees} employees...")
        
        for emp in employees:
            # Skip if no home room assigned
            if not emp.home_room or emp.home_room == "":
                no_home_count += 1
                if no_home_count <= 5:
                    print(f"    {emp.name}: No home room assigned, skipping")
                continue
            
            # Check if already at home
            if emp.current_room == emp.home_room and emp.activity_state == "working":
                already_home_count += 1
                continue
                
            # Force move to home room
            emp.target_room = emp.home_room
            emp.activity_state = "walking"
            moved_count += 1
            
            if moved_count <= 10:
                print(f"   {emp.name}: {emp.current_room or 'None'} -> {emp.home_room}")
        
        # Commit all changes
        await db.commit()
        
        print("\n" + "=" * 60)
        print("RESET COMPLETE")
        print("=" * 60)
        print(f"Total Employees:        {total_employees}")
        print(f"Set to Walking:         {moved_count}")
        print(f"Already Home:           {already_home_count}")
        print(f"No Home Room Assigned:  {no_home_count}")
        print("\nAll employees are now walking to their home rooms.")
        print("The MovementManager will process them automatically.")
        print("=" * 60)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_all_to_home_rooms())
