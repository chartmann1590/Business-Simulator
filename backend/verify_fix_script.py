import asyncio
import logging
import sys
from sqlalchemy import select, and_
from database.database import async_session_maker
from database.models import Employee
from engine.movement_system import fix_walking_employees_without_destination, get_room_capacity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def verify_fix():
    print("--- STARTING VERIFICATION LOOP ---")
    async with async_session_maker() as db:
        # Initial check
        print("Initial Overcrowded Check:")
        await check_overcrowding(db)
        
        # Run fix loop
        print("\nRunning fix loop (5 iterations)...")
        for i in range(5):
            fixed = await fix_walking_employees_without_destination(db)
            await db.commit()
            print(f"Iteration {i+1}: Fixed/Moved {fixed} employees")
            
        # Final check
        print("\nFinal Overcrowded Check:")
        await check_overcrowding(db)

async def check_overcrowding(db):
    result = await db.execute(select(Employee).where(Employee.status == "active"))
    employees = result.scalars().all()
    
    room_counts = {}
    for emp in employees:
        if emp.current_room:
            room_counts[emp.current_room] = room_counts.get(emp.current_room, 0) + 1
            
    overcrowded_rooms = []
    for room, count in room_counts.items():
        capacity = get_room_capacity(room)
        if count > capacity:
            print(f"  Room: {room} | Occupancy: {count}/{capacity} | Over: {count - capacity}")
            overcrowded_rooms.append(room)
            
    if not overcrowded_rooms:
        print("  No overcrowded rooms found!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_fix())
