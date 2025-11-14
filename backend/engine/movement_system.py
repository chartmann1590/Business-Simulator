"""Movement system for employees to move between rooms based on activities."""

import random
from typing import Optional
from employees.room_assigner import (
    ROOM_OPEN_OFFICE, ROOM_CUBICLES, ROOM_CONFERENCE_ROOM,
    ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_TRAINING_ROOM,
    ROOM_STORAGE, ROOM_IT_ROOM, ROOM_MANAGER_OFFICE,
    ROOM_RECEPTION
)


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
        if employee_floor == 2 and not room_id.endswith('_floor2'):
            return f"{room_id}_floor2"
        elif employee_floor == 1 and room_id.endswith('_floor2'):
            return room_id.replace('_floor2', '')
        return room_id
    
    # Meetings → Conference Room (balance between floor 1 and floor 2)
    if "meeting" in activity_lower or "meeting" in desc_lower or "conference" in desc_lower:
        # Balance conference room usage across both floors
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
                
                # Assign to floor with fewer people, or random if equal
                if floor1_count <= floor2_count:
                    return ROOM_CONFERENCE_ROOM  # Floor 1
                else:
                    return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
            except:
                pass
        
        # Fallback: randomly assign between floors (50/50)
        if random.random() < 0.5:
            return ROOM_CONFERENCE_ROOM  # Floor 1
        else:
            return f"{ROOM_CONFERENCE_ROOM}_floor2"  # Floor 2
    
    # Breaks → Breakroom or Lounge (on employee's floor)
    if "break" in activity_lower or "break" in desc_lower or "lunch" in desc_lower or "coffee" in desc_lower:
        # Randomly choose between breakroom and lounge
        chosen_room = random.choice([ROOM_BREAKROOM, ROOM_LOUNGE])
        return get_room_with_floor(chosen_room)
    
    # Training → Training Room (on employee's floor, or can go to training on any floor)
    if "training" in activity_lower or "training" in desc_lower or "learn" in desc_lower:
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
    
    # Collaboration/team work → Conference Room, Open Office, or Cubicles
    if ("collaborate" in desc_lower or "team" in desc_lower or "discuss" in desc_lower or
        "brainstorm" in desc_lower or "review" in desc_lower):
        # 40% conference room (balanced across floors), 30% open office, 30% cubicles
        room_choice = random.choice([
            "conference", "conference",  # 2/5 = 40%
            "open_office",  # 1/5 = 20%
            "cubicles",  # 1/5 = 20%
            "open_office",  # 1/5 = 20% (total 40% for open office)
            "cubicles"  # 1/5 = 20% (total 40% for cubicles)
        ])
        
        if room_choice == "conference":
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
    
    # Default: return to home room if idle, or stay in current room
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
        if employee_floor == 2 and not room_id.endswith('_floor2'):
            return f"{room_id}_floor2"
        elif employee_floor == 1 and room_id.endswith('_floor2'):
            return room_id.replace('_floor2', '')
        return room_id
    
    # IT employees might occasionally visit other areas, but prefer to stay in IT room
    if is_it:
        # Very rarely leave IT room - only for breaks or meetings
        chosen = random.choice([
            ROOM_BREAKROOM,  # Can go for breaks
            ROOM_LOUNGE,     # Can go for breaks
            None, None, None, None, None  # 5/7 chance to stay
        ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Reception employees should stay at reception - only leave for breaks
    if is_reception:
        # Very rarely leave reception - only for breaks
        chosen = random.choice([
            ROOM_BREAKROOM,  # Can go for breaks
            ROOM_LOUNGE,     # Can go for breaks
            None, None, None, None, None, None  # 6/8 chance to stay
        ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Storage employees should stay in storage - only leave for breaks
    if is_storage:
        # Very rarely leave storage - only for breaks
        chosen = random.choice([
            ROOM_BREAKROOM,  # Can go for breaks
            ROOM_LOUNGE,     # Can go for breaks
            None, None, None, None, None, None  # 6/8 chance to stay
        ])
        return get_room_with_floor(chosen) if chosen else None
    
    # Random movement options based on employee role (on their floor)
    if employee.role == "CEO":
        # CEO might visit manager office or conference room
        chosen = random.choice([ROOM_MANAGER_OFFICE, ROOM_CONFERENCE_ROOM, None])
        return get_room_with_floor(chosen) if chosen else None
    elif employee.role == "Manager":
        # Managers might visit various rooms
        chosen = random.choice([
            ROOM_CONFERENCE_ROOM, 
            ROOM_OPEN_OFFICE, 
            ROOM_BREAKROOM,
            ROOM_LOUNGE,
            None
        ])
        return get_room_with_floor(chosen) if chosen else None
    else:
        # Regular employees might visit breakroom, lounge, or other departments
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
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2")
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
    
    # If idle and not in home room, return home
    if activity_type == "idle" and employee.current_room != employee.home_room:
        return True
    
    # If activity is complete and not in home room, return home
    if activity_type in ["completed", "finished"] and employee.current_room != employee.home_room:
        return True
    
    return False


async def update_employee_location(employee, target_room: Optional[str], activity_state: str, db_session):
    """
    Update employee's location and activity state.
    Also updates floor if moving to a room on a different floor.
    
    Args:
        employee: Employee model instance
        target_room: Target room identifier (None to stay in current room)
        activity_state: New activity state
        db_session: Database session
    """
    if target_room and target_room != employee.current_room:
        # Employee is moving
        employee.activity_state = "walking"
        
        # Update floor if moving to a room on a different floor
        if target_room.endswith('_floor2'):
            employee.floor = 2
        elif not target_room.endswith('_floor2') and getattr(employee, 'floor', 1) == 2:
            # Moving from floor 2 to floor 1 room
            employee.floor = 1
        
        # Note: We'll set the current_room after a delay to simulate walking
        # For now, we'll set it immediately but the frontend can animate the transition
        employee.current_room = target_room
    else:
        # Employee is staying in place
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
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2")
    
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
                    # Training complete, move to home room
                    await update_employee_location(employee, employee.home_room, "idle", db_session)
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
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2")
    
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
                           current_room == f"{ROOM_TRAINING_ROOM}_floor2")
    
    # If in training room but not actually training, move to home room
    if is_in_training_room and activity_state != "training" and activity_type.lower() != "training":
        await update_employee_location(employee, employee.home_room, "idle", db_session)
        return
    
    # If no target room determined, stay in current room or go to home room
    if target_room is None:
        home_room = getattr(employee, 'home_room', None)
        current_room = getattr(employee, 'current_room', None)
        
        # Receptionists and Storage employees MUST be at their work stations
        if (is_reception or is_storage) and home_room:
            # If not in their work area, FORCE them back immediately
            if current_room != home_room:
                await update_employee_location(employee, home_room, activity_state, db_session)
            else:
                # They're in their work area - stay there
                await update_employee_location(employee, None, activity_state, db_session)
        elif is_it and employee.current_room != employee.home_room:
            # IT employees should return to work area if not there
            await update_employee_location(employee, employee.home_room, activity_state, db_session)
        elif employee.current_room:
            # Stay in current room (unless it's training room and they shouldn't be there)
            if is_in_training_room and activity_state != "training":
                await update_employee_location(employee, employee.home_room, "idle", db_session)
            else:
                await update_employee_location(employee, None, activity_state, db_session)
        else:
            # No current room, go to home room
            await update_employee_location(employee, employee.home_room, activity_state, db_session)
    else:
        # For IT, Reception, and Storage, they MUST stay in their work areas
        home_room = getattr(employee, 'home_room', None)
        
        # Receptionists and Storage employees are CRITICAL - they MUST be at their stations
        if (is_reception or is_storage) and home_room:
            # ONLY allow breaks and meetings to take them away from their work area
            if target_room != home_room:
                if activity_type in ["break", "meeting"]:
                    # Allow temporary movement for breaks/meetings
                    await update_employee_location(employee, target_room, activity_state, db_session)
                else:
                    # FORCE them back to their work area - they cannot leave!
                    await update_employee_location(employee, home_room, activity_state, db_session)
            else:
                # They're going to their work area - good!
                await update_employee_location(employee, target_room, activity_state, db_session)
        elif is_it and activity_type in ["working", "idle"]:
            # IT employees should stay in their work area when working/idle
            if activity_type not in ["break", "meeting", "training"] and target_room != home_room:
                # Stay in work area instead
                await update_employee_location(employee, home_room, activity_state, db_session)
            else:
                # Move to target room (for breaks, meetings, etc.)
                await update_employee_location(employee, target_room, activity_state, db_session)
        else:
            # Move to target room
            await update_employee_location(employee, target_room, activity_state, db_session)

