"""Room assignment system for employees based on their roles and departments."""

# Room constants - Floor 1
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

# Room constants - Floor 2
ROOM_EXECUTIVE_SUITE = "executive_suite"
ROOM_HR_ROOM = "hr_room"
ROOM_SALES_ROOM = "sales_room"

# Room constants - Floor 3
ROOM_INNOVATION_LAB = "innovation_lab"
ROOM_HOTDESK = "hotdesk"
ROOM_FOCUS_PODS = "focus_pods"
ROOM_COLLAB_LOUNGE = "collab_lounge"
ROOM_WAR_ROOM = "war_room"
ROOM_DESIGN_STUDIO = "design_studio"
ROOM_HR_WELLNESS = "hr_wellness"
ROOM_THEATER = "theater"
ROOM_HUDDLE = "huddle"
ROOM_CORNER_EXEC = "corner_exec"

# Floor 4 is dedicated to training overflow - training rooms and cubicles only

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
    ROOM_EXECUTIVE_SUITE,
    ROOM_HR_ROOM,
    ROOM_SALES_ROOM,
    ROOM_INNOVATION_LAB,
    ROOM_HOTDESK,
    ROOM_FOCUS_PODS,
    ROOM_COLLAB_LOUNGE,
    ROOM_WAR_ROOM,
    ROOM_DESIGN_STUDIO,
    ROOM_HR_WELLNESS,
    ROOM_THEATER,
    ROOM_HUDDLE,
    ROOM_CORNER_EXEC,
]


