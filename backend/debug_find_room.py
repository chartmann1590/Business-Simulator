import asyncio
import logging
import sys
from database.database import async_session_maker
from engine.movement_system import find_available_similar_room, get_room_capacity, get_room_occupancy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_find_room():
    print("--- DEBUGGING FIND ROOM LOGIC ---")
    async with async_session_maker() as db:
        current_room = "cubicles_floor4"
        pending = {}
        
        print(f"Finding alternatives for {current_room}...")
        
        # Simulate 50 requests
        for i in range(50):
            alt = await find_available_similar_room(current_room, db, pending_assignments=pending)
            if alt:
                pending[alt] = pending.get(alt, 0) + 1
                if i % 10 == 0:
                    print(f"Request {i}: Assigned to {alt} (Pending: {pending[alt]})")
            else:
                print(f"Request {i}: No alternative found!")
                
        print("\nFinal Pending Counts:")
        for room, count in pending.items():
            cap = get_room_capacity(room)
            print(f"  {room}: {count} (Capacity: {cap})")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_find_room())
