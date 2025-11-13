"""Movement system for employees to move between rooms based on activities."""

import random
from typing import Optional
from employees.room_assigner import (
    ROOM_OPEN_OFFICE, ROOM_CUBICLES, ROOM_CONFERENCE_ROOM,
    ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_TRAINING_ROOM,
    ROOM_STORAGE, ROOM_IT_ROOM, ROOM_MANAGER_OFFICE,
    ROOM_RECEPTION
)


def determine_target_room(activity_type: str, activity_description: str, employee) -> Optional[str]:
    """
    Determine which room an employee should move to based on their activity.
    
    Args:
        activity_type: Type of activity (e.g., "meeting", "break", "training")
        activity_description: Description of the activity
        employee: Employee model instance
        
    Returns:
        Optional[str]: Target room identifier, or None if should stay in current room
    """
    activity_lower = activity_type.lower()
    desc_lower = (activity_description or "").lower()
    
    # Meetings → Conference Room
    if "meeting" in activity_lower or "meeting" in desc_lower or "conference" in desc_lower:
        return ROOM_CONFERENCE_ROOM
    
    # Breaks → Breakroom or Lounge
    if "break" in activity_lower or "break" in desc_lower or "lunch" in desc_lower or "coffee" in desc_lower:
        # Randomly choose between breakroom and lounge
        return random.choice([ROOM_BREAKROOM, ROOM_LOUNGE])
    
    # Training → Training Room
    if "training" in activity_lower or "training" in desc_lower or "learn" in desc_lower:
        return ROOM_TRAINING_ROOM
    
    # Storage needs → Storage
    if "storage" in activity_lower or "storage" in desc_lower or "supplies" in desc_lower:
        return ROOM_STORAGE
    
    # IT-related work → IT Room (if employee is IT or doing IT work)
    if ("it" in activity_lower or "server" in activity_lower or "network" in activity_lower or 
        "it" in desc_lower or "server" in desc_lower or "network" in desc_lower):
        # Check if employee is IT or if activity is IT-related
        if "it" in (employee.title or "").lower() or "it" in (employee.department or "").lower():
            return ROOM_IT_ROOM
    
    # Reception work → Reception (if employee is receptionist)
    if "reception" in activity_lower or "reception" in desc_lower:
        if "reception" in (employee.title or "").lower():
            return ROOM_RECEPTION
    
    # Manager meetings → Manager Office (if employee is manager/CEO)
    if ("manager" in activity_lower or "executive" in activity_lower or 
        "strategy" in activity_lower or "planning" in activity_lower or
        "discuss" in desc_lower or "review" in desc_lower):
        if employee.role in ["CEO", "Manager"]:
            return ROOM_MANAGER_OFFICE
    
    # Collaboration/team work → Open Office or Conference Room
    if ("collaborate" in desc_lower or "team" in desc_lower or "discuss" in desc_lower or
        "brainstorm" in desc_lower or "review" in desc_lower):
        # 50% chance to go to conference room, 50% to open office
        return random.choice([ROOM_CONFERENCE_ROOM, ROOM_OPEN_OFFICE])
    
    # Default: return to home room if idle, or stay in current room
    return None


def get_random_movement(employee) -> Optional[str]:
    """
    Generate occasional random movement for employees to make the office feel more alive.
    
    Args:
        employee: Employee model instance
        
    Returns:
        Optional[str]: Random target room, or None if should stay
    """
    # 20% chance of random movement when called
    if random.random() > 0.2:
        return None
    
    # Don't move if employee is already walking
    if employee.activity_state == "walking":
        return None
    
    # Random movement options based on employee role
    if employee.role == "CEO":
        # CEO might visit manager office or conference room
        return random.choice([ROOM_MANAGER_OFFICE, ROOM_CONFERENCE_ROOM, None])
    elif employee.role == "Manager":
        # Managers might visit various rooms
        return random.choice([
            ROOM_CONFERENCE_ROOM, 
            ROOM_OPEN_OFFICE, 
            ROOM_BREAKROOM,
            ROOM_LOUNGE,
            None
        ])
    else:
        # Regular employees might visit breakroom, lounge, or other departments
        return random.choice([
            ROOM_BREAKROOM,
            ROOM_LOUNGE,
            ROOM_OPEN_OFFICE,
            ROOM_CUBICLES,
            None
        ])


def should_move_to_home_room(employee, activity_type: str) -> bool:
    """
    Determine if employee should return to their home room.
    
    Args:
        employee: Employee model instance
        activity_type: Current activity type
        
    Returns:
        bool: True if should return to home room
    """
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
    
    Args:
        employee: Employee model instance
        target_room: Target room identifier (None to stay in current room)
        activity_state: New activity state
        db_session: Database session
    """
    if target_room and target_room != employee.current_room:
        # Employee is moving
        employee.activity_state = "walking"
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
    # Check if should return to home room
    if should_move_to_home_room(employee, activity_type):
        await update_employee_location(employee, employee.home_room, "idle", db_session)
        return
    
    # Determine target room based on activity
    target_room = determine_target_room(activity_type, activity_description, employee)
    
    # If no target room from activity, occasionally add random movement
    if target_room is None:
        random_movement = get_random_movement(employee)
        if random_movement:
            target_room = random_movement
    
    # Map activity type to activity state
    activity_state_map = {
        "meeting": "meeting",
        "break": "break",
        "training": "working",
        "working": "working",
        "idle": "idle",
        "completed": "idle",
        "finished": "idle",
    }
    
    activity_state = activity_state_map.get(activity_type.lower(), "working")
    
    # If no target room determined, stay in current room or go to home room
    if target_room is None:
        if employee.current_room:
            # Stay in current room
            await update_employee_location(employee, None, activity_state, db_session)
        else:
            # No current room, go to home room
            await update_employee_location(employee, employee.home_room, activity_state, db_session)
    else:
        # Move to target room
        await update_employee_location(employee, target_room, activity_state, db_session)

