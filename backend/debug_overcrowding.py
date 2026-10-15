import asyncio
import logging
import sys
from sqlalchemy import select, and_, func
from database.database import async_session_maker
from database.models import Employee
from engine.movement_system import get_room_capacity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_overcrowding():
    print("--- STARTING OVERCROWDING DEBUG ---")
    async with async_session_maker() as db:
        # 1. Get all employees
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        
        # 2. Group by room to calculate occupancy
        room_counts = {}
        for emp in employees:
            if emp.current_room:
                room_counts[emp.current_room] = room_counts.get(emp.current_room, 0) + 1
        
        # 3. Identify overcrowded rooms
        print("\n--- OVERCROWDED ROOMS ---")
        overcrowded_rooms = []
        for room, count in room_counts.items():
            capacity = get_room_capacity(room)
            if count > capacity:
                print(f"Room: {room} | Occupancy: {count}/{capacity} | Over: {count - capacity}")
                overcrowded_rooms.append(room)
        
        if not overcrowded_rooms:
            print("No overcrowded rooms found.")
            
        # 4. Analyze stuck walking employees in these rooms
        print("\n--- STUCK WALKING EMPLOYEES ---")
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state == "walking",
                    Employee.current_room.in_(overcrowded_rooms) if overcrowded_rooms else False
                )
            )
        )
        stuck_employees = result.scalars().all()
        
        if not stuck_employees:
            print("No walking employees found in overcrowded rooms.")
        
        for emp in stuck_employees:
            print(f"Employee: {emp.name} (ID: {emp.id})")
            print(f"  Current Room: {emp.current_room}")
            print(f"  Target Room:  {emp.target_room}")
            print(f"  Is Target == Current? {emp.current_room == emp.target_room}")
            
            # Check if they are trying to go to another full room
            if emp.target_room:
                target_count = room_counts.get(emp.target_room, 0)
                target_cap = get_room_capacity(emp.target_room)
                print(f"  Target Occupancy: {target_count}/{target_cap}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_overcrowding())
