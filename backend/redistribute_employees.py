"""
Script to redistribute employees from overcrowded rooms to new rooms on floor 5.
Ensures no room has more than 20 people.
"""
import asyncio
from database.database import async_session_maker
from database.models import Employee
from sqlalchemy import select, and_
from collections import defaultdict

# Room capacity limit
MAX_CAPACITY = 20

# Define room mappings for overcrowded departments
ROOM_EXPANSIONS = {
    'sales_room_floor2': ['sales_room_floor2', 'sales_room_2_floor2', 'sales_room_3_floor5', 'sales_room_4_floor5', 'sales_room_5_floor5'],
    'hr_room_floor2': ['hr_room_floor2', 'hr_room_2_floor2', 'hr_room_3_floor5', 'hr_room_4_floor5', 'hr_room_5_floor5'],
    'it_room': ['it_room', 'it_room_3_floor5'],
    'it_room_floor2': ['it_room_floor2', 'it_room_4_floor5'],
    'open_office': ['open_office', 'open_office_floor2'],
    'cubicles': ['cubicles', 'cubicles_floor2'],
    'design_studio_floor3': ['design_studio_floor3', 'design_studio_floor5'],
    'innovation_lab_floor3': ['innovation_lab_floor3', 'innovation_lab_floor5'],
}

async def redistribute_employees():
    """Redistribute employees from overcrowded rooms to new rooms."""
    async with async_session_maker() as db:
        print('\n=== STARTING EMPLOYEE REDISTRIBUTION ===\n')

        total_moved = 0

        for overcrowded_room, target_rooms in ROOM_EXPANSIONS.items():
            print(f'\nProcessing {overcrowded_room}...')

            # Get all employees in this overcrowded room
            result = await db.execute(
                select(Employee).where(
                    and_(
                        Employee.status == 'active',
                        Employee.home_room == overcrowded_room
                    )
                )
            )
            employees = result.scalars().all()

            if not employees:
                print(f'  No employees found in {overcrowded_room}')
                continue

            print(f'  Found {len(employees)} employees')

            # Distribute employees across target rooms
            room_assignments = defaultdict(list)
            current_room_index = 0

            for emp in employees:
                # Assign to current target room
                target_room = target_rooms[current_room_index]
                room_assignments[target_room].append(emp)

                # If current room hits capacity, move to next room
                if len(room_assignments[target_room]) >= MAX_CAPACITY:
                    current_room_index += 1
                    if current_room_index >= len(target_rooms):
                        # If we've filled all target rooms, stay on last one
                        # (shouldn't happen if we calculated correctly)
                        current_room_index = len(target_rooms) - 1

            # Apply the assignments
            for target_room, assigned_employees in room_assignments.items():
                print(f'  Assigning {len(assigned_employees)} employees to {target_room}')

                # Determine floor from room name
                if '_floor5' in target_room:
                    floor = 5
                elif '_floor2' in target_room:
                    floor = 2
                elif '_floor3' in target_room:
                    floor = 3
                else:
                    floor = 1

                for emp in assigned_employees:
                    old_room = emp.home_room
                    emp.home_room = target_room
                    emp.floor = floor

                    # Also update current_room if they're currently in their old home room
                    if emp.current_room == old_room:
                        emp.current_room = target_room

                    if old_room != target_room:
                        total_moved += 1

        # Commit all changes
        await db.commit()

        print(f'\n=== REDISTRIBUTION COMPLETE ===')
        print(f'Total employees reassigned: {total_moved}')

        # Verify the results
        print(f'\n=== VERIFYING ROOM CAPACITIES ===')

        # Get all rooms and their counts
        result = await db.execute(
            select(Employee.home_room).where(Employee.status == 'active')
        )
        all_home_rooms = [row[0] for row in result.all()]

        from collections import Counter
        room_counts = Counter(all_home_rooms)

        over_capacity = []
        for room, count in sorted(room_counts.items(), key=lambda x: x[1], reverse=True):
            status = 'OVER CAPACITY!' if count > MAX_CAPACITY else 'OK'
            if count > MAX_CAPACITY:
                over_capacity.append((room, count))
                print(f'{room}: {count} people [{status}]')
            elif count > 15:  # Only show rooms with >15 people
                print(f'{room}: {count} people [{status}]')

        if over_capacity:
            print(f'\nWARNING: {len(over_capacity)} rooms still over capacity!')
        else:
            print(f'\nSUCCESS: All rooms are at or below {MAX_CAPACITY} capacity!')

if __name__ == '__main__':
    asyncio.run(redistribute_employees())
