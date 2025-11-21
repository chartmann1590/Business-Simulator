"""
Script to backfill missing clock-out events for employees who already left.
Run this to immediately create clock-out records for employees who are at home
but don't have clock-out events for today.
"""
import asyncio
from database.database import async_session_maker
from business.clock_manager import ClockManager


async def backfill_clock_outs():
    """Backfill missing clock-out events."""
    print("Starting clock-out backfill...")
    
    try:
        async with async_session_maker() as db:
            clock_manager = ClockManager(db)
            
            result = await clock_manager.backfill_missing_clock_outs()
            
            print(f"\n[RESULT]")
            print(f"  Backfilled: {result['backfilled']} clock-out events")
            print(f"  Total checked: {result['total_checked']} employees")
            print(f"  Activities created: {result['activities_created']}")
            print(f"  Message: {result['message']}")
            
            if result['backfilled'] > 0:
                print(f"\n[SUCCESS] Successfully backfilled {result['backfilled']} clock-out events!")
            else:
                print(f"\n[INFO] No clock-outs needed to be backfilled.")
                
    except Exception as e:
        print(f"\n[ERROR] Error during backfill: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(backfill_clock_outs())

