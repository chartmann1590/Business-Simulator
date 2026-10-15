import asyncio
import logging
import sys
from database.database import async_session_maker
from engine.movement_system import return_employees_to_home_room, get_room_capacity, get_room_occupancy
from sqlalchemy import select, and_
from database.models import Employee

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_return_to_desk():
    print("--- TESTING RETURN TO DESK LOGIC ---")
    async with async_session_maker() as db:
        # Count initial mismatches
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.in_(["working", "idle"]),
                    Employee.home_room.isnot(None),
                    Employee.home_room != "",
                    Employee.current_room != Employee.home_room
                )
            )
        )
        initial_mismatches = len(result.scalars().all())
        print(f"Initial mismatches: {initial_mismatches}")
        
        # Run the function 5 times (simulating 5 ticks)
        total_returned = 0
        for i in range(5):
            returned = await return_employees_to_home_room(db, max_to_move=50)
            await db.commit()
            total_returned += returned
            print(f"Iteration {i+1}: Returned {returned} employees")
            
        # Count final mismatches
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.in_(["working", "idle"]),
                    Employee.home_room.isnot(None),
                    Employee.home_room != "",
                    Employee.current_room != Employee.home_room
                )
            )
        )
        final_mismatches = len(result.scalars().all())
        
        print(f"\nResults:")
        print(f"  Initial mismatches: {initial_mismatches}")
        print(f"  Total returned: {total_returned}")
        print(f"  Final mismatches: {final_mismatches}")
        print(f"  Reduction: {initial_mismatches - final_mismatches}")
        
        # The final mismatches should include walking employees (they are no longer "working")
        # So we expect the count to be roughly initial - total_returned
        
if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_return_to_desk())
