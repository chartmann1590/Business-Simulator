"""Movement system for employees to move between rooms based on activities."""

import random
from typing import Optional
from employees.room_assigner import (
    ROOM_OPEN_OFFICE, ROOM_CUBICLES, ROOM_CONFERENCE_ROOM,
    ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_TRAINING_ROOM,
    ROOM_STORAGE, ROOM_IT_ROOM, ROOM_MANAGER_OFFICE,
    ROOM_RECEPTION, ROOM_EXECUTIVE_SUITE, ROOM_HR_ROOM,
    ROOM_SALES_ROOM, ROOM_INNOVATION_LAB, ROOM_HOTDESK,
    ROOM_FOCUS_PODS, ROOM_COLLAB_LOUNGE, ROOM_WAR_ROOM,
    ROOM_DESIGN_STUDIO, ROOM_HR_WELLNESS, ROOM_THEATER,
    ROOM_HUDDLE, ROOM_CORNER_EXEC
)


def get_room_capacity(room_id: str) -> int:
    """
    Get the capacity for a given room.
    
    Args:
        room_id: Room identifier (with or without floor suffix)
        
    Returns:
        int: Room capacity, or 999 if room not found (unlimited for unknown rooms)
    """
    # Room capacity mapping - matches API routes
    capacity_map = {
        # Floor 1
        ROOM_OPEN_OFFICE: 20,
        ROOM_CUBICLES: 15,
        ROOM_CONFERENCE_ROOM: 10,
        ROOM_BREAKROOM: 8,
        ROOM_RECEPTION: 3,
        ROOM_IT_ROOM: 5,
        ROOM_MANAGER_OFFICE: 6,
        ROOM_TRAINING_ROOM: 12,
        ROOM_LOUNGE: 10,
        ROOM_STORAGE: 2,
        # Floor 2
        f"{ROOM_EXECUTIVE_SUITE}_floor2": 8,
        f"{ROOM_CUBICLES}_floor2": 20,
        f"{ROOM_BREAKROOM}_floor2": 10,
        f"{ROOM_CONFERENCE_ROOM}_floor2": 12,
        f"{ROOM_TRAINING_ROOM}_floor2": 15,
        f"{ROOM_IT_ROOM}_floor2": 6,
        f"{ROOM_STORAGE}_floor2": 3,
        f"{ROOM_LOUNGE}_floor2": 12,
        f"{ROOM_HR_ROOM}_floor2": 6,
        f"{ROOM_SALES_ROOM}_floor2": 10,
        # Floor 3
        f"{ROOM_INNOVATION_LAB}_floor3": 12,
        f"{ROOM_HOTDESK}_floor3": 18,
        f"{ROOM_FOCUS_PODS}_floor3": 8,
        f"{ROOM_COLLAB_LOUNGE}_floor3": 15,
        f"{ROOM_WAR_ROOM}_floor3": 10,
        f"{ROOM_DESIGN_STUDIO}_floor3": 8,
        f"{ROOM_HR_WELLNESS}_floor3": 6,
        f"{ROOM_THEATER}_floor3": 20,
        f"{ROOM_HUDDLE}_floor3": 6,
        f"{ROOM_CORNER_EXEC}_floor3": 4,
        # Floor 4 - Training overflow floor (5 training rooms and 5 cubicles)
        f"{ROOM_TRAINING_ROOM}_floor4": 20,  # Training Room 1
        f"{ROOM_CUBICLES}_floor4": 25,  # Cubicles 1
        f"{ROOM_TRAINING_ROOM}_floor4_2": 20,  # Training Room 2
        f"{ROOM_CUBICLES}_floor4_2": 25,  # Cubicles 2
        f"{ROOM_TRAINING_ROOM}_floor4_3": 18,  # Training Room 3
        f"{ROOM_CUBICLES}_floor4_3": 22,  # Cubicles 3
        f"{ROOM_TRAINING_ROOM}_floor4_4": 20,  # Training Room 4
        f"{ROOM_CUBICLES}_floor4_4": 25,  # Cubicles 4
        f"{ROOM_TRAINING_ROOM}_floor4_5": 18,  # Training Room 5
        f"{ROOM_CUBICLES}_floor4_5": 22,  # Cubicles 5
    }
    
    # Check exact match first
    if room_id in capacity_map:
        return capacity_map[room_id]
    
    # Check if it's a base room without floor suffix
    base_room = room_id.replace('_floor2', '').replace('_floor3', '')
    if base_room in capacity_map:
        return capacity_map[base_room]
    
    # Default: return high capacity for unknown rooms (shouldn't happen, but safe fallback)
    return 999


