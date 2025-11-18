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
        # Employees take coffee breaks every 2-4 hours
        if not employee.last_coffee_break:
            return True  # Never had a break
        
        time_since_break = local_now() - employee.last_coffee_break
        hours_since = time_since_break.total_seconds() / 3600
        
        # Random chance based on time since last break
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
        
        for employee in employees_on_break:
            # Check if they have a break start time
            if not employee.last_coffee_break:
                continue
            
            time_on_break = now - employee.last_coffee_break
            
            # If break is longer than 30 minutes, return to work
            if time_on_break > break_time_limit:
                # Return employee to their home room
                if employee.home_room:
                    await update_employee_location(employee, employee.home_room, "working", self.db)
                else:
                    # If no home room, set to idle state
                    employee.activity_state = "idle"
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

