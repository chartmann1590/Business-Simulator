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


async def assign_home_room(employee, db_session=None) -> tuple:
    """
    Assign a home room and floor to an employee based on their role, title, and department.
    
    Args:
        employee: Employee model instance
        db_session: Optional database session to check employee distribution
        
    Returns:
        tuple: (room_id, floor) - Room identifier and floor number (1 or 2)
    """
    import random
    from sqlalchemy import select, func
    
    role = employee.role or ""
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    
    # Determine base room (without floor suffix)
    base_room = None
    
    # CEO/Executives/Chiefs → Manager Office (check this first!)
    if role == "CEO" or "executive" in title or "ceo" in title or "chief" in title:
        base_room = ROOM_MANAGER_OFFICE
        # CEO stays on floor 1
        floor = 1
    # IT → IT Room (can be on either floor)
    elif "it" in title or "information technology" in title or department == "it":
        base_room = ROOM_IT_ROOM
        # IT staff can be on either floor - check distribution
        floor = await _determine_floor_for_special_room(ROOM_IT_ROOM, db_session)
    # Reception → Reception (usually floor 1, but can have floor 2)
    elif "reception" in title or "receptionist" in title:
        base_room = ROOM_RECEPTION
        # Reception usually on floor 1, but can have floor 2
        floor = await _determine_floor_for_special_room(ROOM_RECEPTION, db_session)
    # Storage → Storage Room (needs coverage on both floors)
    elif "storage" in title or "warehouse" in title or "inventory" in title or "stock" in title:
        base_room = ROOM_STORAGE
        # Storage employees can be on either floor - ensure coverage on both
        floor = await _determine_floor_for_special_room(ROOM_STORAGE, db_session)
    # Training/HR → Training Room or Open Office
    elif "training" in title or "trainer" in title:
        base_room = ROOM_TRAINING_ROOM
        # Training can be on either floor
        floor = await _determine_floor_for_special_room(ROOM_TRAINING_ROOM, db_session)
    elif "hr" in title or "human resources" in title or department == "hr":
        base_room = ROOM_OPEN_OFFICE
        floor = await _determine_floor_for_regular_employee(db_session)
    # Managers → Manager Office or Open Office/Cubicles (based on seniority)
    elif role == "Manager":
        # Senior managers and directors go to manager office
        if "senior" in title or "director" in title:
            base_room = ROOM_MANAGER_OFFICE
            floor = await _determine_floor_for_regular_employee(db_session)
        else:
            # Other managers can go to open office or cubicles - balance distribution
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    # Default assignments based on department
    elif department:
        if department == "engineering" or department == "development":
            # Engineering/Development prefer cubicles but can use open office if needed
            base_room = await _determine_office_space(db_session, ROOM_CUBICLES, ROOM_OPEN_OFFICE, prefer_first=True)
            floor = await _determine_floor_for_regular_employee(db_session)
        elif department == "sales":
            # Sales can use either open office or cubicles - balance distribution
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
        elif department == "marketing":
            # Marketing can use either open office or cubicles - balance distribution
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
        elif department == "operations":
            # Operations can use either open office or cubicles - balance distribution
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
        elif department == "product":
            # Product can use either open office or cubicles - balance distribution
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
        else:
            # Other departments - balance between open office and cubicles
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    else:
        # Default: Balance between Open Office and Cubicles
        base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
        floor = await _determine_floor_for_regular_employee(db_session)
    
    # For floor 2, add _floor2 suffix to room ID
    if floor == 2:
        room_id = f"{base_room}_floor2"
    else:
        room_id = base_room
    
    return (room_id, floor)