async def get_room_occupancy(room_id: str, db_session) -> int:
    """
    Get the current number of employees in a room.
    
    Args:
        room_id: Room identifier
        db_session: Database session
        
    Returns:
        int: Number of employees currently in the room
    """
    from database.models import Employee
    from sqlalchemy import select, func
    
    result = await db_session.execute(
        select(func.count(Employee.id)).where(
            Employee.status == "active",
            Employee.current_room == room_id
        )
    )
    count = result.scalar() or 0
    return count


async def check_room_has_space(room_id: str, db_session, exclude_employee_id: int = None) -> bool:
    """
    Check if a room has available space.
    
    Args:
        room_id: Room identifier
        db_session: Database session
        exclude_employee_id: Optional employee ID to exclude from count (if they're leaving)
        
    Returns:
        bool: True if room has space, False if full
    """
    capacity = get_room_capacity(room_id)
    occupancy = await get_room_occupancy(room_id, db_session)
    
    # If excluding an employee (they're leaving), reduce occupancy by 1
    if exclude_employee_id:
        from database.models import Employee
        from sqlalchemy import select
        result = await db_session.execute(
            select(Employee).where(
                Employee.id == exclude_employee_id,
                Employee.current_room == room_id
            )
        )
        if result.scalar_one_or_none():
            occupancy = max(0, occupancy - 1)
    
    return occupancy < capacity


