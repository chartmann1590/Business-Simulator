"""
Emergency script to fix all stuck walking employees.
Run this ONLY when the backend server is stopped!
"""
import asyncio
from database.database import async_session_maker
from database.models import Employee
from sqlalchemy import select, and_

async def fix_stuck_employees():
    """Fix all employees stuck in walking state."""
    async with async_session_maker() as db:
        # Get all walking employees
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == 'active',
                    Employee.activity_state == 'walking'
                )
            )
        )
        walking = result.scalars().all()

        print(f'\n=== FIXING STUCK EMPLOYEES ===')
        print(f'Found {len(walking)} employees stuck in walking state')

        if not walking:
            print('No stuck employees found!')
            return

        # Fix each employee
        fixed = 0
        for emp in walking:
            emp.current_room = emp.home_room
            emp.target_room = None
            emp.activity_state = 'working'
            fixed += 1
            if fixed <= 10:  # Show first 10
                print(f'  Fixed {emp.name}: moved to {emp.home_room}')

        if fixed > 10:
            print(f'  ... and {fixed - 10} more')

        await db.commit()
        print(f'\n Successfully fixed {fixed} employees!')
        print('\nNow restart the backend server with the updated code.')

if __name__ == '__main__':
    asyncio.run(fix_stuck_employees())
