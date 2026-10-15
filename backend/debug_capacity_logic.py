import asyncio
import logging
import sys
from database.database import async_session_maker
from engine.movement_system import check_room_has_space, get_room_capacity, get_room_occupancy, find_available_similar_room

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_capacity():
    print("--- STARTING CAPACITY DEBUG ---")
    async with async_session_maker() as db:
        # 1. Check specific overcrowded rooms from previous logs
        rooms_to_check = ["cubicles_floor4", "cubicles_floor2", "open_office"]
        
        for room in rooms_to_check:
            cap = get_room_capacity(room)
            occ = await get_room_occupancy(room, db)
            has_space = await check_room_has_space(room, db)
            print(f"Room: {room}")
            print(f"  Capacity: {cap}")
            print(f"  Occupancy: {occ}")
            print(f"  Has Space? {has_space}")
            
            if occ >= cap and has_space:
                print("  ERROR: Room is full but check_room_has_space returns True!")
            elif occ < cap and not has_space:
                print("  WARNING: Room has space but check_room_has_space returns False (could be reserved?)")
            else:
                print("  Check logic seems correct.")

        # 2. Simulate finding a room for a hypothetical employee
        print("\n--- SIMULATING ROOM FINDING ---")
        # Assume we are trying to move an employee from a full room
        test_room = "cubicles_floor2"
        print(f"Finding alternative for room: {test_room}")
        alt = await find_available_similar_room(test_room, db)
        print(f"  Found alternative: {alt}")
        
        if alt:
            alt_cap = get_room_capacity(alt)
            alt_occ = await get_room_occupancy(alt, db)
            print(f"  Alternative Status: {alt_occ}/{alt_cap}")
            if alt_occ >= alt_cap:
                print("  ERROR: Alternative room is ALSO full!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_capacity())