async def determine_target_room(activity_type: str, activity_description: str, employee, db_session=None) -> Optional[str]:
    """
    Determine which room an employee should move to based on their activity.
    Takes into account the employee's floor.
    
    Args:
        activity_type: Type of activity (e.g., "meeting", "break", "training")
        activity_description: Description of the activity
        employee: Employee model instance
        
    Returns:
        Optional[str]: Target room identifier (with floor suffix if needed), or None if should stay in current room
    """
    activity_lower = activity_type.lower()
    desc_lower = (activity_description or "").lower()
    
    # Get employee's floor (default to 1)
    employee_floor = getattr(employee, 'floor', 1)
    
    # Helper to add floor suffix if needed
    def get_room_with_floor(room_id):
        if employee_floor == 2 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor2"
        elif employee_floor == 3 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor3"
        elif employee_floor == 4 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor4"
        elif employee_floor == 1 and (room_id.endswith('_floor2') or room_id.endswith('_floor3') or room_id.endswith('_floor4')):
            # Remove floor suffix for floor 1
            room_id = room_id.replace('_floor2', '').replace('_floor3', '').replace('_floor4', '')
            return room_id
        return room_id
    
    # Meetings → Conference Room, Huddle (floor 3), or War Room (floor 3) - balance across all floors
    if "meeting" in activity_lower or "meeting" in desc_lower or "conference" in desc_lower:
        # Small meetings can use Huddle (floor 3), large meetings use Conference Room or War Room
        if "huddle" in desc_lower or "quick" in desc_lower or "standup" in desc_lower:
            # Small meetings → Huddle (floor 3)
            return f"{ROOM_HUDDLE}_floor3"
        elif "war room" in desc_lower or "sprint" in desc_lower or "planning" in desc_lower:
            # Strategic meetings → War Room (floor 3)
            return f"{ROOM_WAR_ROOM}_floor3"
        
        # Balance conference room usage across all floors
        if db_session:
            try:
                from database.models import Employee
                from sqlalchemy import select, func
                
                # Count employees in conference room on floor 1
                result = await db_session.execute(
                    select(func.count(Employee.id)).where(
                        Employee.status == "active",
                        Employee.current_room == ROOM_CONFERENCE_ROOM
                    )
                )
                floor1_count = result.scalar() or 0
                
                # Count employees in conference room on floor 2
                result = await db_session.execute(
                    select(func.count(Employee.id)).where(
                        Employee.status == "active",
                        Employee.current_room == f"{ROOM_CONFERENCE_ROOM}_floor2"
                    )
                )
                floor2_count = result.scalar() or 0
                
                # Count employees in huddle or war room on floor 3
                result = await db_session.execute(
                    select(func.count(Employee.id)).where(
                        Employee.status == "active",
                        Employee.current_room.in_([f"{ROOM_HUDDLE}_floor3", f"{ROOM_WAR_ROOM}_floor3"])
                    )
                )
                floor3_count = result.scalar() or 0
                
                # Assign to floor with fewer people
                if floor1_count <= floor2_count and floor1_count <= floor3_count:
                    return ROOM_CONFERENCE_ROOM  # Floor 1
                elif floor2_count <= floor3_count:
                    return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
                else:
                    # Use huddle for floor 3 (smaller meetings)
                    return f"{ROOM_HUDDLE}_floor3"  # Floor 3
            except:
                pass
        
        # Fallback: randomly assign between floors
        rand = random.random()
        if rand < 0.33:
            return ROOM_CONFERENCE_ROOM  # Floor 1
        elif rand < 0.66:
            return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
        else:
            return f"{ROOM_HUDDLE}_floor3"  # Floor 3
    
    # Breaks → Breakroom, Lounge, HR Wellness, or Theater (on employee's floor)
    if "break" in activity_lower or "break" in desc_lower or "lunch" in desc_lower or "coffee" in desc_lower:
        # Randomly choose between breakroom, lounge, HR wellness (floor 3), or theater (floor 3)
        # HR Wellness and Theater are on floor 3, so employees on floor 3 can use them
        if employee_floor == 3:
            chosen_room = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, 
                ROOM_HR_WELLNESS, ROOM_THEATER
            ])
        else:
            # For other floors, use breakroom or lounge
            chosen_room = random.choice([ROOM_BREAKROOM, ROOM_LOUNGE])
        return get_room_with_floor(chosen_room)
    
    # Training → Training Room (on employee's floor, or can go to training on any floor)
    # Floor 4 is dedicated to training overflow with 5 training rooms
    if "training" in activity_lower or "training" in desc_lower or "learn" in desc_lower:
        # If employee is on floor 4, find the best available training room
        if employee_floor == 4:
            # Find training room with most available space
            if db_session:
                try:
                    floor4_training_rooms = [
                        f"{ROOM_TRAINING_ROOM}_floor4",
                        f"{ROOM_TRAINING_ROOM}_floor4_2",
                        f"{ROOM_TRAINING_ROOM}_floor4_3",
                        f"{ROOM_TRAINING_ROOM}_floor4_4",
                        f"{ROOM_TRAINING_ROOM}_floor4_5"
                    ]
                    
                    best_room = None
                    most_space = -1
                    
                    for room_id in floor4_training_rooms:
                        occupancy = await get_room_occupancy(room_id, db_session)
                        capacity = get_room_capacity(room_id)
                        available_space = capacity - occupancy
                        
                        if available_space > most_space:
                            most_space = available_space
                            best_room = room_id
                    
                    if best_room:
                        return best_room
                except:
                    pass
            # Fallback to first training room
            return f"{ROOM_TRAINING_ROOM}_floor4"
        # Otherwise use their floor's training room
        return get_room_with_floor(ROOM_TRAINING_ROOM)
    
    # Storage needs → Storage (on employee's floor)
    if "storage" in activity_lower or "storage" in desc_lower or "supplies" in desc_lower:
        # Check if employee is storage staff
        if ("storage" in (employee.title or "").lower() or "warehouse" in (employee.title or "").lower() or
            "inventory" in (employee.title or "").lower() or "stock" in (employee.title or "").lower()):
            # Storage staff go to their assigned storage room (could be on either floor)
            home_room = getattr(employee, 'home_room', None)
            if home_room and ROOM_STORAGE in home_room:
                return home_room  # Use their assigned storage room
        return get_room_with_floor(ROOM_STORAGE)
    
    # IT-related work → IT Room (if employee is IT, go to IT room on their floor or assigned floor)
    if ("it" in activity_lower or "server" in activity_lower or "network" in activity_lower or 
        "it" in desc_lower or "server" in desc_lower or "network" in desc_lower):
        # Check if employee is IT or if activity is IT-related
        if "it" in (employee.title or "").lower() or "it" in (employee.department or "").lower():
            # IT staff go to their assigned IT room (could be on either floor)
            home_room = getattr(employee, 'home_room', None)
            if home_room and ROOM_IT_ROOM in home_room:
                return home_room  # Use their assigned IT room
            return get_room_with_floor(ROOM_IT_ROOM)
    
    # Reception work → Reception (if employee is receptionist, go to their assigned reception)
    if "reception" in activity_lower or "reception" in desc_lower:
        if "reception" in (employee.title or "").lower():
            # Reception staff go to their assigned reception (usually floor 1, but can be floor 2)
            home_room = getattr(employee, 'home_room', None)
            if home_room and ROOM_RECEPTION in home_room:
                return home_room  # Use their assigned reception
            return get_room_with_floor(ROOM_RECEPTION)
    
    # Manager meetings → Manager Office (on employee's floor)
    if ("manager" in activity_lower or "executive" in activity_lower or 
        "strategy" in activity_lower or "planning" in activity_lower or
        "discuss" in desc_lower or "review" in desc_lower):
        if employee.role in ["CEO", "Manager"]:
            return get_room_with_floor(ROOM_MANAGER_OFFICE)
    
    # Collaboration/team work → Conference Room, Collaboration Lounge (floor 3), Open Office, or Cubicles
    if ("collaborate" in desc_lower or "team" in desc_lower or "discuss" in desc_lower or
        "brainstorm" in desc_lower or "review" in desc_lower):
        # 30% collaboration lounge (floor 3), 20% conference room, 25% open office, 25% cubicles
        room_choice = random.choice([
            "collab_lounge", "collab_lounge", "collab_lounge",  # 30%
            "conference", "conference",  # 20%
            "open_office", "open_office", "open_office",  # 25%
            "cubicles", "cubicles", "cubicles"  # 25%
        ])
        
        if room_choice == "collab_lounge":
            return f"{ROOM_COLLAB_LOUNGE}_floor3"  # Floor 3
        elif room_choice == "conference":
            # Balance conference room usage across floors
            if db_session:
                try:
                    from database.models import Employee
                    from sqlalchemy import select, func
                    
                    # Count employees in conference room on floor 1
                    result = await db_session.execute(
                        select(func.count(Employee.id)).where(
                            Employee.status == "active",
                            Employee.current_room == ROOM_CONFERENCE_ROOM
                        )
                    )
                    floor1_count = result.scalar() or 0
                    
                    # Count employees in conference room on floor 2
                    result = await db_session.execute(
                        select(func.count(Employee.id)).where(
                            Employee.status == "active",
                            Employee.current_room == f"{ROOM_CONFERENCE_ROOM}_floor2"
                        )
                    )
                    floor2_count = result.scalar() or 0
                    
                    # Assign to floor with fewer people
                    if floor1_count <= floor2_count:
                        return ROOM_CONFERENCE_ROOM  # Floor 1
                    else:
                        return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
                except:
                    pass
            
            # Fallback: randomly assign between floors
            if random.random() < 0.5:
                return ROOM_CONFERENCE_ROOM  # Floor 1
            else:
                return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
        else:
            # Open office or cubicles - use employee's floor
            if room_choice == "open_office":
                return get_room_with_floor(ROOM_OPEN_OFFICE)
            else:
                return get_room_with_floor(ROOM_CUBICLES)
    
    # For IT, Reception, and Storage employees, they MUST stay in their work areas
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    is_it = "it" in title or "it" in department
    is_reception = "reception" in title or "receptionist" in title
    is_storage = ("storage" in title or "warehouse" in title or "inventory" in title or "stock" in title)
    
    home_room = getattr(employee, 'home_room', None)
    current_room = getattr(employee, 'current_room', None)
    
    # Receptionists and Storage employees MUST be at their work stations
    if (is_reception or is_storage) and home_room:
        # If not in their work area, return immediately unless on break or in meeting
        if current_room != home_room:
            # Only allow breaks and meetings to take them away
            if activity_type not in ["break", "meeting"]:
                return home_room  # IMMEDIATELY return to work area
    
    # IT employees should also stay in their work area when working/idle
    if is_it and activity_type in ["working", "idle"]:
        if home_room and current_room != home_room:
            # Return to work area
            return home_room
    
    # Default: return to home room if working, or use break/lounge areas if idle
    home_room = getattr(employee, 'home_room', None)
    if activity_type == "working":
        # When working, use home room (or cubicles if full)
        if home_room:
            if db_session:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if not has_space:
                    # Home room is full - use cubicles as overflow
                    return get_room_with_floor(ROOM_CUBICLES)
            return home_room
    elif activity_type == "idle":
        # When idle (not working), use break/lounge/wellness/theater areas
        # Randomly choose between breakroom, lounge, HR wellness (floor 3), or theater (floor 3)
        if employee_floor == 3:
            chosen_room = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, 
                ROOM_HR_WELLNESS, ROOM_THEATER
            ])
        else:
            # For other floors, use breakroom or lounge
            chosen_room = random.choice([ROOM_BREAKROOM, ROOM_LOUNGE])
        return get_room_with_floor(chosen_room)
    
    return None


