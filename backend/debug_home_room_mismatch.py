import asyncio
import logging
import sys
from sqlalchemy import select, and_
from database.database import async_session_maker
from database.models import Employee
from engine.movement_system import get_room_capacity, get_room_occupancy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_home_room_mismatch():
    print("--- STARTING HOME ROOM MISMATCH DEBUG ---")
    async with async_session_maker() as db:
        # Get all active employees
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        
        mismatch_count = 0
        total_employees = len(employees)
        
        print(f"Analyzing {total_employees} employees...")
        
        room_mismatches = {} # Key: current_room, Value: count of misplaced people there
        
        for emp in employees:
            # Skip if no home room assigned
            if not emp.home_room:
                continue
                
            # Skip if walking, meeting, or on break (these are valid reasons to be away)
            if emp.activity_state in ["walking", "meeting", "break", "training"]:
                continue
                
            # Check if they are in their home room
            if emp.current_room != emp.home_room:
                mismatch_count += 1
                
                # Track where they are hanging out instead
                current = emp.current_room or "None"
                room_mismatches[current] = room_mismatches.get(current, 0) + 1
                
                # Check if their home room is actually full
                home_cap = get_room_capacity(emp.home_room)
                home_occ = await get_room_occupancy(emp.home_room, db)
                
                if mismatch_count <= 20: # Only print first 20 details
                    print(f"Employee: {emp.name} (ID: {emp.id})")
                    print(f"  Current: {current} (State: {emp.activity_state})")
                    print(f"  Home:    {emp.home_room}")
                    print(f"  Home Status: {home_occ}/{home_cap}")
                    if home_occ >= home_cap:
                        print("  -> Home room is FULL, that's why they are here.")
                    else:
                        print("  -> Home room has SPACE! They should go back.")
        
        print(f"\nTotal Mismatches: {mismatch_count}/{total_employees}")
        
        print("\nTop Locations for Misplaced Employees:")
        sorted_mismatches = sorted(room_mismatches.items(), key=lambda x: x[1], reverse=True)
        for room, count in sorted_mismatches[:10]:
             cap = get_room_capacity(room)
             occ = await get_room_occupancy(room, db)
             print(f"  {room}: {count} misplaced people (Total Occupancy: {occ}/{cap})")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_home_room_mismatch())
