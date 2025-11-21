from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Activity, Meeting, BirthdayCelebration, HolidayCelebration
from sqlalchemy import select, or_, func
from datetime import datetime, timedelta
from config import now as local_now
import random

class CoffeeBreakManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def should_take_coffee_break(self, employee: Employee) -> bool:
        """Determine if an employee should take a coffee break."""
        # Managers have stricter break rules to prevent abuse
        is_manager = employee.role in ["Manager", "CEO", "CTO", "COO", "CFO"] or employee.hierarchy_level < 3

        # STRICT RULE: Must wait at least 2 hours since last break (no exceptions)
        if employee.last_coffee_break:
            time_since_break = local_now() - employee.last_coffee_break
            hours_since = time_since_break.total_seconds() / 3600

            if hours_since < 2.0:
                return False  # Absolute minimum 2 hours between breaks

        # First break of the day
        if not employee.last_coffee_break:
            # Managers should wait longer before their first break
            if is_manager:
                return False  # Managers don't get immediate breaks
            return True  # Regular employees can take first break

        time_since_break = local_now() - employee.last_coffee_break
        hours_since = time_since_break.total_seconds() / 3600

        if is_manager:
            # Managers: stricter rules - breaks every 4-6 hours with lower probability
            if hours_since >= 6:
                return True  # Definitely time for a break after 6 hours
            elif hours_since >= 4:
                return random.random() < 0.15  # Only 15% chance (vs 30% for regular employees)
            else:
                return False  # No breaks before 4 hours
        else:
            # Regular employees: breaks every 2-4 hours
            if hours_since >= 4:
                return True  # Definitely time for a break
            elif hours_since >= 2:
                return random.random() < 0.3  # 30% chance
            else:
                return False
    
    async def take_coffee_break(self, employee: Employee) -> Activity:
        """Record a coffee break for an employee and move them to breakroom."""
        from engine.movement_system import update_employee_location
        from employees.room_assigner import ROOM_BREAKROOM
        now = local_now()

        # Check 1: Ensure at least 2 hours since last break
        if employee.last_coffee_break:
            time_since_break = now - employee.last_coffee_break
            hours_since = time_since_break.total_seconds() / 3600
            if hours_since < 2.0:
                raise ValueError(f"Break denied: Only {hours_since:.1f} hours since last break (minimum 2 hours required)")

        # Check 2: Check if employee has a meeting coming up soon (within next 30 minutes)
        upcoming_meeting = await self.check_upcoming_meetings(employee, minutes_ahead=30)
        if upcoming_meeting:
            meeting_time = upcoming_meeting.start_time.strftime("%I:%M %p")
            raise ValueError(f"Break denied: Meeting scheduled at {meeting_time} (within 30 minutes)")

        # Check 3: Check break room capacity before allowing break
        target_breakroom = ROOM_BREAKROOM
        if employee.floor == 2:
            target_breakroom = f"{ROOM_BREAKROOM}_floor2"
        elif employee.floor >= 3:
            # Use breakroom on floor 2 or 1
            target_breakroom = f"{ROOM_BREAKROOM}_floor2" if random.random() < 0.5 else ROOM_BREAKROOM

        # Check capacity of target breakroom
        capacity_check = await self.check_breakroom_capacity(target_breakroom)
        if not capacity_check["has_space"]:
            # Try the other breakroom if first choice is full
            if target_breakroom == ROOM_BREAKROOM:
                alternate_breakroom = f"{ROOM_BREAKROOM}_floor2"
            else:
                alternate_breakroom = ROOM_BREAKROOM

            alternate_capacity = await self.check_breakroom_capacity(alternate_breakroom)
            if alternate_capacity["has_space"]:
                target_breakroom = alternate_breakroom
            else:
                # Both breakrooms are full
                raise ValueError(f"Break denied: All break rooms are at capacity ({capacity_check['current']}/{capacity_check['capacity']})")

        # Check 4: Manager break abuse before allowing break
        is_manager = employee.role in ["Manager", "CEO", "CTO", "COO", "CFO"] or employee.hierarchy_level < 3
        if is_manager:
            abuse_check = await self.check_manager_break_frequency(employee)
            if abuse_check.get("is_abuse", False):
                # Deny break and log abuse attempt
                from database.models import Activity
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="break_denied",
                    description=f"⚠️ Break request denied for {employee.name}: {abuse_check.get('reason', 'Break abuse detected')}",
                    activity_metadata={
                        "break_type": "coffee",
                        "timestamp": now.isoformat(),
                        "denied": True,
                        "reason": abuse_check.get("reason"),
                        "is_manager": True
                    }
                )
                self.db.add(activity)
                await self.db.commit()
                print(f"🚫 BREAK DENIED: Manager {employee.name} attempted to take break but was denied: {abuse_check.get('reason')}")
                raise ValueError(f"Break denied: {abuse_check.get('reason')}")

        # All checks passed - grant the break
        # Update last coffee break time
        employee.last_coffee_break = now
        self.db.add(employee)

        # Move employee to breakroom
        await update_employee_location(employee, target_breakroom, "break", self.db)
        
        # Create activity
        break_messages = [
            f"☕ Taking a coffee break to recharge",
            f"☕ Grabbing a cup of coffee",
            f"☕ Coffee break time!",
            f"☕ Stepping away for a quick coffee",
            f"☕ Need some caffeine to keep going"
        ]
        
        activity = Activity(
            employee_id=employee.id,
            activity_type="coffee_break",
            description=random.choice(break_messages),
            activity_metadata={
                "break_type": "coffee",
                "timestamp": now.isoformat(),
                "target_room": target_breakroom
            }
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)
        
        return activity
    
    async def check_and_return_long_breaks(self, manager_id: Optional[int] = None, manager_name: Optional[str] = None) -> list:
        """Check for employees on break for more than 30 minutes and return them to work.
        Returns list of employees that were returned to work.
        
        Args:
            manager_id: ID of the manager returning employees (optional)
            manager_name: Name of the manager returning employees (optional)
        """
        from engine.movement_system import update_employee_location
        from sqlalchemy import select
        from employees.room_assigner import ROOM_BREAKROOM
        
        now = local_now()
        break_time_limit = timedelta(minutes=30)
        returned_employees = []
        
        # Find all employees currently on break (either activity_state is "break" or in a breakroom)
        # This includes ALL employees regardless of role - managers must also follow the 30-minute rule
        from sqlalchemy import or_
        result = await self.db.execute(
            select(Employee).where(
                Employee.status == "active",
                or_(
                    Employee.activity_state == "break",
                    Employee.current_room.like(f"%{ROOM_BREAKROOM}%")
                )
            )
        )
        employees_on_break = result.scalars().all()
        
        # If the manager checking is also on break, we need another manager to return them
        # Find an available manager who is NOT on break to handle returns
        available_manager = None
        if manager_id:
            manager_result = await self.db.execute(
                select(Employee).where(
                    Employee.id == manager_id,
                    Employee.status == "active"
                )
            )
            checking_manager = manager_result.scalar_one_or_none()
            # If the checking manager is also on break, find another manager
            if checking_manager and (
                checking_manager.activity_state == "break" or 
                (checking_manager.current_room and ROOM_BREAKROOM in checking_manager.current_room)
            ):
                # Find another manager who is not on break
                other_managers_result = await self.db.execute(
                    select(Employee).where(
                        Employee.id != manager_id,
                        Employee.status == "active",
                        Employee.role.in_(["Manager", "CEO", "CTO", "COO", "CFO"]),
                        Employee.activity_state != "break",
                        ~Employee.current_room.like(f"%{ROOM_BREAKROOM}%")
                    )
                )
                other_managers = other_managers_result.scalars().all()
                if other_managers:
                    available_manager = other_managers[0]
                    manager_id = available_manager.id
                    manager_name = available_manager.name
                    print(f"⚠️ Manager {checking_manager.name} is on break - {available_manager.name} will handle break returns")
        
        for employee in employees_on_break:
            # First check: If employee is in breakroom but NOT on break, move them to work room immediately
            is_in_breakroom = employee.current_room and ROOM_BREAKROOM in employee.current_room
            is_actually_on_break = employee.activity_state == "break"
            
            if is_in_breakroom and not is_actually_on_break:
                # Employee is in breakroom but not on break - move them to work
                if employee.home_room:
                    await update_employee_location(employee, employee.home_room, "working", self.db)
                else:
                    employee.activity_state = "working"
                    employee.current_room = None
                    self.db.add(employee)
                
                # Get manager name if not provided
                manager_display_name = manager_name or "System"
                if manager_id and not manager_name:
                    manager_result = await self.db.execute(
                        select(Employee).where(Employee.id == manager_id)
                    )
                    manager = manager_result.scalar_one_or_none()
                    if manager:
                        manager_display_name = manager.name
                
                # Create activity for moving employee out of breakroom
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="break_returned",
                    description=f"⏰ {manager_display_name} moved {employee.name} from breakroom to work (not on break)",
                    activity_metadata={
                        "returned_at": now.isoformat(),
                        "reason": "in_breakroom_not_on_break",
                        "manager_id": manager_id,
                        "manager_name": manager_display_name
                    }
                )
                self.db.add(activity)
                returned_employees.append(employee)
                print(f"⚠️ {employee.name} was in breakroom but not on break - moved to work")
                continue  # Skip break duration check for this employee
            
            # Second check: If employee is on break, check if they're in a scheduled celebration
            # If they are, don't kick them out until the celebration is over
            celebration_end_time = await self.check_employee_in_scheduled_celebration(employee)
            if celebration_end_time:
                # Employee is in a scheduled celebration - check if it's still ongoing
                if now < celebration_end_time:
                    # Celebration is still ongoing, don't kick them out
                    continue
                # Celebration has ended, proceed with normal break enforcement
            
            # Third check: If employee is on break, check break duration
            if not employee.last_coffee_break:
                continue
            
            # Ensure both datetimes are timezone-aware for comparison
            break_start = employee.last_coffee_break
            if break_start.tzinfo is None:
                # If break_start is naive, make it timezone-aware using UTC
                from datetime import timezone
                break_start = break_start.replace(tzinfo=timezone.utc)
            elif now.tzinfo is None:
                # If now is naive, make it timezone-aware
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
            
            time_on_break = now - break_start
            
            # If break is longer than 30 minutes, return to work
            if time_on_break > break_time_limit:
                # Return employee to their home room
                if employee.home_room:
                    await update_employee_location(employee, employee.home_room, "working", self.db)
                else:
                    # If no home room, set to working state
                    employee.activity_state = "working"
                    self.db.add(employee)
                
                # Get manager name if not provided
                manager_display_name = manager_name or "Manager"
                if manager_id and not manager_name:
                    manager_result = await self.db.execute(
                        select(Employee).where(Employee.id == manager_id)
                    )
                    manager = manager_result.scalar_one_or_none()
                    if manager:
                        manager_display_name = manager.name
                
                # Create activity for manager returning employee
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="break_returned",
                    description=f"⏰ {manager_display_name} returned {employee.name} to work after {int(time_on_break.total_seconds() / 60)} minute break",
                    activity_metadata={
                        "break_duration_minutes": int(time_on_break.total_seconds() / 60),
                        "returned_at": now.isoformat(),
                        "reason": "break_limit_exceeded",
                        "manager_id": manager_id,
                        "manager_name": manager_display_name
                    }
                )
                self.db.add(activity)
                returned_employees.append(employee)
        
        if returned_employees:
            await self.db.commit()
        
        return returned_employees
    
    async def enforce_break_limits_system_level(self) -> dict:
        """System-level enforcement of break limits that works independently of managers.
        This ensures managers can't abuse breaks even if all managers are on break.
        Returns dict with enforcement statistics.
        """
        from engine.movement_system import update_employee_location
        from sqlalchemy import select, or_
        from employees.room_assigner import ROOM_BREAKROOM
        
        now = local_now()
        break_time_limit = timedelta(minutes=30)
        returned_employees = []
        manager_abuse_count = 0
        
        # Find all employees currently on break
        result = await self.db.execute(
            select(Employee).where(
                Employee.status == "active",
                or_(
                    Employee.activity_state == "break",
                    Employee.current_room.like(f"%{ROOM_BREAKROOM}%")
                )
            )
        )
        employees_on_break = result.scalars().all()
        
        for employee in employees_on_break:
            # First check: If employee is in breakroom but NOT on break, move them to work room immediately
            is_in_breakroom = employee.current_room and ROOM_BREAKROOM in employee.current_room
            is_actually_on_break = employee.activity_state == "break"
            
            if is_in_breakroom and not is_actually_on_break:
                # Employee is in breakroom but not on break - move them to work
                if employee.home_room:
                    await update_employee_location(employee, employee.home_room, "working", self.db)
                else:
                    employee.activity_state = "working"
                    employee.current_room = None
                    self.db.add(employee)
                
                is_manager = employee.role in ["Manager", "CEO", "CTO", "COO", "CFO"] or employee.hierarchy_level < 3
                if is_manager:
                    manager_abuse_count += 1
                
                # Create activity for system-level enforcement
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="break_returned",
                    description=f"⏰ System automatically moved {employee.name} from breakroom to work (not on break)" + 
                               (f" (Manager break abuse detected)" if is_manager else ""),
                    activity_metadata={
                        "returned_at": now.isoformat(),
                        "reason": "in_breakroom_not_on_break",
                        "enforcement_type": "manager_break_enforcement" if is_manager else "system_break_enforcement",
                        "is_manager": is_manager,
                        "manager_name": employee.name if is_manager else None
                    }
                )
                self.db.add(activity)
                returned_employees.append(employee)
                
                if is_manager:
                    print(f"⚠️ MANAGER BREAK ABUSE: {employee.name} was in breakroom but not on break - automatically moved to work")
                else:
                    print(f"⚠️ {employee.name} was in breakroom but not on break - moved to work")
                continue  # Skip break duration check for this employee
            
            # Second check: If employee is on break, check if they're in a scheduled celebration
            # If they are, don't kick them out until the celebration is over
            celebration_end_time = await self.check_employee_in_scheduled_celebration(employee)
            if celebration_end_time:
                # Employee is in a scheduled celebration - check if it's still ongoing
                if now < celebration_end_time:
                    # Celebration is still ongoing, don't kick them out
                    continue
                # Celebration has ended, proceed with normal break enforcement
            
            # Third check: If employee is on break, check break duration
            if not employee.last_coffee_break:
                continue
            
            # Ensure both datetimes are timezone-aware for comparison
            break_start = employee.last_coffee_break
            if break_start.tzinfo is None:
                from datetime import timezone
                break_start = break_start.replace(tzinfo=timezone.utc)
            elif now.tzinfo is None:
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
            
            time_on_break = now - break_start
            
            # If break is longer than 30 minutes, return to work
            if time_on_break > break_time_limit:
                is_manager = employee.role in ["Manager", "CEO", "CTO", "COO", "CFO"] or employee.hierarchy_level < 3
                
                # Return employee to their home room
                if employee.home_room:
                    await update_employee_location(employee, employee.home_room, "working", self.db)
                else:
                    employee.activity_state = "working"
                    self.db.add(employee)
                
                # Create activity for system-level enforcement
                enforcement_type = "system_break_enforcement"
                if is_manager:
                    enforcement_type = "manager_break_enforcement"
                    manager_abuse_count += 1
                
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="break_returned",
                    description=f"⏰ System automatically returned {employee.name} to work after {int(time_on_break.total_seconds() / 60)} minute break" + 
                               (f" (Manager break abuse detected)" if is_manager else ""),
                    activity_metadata={
                        "break_duration_minutes": int(time_on_break.total_seconds() / 60),
                        "returned_at": now.isoformat(),
                        "reason": "break_limit_exceeded",
                        "enforcement_type": enforcement_type,
                        "is_manager": is_manager,
                        "manager_name": employee.name if is_manager else None
                    }
                )
                self.db.add(activity)
                returned_employees.append(employee)
                
                if is_manager:
                    print(f"⚠️ MANAGER BREAK ABUSE: {employee.name} was on break for {int(time_on_break.total_seconds() / 60)} minutes - automatically returned to work")
        
        if returned_employees:
            await self.db.commit()
        
        return {
            "total_returned": len(returned_employees),
            "managers_returned": manager_abuse_count,
            "regular_employees_returned": len(returned_employees) - manager_abuse_count
        }
    
    async def check_employee_in_scheduled_celebration(self, employee: Employee) -> Optional[datetime]:
        """Check if an employee is in a scheduled birthday or holiday celebration party.
        Returns the end time of the party if the employee is in one, None otherwise.
        """
        now = local_now()
        
        # Check Meeting records for birthday or holiday parties
        # Look for meetings that are currently happening (start_time <= now <= end_time)
        meeting_result = await self.db.execute(
            select(Meeting).where(
                Meeting.start_time <= now,
                Meeting.end_time >= now
            )
        )
        meetings = meeting_result.scalars().all()
        
        for meeting in meetings:
            # Check if employee is organizer or in attendee_ids
            is_organizer = meeting.organizer_id == employee.id
            is_attendee = False
            if meeting.attendee_ids:
                # Convert attendee_ids to a set of integers for comparison
                attendee_ids_set = set()
                for aid in meeting.attendee_ids:
                    if isinstance(aid, int):
                        attendee_ids_set.add(aid)
                    elif isinstance(aid, str) and aid.isdigit():
                        attendee_ids_set.add(int(aid))
                    elif isinstance(aid, (int, float)):
                        attendee_ids_set.add(int(aid))
                is_attendee = employee.id in attendee_ids_set
            
            if is_organizer or is_attendee:
                metadata = meeting.meeting_metadata or {}
                if isinstance(metadata, dict):
                    # Check if it's a birthday or holiday party
                    if metadata.get('is_birthday_party') or metadata.get('is_holiday_party'):
                        # Check if employee is in the breakroom (where parties are held)
                        from employees.room_assigner import ROOM_BREAKROOM
                        if employee.current_room and ROOM_BREAKROOM in employee.current_room:
                            # Party is still ongoing, return end time
                            return meeting.end_time
        
        # Check BirthdayCelebration records
        # Look for celebrations today where employee is an attendee or the birthday person
        birthday_result = await self.db.execute(
            select(BirthdayCelebration).where(
                func.date(BirthdayCelebration.celebration_date) == now.date()
            )
        )
        birthday_celebrations = birthday_result.scalars().all()
        
        for celebration in birthday_celebrations:
            # Check if employee is the birthday person or in attendees
            is_birthday_person = celebration.employee_id == employee.id
            is_attendee = False
            if celebration.attendees:
                # Convert attendees to a set of integers for comparison
                attendee_ids_set = set()
                for aid in celebration.attendees:
                    if isinstance(aid, int):
                        attendee_ids_set.add(aid)
                    elif isinstance(aid, str) and aid.isdigit():
                        attendee_ids_set.add(int(aid))
                    elif isinstance(aid, (int, float)):
                        attendee_ids_set.add(int(aid))
                is_attendee = employee.id in attendee_ids_set
            
            if is_birthday_person or is_attendee:
                # Check if employee is in the breakroom where the party is held
                from employees.room_assigner import ROOM_BREAKROOM
                if employee.current_room and celebration.party_room:
                    if ROOM_BREAKROOM in employee.current_room and ROOM_BREAKROOM in celebration.party_room:
                        # Check if party time is set and hasn't ended yet
                        if celebration.party_time:
                            # Party time is the start, assume 1 hour duration
                            party_end = celebration.party_time + timedelta(hours=1)
                            if now < party_end:
                                return party_end
                        else:
                            # No party_time set, use celebration_date + 1 hour as fallback
                            party_end = celebration.celebration_date + timedelta(hours=1)
                            if now < party_end:
                                return party_end
        
        # Check HolidayCelebration records
        # Look for celebrations today where employee is an attendee
        holiday_result = await self.db.execute(
            select(HolidayCelebration).where(
                func.date(HolidayCelebration.celebration_date) == now.date()
            )
        )
        holiday_celebrations = holiday_result.scalars().all()
        
        for celebration in holiday_celebrations:
            # Check if employee is in attendees
            is_attendee = False
            if celebration.attendees:
                # Convert attendees to a set of integers for comparison
                attendee_ids_set = set()
                for aid in celebration.attendees:
                    if isinstance(aid, int):
                        attendee_ids_set.add(aid)
                    elif isinstance(aid, str) and aid.isdigit():
                        attendee_ids_set.add(int(aid))
                    elif isinstance(aid, (int, float)):
                        attendee_ids_set.add(int(aid))
                is_attendee = employee.id in attendee_ids_set
            
            if is_attendee:
                # Check if employee is in the breakroom where the party is held
                from employees.room_assigner import ROOM_BREAKROOM
                if employee.current_room and celebration.party_room:
                    if ROOM_BREAKROOM in employee.current_room and ROOM_BREAKROOM in celebration.party_room:
                        # Check if party time is set and hasn't ended yet
                        if celebration.party_time:
                            # Party time is the start, assume 1 hour duration
                            party_end = celebration.party_time + timedelta(hours=1)
                            if now < party_end:
                                return party_end
                        else:
                            # No party_time set, use celebration_date + 1 hour as fallback
                            party_end = celebration.celebration_date + timedelta(hours=1)
                            if now < party_end:
                                return party_end
        
        return None
    
    async def check_manager_break_frequency(self, employee: Employee) -> dict:
        """Check if a manager is taking breaks too frequently (abuse detection).
        Returns dict with abuse status and statistics.
        """
        if not employee.last_coffee_break:
            return {"is_abuse": False, "reason": "No break history"}
        
        # Check recent break frequency
        from sqlalchemy import select, func
        from datetime import timedelta
        
        # Get all coffee break activities in the last 8 hours
        eight_hours_ago = local_now() - timedelta(hours=8)
        result = await self.db.execute(
            select(Activity).where(
                Activity.employee_id == employee.id,
                Activity.activity_type == "coffee_break",
                Activity.timestamp >= eight_hours_ago
            ).order_by(Activity.timestamp.desc())
        )
        recent_breaks = result.scalars().all()
        
        # Managers should not take more than 2 breaks in 8 hours
        if len(recent_breaks) > 2:
            return {
                "is_abuse": True,
                "reason": f"Too many breaks: {len(recent_breaks)} breaks in the last 8 hours (max 2 allowed)",
                "break_count": len(recent_breaks),
                "time_window_hours": 8
            }
        
        # Check time since last break
        time_since_break = local_now() - employee.last_coffee_break
        hours_since = time_since_break.total_seconds() / 3600
        
        # Managers should wait at least 4 hours between breaks
        if hours_since < 4:
            return {
                "is_abuse": True,
                "reason": f"Break too soon: only {hours_since:.1f} hours since last break (minimum 4 hours required)",
                "hours_since_last_break": hours_since,
                "minimum_hours": 4
            }
        
        return {"is_abuse": False, "reason": "Break frequency is acceptable"}

    async def check_breakroom_capacity(self, breakroom_id: str) -> dict:
        """Check if a breakroom has available capacity.

        Args:
            breakroom_id: ID of the breakroom to check (e.g., "breakroom" or "breakroom_floor2")

        Returns:
            Dict with has_space (bool), current (int), capacity (int), available (int)
        """
        from sqlalchemy import select, or_
        from employees.room_assigner import ROOM_BREAKROOM

        # Break room capacities
        BREAKROOM_CAPACITY = 15  # Each breakroom holds 15 people

        # Count employees currently in this breakroom
        result = await self.db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.current_room == breakroom_id
            )
        )
        employees_in_room = result.scalars().all()
        current_count = len(employees_in_room)

        has_space = current_count < BREAKROOM_CAPACITY
        available = BREAKROOM_CAPACITY - current_count

        return {
            "has_space": has_space,
            "current": current_count,
            "capacity": BREAKROOM_CAPACITY,
            "available": available
        }

    async def check_upcoming_meetings(self, employee: Employee, minutes_ahead: int = 30) -> Optional[Meeting]:
        """Check if an employee has a meeting coming up soon.

        Args:
            employee: Employee to check
            minutes_ahead: How many minutes ahead to check (default: 30)

        Returns:
            Meeting object if employee has an upcoming meeting, None otherwise
        """
        from sqlalchemy import select, or_
        from datetime import timedelta

        now = local_now()
        check_until = now + timedelta(minutes=minutes_ahead)

        # Check if employee is organizer or attendee of any meetings in the next X minutes
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.start_time >= now,
                Meeting.start_time <= check_until,
                or_(
                    Meeting.organizer_id == employee.id,
                    Meeting.attendee_ids.contains([employee.id])  # Check if employee is in attendee list
                )
            ).order_by(Meeting.start_time)
        )
        meetings = result.scalars().all()

        # Check attendee_ids more carefully (JSON field)
        for meeting in meetings:
            # Check if employee is organizer
            if meeting.organizer_id == employee.id:
                return meeting

            # Check if employee is in attendee_ids
            if meeting.attendee_ids:
                # Convert attendee_ids to set for comparison
                attendee_ids_set = set()
                for aid in meeting.attendee_ids:
                    if isinstance(aid, int):
                        attendee_ids_set.add(aid)
                    elif isinstance(aid, str) and aid.isdigit():
                        attendee_ids_set.add(int(aid))
                    elif isinstance(aid, (int, float)):
                        attendee_ids_set.add(int(aid))

                if employee.id in attendee_ids_set:
                    return meeting

        return None