def get_random_movement(employee) -> Optional[str]:
    """
    Generate occasional random movement for employees to make the office feel more alive.
    Employees move to rooms on their own floor.
    IT and Reception employees have reduced random movement to keep them in their work areas.
    
    Args:
        employee: Employee model instance
        
    Returns:
        Optional[str]: Random target room (with floor suffix if needed), or None if should stay
    """
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    
    # Check if employee is IT, Reception, or Storage
    is_it = "it" in title or "it" in department
    is_reception = "reception" in title or "receptionist" in title
    is_storage = ("storage" in title or "warehouse" in title or "inventory" in title or "stock" in title)
    
    # IT, Reception, and Storage employees should stay in their work areas - reduce random movement
    if is_it or is_reception or is_storage:
        # Only 5% chance of random movement (vs 20% for others)
        if random.random() > 0.05:
            return None
    else:
        # 20% chance of random movement when called
        if random.random() > 0.2:
            return None
    
    # Don't move if employee is already walking
    if employee.activity_state == "walking":
        return None
    
    # Get employee's floor (default to 1)
    employee_floor = getattr(employee, 'floor', 1)
    
    # Helper to add floor suffix if needed
    def get_room_with_floor(room_id):
        if employee_floor == 2 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor2"
        elif employee_floor == 3 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor3"
        elif employee_floor == 4 and not room_id.endswith('_floor2') and not room_id.endswith('_floor3') and not room_id.endswith('_floor4'):
            return f"{room_id}_floor4"
        elif employee_floor == 1 and (room_id.endswith('_floor2') or room_id.endswith('_floor3') or room_id.endswith('_floor4')):
            # Remove floor suffix for floor 1
            room_id = room_id.replace('_floor2', '').replace('_floor3', '').replace('_floor4', '')
            return room_id
        return room_id
    
    # IT employees might occasionally visit other areas, but prefer to stay in IT room
    if is_it:
        # Very rarely leave IT room - only for breaks or meetings
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS, ROOM_THEATER,  # Can go for breaks/wellness
                None, None, None, None, None  # 5/9 chance to stay
            ])
        else:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE,  # Can go for breaks
                None, None, None, None, None  # 5/7 chance to stay
            ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Reception employees should stay at reception - only leave for breaks
    if is_reception:
        # Very rarely leave reception - only for breaks
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS, ROOM_THEATER,  # Can go for breaks/wellness
                None, None, None, None, None, None  # 6/10 chance to stay
            ])
        else:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE,  # Can go for breaks
                None, None, None, None, None, None  # 6/8 chance to stay
            ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Storage employees should stay in storage - only leave for breaks
    if is_storage:
        # Very rarely leave storage - only for breaks
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS, ROOM_THEATER,  # Can go for breaks/wellness
                None, None, None, None, None, None  # 6/10 chance to stay
            ])
        else:
            chosen = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE,  # Can go for breaks
                None, None, None, None, None, None  # 6/8 chance to stay
            ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Random movement options based on employee role (on their floor)
    if employee.role == "CEO":
        # CEO might visit manager office or conference room
        chosen = random.choice([ROOM_MANAGER_OFFICE, ROOM_CONFERENCE_ROOM, None])
        return get_room_with_floor(chosen) if chosen else None
    elif employee.role == "Manager":
        # Managers might visit various rooms including break/lounge/wellness/theater
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_CONFERENCE_ROOM, 
                ROOM_OPEN_OFFICE, 
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                ROOM_HR_WELLNESS,
                ROOM_THEATER,
                None
            ])
        else:
            chosen = random.choice([
                ROOM_CONFERENCE_ROOM, 
                ROOM_OPEN_OFFICE, 
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                None
            ])
        return get_room_with_floor(chosen) if chosen else None
    else:
        # Regular employees might visit breakroom, lounge, wellness, theater, or other departments
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                ROOM_HR_WELLNESS,
                ROOM_THEATER,
                ROOM_OPEN_OFFICE,
                ROOM_CUBICLES,
                None
            ])
        else:
            chosen = random.choice([
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                ROOM_OPEN_OFFICE,
                ROOM_CUBICLES,
                None
            ])
        return get_room_with_floor(chosen) if chosen else None


