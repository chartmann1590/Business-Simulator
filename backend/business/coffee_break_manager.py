from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Activity
from sqlalchemy import select
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
        
        # Check for manager break abuse before allowing break
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
        
        # Update last coffee break time
        employee.last_coffee_break = now
        self.db.add(employee)
        
        # Find a breakroom on the employee's floor or nearby
        target_breakroom = ROOM_BREAKROOM
        if employee.floor == 2:
            target_breakroom = f"{ROOM_BREAKROOM}_floor2"
        elif employee.floor >= 3:
            # Use breakroom on floor 2 or 1
            target_breakroom = f"{ROOM_BREAKROOM}_floor2" if random.random() < 0.5 else ROOM_BREAKROOM
        
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
            
            # Second check: If employee is on break, check break duration
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
            
            # Second check: If employee is on break, check break duration
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

