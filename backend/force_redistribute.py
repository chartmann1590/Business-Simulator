import asyncio
import logging
import sys
from sqlalchemy import select, and_
from database.database import async_session_maker
from database.models import Employee
from engine.movement_system import fix_walking_employees_without_destination, get_room_capacity, get_room_occupancy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def force_redistribute():
    print("--- STARTING FORCED REDISTRIBUTION ---")
    async with async_session_maker() as db:
        # 1. Identify overcrowded rooms
        overcrowded_rooms = ["cubicles_floor4"] # We know this one is bad
        
        print(f"Targeting rooms: {overcrowded_rooms}")
        
        # 2. Get employees in these rooms
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.current_room.in_(overcrowded_rooms)
                )
            )
        )
        employees = result.scalars().all()
        print(f"Found {len(employees)} employees in target rooms.")
        
        # 3. Set them to walking so the fix function picks them up
        # Only pick those over capacity
        room_counts = {}
        employees_to_move = []
        
        for emp in employees:
            room_counts[emp.current_room] = room_counts.get(emp.current_room, 0) + 1
            cap = get_room_capacity(emp.current_room)
            if room_counts[emp.current_room] > cap:
                employees_to_move.append(emp)
                
        print(f"Marking {len(employees_to_move)} employees as 'walking' to force move...")
        
        for emp in employees_to_move:
            emp.activity_state = "walking"
            # Don't clear target_room, let the fix function handle it or generate a new one
            
        await db.commit()
        
        # 4. Run the fix function
        print("Running fix function with Smart Distribution...")
        fixed = await fix_walking_employees_without_destination(db)
        await db.commit()
        print(f"Fixed/Moved {fixed} employees")
        
        # 5. Check distribution
        print("\n--- FINAL DISTRIBUTION ---")
        all_rooms = {}
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        all_emps = result.scalars().all()
        
        for emp in all_emps:
            if emp.current_room:
                all_rooms[emp.current_room] = all_rooms.get(emp.current_room, 0) + 1
                
        # Check cubicles on floor 4 specifically
        for room in ["cubicles_floor4", "cubicles_floor4_2", "cubicles_floor4_3", "open_office_floor4"]:
            count = all_rooms.get(room, 0)
            cap = get_room_capacity(room)
            print(f"Room: {room} | Occupancy: {count}/{cap}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(force_redistribute())