def should_move_to_home_room(employee, activity_type: str) -> bool:
    """
    Determine if employee should return to their home room.
    IT and Reception employees should return to their work areas more often.
    Employees in training room should only be there if actually in training.
    
    Args:
        employee: Employee model instance
        activity_type: Current activity type
        
    Returns:
        bool: True if should return to home room
    """
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    home_room = getattr(employee, 'home_room', None)
    current_room = getattr(employee, 'current_room', None)
    activity_state = getattr(employee, 'activity_state', 'idle')
    
    # Check if employee is in training room but not actually in training
    from employees.room_assigner import ROOM_TRAINING_ROOM
    is_in_training_room = (current_room == ROOM_TRAINING_ROOM or 
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_5")
    is_actually_training = (activity_state == "training" or 
                           activity_type.lower() == "training" or
                           "training" in (getattr(employee, 'activity_state', '') or '').lower())
    
    # If in training room but not actually training, return to home room
    if is_in_training_room and not is_actually_training:
        return True
    
    # Check if employee is IT, Reception, or Storage
    is_it = "it" in title or "it" in department
    is_reception = "reception" in title or "receptionist" in title
    is_storage = ("storage" in title or "warehouse" in title or "inventory" in title or "stock" in title)
    
    # IT, Reception, and Storage employees MUST stay in their work areas
    if is_it or is_reception or is_storage:
        # If they're not in their home room, they MUST return immediately
        if current_room != home_room and home_room:
            # Receptionists and Storage employees are CRITICAL - they MUST be at their stations
            # Only allow them to leave for breaks or meetings, and return immediately after
            if activity_type in ["idle", "working", "completed", "finished"]:
                return True  # IMMEDIATELY return to work area
            # For breaks, return quickly (80% chance)
            if activity_type == "break" and random.random() < 0.8:
                return True
            # For meetings, return after meeting (50% chance - meetings can be longer)
            if activity_type == "meeting" and random.random() < 0.5:
                return True
    
    # If idle and not in home room, use break/lounge/wellness/theater areas (don't force return to home)
    if activity_type == "idle":
        # Check if employee is in a break/lounge/wellness/theater area - that's fine for idle
        from employees.room_assigner import ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS, ROOM_THEATER
        is_in_relaxation_area = (
            employee.current_room == ROOM_BREAKROOM or 
            employee.current_room == f"{ROOM_BREAKROOM}_floor2" or
            employee.current_room == f"{ROOM_BREAKROOM}_floor3" or
            employee.current_room == ROOM_LOUNGE or
            employee.current_room == f"{ROOM_LOUNGE}_floor2" or
            employee.current_room == f"{ROOM_LOUNGE}_floor3" or
            employee.current_room == f"{ROOM_HR_WELLNESS}_floor3" or
            employee.current_room == f"{ROOM_THEATER}_floor3"
        )
        if is_in_relaxation_area:
            return False  # Already in a relaxation area, that's perfect for idle
        # If not in relaxation area and not in home room, they should go to one (not home room when idle)
        if employee.current_room != employee.home_room:
            return False  # Don't force return to home room when idle - let them use relaxation areas
    
    # If activity is complete and not in home room, return home
    if activity_type in ["completed", "finished"] and employee.current_room != employee.home_room:
        return True
    
    return False


async def update_employee_location(employee, target_room: Optional[str], activity_state: str, db_session):
    """
    Update employee's location and activity state.
    Also updates floor if moving to a room on a different floor.
    RESPECTS ROOM CAPACITY - if room is full, employee will wait.
    
    Args:
        employee: Employee model instance
        target_room: Target room identifier (None to stay in current room)
        activity_state: New activity state
        db_session: Database session
    """
    if target_room and target_room != employee.current_room:
        # Check if target room has space
        has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
        
        if not has_space:
            # Room is full - employee must wait
            # Set activity state to "waiting" to indicate they're waiting for room to open
            employee.activity_state = "waiting"
            # Keep them in current room (or set to None if they don't have one)
            if not employee.current_room:
                # If they don't have a current room, put them in a hallway/waiting area
                # For now, we'll keep current_room as None and they'll appear as "waiting"
                pass
            # Don't update current_room - they stay where they are
            await db_session.flush()
            return  # Exit early - employee is waiting
        
        # Room has space - employee can move
        employee.activity_state = "walking"
        
        # Update floor if moving to a room on a different floor
        if target_room.endswith('_floor2'):
            employee.floor = 2
        elif target_room.endswith('_floor3'):
            employee.floor = 3
        elif target_room.endswith('_floor4'):
            employee.floor = 4
        elif not target_room.endswith('_floor2') and not target_room.endswith('_floor3') and not target_room.endswith('_floor4'):
            # Moving to floor 1 room
            if getattr(employee, 'floor', 1) in [2, 3, 4]:
                employee.floor = 1
        
        # Note: We'll set the current_room after a delay to simulate walking
        # For now, we'll set it immediately but the frontend can animate the transition
        employee.current_room = target_room
    else:
        # Employee is staying in place
        # If they were waiting, check if they can now enter their intended room
        if employee.activity_state == "waiting" and target_room:
            # Check if the room they were waiting for now has space
            has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                # Room now has space - allow entry
                employee.current_room = target_room
                employee.activity_state = activity_state
            else:
                # Still waiting
                employee.activity_state = "waiting"
        else:
            # Normal stay in place
            employee.activity_state = activity_state
    
    await db_session.flush()


async def process_employee_movement(employee, activity_type: str, activity_description: str, db_session):
    """
    Process employee movement based on their activity.
    
    Args:
        employee: Employee model instance
        activity_type: Type of activity
        activity_description: Description of activity
        db_session: Database session
    """
    # Check if employee has been in training room too long (more than 1 hour since hire)
    from employees.room_assigner import ROOM_TRAINING_ROOM
    from datetime import datetime, timedelta
    current_room = getattr(employee, 'current_room', None)
    is_in_training_room = (current_room == ROOM_TRAINING_ROOM or 
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4_5")
    
    if is_in_training_room:
        # Check if they've been hired recently (within last hour = still in training)
        hired_at = getattr(employee, 'hired_at', None)
        if hired_at:
            try:
                # Handle timezone-aware datetime
                if hasattr(hired_at, 'replace'):
                    if hired_at.tzinfo is not None:
                        # Timezone-aware, convert to UTC naive
                        hired_at_naive = hired_at.replace(tzinfo=None)
                    else:
                        hired_at_naive = hired_at
                else:
                    hired_at_naive = hired_at
                
                time_since_hire = datetime.utcnow() - hired_at_naive
                # If hired more than 1 hour ago and still in training room, move them out
                if time_since_hire > timedelta(hours=1):
                    # Training complete - move to home room and update activity state
                    employee.activity_state = "idle"  # No longer in training
                    await update_employee_location(employee, employee.home_room, "idle", db_session)
                    # Create activity to log training completion
                    from database.models import Activity
                    activity = Activity(
                        employee_id=employee.id,
                        activity_type="training_completed",
                        description=f"{employee.name} completed training and reported to work area ({employee.home_room})",
                        activity_metadata={
                            "training_duration": str(time_since_hire),
                            "home_room": employee.home_room
                        }
                    )
                    db_session.add(activity)
                    await db_session.flush()
                    return
            except Exception:
                # If there's any error with date comparison, just proceed normally
                pass
    
    # Check if should return to home room
    if should_move_to_home_room(employee, activity_type):
        await update_employee_location(employee, employee.home_room, "idle", db_session)
        return
    
    # Determine target room based on activity
    target_room = await determine_target_room(activity_type, activity_description, employee, db_session)
    
    # If no target room from activity, occasionally add random movement
    if target_room is None:
        random_movement = get_random_movement(employee)
        if random_movement:
            target_room = random_movement
    
    # Map activity type to activity state
    # Special handling: if employee is in training room, keep them in training state
    current_room = getattr(employee, 'current_room', None)
    from employees.room_assigner import ROOM_TRAINING_ROOM
    is_in_training_room = (current_room == ROOM_TRAINING_ROOM or 
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4")
    
    activity_state_map = {
        "meeting": "meeting",
        "break": "break",
        "training": "training",  # Keep as training, not working
        "working": "working",
        "idle": "idle",
        "completed": "idle",
        "finished": "idle",
    }
    
    activity_state = activity_state_map.get(activity_type.lower(), "working")
    
    # If employee is in training room, they should be in training state
    # If they're working/idle in training room, they should leave
    if is_in_training_room:
        if activity_type.lower() == "training" or "training" in activity_type.lower():
            activity_state = "training"
        elif activity_type.lower() in ["working", "idle", "completed", "finished"]:
            # They're done training, should return to home room
            await update_employee_location(employee, employee.home_room, "idle", db_session)
            return
    
    # Special handling for IT, Reception, and Storage employees - keep them in their work areas
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    is_it = "it" in title or "it" in department
    is_reception = "reception" in title or "receptionist" in title
    is_storage = ("storage" in title or "warehouse" in title or "inventory" in title or "stock" in title)
    
    # Check if employee is in training room but shouldn't be
    from employees.room_assigner import ROOM_TRAINING_ROOM
    current_room = getattr(employee, 'current_room', None)
    is_in_training_room = (current_room == ROOM_TRAINING_ROOM or 
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                           current_room == f"{ROOM_TRAINING_ROOM}_floor4")
    
    # If in training room but not actually training, move to home room
    if is_in_training_room and activity_state != "training" and activity_type.lower() != "training":
        await update_employee_location(employee, employee.home_room, "idle", db_session)
        return
    
    # If employee is waiting, they should retry entering their target room
    # (capacity check will happen in update_employee_location)
    if employee.activity_state == "waiting":
        # Employee was waiting - retry the movement
        # determine_target_room should return the same room based on activity
        if target_room:
            # Try to enter the target room again (capacity will be checked)
            await update_employee_location(employee, target_room, activity_state, db_session)
        else:
            # No target room determined - go to home room instead
            await update_employee_location(employee, employee.home_room, activity_state, db_session)
        return
    
    # If no target room determined, stay in current room or go to home room
    if target_room is None:
        home_room = getattr(employee, 'home_room', None)
        current_room = getattr(employee, 'current_room', None)
        
        # Receptionists and Storage employees MUST be at their work stations
        if (is_reception or is_storage) and home_room:
            # If not in their work area, FORCE them back immediately (or cubicles if work area is full)
            if current_room != home_room:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                else:
                    # Work area full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                # They're in their work area - stay there
                await update_employee_location(employee, None, activity_state, db_session)
        elif is_it and employee.current_room != employee.home_room:
            # IT employees should return to work area if not there (or cubicles if work area is full)
            home_room = getattr(employee, 'home_room', None)
            if home_room:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                else:
                    # Work area full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                await update_employee_location(employee, employee.home_room, activity_state, db_session)
        elif employee.current_room:
            # Stay in current room (unless it's training room and they shouldn't be there)
            if is_in_training_room and activity_state != "training":
                # Training complete - try to go to home room, or cubicles if full
                home_room = getattr(employee, 'home_room', None)
                if home_room:
                    has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                    if has_space:
                        await update_employee_location(employee, home_room, "idle", db_session)
                    else:
                        # Home room full - use cubicles as overflow
                        from employees.room_assigner import ROOM_CUBICLES
                        cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                        await update_employee_location(employee, cubicles_room, "idle", db_session)
                else:
                    await update_employee_location(employee, employee.home_room, "idle", db_session)
            else:
                await update_employee_location(employee, None, activity_state, db_session)
        else:
            # No current room, go to home room (or cubicles if home room is full)
            home_room = getattr(employee, 'home_room', None)
            if home_room and activity_state in ["working", "idle"]:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                else:
                    # Home room full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                await update_employee_location(employee, employee.home_room, activity_state, db_session)
    else:
        # For IT, Reception, and Storage, they MUST stay in their work areas
        home_room = getattr(employee, 'home_room', None)
        
        # Receptionists and Storage employees are CRITICAL - they MUST be at their stations
        if (is_reception or is_storage) and home_room:
            # ONLY allow breaks and meetings to take them away from their work area
            if target_room != home_room:
                if activity_type in ["break", "meeting"]:
                    # Allow temporary movement for breaks/meetings (capacity will be checked)
                    await update_employee_location(employee, target_room, activity_state, db_session)
                else:
                    # FORCE them back to their work area - but if full, use cubicles
                    has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                    if has_space:
                        await update_employee_location(employee, home_room, activity_state, db_session)
                    else:
                        # Work area full - use cubicles as overflow
                        from employees.room_assigner import ROOM_CUBICLES
                        cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                        await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                # They're going to their work area - but check if full, use cubicles if needed
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, target_room, activity_state, db_session)
                else:
                    # Work area full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
        elif is_it and activity_type in ["working", "idle"]:
            # IT employees should stay in their work area when working/idle
            if activity_type not in ["break", "meeting", "training"] and target_room != home_room:
                # Stay in work area instead (or cubicles if full)
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                else:
                    # Work area full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                # Move to target room (for breaks, meetings, etc.) - capacity will be checked
                await update_employee_location(employee, target_room, activity_state, db_session)
        else:
            # For other employees working/idle, check if target room is home room and if it's full
            if target_room == home_room and activity_state in ["working", "idle"] and home_room:
                has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
                if not has_space:
                    # Home room full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
                    return
            # Move to target room - capacity will be checked in update_employee_location
            await update_employee_location(employee, target_room, activity_state, db_session)

