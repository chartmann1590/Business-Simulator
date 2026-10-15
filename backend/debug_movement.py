import asyncio
import logging
import sys
from sqlalchemy import select, and_
from database.database import async_session_maker
from database.models import Employee
from engine.movement_system import fix_walking_employees_without_destination, get_next_room_in_path

# Configure logging to print to console
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_movement():
    print("--- STARTING DEBUG MOVEMENT ---")
    async with async_session_maker() as db:
        # 1. Check walking employees
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state == "walking"
                )
            )
        )
        walking_employees = result.scalars().all()
        print(f"Found {len(walking_employees)} employees in 'walking' state.")
        
        for i, emp in enumerate(walking_employees):
            if i >= 20:
                break
            print(f"Employee: {emp.name} (ID: {emp.id})")
            print(f"  Current Room: {emp.current_room}")
            print(f"  Target Room:  {emp.target_room}")
            print(f"  Floor:        {emp.floor}")
            
            if emp.target_room:
                next_room = get_next_room_in_path(emp.current_room, emp.target_room, emp.floor)
                print(f"  Calculated Next Room: {next_room}")
            else:
                print("  NO TARGET ROOM!")

        # 2. Run the fix function
        print("\n--- RUNNING FIX FUNCTION ---")
        fixed = await fix_walking_employees_without_destination(db)
        print(f"Function returned: {fixed}")
        await db.commit()
        
        # 3. Check again to see if anything changed
        print("\n--- POST-FIX STATUS ---")
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state == "walking"
                )
            )
        )
        walking_employees_after = result.scalars().all()
        
        still_stuck_count = 0
        rescued_count = 0
        
        for emp in walking_employees_after:
            if not emp.current_room:
                still_stuck_count += 1
            else:
                rescued_count += 1
                
        print(f"Employees with valid room: {rescued_count}")
        print(f"Employees still in limbo: {still_stuck_count}")
        
        if still_stuck_count == 0 and rescued_count > 0:
            print("SUCCESS: All walking employees have valid rooms!")
        elif rescued_count > 0:
            print("PARTIAL SUCCESS: Some employees rescued, some still stuck.")
        else:
            print("FAILURE: No employees rescued.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_movement())
