"""
Script to send all employees to their home rooms
Run this during work hours to ensure employees are in the correct locations
"""
import asyncio
from database.database import async_session_maker
from database.models import Employee
from sqlalchemy import select, and_
from config import is_work_hours, now

async def send_employees_to_home_rooms():
    """Send all employees to their home rooms during work hours."""
    current_time = now()

    # Only during work hours
    if not is_work_hours():
        print(f'[{current_time}] Not work hours - skipping')
        return

    async with async_session_maker() as db:
        # Get all active employees not currently sick
        result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == 'active',
                    Employee.is_sick == False
                )
            )
        )
        employees = result.scalars().all()

        print(f'[{current_time}] Processing {len(employees)} employees...')

        moved = 0

        for emp in employees:
            if not emp.home_room:
                print(f'WARNING: {emp.name} has no home_room!')
                continue

            # Skip if already in home room and working
            if emp.current_room == emp.home_room and emp.activity_state == 'working':
                continue

            # Skip if on break or in meeting
            if emp.activity_state in ['on_break', 'on_lunch', 'in_meeting']:
                continue

            # Move to home room
            old_room = emp.current_room
            emp.current_room = emp.home_room
            emp.target_room = None
            emp.activity_state = 'working'

            print(f'  Moved {emp.name}: {old_room} -> {emp.home_room}')
            moved += 1

        if moved > 0:
            await db.commit()
            print(f'[{current_time}] Successfully moved {moved} employees to their home rooms')
        else:
            print(f'[{current_time}] All employees already in correct rooms')

if __name__ == '__main__':
    asyncio.run(send_employees_to_home_rooms())
