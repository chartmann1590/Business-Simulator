"""Movement system for employees to move between rooms based on activities."""

import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)
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


async def find_available_training_room(db_session, exclude_employee_id: int = None) -> Optional[str]:
    """
    Find an available training room across all floors, including floor 4 overflow rooms.
    Prioritizes rooms with the most available space.
    
    Args:
        db_session: Database session
        exclude_employee_id: Optional employee ID to exclude from count
        
    Returns:
        Optional[str]: Available training room ID, or None if all are full
    """
    from employees.room_assigner import ROOM_TRAINING_ROOM
    
    # All possible training rooms (prioritize floor 4 overflow rooms for better distribution)
    training_rooms = [
        f"{ROOM_TRAINING_ROOM}_floor4",
        f"{ROOM_TRAINING_ROOM}_floor4_2",
        f"{ROOM_TRAINING_ROOM}_floor4_3",
        f"{ROOM_TRAINING_ROOM}_floor4_4",
        f"{ROOM_TRAINING_ROOM}_floor4_5",
        ROOM_TRAINING_ROOM,  # Floor 1
        f"{ROOM_TRAINING_ROOM}_floor2",  # Floor 2
    ]
    
    best_room = None
    most_space = -1
    
    for room_id in training_rooms:
        has_space = await check_room_has_space(room_id, db_session, exclude_employee_id)
        if has_space:
            # Calculate available space
            capacity = get_room_capacity(room_id)
            occupancy = await get_room_occupancy(room_id, db_session)
            available_space = capacity - occupancy
            
            if available_space > most_space:
                most_space = available_space
                best_room = room_id
    
    return best_room


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
    
    # Presentations, large meetings, events → Theater (floor 3)
    if ("presentation" in activity_lower or "presentation" in desc_lower or 
        "present" in desc_lower or "showcase" in desc_lower or 
        "all-hands" in desc_lower or "all hands" in desc_lower or
        "event" in desc_lower or "demo" in desc_lower or "demonstration" in desc_lower):
        return f"{ROOM_THEATER}_floor3"
    
    # Meetings → Conference Room, Huddle (floor 3), War Room (floor 3), or Theater (floor 3) - balance across all floors
    if "meeting" in activity_lower or "meeting" in desc_lower or "conference" in desc_lower:
        # Large meetings (10+ people mentioned) → Theater (floor 3)
        if "large" in desc_lower or "big" in desc_lower or "many" in desc_lower:
            return f"{ROOM_THEATER}_floor3"
        
        # Small meetings can use Huddle (floor 3), strategic meetings use War Room (floor 3)
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
    
    # Breaks → Breakroom, Lounge, or HR Wellness (on employee's floor)
    # Theater is NOT used for breaks - it's for presentations/events only
    if "break" in activity_lower or "break" in desc_lower or "lunch" in desc_lower or "coffee" in desc_lower:
        # Randomly choose between breakroom, lounge, or HR wellness (floor 3)
        # HR Wellness is on floor 3, so employees on floor 3 can use it
        if employee_floor == 3:
            chosen_room = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, 
                ROOM_HR_WELLNESS
            ])
        else:
            # For other floors, use breakroom or lounge
            # Allow employees from other floors to visit HR Wellness occasionally (15% chance)
            if random.random() < 0.15:
                return f"{ROOM_HR_WELLNESS}_floor3"
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
    
    # One-on-ones, performance reviews → Manager Office (on employee's floor)
    if ("one-on-one" in desc_lower or "one on one" in desc_lower or 
        "performance review" in desc_lower or 
        ("review" in desc_lower and "performance" in desc_lower) or
        "1-on-1" in desc_lower or "1:1" in desc_lower):
        return get_room_with_floor(ROOM_MANAGER_OFFICE)
    
    # Manager meetings → Manager Office (on employee's floor)
    if ("manager" in activity_lower or "executive" in activity_lower or 
        "strategy" in activity_lower or "planning" in activity_lower or
        "discuss" in desc_lower):
        if employee.role in ["CEO", "Manager"]:
            return get_room_with_floor(ROOM_MANAGER_OFFICE)
    
    # Design and creative work → Design Studio (floor 3)
    if ("design" in activity_lower or "design" in desc_lower or 
        "creative" in desc_lower or "prototype" in desc_lower or 
        "mockup" in desc_lower or "wireframe" in desc_lower or
        "ui" in desc_lower or "ux" in desc_lower or "graphic" in desc_lower):
        # Designers go to Design Studio, others can also use it for design-related work
        return f"{ROOM_DESIGN_STUDIO}_floor3"
    
    # Research and innovation work → Innovation Lab (floor 3)
    if ("research" in activity_lower or "research" in desc_lower or 
        "innovation" in desc_lower or "experiment" in desc_lower or
        "r&d" in desc_lower or "r and d" in desc_lower or
        "develop" in desc_lower and "new" in desc_lower or
        "explore" in desc_lower and ("technology" in desc_lower or "solution" in desc_lower)):
        return f"{ROOM_INNOVATION_LAB}_floor3"
    
    # Deep work and focused tasks → Focus Pods (floor 3)
    if ("focus" in desc_lower or "concentrate" in desc_lower or 
        "deep work" in desc_lower or "quiet" in desc_lower and "work" in desc_lower or
        "individual" in desc_lower and "work" in desc_lower or
        "solo" in desc_lower or "alone" in desc_lower and "work" in desc_lower):
        return f"{ROOM_FOCUS_PODS}_floor3"
    
    # Wellness and health activities → HR Wellness (floor 3)
    if ("wellness" in activity_lower or "wellness" in desc_lower or 
        "health" in desc_lower or "meditation" in desc_lower or
        "yoga" in desc_lower or "stress" in desc_lower or "relax" in desc_lower or
        "mental health" in desc_lower):
        return f"{ROOM_HR_WELLNESS}_floor3"
    
    # Collaboration/team work → Conference Room, Collaboration Lounge (floor 3), Open Office, or Cubicles
    # Exclude performance reviews (handled above) and code reviews (which might be design/tech work)
    if (("collaborate" in desc_lower or "team" in desc_lower or "discuss" in desc_lower or
        "brainstorm" in desc_lower or ("review" in desc_lower and "performance" not in desc_lower)) and
        "one-on-one" not in desc_lower and "one on one" not in desc_lower):
        # 25% collaboration lounge (floor 3), 20% conference room, 30% open office, 25% cubicles
        # Increased open office usage for better collaboration
        room_choice = random.choice([
            "collab_lounge", "collab_lounge", "collab_lounge", "collab_lounge",  # 25%
            "conference", "conference",  # 20%
            "open_office", "open_office", "open_office", "open_office", "open_office", "open_office",  # 30%
            "cubicles", "cubicles", "cubicles", "cubicles"  # 25%
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
        # But check if activity description suggests a specific room
        if home_room:
            # Check if working activity suggests focus pods for deep work
            if ("focus" in desc_lower or "concentrate" in desc_lower or 
                "deep work" in desc_lower or "quiet" in desc_lower):
                return f"{ROOM_FOCUS_PODS}_floor3"
            
            # Check if working activity suggests design work
            if ("design" in desc_lower or "creative" in desc_lower or 
                "prototype" in desc_lower or "mockup" in desc_lower):
                return f"{ROOM_DESIGN_STUDIO}_floor3"
            
            # Check if working activity suggests research/innovation
            if ("research" in desc_lower or "innovation" in desc_lower or 
                "experiment" in desc_lower or "r&d" in desc_lower):
                return f"{ROOM_INNOVATION_LAB}_floor3"
            
            if db_session:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if not has_space:
                    # Home room is full - use cubicles as overflow
                    return get_room_with_floor(ROOM_CUBICLES)
            return home_room
    elif activity_type == "idle":
        # When idle (not working), use break/lounge/wellness/theater areas
        # Randomly choose between breakroom, lounge, HR wellness (floor 3), or theater (floor 3)
        # But don't use theater for idle - it's for presentations/events
        if employee_floor == 3:
            chosen_room = random.choice([
                ROOM_BREAKROOM, ROOM_LOUNGE, 
                ROOM_HR_WELLNESS
            ])
        else:
            # For other floors, use breakroom or lounge
            # Allow employees from other floors to visit HR Wellness occasionally (10% chance)
            if random.random() < 0.1:
                return f"{ROOM_HR_WELLNESS}_floor3"
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
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS,  # Can go for breaks/wellness
                None, None, None, None, None  # 5/8 chance to stay
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
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS,  # Can go for breaks/wellness
                None, None, None, None, None, None  # 6/9 chance to stay
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
                ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS,  # Can go for breaks/wellness
                None, None, None, None, None, None  # 6/9 chance to stay
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
    elif employee.role in ["Manager", "CTO", "COO", "CFO"]:
        # Managers might visit various rooms including break/lounge/wellness
        # Theater is NOT used for random movement - only for presentations/events
        if employee_floor == 3:
            chosen = random.choice([
                ROOM_CONFERENCE_ROOM, 
                ROOM_OPEN_OFFICE, 
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                ROOM_HR_WELLNESS,
                ROOM_COLLAB_LOUNGE,  # Can visit collaboration spaces
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
        # Regular employees might visit various rooms based on their work
        # Check if they're designers, engineers, or researchers for specialized rooms
        is_designer = "design" in title or "design" in department
        is_engineer = "engineer" in title or "developer" in title or department in ["engineering", "development"]
        is_researcher = "research" in title or "r&d" in title or department == "research"
        
        if employee_floor == 3:
            # Floor 3 employees have access to all floor 3 rooms
            options = [
                ROOM_BREAKROOM,
                ROOM_LOUNGE,
                ROOM_HR_WELLNESS,
                ROOM_OPEN_OFFICE,
                ROOM_CUBICLES,
                ROOM_COLLAB_LOUNGE,
            ]
            # Add specialized rooms based on role
            if is_designer:
                options.append(ROOM_DESIGN_STUDIO)
            if is_engineer:
                options.append(ROOM_FOCUS_PODS)
            if is_researcher:
                options.append(ROOM_INNOVATION_LAB)
            options.append(None)
            chosen = random.choice(options)
        else:
            # Other floors - can visit floor 3 specialized rooms occasionally (5% chance each)
            rand = random.random()
            if rand < 0.05 and is_designer:
                return f"{ROOM_DESIGN_STUDIO}_floor3"
            elif rand < 0.10 and is_engineer:
                return f"{ROOM_FOCUS_PODS}_floor3"
            elif rand < 0.15 and is_researcher:
                return f"{ROOM_INNOVATION_LAB}_floor3"
            elif rand < 0.20:
                # 5% chance to visit HR Wellness on floor 3
                return f"{ROOM_HR_WELLNESS}_floor3"
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
    activity_state = getattr(employee, 'activity_state', 'working')
    
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


async def fix_walking_employees_without_destination(db_session):
    """Fix employees who are in walking state but don't have a target_room, and complete journeys for those who have arrived.
    This function ensures EVERY walking employee has a target_room set."""
    from sqlalchemy import select, and_, or_
    from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
    from database.models import Employee
    
    fixed_count = 0
    completed_count = 0
    
    # Get ALL walking employees first to see the full picture
    all_walking_result = await db_session.execute(
        select(Employee).where(
            and_(
                Employee.status == "active",
                Employee.activity_state == "walking"
            )
        )
    )
    all_walking = all_walking_result.scalars().all()
    logger.info(f"Found {len(all_walking)} employees in walking state")
    
    # First: Complete journeys for employees who have arrived at their destination
    result = await db_session.execute(
        select(Employee).where(
            and_(
                Employee.status == "active",
                Employee.activity_state == "walking",
                Employee.target_room.isnot(None),
                Employee.target_room != "",
                Employee.current_room == Employee.target_room
            )
        )
    )
    arrived_employees = result.scalars().all()
    
    for employee in arrived_employees:
        # They've arrived - complete the journey
        employee.activity_state = "working"
        employee.target_room = None
        completed_count += 1
    
    # Second: Fix employees walking without a target_room
    result = await db_session.execute(
        select(Employee).where(
            and_(
                Employee.status == "active",
                Employee.activity_state == "walking",
                or_(
                    Employee.target_room.is_(None),
                    Employee.target_room == ""
                )
            )
        )
    )
    stuck_employees = result.scalars().all()
    
    for employee in stuck_employees:
        # Generate a destination for them - be aggressive about finding one
        target_room = None
        
        # First try: home room
        if employee.home_room:
            has_space = await check_room_has_space(employee.home_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                target_room = employee.home_room
        
        # Second try: current room (if they have one, they're already there - complete journey)
        if not target_room and employee.current_room:
            # If they're already in a room, complete the journey
            employee.activity_state = "working"
            employee.target_room = None
            fixed_count += 1
            logger.info(f"Completed journey for {employee.name} (ID: {employee.id}) - already in {employee.current_room}")
            continue
        
        # Third try: cubicles on their floor
        if not target_room:
            employee_floor = getattr(employee, 'floor', 1)
            cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
            has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                target_room = cubicles_room
        
        # Fourth try: open office on their floor
        if not target_room:
            employee_floor = getattr(employee, 'floor', 1)
            open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
            has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                target_room = open_office_room
        
        # Fifth try: try ANY floor's cubicles or open office
        if not target_room:
            for floor in [1, 2, 3, 4]:
                if floor == 1:
                    test_rooms = [ROOM_CUBICLES, ROOM_OPEN_OFFICE]
                else:
                    test_rooms = [
                        f"{ROOM_CUBICLES}_floor{floor}",
                        f"{ROOM_OPEN_OFFICE}_floor{floor}"
                    ]
                for test_room in test_rooms:
                    has_space = await check_room_has_space(test_room, db_session, exclude_employee_id=employee.id)
                    if has_space:
                        target_room = test_room
                        # Update their floor to match
                        employee.floor = floor
                        break
                if target_room:
                    break
        
        if target_room:
            employee.target_room = target_room
            # Don't move current_room yet - keep them walking to show destination
            fixed_count += 1
            logger.info(f"Assigned destination {target_room} to {employee.name} (ID: {employee.id})")
        else:
            # Last resort: if we can't find ANY room, set them to working in current room or home room
            if employee.current_room:
                employee.activity_state = "working"
                employee.target_room = None
                fixed_count += 1
                logger.info(f"Completed journey for {employee.name} (ID: {employee.id}) - no available rooms, staying in {employee.current_room}")
            elif employee.home_room:
                employee.current_room = employee.home_room
                employee.activity_state = "working"
                employee.target_room = None
                fixed_count += 1
                logger.info(f"Set {employee.name} (ID: {employee.id}) to working in home room {employee.home_room}")
            else:
                # No room at all - assign them to open office floor 1
                employee.current_room = ROOM_OPEN_OFFICE
                employee.floor = 1
                employee.activity_state = "working"
                employee.target_room = None
                fixed_count += 1
                logger.info(f"Assigned {employee.name} (ID: {employee.id}) to {ROOM_OPEN_OFFICE} as last resort")
    
    # Third: Move employees who are walking to their destination (if they haven't arrived yet)
    result = await db_session.execute(
        select(Employee).where(
            and_(
                Employee.status == "active",
                Employee.activity_state == "walking",
                Employee.target_room.isnot(None),
                Employee.target_room != "",
                Employee.current_room != Employee.target_room
            )
        )
    )
    walking_employees = result.scalars().all()
    
    for employee in walking_employees:
        # Check if destination still has space
        has_space = await check_room_has_space(employee.target_room, db_session, exclude_employee_id=employee.id)
        if has_space:
            # Move them to destination and complete journey
            # Track training sessions when entering/leaving training rooms
            from business.training_manager import TrainingManager
            training_manager = TrainingManager()
            old_room = employee.current_room
            new_room = employee.target_room
            
            # Check if entering or leaving a training room
            is_training_room = (new_room and (
                new_room == ROOM_TRAINING_ROOM or
                new_room.startswith(f"{ROOM_TRAINING_ROOM}_floor")
            ))
            was_training_room = (old_room and (
                old_room == ROOM_TRAINING_ROOM or
                old_room.startswith(f"{ROOM_TRAINING_ROOM}_floor")
            ))
            
            # End training session if leaving training room
            if was_training_room and not is_training_room:
                try:
                    await training_manager.end_training_session(employee, db_session)
                except Exception as e:
                    logger.error(f"Error ending training session for {employee.name}: {e}")
            
            employee.current_room = employee.target_room
            employee.activity_state = "working"
            employee.target_room = None
            
            # Start training session if entering training room
            if is_training_room and not was_training_room:
                try:
                    await training_manager.start_training_session(employee, new_room, db_session)
                except Exception as e:
                    logger.error(f"Error starting training session for {employee.name}: {e}")
            completed_count += 1
        else:
            # Destination is full - find alternative
            if employee.home_room:
                has_space = await check_room_has_space(employee.home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    employee.target_room = employee.home_room
                    employee.current_room = employee.home_room
                    employee.activity_state = "working"
                    employee.target_room = None
                    completed_count += 1
    
    # Final safety check: Find ANY remaining walking employees without target_room and fix them
    final_check_result = await db_session.execute(
        select(Employee).where(
            and_(
                Employee.status == "active",
                Employee.activity_state == "walking",
                or_(
                    Employee.target_room.is_(None),
                    Employee.target_room == ""
                )
            )
        )
    )
    final_stuck = final_check_result.scalars().all()
    
    for employee in final_stuck:
        # Emergency fix - assign to any available room
        from employees.room_assigner import ROOM_OPEN_OFFICE, ROOM_CUBICLES
        employee_floor = getattr(employee, 'floor', 1)
        
        # Try open office first
        open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
        has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
        if has_space:
            employee.target_room = open_office_room
            fixed_count += 1
        else:
            # Try cubicles
            cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
            has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                employee.target_room = cubicles_room
                fixed_count += 1
            else:
                # Last resort: just assign it anyway (they'll complete the journey)
                employee.target_room = open_office_room
                fixed_count += 1
                logger.warning(f"Assigned {employee.name} (ID: {employee.id}) to {open_office_room} even though it may be full")
    
    if fixed_count > 0 or completed_count > 0:
        await db_session.flush()
        logger.info(f"Fixed {fixed_count} employees walking without destination, completed {completed_count} journeys")
    
    return fixed_count + completed_count


async def update_employee_location(employee, target_room: Optional[str], activity_state: str, db_session):
    """
    Update employee's location and activity state.
    Also updates floor if moving to a room on a different floor.
    RESPECTS ROOM CAPACITY - if room is full, tries alternatives before setting to waiting.
    
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
            # Room is full - try alternatives BEFORE setting to waiting
            # Only set to waiting as last resort
            if activity_state in ["working"]:
                # Try home room first
                home_room = getattr(employee, 'home_room', None)
                if home_room and home_room != target_room:
                    has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                    if has_space:
                        target_room = home_room
                        has_space = True
                
                # Try cubicles as fallback
                if not has_space:
                    from employees.room_assigner import ROOM_CUBICLES
                    employee_floor = getattr(employee, 'floor', 1)
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                    if cubicles_room != target_room:
                        has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
                        if has_space:
                            target_room = cubicles_room
                            has_space = True
                
                # Try open office as fallback
                if not has_space:
                    from employees.room_assigner import ROOM_OPEN_OFFICE
                    open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                    if open_office_room != target_room:
                        has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
                        if has_space:
                            target_room = open_office_room
                            has_space = True
            
            if not has_space:
                # All alternatives tried - set to waiting as last resort
                employee.activity_state = "waiting"
                # Keep them in current room (or set to None if they don't have one)
                if not employee.current_room:
                    # If they don't have a current room, put them in a hallway/waiting area
                    # For now, we'll keep current_room as None and they'll appear as "waiting"
                    pass
                # Don't update current_room - they stay where they are
                await db_session.flush()
                return  # Exit early - employee is waiting
        
        # HARDENED CAPACITY CHECK: Double-check room has space before allowing movement
        # This prevents any race conditions or edge cases that might allow over-capacity
        final_check = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
        if not final_check:
            # Room became full between checks - try similar room or fallback
            logger.warning(f"Room {target_room} became full during movement check for {employee.name} (ID: {employee.id}), finding alternative...")
            alternative_room = await find_available_similar_room(target_room, db_session, exclude_employee_id=employee.id)
            if alternative_room:
                target_room = alternative_room
                final_check = True
            else:
                # Try generic fallbacks
                employee_floor = getattr(employee, 'floor', 1)
                from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                if await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id):
                    target_room = cubicles_room
                    final_check = True
                else:
                    open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                    if await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id):
                        target_room = open_office_room
                        final_check = True
                    else:
                        # All rooms full - set to waiting
                        employee.activity_state = "waiting"
                        await db_session.flush()
                        return
        
        # Room has space - employee can move
        employee.activity_state = "walking"
        # Set target_room to track where they're walking to - ALWAYS set it, NO EXCEPTIONS
        if target_room:
            employee.target_room = target_room
        else:
            # If no target_room provided but we're setting to walking, this should NEVER happen
            # But if it does, generate a destination immediately
            logger.error(f"CRITICAL: Employee {employee.name} (ID: {employee.id}) set to walking without target_room! Generating destination...")
            # Try home room first
            if employee.home_room:
                employee.target_room = employee.home_room
            elif employee.current_room:
                employee.target_room = employee.current_room
            else:
                # Last resort: assign to open office on their floor
                from employees.room_assigner import ROOM_OPEN_OFFICE
                employee_floor = getattr(employee, 'floor', 1)
                employee.target_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                logger.error(f"Assigned {employee.name} (ID: {employee.id}) to {employee.target_room} as emergency destination")
        
        # Update floor if moving to a room on a different floor
        if target_room:
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
        
        # Keep current_room as is while walking - don't update it immediately
        # This allows the frontend to show where they're going
        # The current_room will be updated when they actually arrive (in a future tick)
        # For now, keep them in their current room but mark them as walking to target_room
    else:
        # Employee is staying in place
        # HARDENED CHECK: Verify current room is not over-capacity
        if employee.current_room:
            current_occupancy = await get_room_occupancy(employee.current_room, db_session)
            current_capacity = get_room_capacity(employee.current_room)
            if current_occupancy > current_capacity:
                # Current room is over-capacity - must move immediately
                logger.error(f"CRITICAL: Employee {employee.name} (ID: {employee.id}) is in over-capacity room {employee.current_room} ({current_occupancy}/{current_capacity}). Moving immediately!")
                alternative_room = await find_available_similar_room(employee.current_room, db_session, exclude_employee_id=employee.id)
                if alternative_room:
                    employee.activity_state = "walking"
                    employee.target_room = alternative_room
                    # Update floor if needed
                    if alternative_room.endswith('_floor2'):
                        employee.floor = 2
                    elif alternative_room.endswith('_floor3'):
                        employee.floor = 3
                    elif alternative_room.endswith('_floor4'):
                        employee.floor = 4
                    await db_session.flush()
                    return
                else:
                    # No alternative found - try generic fallback
                    employee_floor = getattr(employee, 'floor', 1)
                    from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                    if await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id):
                        employee.activity_state = "walking"
                        employee.target_room = cubicles_room
                        await db_session.flush()
                        return
        
        # If they were waiting, check if they can now enter their intended room
        if employee.activity_state == "waiting" and target_room:
            # Check if the room they were waiting for now has space
            has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                # Room now has space - allow entry (but verify capacity one more time)
                final_occupancy = await get_room_occupancy(target_room, db_session)
                final_capacity = get_room_capacity(target_room)
                if final_occupancy < final_capacity:
                    # Track training sessions when entering/leaving training rooms
                    from business.training_manager import TrainingManager
                    training_manager = TrainingManager()
                    old_room = employee.current_room
                    new_room = target_room
                    
                    # Check if entering or leaving a training room
                    is_training_room = (new_room and (
                        new_room == ROOM_TRAINING_ROOM or
                        new_room.startswith(f"{ROOM_TRAINING_ROOM}_floor")
                    ))
                    was_training_room = (old_room and (
                        old_room == ROOM_TRAINING_ROOM or
                        old_room.startswith(f"{ROOM_TRAINING_ROOM}_floor")
                    ))
                    
                    # End training session if leaving training room
                    if was_training_room and not is_training_room:
                        try:
                            await training_manager.end_training_session(employee, db_session)
                        except Exception as e:
                            logger.error(f"Error ending training session for {employee.name}: {e}")
                    
                    employee.current_room = target_room
                    employee.activity_state = activity_state
                    # Clear target_room since they've arrived
                    employee.target_room = None
                    
                    # Start training session if entering training room
                    if is_training_room and not was_training_room:
                        try:
                            await training_manager.start_training_session(employee, new_room, db_session)
                        except Exception as e:
                            logger.error(f"Error starting training session for {employee.name}: {e}")
                else:
                    # Room became full - still waiting
                    employee.activity_state = "waiting"
            else:
                # Still waiting
                employee.activity_state = "waiting"
        else:
            # Normal stay in place - clear target_room if they were walking
            if employee.activity_state == "walking" and activity_state != "walking":
                # They've arrived at their destination
                employee.target_room = None
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
    # Check if employee has been in training room too long (more than 30 minutes - training limit)
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
        # FIRST: If employee is in training room but has "waiting" status, fix it immediately
        # They're already in the room, so they should be in "training" state
        if employee.activity_state == "waiting":
            employee.activity_state = "training"
            await db_session.flush()
            # Continue processing to check if training should be complete
        
        # Check if training session has exceeded 30 minutes (primary check)
        from database.models import TrainingSession
        from sqlalchemy import select, and_
        session_result = await db_session.execute(
            select(TrainingSession).where(
                and_(
                    TrainingSession.employee_id == employee.id,
                    TrainingSession.status == "in_progress"
                )
            )
            .order_by(TrainingSession.start_time.desc())
        )
        training_session = session_result.scalar_one_or_none()
        
        if training_session and training_session.start_time:
            # Check session duration
            start_time_naive = training_session.start_time.replace(tzinfo=None) if training_session.start_time.tzinfo else training_session.start_time
            time_in_training = datetime.utcnow() - start_time_naive
            if time_in_training > timedelta(minutes=30):
                # Training exceeded 30 minutes - end session and move employee out
                training_session.end_time = datetime.utcnow()
                training_session.status = "completed"
                duration = training_session.end_time - start_time_naive
                training_session.duration_minutes = int(duration.total_seconds() / 60)
                
                # Move to home room and start working
                employee.activity_state = "working"
                await update_employee_location(employee, employee.home_room, "working", db_session)
                
                # Create activity to log training completion
                from database.models import Activity
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="training_completed",
                    description=f"{employee.name} completed training (30 minute limit reached) and reported to work area ({employee.home_room})",
                    activity_metadata={
                        "training_duration_minutes": training_session.duration_minutes,
                        "home_room": employee.home_room
                    }
                )
                db_session.add(activity)
                await db_session.flush()
                return
        
        # Fallback: Check if they've been hired recently (for employees without session records)
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
                # If hired more than 30 minutes ago and still in training room, move them out
                # (Training should never last more than 30 minutes)
                if time_since_hire > timedelta(minutes=30):
                    # Training complete - move to home room and start working
                    employee.activity_state = "working"
                    await update_employee_location(employee, employee.home_room, "working", db_session)
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
    
    # Check if employee is in training state but not in a training room (stuck waiting)
    # This can happen if they were waiting for a training room that was full
    if employee.activity_state == "training" and not is_in_training_room:
        # Find an available training room
        available_training_room = await find_available_training_room(db_session, exclude_employee_id=employee.id)
        if available_training_room:
            # Found an available training room - move there
            await update_employee_location(employee, available_training_room, "training", db_session)
            return
        # If no training room available, check if training should be complete
        hired_at = getattr(employee, 'hired_at', None)
        if hired_at:
            try:
                from datetime import datetime, timedelta
                if hasattr(hired_at, 'replace'):
                    if hired_at.tzinfo is not None:
                        hired_at_naive = hired_at.replace(tzinfo=None)
                    else:
                        hired_at_naive = hired_at
                else:
                    hired_at_naive = hired_at
                
                time_since_hire = datetime.utcnow() - hired_at_naive
                if time_since_hire > timedelta(hours=1):
                    # Training complete - move to home room and start working
                    employee.activity_state = "working"
                    await update_employee_location(employee, employee.home_room, "working", db_session)
                    from database.models import Activity
                    activity = Activity(
                        employee_id=employee.id,
                        activity_type="training_completed",
                        description=f"{employee.name} completed training and reported to work area ({employee.home_room})",
                        activity_metadata={
                            "training_duration": str(time_since_hire),
                            "home_room": employee.home_room,
                            "note": "Training completed while waiting for room"
                        }
                    )
                    db_session.add(activity)
                    await db_session.flush()
                    return
            except Exception:
                pass
    
    # Check if should return to home room
    if should_move_to_home_room(employee, activity_type):
        await update_employee_location(employee, employee.home_room, "working", db_session)
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
        "idle": "working",  # Employees should be working, not idle
        "completed": "working",  # After completing something, they should be working
        "finished": "working",  # After finishing something, they should be working
    }
    
    activity_state = activity_state_map.get(activity_type.lower(), "working")
    
    # If employee is in training room, they should be in training state
    # If they're working/idle in training room, they should leave
    if is_in_training_room:
        if activity_type.lower() == "training" or "training" in activity_type.lower():
            activity_state = "training"
        elif activity_type.lower() in ["working", "idle", "completed", "finished"]:
            # They're done training, should return to home room and start working
            await update_employee_location(employee, employee.home_room, "working", db_session)
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
    
    # If in training room but not actually training, move to home room and start working
    if is_in_training_room and activity_state != "training" and activity_type.lower() != "training":
        await update_employee_location(employee, employee.home_room, "working", db_session)
        return
    
    # If employee is waiting, IMMEDIATELY try to fix it - don't wait
    # (capacity check will happen in update_employee_location)
    if employee.activity_state == "waiting":
        # FIRST: Check if they're already in a training room - if so, just fix the status
        current_room = getattr(employee, 'current_room', None)
        from employees.room_assigner import ROOM_TRAINING_ROOM
        is_in_training_room_waiting = (current_room == ROOM_TRAINING_ROOM or 
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                                      current_room == f"{ROOM_TRAINING_ROOM}_floor4_5")
        
        if is_in_training_room_waiting:
            # They're already in a training room but marked as waiting - fix the status
            employee.activity_state = "training"
            await db_session.flush()
            return  # They're already where they need to be
        
        # Employee was waiting - try to find an available room
        # Special handling for training: find ANY available training room
        is_training_state = (activity_state == "training" or 
                            activity_type.lower() == "training" or
                            "training" in (getattr(employee, 'activity_state', '') or '').lower())
        
        if is_training_state:
            # Employee is waiting for training - find any available training room
            available_training_room = await find_available_training_room(db_session, exclude_employee_id=employee.id)
            if available_training_room:
                # Found an available training room - move there
                await update_employee_location(employee, available_training_room, "training", db_session)
                return
            else:
                # All training rooms are full - check if they've been in training too long
                # If hired more than 1 hour ago, move them out even if waiting
                hired_at = getattr(employee, 'hired_at', None)
                if hired_at:
                    try:
                        from datetime import datetime, timedelta
                        if hasattr(hired_at, 'replace'):
                            if hired_at.tzinfo is not None:
                                hired_at_naive = hired_at.replace(tzinfo=None)
                            else:
                                hired_at_naive = hired_at
                        else:
                            hired_at_naive = hired_at
                        
                        time_since_hire = datetime.utcnow() - hired_at_naive
                        if time_since_hire > timedelta(hours=1):
                            # Training complete - move to home room and start working
                            employee.activity_state = "working"
                            await update_employee_location(employee, employee.home_room, "working", db_session)
                            from database.models import Activity
                            activity = Activity(
                                employee_id=employee.id,
                                activity_type="training_completed",
                                description=f"{employee.name} completed training and reported to work area ({employee.home_room})",
                                activity_metadata={
                                    "training_duration": str(time_since_hire),
                                    "home_room": employee.home_room,
                                    "note": "Moved out due to training room capacity"
                                }
                            )
                            db_session.add(activity)
                            await db_session.flush()
                            return
                    except Exception:
                        pass
                # Still waiting for training room - keep waiting but try again next tick
                return
        
        # Not training - AGGRESSIVELY find an alternative room
        # Don't just retry - try multiple fallback options
        moved = False
        
        if target_room:
            # Try target room first
            has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
            if has_space:
                await update_employee_location(employee, target_room, activity_state, db_session)
                moved = True
            else:
                # Target room full - try alternatives based on activity
                if activity_state in ["working"]:
                    # For working, try home room, then cubicles, then open office
                    home_room = getattr(employee, 'home_room', None)
                    if home_room:
                        has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                        if has_space:
                            await update_employee_location(employee, home_room, activity_state, db_session)
                            moved = True
                    
                    if not moved:
                        from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                        employee_floor = getattr(employee, 'floor', 1)
                        # Try cubicles
                        cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                        has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
                        if has_space:
                            await update_employee_location(employee, cubicles_room, activity_state, db_session)
                            moved = True
                        
                        # Try open office
                        if not moved:
                            open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                            has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
                            if has_space:
                                await update_employee_location(employee, open_office_room, activity_state, db_session)
                                moved = True
                else:
                    # For other activities, just retry target room (it will set to waiting if still full)
                    await update_employee_location(employee, target_room, activity_state, db_session)
                    moved = True
        else:
            # No target room - try home room, then cubicles, then open office
            home_room = getattr(employee, 'home_room', None)
            if home_room:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                    moved = True
            
            if not moved:
                from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                employee_floor = getattr(employee, 'floor', 1)
                cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
                    moved = True
                
                if not moved:
                    open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                    has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
                    if has_space:
                        await update_employee_location(employee, open_office_room, activity_state, db_session)
                        moved = True
        
        # If still not moved and they're waiting, change state to working if they have a current room
        # This prevents infinite waiting - they should be working, not idle
        if not moved and employee.activity_state == "waiting" and employee.current_room:
            # Clear target_room if they were walking
            if getattr(employee, 'target_room', None):
                employee.target_room = None
            employee.activity_state = "working"
            await db_session.flush()
        
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
                        await update_employee_location(employee, home_room, "working", db_session)
                    else:
                        # Home room full - use cubicles as overflow
                        from employees.room_assigner import ROOM_CUBICLES
                        cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                        await update_employee_location(employee, cubicles_room, "working", db_session)
                else:
                    await update_employee_location(employee, employee.home_room, "working", db_session)
            else:
                await update_employee_location(employee, None, activity_state, db_session)
        else:
            # No current room, go to home room (or cubicles if home room is full)
            home_room = getattr(employee, 'home_room', None)
            # Convert "idle" to "working" - employees should be working, not idle
            if activity_state == "idle":
                activity_state = "working"
            if home_room and activity_state in ["working"]:
                has_space = await check_room_has_space(home_room, db_session, exclude_employee_id=employee.id)
                if has_space:
                    await update_employee_location(employee, home_room, activity_state, db_session)
                else:
                    # Home room full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
            else:
                # Ensure we use "working" not "idle"
                final_state = "working" if activity_state == "idle" else activity_state
                await update_employee_location(employee, employee.home_room, final_state, db_session)
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
            if target_room == home_room and activity_state in ["working"] and home_room:
                has_space = await check_room_has_space(target_room, db_session, exclude_employee_id=employee.id)
                if not has_space:
                    # Home room full - use cubicles as overflow
                    from employees.room_assigner import ROOM_CUBICLES
                    cubicles_room = f"{ROOM_CUBICLES}_floor{employee.floor}" if employee.floor > 1 else ROOM_CUBICLES
                    await update_employee_location(employee, cubicles_room, activity_state, db_session)
                    return
            # Move to target room - capacity will be checked in update_employee_location
            await update_employee_location(employee, target_room, activity_state, db_session)


def find_similar_rooms(room_id: str) -> list:
    """
    Find similar rooms that can be used as alternatives for a given room.
    Groups rooms by type (office space, meeting rooms, break areas, etc.)
    
    Args:
        room_id: Room identifier
        
    Returns:
        list: List of similar room identifiers that can serve as alternatives
    """
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
    
    # Extract base room type and floor
    base_room = room_id.replace('_floor2', '').replace('_floor3', '').replace('_floor4', '').replace('_floor4_2', '').replace('_floor4_3', '').replace('_floor4_4', '').replace('_floor4_5', '')
    
    # Determine floor
    floor = 1
    if '_floor2' in room_id:
        floor = 2
    elif '_floor3' in room_id:
        floor = 3
    elif '_floor4' in room_id:
        floor = 4
    
    similar_rooms = []
    
    # Office space group (open office, cubicles, hotdesk)
    if base_room in [ROOM_OPEN_OFFICE, ROOM_CUBICLES, ROOM_HOTDESK]:
        if floor == 1:
            similar_rooms = [ROOM_OPEN_OFFICE, ROOM_CUBICLES]
        elif floor == 2:
            similar_rooms = [f"{ROOM_OPEN_OFFICE}_floor2", f"{ROOM_CUBICLES}_floor2"]
        elif floor == 3:
            similar_rooms = [f"{ROOM_OPEN_OFFICE}_floor3", f"{ROOM_CUBICLES}_floor3", f"{ROOM_HOTDESK}_floor3"]
        elif floor == 4:
            similar_rooms = [
                f"{ROOM_CUBICLES}_floor4", f"{ROOM_CUBICLES}_floor4_2", 
                f"{ROOM_CUBICLES}_floor4_3", f"{ROOM_CUBICLES}_floor4_4", 
                f"{ROOM_CUBICLES}_floor4_5"
            ]
        # Also include other floors' office spaces
        for f in [1, 2, 3, 4]:
            if f != floor:
                if f == 1:
                    similar_rooms.extend([ROOM_OPEN_OFFICE, ROOM_CUBICLES])
                elif f == 2:
                    similar_rooms.extend([f"{ROOM_OPEN_OFFICE}_floor2", f"{ROOM_CUBICLES}_floor2"])
                elif f == 3:
                    similar_rooms.extend([f"{ROOM_OPEN_OFFICE}_floor3", f"{ROOM_CUBICLES}_floor3", f"{ROOM_HOTDESK}_floor3"])
                elif f == 4:
                    similar_rooms.extend([
                        f"{ROOM_CUBICLES}_floor4", f"{ROOM_CUBICLES}_floor4_2", 
                        f"{ROOM_CUBICLES}_floor4_3", f"{ROOM_CUBICLES}_floor4_4", 
                        f"{ROOM_CUBICLES}_floor4_5"
                    ])
    
    # Meeting rooms group (conference, huddle, war room, theater)
    elif base_room in [ROOM_CONFERENCE_ROOM, ROOM_HUDDLE, ROOM_WAR_ROOM, ROOM_THEATER]:
        if floor == 1:
            similar_rooms = [ROOM_CONFERENCE_ROOM]
        elif floor == 2:
            similar_rooms = [f"{ROOM_CONFERENCE_ROOM}_floor2"]
        elif floor == 3:
            similar_rooms = [f"{ROOM_CONFERENCE_ROOM}_floor3", f"{ROOM_HUDDLE}_floor3", f"{ROOM_WAR_ROOM}_floor3", f"{ROOM_THEATER}_floor3"]
        # Include other floors' meeting rooms
        similar_rooms.extend([ROOM_CONFERENCE_ROOM, f"{ROOM_CONFERENCE_ROOM}_floor2", f"{ROOM_HUDDLE}_floor3", f"{ROOM_WAR_ROOM}_floor3", f"{ROOM_THEATER}_floor3"])
    
    # Break/relaxation areas (breakroom, lounge, HR wellness)
    elif base_room in [ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_HR_WELLNESS]:
        if floor == 1:
            similar_rooms = [ROOM_BREAKROOM, ROOM_LOUNGE]
        elif floor == 2:
            similar_rooms = [f"{ROOM_BREAKROOM}_floor2", f"{ROOM_LOUNGE}_floor2"]
        elif floor == 3:
            similar_rooms = [f"{ROOM_BREAKROOM}_floor3", f"{ROOM_LOUNGE}_floor3", f"{ROOM_HR_WELLNESS}_floor3"]
        # Include other floors' break areas
        similar_rooms.extend([ROOM_BREAKROOM, ROOM_LOUNGE, f"{ROOM_BREAKROOM}_floor2", f"{ROOM_LOUNGE}_floor2", f"{ROOM_BREAKROOM}_floor3", f"{ROOM_LOUNGE}_floor3", f"{ROOM_HR_WELLNESS}_floor3"])
    
    # Training rooms
    elif base_room == ROOM_TRAINING_ROOM:
        similar_rooms = [
            ROOM_TRAINING_ROOM,
            f"{ROOM_TRAINING_ROOM}_floor2",
            f"{ROOM_TRAINING_ROOM}_floor4",
            f"{ROOM_TRAINING_ROOM}_floor4_2",
            f"{ROOM_TRAINING_ROOM}_floor4_3",
            f"{ROOM_TRAINING_ROOM}_floor4_4",
            f"{ROOM_TRAINING_ROOM}_floor4_5"
        ]
    
    # Specialized work areas (IT, Storage, Reception) - these are more restrictive
    elif base_room in [ROOM_IT_ROOM, ROOM_STORAGE, ROOM_RECEPTION]:
        # For these, only include same type on different floors
        if base_room == ROOM_IT_ROOM:
            similar_rooms = [ROOM_IT_ROOM, f"{ROOM_IT_ROOM}_floor2"]
        elif base_room == ROOM_STORAGE:
            similar_rooms = [ROOM_STORAGE, f"{ROOM_STORAGE}_floor2"]
        elif base_room == ROOM_RECEPTION:
            similar_rooms = [ROOM_RECEPTION]  # Reception usually only on floor 1
    
    # Executive/Manager offices
    elif base_room in [ROOM_MANAGER_OFFICE, ROOM_EXECUTIVE_SUITE, ROOM_CORNER_EXEC]:
        if floor == 1:
            similar_rooms = [ROOM_MANAGER_OFFICE]
        elif floor == 2:
            similar_rooms = [f"{ROOM_EXECUTIVE_SUITE}_floor2", ROOM_MANAGER_OFFICE]
        elif floor == 3:
            similar_rooms = [f"{ROOM_CORNER_EXEC}_floor3", ROOM_MANAGER_OFFICE]
        similar_rooms.extend([ROOM_MANAGER_OFFICE, f"{ROOM_EXECUTIVE_SUITE}_floor2", f"{ROOM_CORNER_EXEC}_floor3"])
    
    # Collaboration spaces
    elif base_room in [ROOM_COLLAB_LOUNGE]:
        similar_rooms = [f"{ROOM_COLLAB_LOUNGE}_floor3", ROOM_CONFERENCE_ROOM, f"{ROOM_CONFERENCE_ROOM}_floor2"]
    
    # Design/Innovation spaces
    elif base_room in [ROOM_DESIGN_STUDIO, ROOM_INNOVATION_LAB, ROOM_FOCUS_PODS]:
        similar_rooms = [f"{ROOM_DESIGN_STUDIO}_floor3", f"{ROOM_INNOVATION_LAB}_floor3", f"{ROOM_FOCUS_PODS}_floor3"]
    
    # Department-specific rooms (HR, Sales)
    elif base_room in [ROOM_HR_ROOM, ROOM_SALES_ROOM]:
        if base_room == ROOM_HR_ROOM:
            similar_rooms = [f"{ROOM_HR_ROOM}_floor2", ROOM_MANAGER_OFFICE]
        elif base_room == ROOM_SALES_ROOM:
            similar_rooms = [f"{ROOM_SALES_ROOM}_floor2", ROOM_CONFERENCE_ROOM, f"{ROOM_CONFERENCE_ROOM}_floor2"]
    
    # Remove the original room from the list
    if room_id in similar_rooms:
        similar_rooms.remove(room_id)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_rooms = []
    for room in similar_rooms:
        if room not in seen:
            seen.add(room)
            unique_rooms.append(room)
    
    return unique_rooms


async def find_available_similar_room(room_id: str, db_session, exclude_employee_id: int = None) -> Optional[str]:
    """
    Find an available similar room that can serve as an alternative.
    Prioritizes rooms with the most available space.
    
    Args:
        room_id: Original room identifier
        db_session: Database session
        exclude_employee_id: Optional employee ID to exclude from count
        
    Returns:
        Optional[str]: Available similar room ID, or None if all are full
    """
    similar_rooms = find_similar_rooms(room_id)
    
    if not similar_rooms:
        return None
    
    best_room = None
    most_space = -1
    
    for alt_room_id in similar_rooms:
        has_space = await check_room_has_space(alt_room_id, db_session, exclude_employee_id)
        if has_space:
            # Calculate available space
            capacity = get_room_capacity(alt_room_id)
            occupancy = await get_room_occupancy(alt_room_id, db_session)
            available_space = capacity - occupancy
            
            if available_space > most_space:
                most_space = available_space
                best_room = alt_room_id
    
    return best_room


async def enforce_room_capacity(db_session) -> dict:
    """
    Detect and fix all over-capacity rooms by redistributing employees to similar rooms.
    Makes employees physically walk to less crowded rooms.
    
    Args:
        db_session: Database session
        
    Returns:
        dict: Statistics about the fix operation
    """
    from database.models import Employee
    from sqlalchemy import select, func
    import random
    
    stats = {
        "over_capacity_rooms": 0,
        "employees_redistributed": 0,
        "rooms_fixed": []
    }
    
    # Get all unique rooms that have employees
    result = await db_session.execute(
        select(Employee.current_room, func.count(Employee.id).label('count'))
        .where(Employee.status == "active", Employee.current_room.isnot(None))
        .group_by(Employee.current_room)
    )
    room_occupancies = result.all()
    
    # Check each room for over-capacity
    over_capacity_rooms = []
    for room_id, occupancy in room_occupancies:
        capacity = get_room_capacity(room_id)
        if occupancy > capacity:
            over_capacity = occupancy - capacity
            over_capacity_rooms.append({
                "room_id": room_id,
                "capacity": capacity,
                "occupancy": occupancy,
                "over_by": over_capacity
            })
    
    if not over_capacity_rooms:
        return stats
    
    stats["over_capacity_rooms"] = len(over_capacity_rooms)
    
    # Fix each over-capacity room
    for room_info in over_capacity_rooms:
        room_id = room_info["room_id"]
        over_by = room_info["over_by"]
        
        # Get all employees in this over-capacity room
        result = await db_session.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.current_room == room_id
            )
        )
        employees_in_room = result.scalars().all()
        
        # Shuffle to randomly select who gets moved
        random.shuffle(employees_in_room)
        
        # Move the excess employees to similar rooms
        moved_count = 0
        for employee in employees_in_room[:over_by]:
            # Find an available similar room
            alternative_room = await find_available_similar_room(room_id, db_session, exclude_employee_id=employee.id)
            
            if alternative_room:
                # Make employee walk to the alternative room
                employee.activity_state = "walking"
                employee.target_room = alternative_room
                # Update floor if moving to different floor
                if alternative_room.endswith('_floor2'):
                    employee.floor = 2
                elif alternative_room.endswith('_floor3'):
                    employee.floor = 3
                elif alternative_room.endswith('_floor4'):
                    employee.floor = 4
                elif not alternative_room.endswith('_floor2') and not alternative_room.endswith('_floor3') and not alternative_room.endswith('_floor4'):
                    if getattr(employee, 'floor', 1) in [2, 3, 4]:
                        employee.floor = 1
                
                moved_count += 1
                stats["employees_redistributed"] += 1
                logger.info(f"Moving {employee.name} (ID: {employee.id}) from over-capacity room {room_id} to {alternative_room}")
            else:
                # No similar room available - try generic fallback rooms
                employee_floor = getattr(employee, 'floor', 1)
                
                # Try cubicles on their floor
                from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                has_space = await check_room_has_space(cubicles_room, db_session, exclude_employee_id=employee.id)
                
                if has_space:
                    employee.activity_state = "walking"
                    employee.target_room = cubicles_room
                    moved_count += 1
                    stats["employees_redistributed"] += 1
                    logger.info(f"Moving {employee.name} (ID: {employee.id}) from over-capacity room {room_id} to fallback {cubicles_room}")
                else:
                    # Try open office
                    open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                    has_space = await check_room_has_space(open_office_room, db_session, exclude_employee_id=employee.id)
                    
                    if has_space:
                        employee.activity_state = "walking"
                        employee.target_room = open_office_room
                        moved_count += 1
                        stats["employees_redistributed"] += 1
                        logger.info(f"Moving {employee.name} (ID: {employee.id}) from over-capacity room {room_id} to fallback {open_office_room}")
                    else:
                        # Last resort: try any floor's cubicles or open office
                        found_fallback = False
                        for floor in [1, 2, 3, 4]:
                            if floor == 1:
                                test_rooms = [ROOM_CUBICLES, ROOM_OPEN_OFFICE]
                            else:
                                test_rooms = [
                                    f"{ROOM_CUBICLES}_floor{floor}",
                                    f"{ROOM_OPEN_OFFICE}_floor{floor}"
                                ]
                            
                            for test_room in test_rooms:
                                has_space = await check_room_has_space(test_room, db_session, exclude_employee_id=employee.id)
                                if has_space:
                                    employee.activity_state = "walking"
                                    employee.target_room = test_room
                                    employee.floor = floor
                                    moved_count += 1
                                    stats["employees_redistributed"] += 1
                                    logger.info(f"Moving {employee.name} (ID: {employee.id}) from over-capacity room {room_id} to emergency fallback {test_room}")
                                    found_fallback = True
                                    break
                            
                            if found_fallback:
                                break
        
        if moved_count > 0:
            stats["rooms_fixed"].append({
                "room_id": room_id,
                "moved": moved_count,
                "over_by": over_by
            })
            logger.warning(f"Fixed over-capacity room {room_id}: moved {moved_count} employees (was {room_info['occupancy']}/{room_info['capacity']})")
    
    await db_session.flush()
    
    if stats["employees_redistributed"] > 0:
        logger.warning(f"Capacity enforcement: Fixed {stats['over_capacity_rooms']} over-capacity rooms, redistributed {stats['employees_redistributed']} employees")
    
    return stats

