"""Room assignment system for employees based on their roles and departments."""

# Room constants
ROOM_OPEN_OFFICE = "open_office"
ROOM_CUBICLES = "cubicles"
ROOM_CONFERENCE_ROOM = "conference_room"
ROOM_BREAKROOM = "breakroom"
ROOM_RECEPTION = "reception"
ROOM_IT_ROOM = "it_room"
ROOM_MANAGER_OFFICE = "manager_office"
ROOM_TRAINING_ROOM = "training_room"
ROOM_LOUNGE = "lounge"
ROOM_STORAGE = "storage"

ALL_ROOMS = [
    ROOM_OPEN_OFFICE,
    ROOM_CUBICLES,
    ROOM_CONFERENCE_ROOM,
    ROOM_BREAKROOM,
    ROOM_RECEPTION,
    ROOM_IT_ROOM,
    ROOM_MANAGER_OFFICE,
    ROOM_TRAINING_ROOM,
    ROOM_LOUNGE,
    ROOM_STORAGE,
]


def assign_home_room(employee) -> str:
    """
    Assign a home room to an employee based on their role, title, and department.
    
    Args:
        employee: Employee model instance
        
    Returns:
        str: Room identifier
    """
    role = employee.role or ""
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    
    # CEO/Executives/Chiefs → Manager Office (check this first!)
    if role == "CEO" or "executive" in title or "ceo" in title or "chief" in title:
        return ROOM_MANAGER_OFFICE
    
    # IT → IT Room
    if "it" in title or "information technology" in title or department == "it":
        return ROOM_IT_ROOM
    
    # Reception → Reception
    if "reception" in title or "receptionist" in title:
        return ROOM_RECEPTION
    
    # Training/HR → Training Room or Open Office
    if "training" in title or "trainer" in title:
        return ROOM_TRAINING_ROOM
    if "hr" in title or "human resources" in title or department == "hr":
        return ROOM_OPEN_OFFICE
    
    # Managers → Manager Office or Open Office (based on seniority)
    if role == "Manager":
        # Senior managers and directors go to manager office
        if "senior" in title or "director" in title:
            return ROOM_MANAGER_OFFICE
        # Other managers go to open office
        return ROOM_OPEN_OFFICE
    
    # Default assignments based on department
    if department:
        if department == "engineering" or department == "development":
            return ROOM_CUBICLES
        elif department == "sales":
            return ROOM_OPEN_OFFICE
        elif department == "marketing":
            return ROOM_OPEN_OFFICE
        elif department == "operations":
            return ROOM_OPEN_OFFICE
    
    # Default: Open Office (most common)
    return ROOM_OPEN_OFFICE


async def assign_rooms_to_existing_employees(db_session):
    """
    Assign home rooms to all existing employees that don't have one.
    
    Args:
        db_session: Database session
    """
    from database.models import Employee
    from sqlalchemy import select
    
    result = await db_session.execute(
        select(Employee).where(Employee.home_room.is_(None))
    )
    employees = result.scalars().all()
    
    for employee in employees:
        employee.home_room = assign_home_room(employee)
        if not employee.current_room:
            employee.current_room = employee.home_room
        if not employee.activity_state:
            employee.activity_state = "idle"
    
    await db_session.commit()

