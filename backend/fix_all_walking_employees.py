"""One-time script to fix ALL employees walking without destinations."""
import asyncio
import os
from dotenv import load_dotenv
from database.database import async_session_maker
from engine.movement_system import fix_walking_employees_without_destination

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

async def fix_all_walking():
    """Fix all employees walking without destinations."""
    print("Starting fix for all walking employees...")
    
    async with async_session_maker() as db:
        # Run the fix function multiple times to catch all cases
        total_fixed = 0
        for i in range(5):  # Run up to 5 times to catch all cases
            fixed = await fix_walking_employees_without_destination(db)
            await db.commit()
            total_fixed += fixed
            print(f"Iteration {i+1}: Fixed {fixed} employees")
            if fixed == 0:
                break
        
        # Final check - get all walking employees and verify they all have target_room
        from sqlalchemy import select, and_, or_
        from database.models import Employee
        
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state == "walking"
                )
            )
        )
        all_walking = result.scalars().all()
        
        still_broken = []
        for emp in all_walking:
            if not emp.target_room or emp.target_room == "":
                still_broken.append(emp)
                # Force fix this one
                from employees.room_assigner import ROOM_OPEN_OFFICE
                from engine.movement_system import check_room_has_space
                
                target = None
                if emp.home_room:
                    has_space = await check_room_has_space(emp.home_room, db, exclude_employee_id=emp.id)
                    if has_space:
                        target = emp.home_room
                
                if not target:
                    floor = getattr(emp, 'floor', 1)
                    target = f"{ROOM_OPEN_OFFICE}_floor{floor}" if floor > 1 else ROOM_OPEN_OFFICE
                
                emp.target_room = target
                print(f"  Force-fixed {emp.name} (ID: {emp.id}) -> {target}")
        
        if still_broken:
            await db.commit()
            print(f"Force-fixed {len(still_broken)} additional employees")
        
        print(f"\n[OK] Total fixed: {total_fixed + len(still_broken)}")
        print(f"[OK] All {len(all_walking)} walking employees now have destinations!")

if __name__ == "__main__":
    asyncio.run(fix_all_walking())