async def assign_home_room(employee, db_session=None) -> tuple:
    """
    Assign a home room and floor to an employee based on their role, title, and department.
    Distributes employees across all three floors to utilize the whole building.
    
    Args:
        employee: Employee model instance
        db_session: Optional database session to check employee distribution
        
    Returns:
        tuple: (room_id, floor) - Room identifier and floor number (1, 2, or 3)
    """
    import random
    from sqlalchemy import select, func
    
    role = employee.role or ""
    title = (employee.title or "").lower()
    department = (employee.department or "").lower()
    
    # Determine base room (without floor suffix) and floor
    base_room = None
    floor = None
    
    # CEO/Executives/Chiefs → Executive Suite (floor 2) or Corner Executive (floor 3)
    if role == "CEO" or "ceo" in title:
        # CEO gets the best office - Corner Executive on floor 3
        base_room = ROOM_CORNER_EXEC
        floor = 3
    elif "executive" in title or "chief" in title:
        # Senior executives get executive suites or corner executive
        if random.random() < 0.4:  # 40% chance for floor 3 corner exec
            base_room = ROOM_CORNER_EXEC
            floor = 3
        else:  # 60% chance for floor 2 executive suite
            base_room = ROOM_EXECUTIVE_SUITE
            floor = 2
    
    # Sales → Sales Room on floor 2
    elif department == "sales" or "sales" in title:
        base_room = ROOM_SALES_ROOM
        floor = 2  # Sales always on floor 2
    
    # HR → HR Room on floor 2
    elif "hr" in title or "human resources" in title or department == "hr":
        base_room = ROOM_HR_ROOM
        floor = 2  # HR always on floor 2
    
    # Design/Creative → Design Studio (floor 3) or Innovation Lab (floor 3)
    elif "design" in title or "designer" in title or department == "design":
        if random.random() < 0.6:  # 60% design studio
            base_room = ROOM_DESIGN_STUDIO
            floor = 3
        else:  # 40% innovation lab
            base_room = ROOM_INNOVATION_LAB
            floor = 3
    
    # R&D/Innovation → Innovation Lab (floor 3)
    elif "research" in title or "r&d" in title or "innovation" in title or department == "research":
        base_room = ROOM_INNOVATION_LAB
        floor = 3
    
    # IT → IT Room (can be on floor 1 or 2)
    elif "it" in title or "information technology" in title or department == "it":
        base_room = ROOM_IT_ROOM
        floor = await _determine_floor_for_special_room(ROOM_IT_ROOM, db_session)
    
    # Reception → Reception (usually floor 1, but can have floor 2)
    elif "reception" in title or "receptionist" in title:
        base_room = ROOM_RECEPTION
        floor = await _determine_floor_for_special_room(ROOM_RECEPTION, db_session)
    
    # Storage → Storage Room (needs coverage on floors 1 and 2)
    elif "storage" in title or "warehouse" in title or "inventory" in title or "stock" in title:
        base_room = ROOM_STORAGE
        floor = await _determine_floor_for_special_room(ROOM_STORAGE, db_session)
    
    # Training → Training Room (can be on floor 1, 2, or 4 for overflow)
    elif "training" in title or "trainer" in title:
        base_room = ROOM_TRAINING_ROOM
        floor = await _determine_floor_for_training_room(db_session)
    
    # Engineering/Development → Focus Pods (floor 3), Cubicles, or Open Office
    elif department == "engineering" or department == "development" or "engineer" in title or "developer" in title:
        if random.random() < 0.3:  # 30% floor 3 focus pods
            base_room = ROOM_FOCUS_PODS
            floor = 3
        else:  # 70% traditional spaces, balance across floors
            base_room = await _determine_office_space(db_session, ROOM_CUBICLES, ROOM_OPEN_OFFICE, prefer_first=True)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Product → Collaboration Lounge (floor 3), War Room (floor 3), or traditional spaces
    elif department == "product" or "product" in title:
        rand = random.random()
        if rand < 0.3:  # 30% collaboration lounge
            base_room = ROOM_COLLAB_LOUNGE
            floor = 3
        elif rand < 0.5:  # 20% war room
            base_room = ROOM_WAR_ROOM
            floor = 3
        else:  # 50% traditional spaces
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Marketing → Hotdesk (floor 3), Collaboration Lounge (floor 3), or traditional spaces
    elif department == "marketing" or "marketing" in title:
        rand = random.random()
        if rand < 0.3:  # 30% hotdesk
            base_room = ROOM_HOTDESK
            floor = 3
        elif rand < 0.5:  # 20% collaboration lounge
            base_room = ROOM_COLLAB_LOUNGE
            floor = 3
        else:  # 50% traditional spaces
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Managers and C-level executives → Executive Suite, Corner Executive, or Manager Office based on seniority
    elif role in ["Manager", "CTO", "COO", "CFO"]:
        if "senior" in title or "director" in title or "vp" in title or "vice president" in title:
            # High-level managers get executive spaces
            rand = random.random()
            if rand < 0.4:  # 40% floor 3 corner exec
                base_room = ROOM_CORNER_EXEC
                floor = 3
            else:  # 60% floor 2 executive suite
                base_room = ROOM_EXECUTIVE_SUITE
                floor = 2
        else:
            # Regular managers - traditional spaces
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Operations → Hotdesk (floor 3) or traditional spaces
    elif department == "operations" or "operations" in title:
        if random.random() < 0.3:  # 30% hotdesk
            base_room = ROOM_HOTDESK
            floor = 3
        else:  # 70% traditional spaces
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Default: Balance across all floors - use traditional spaces or floor 3 options
    else:
        rand = random.random()
        if rand < 0.2:  # 20% floor 3 hotdesk
            base_room = ROOM_HOTDESK
            floor = 3
        elif rand < 0.3:  # 10% floor 3 focus pods
            base_room = ROOM_FOCUS_PODS
            floor = 3
        else:  # 70% traditional spaces across floors 1 and 2
            base_room = await _determine_office_space(db_session, ROOM_OPEN_OFFICE, ROOM_CUBICLES)
            floor = await _determine_floor_for_regular_employee(db_session)
    
    # Add floor suffix to room ID if needed
    if floor == 2:
        room_id = f"{base_room}_floor2"
    elif floor == 3:
        room_id = f"{base_room}_floor3"
    elif floor == 4:
        room_id = f"{base_room}_floor4"
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
    Determine which floor to assign a regular employee to, balancing distribution across all floors.
    
    Returns:
        int: Floor number (1, 2, or 3)
    """
    import random
    
    if db_session is None:
        # If no session, randomly assign across all floors (weighted toward 1 and 2)
        return random.choice([1, 1, 2, 2, 3])  # 40% floor 1, 40% floor 2, 20% floor 3
    
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
        
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.floor == 3
            )
        )
        floor3_count = result.scalar() or 0
        
        # Balance floors - assign to floor with fewer employees
        if floor1_count <= floor2_count and floor1_count <= floor3_count:
            return 1
        elif floor2_count <= floor3_count:
            return 2
        else:
            return 3
    except:
        # Fallback to random if error
        return random.choice([1, 1, 2, 2, 3])


async def _determine_floor_for_training_room(db_session) -> int:
    """
    Determine which floor to assign training room employees.
    Floor 4 is dedicated to training overflow, so we check if floors 1-2 are full first.
    
    Args:
        db_session: Database session
        
    Returns:
        int: Floor number (1, 2, or 4)
    """
    import random
    
    if db_session is None:
        # If no session, prefer floor 1, then 2, then 4
        return random.choice([1, 1, 2, 4])
    
    try:
        from database.models import Employee
        from sqlalchemy import select, func
        
        # Count employees in training rooms on each floor
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.home_room == ROOM_TRAINING_ROOM
            )
        )
        floor1_count = result.scalar() or 0
        
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.home_room == f"{ROOM_TRAINING_ROOM}_floor2"
            )
        )
        floor2_count = result.scalar() or 0
        
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.home_room == f"{ROOM_TRAINING_ROOM}_floor4"
            )
        )
        floor4_count = result.scalar() or 0
        
        # Also check current occupancy of training rooms (for overflow assignment)
        # Check floor 1 training room occupancy
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.current_room == ROOM_TRAINING_ROOM
            )
        )
        floor1_occupancy = result.scalar() or 0
        
        # Check floor 2 training room occupancy
        result = await db_session.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                Employee.current_room == f"{ROOM_TRAINING_ROOM}_floor2"
            )
        )
        floor2_occupancy = result.scalar() or 0
        
        # Training room capacities: floor 1 = 12, floor 2 = 15
        # If floors 1-2 training rooms are getting full, use floor 4 for overflow
        if floor1_occupancy >= 10 or floor2_occupancy >= 13:  # Near capacity
            return 4  # Use floor 4 for overflow
        
        # Balance assignment across floors 1 and 2, use floor 4 if both are busy
        if floor1_count <= floor2_count and floor1_count <= floor4_count:
            return 1
        elif floor2_count <= floor4_count:
            return 2
        else:
            return 4
    except:
        # Fallback
        return random.choice([1, 2, 4])


async def _determine_floor_for_special_room(room_type: str, db_session) -> int:
    """
    Determine which floor to assign special room employees (IT, Reception, Training, Storage).
    These can be on floors 1 or 2 (not floor 3 for these specific rooms).
    We balance them and ensure at least one on each floor where applicable.
    
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