async def _determine_office_space(db_session, room1: str, room2: str, prefer_first: bool = False) -> str:
    """
    Determine which office space (open office or cubicles) to assign an employee to,
    balancing capacity between the two options.
    
    Args:
        db_session: Database session
        room1: First room option (e.g., ROOM_OPEN_OFFICE)
        room2: Second room option (e.g., ROOM_CUBICLES)
        prefer_first: If True, prefer room1 when counts are equal
        
    Returns:
        str: Room identifier (room1 or room2)
    """
    import random
    
    if db_session is None:
        # If no session, randomly choose (50/50) or prefer first if specified
        if prefer_first:
            return random.choice([room1, room1, room2])  # 2/3 chance for room1
        return random.choice([room1, room2])
    
    try:
        from database.models import Employee
        from sqlalchemy import select, func, or_
        
        # Count employees in room1 (both floors)
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                or_(
                    Employee.home_room == room1,
                    Employee.home_room == f"{room1}_floor2"
                )
            )
        )
        room1_count = result.scalar() or 0
        
        # Count employees in room2 (both floors)
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                or_(
                    Employee.home_room == room2,
                    Employee.home_room == f"{room2}_floor2"
                )
            )
        )
        room2_count = result.scalar() or 0
        
        # Balance distribution - assign to room with fewer employees
        if room1_count < room2_count:
            return room1
        elif room2_count < room1_count:
            return room2
        else:
            # Equal counts - use preference or random
            if prefer_first:
                return room1
            return random.choice([room1, room2])
    except:
        # Fallback to random if error
        if prefer_first:
            return random.choice([room1, room1, room2])
        return random.choice([room1, room2])


async def _determine_floor_for_regular_employee(db_session) -> int:
    """
    Determine which floor to assign a regular employee to, balancing distribution.
    
    Returns:
        int: Floor number (1 or 2)
    """
    import random
    
    if db_session is None:
        # If no session, randomly assign (50/50)
        return random.choice([1, 2])
    
    try:
        from database.models import Employee
        from sqlalchemy import select, func
        
        # Count employees on each floor
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.floor == 1
            )
        )
        floor1_count = result.scalar() or 0
        
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.floor == 2
            )
        )
        floor2_count = result.scalar() or 0
        
        # Balance floors - assign to floor with fewer employees
        if floor1_count <= floor2_count:
            return 1
        else:
            return 2
    except:
        # Fallback to random if error
        return random.choice([1, 2])


async def _determine_floor_for_special_room(room_type: str, db_session) -> int:
    """
    Determine which floor to assign special room employees (IT, Reception, Training, Storage).
    These can be on either floor but we balance them and ensure at least one on each floor.
    
    Args:
        room_type: Type of room (ROOM_IT_ROOM, ROOM_RECEPTION, ROOM_STORAGE, etc.)
        db_session: Database session
        
    Returns:
        int: Floor number (1 or 2)
    """
    import random
    
    if db_session is None:
        # If no session, prefer floor 1 for special rooms (reception/IT usually on floor 1)
        if room_type == ROOM_RECEPTION:
            return 1  # Reception typically on floor 1
        return random.choice([1, 2])
    
    try:
        from database.models import Employee
        from sqlalchemy import select, func
        
        # Count employees in this room type on each floor
        # For floor 1, check base room name
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.home_room == room_type
            )
        )
        floor1_count = result.scalar() or 0
        
        # For floor 2, check room name with _floor2 suffix
        floor2_room = f"{room_type}_floor2"
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.home_room == floor2_room
            )
        )
        floor2_count = result.scalar() or 0
        
        # For reception and storage, ensure at least one on each floor
        if room_type == ROOM_RECEPTION or room_type == ROOM_STORAGE:
            # If floor 1 has none, assign to floor 1
            if floor1_count == 0:
                return 1
            # If floor 2 has none, assign to floor 2
            elif floor2_count == 0:
                return 2
            # If both have at least one, balance them
            elif floor1_count <= floor2_count:
                return 1
            else:
                return 2
        
        # For other special rooms, balance between floors
        if floor1_count <= floor2_count:
            return 1
        else:
            return 2
    except:
        # Fallback
        if room_type == ROOM_RECEPTION:
            return 1
        return random.choice([1, 2])


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
        room_id, floor = await assign_home_room(employee, db_session)
        employee.home_room = room_id
        employee.floor = floor
        if not employee.current_room:
            employee.current_room = room_id
        if not employee.activity_state:
            employee.activity_state = "idle"
    
    await db_session.commit()

