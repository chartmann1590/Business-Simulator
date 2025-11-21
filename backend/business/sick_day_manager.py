"""
Sick Day Manager - Handles employee sick day call-ins and tracking
Employees can call in sick, stay home, and track sick day history
"""
import random
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Activity
from config import now, TIMEZONE_NAME

logger = logging.getLogger(__name__)


class SickDayManager:
    """Manages sick day call-ins and tracking for employees."""

    # Common sick day reasons
    SICK_REASONS = [
        "Flu symptoms",
        "Stomach bug",
        "Migraine",
        "Cold and fever",
        "Back pain",
        "Sinus infection",
        "Allergies",
        "Not feeling well",
        "Doctor's appointment",
        "Family emergency (sick child)",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_random_sick_calls(self) -> dict:
        """
        Randomly generate sick day call-ins.
        Realistic rates: 2-4% of employees call in sick on any given day.

        Returns:
            Dictionary with sick call statistics
        """
        current_time = now()
        current_hour = current_time.hour
        current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday

        # Only process on weekdays during early morning (5am-7am)
        # This is when employees would call in sick before work
        if current_weekday >= 5:  # Weekend
            return {"sick_calls": 0, "message": "Weekend - no sick calls"}

        if current_hour < 5 or current_hour >= 8:
            return {"sick_calls": 0, "message": "Not in sick call window (5am-8am)"}

        # Get all active employees who are not already sick
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.is_sick == False
                )
            )
        )
        employees = result.scalars().all()

        if not employees:
            return {"sick_calls": 0, "message": "No eligible employees"}

        sick_calls = 0
        notifications = []

        # Realistic sick rate: 2-4% of workforce per day
        sick_rate = random.uniform(0.02, 0.04)

        for employee in employees:
            # Random chance to call in sick based on sick rate
            if random.random() < sick_rate:
                # Call in sick
                sick_result = await self.call_in_sick(
                    employee=employee,
                    reason=random.choice(self.SICK_REASONS),
                    auto_generated=True
                )

                if sick_result["success"]:
                    sick_calls += 1
                    notifications.append(sick_result["notification"])

        if sick_calls > 0:
            await self.db.commit()

        return {
            "sick_calls": sick_calls,
            "total_employees": len(employees),
            "sick_rate": f"{(sick_calls / len(employees) * 100):.2f}%",
            "notifications": notifications,
            "message": f"{sick_calls} employees called in sick"
        }

    async def call_in_sick(
        self,
        employee: Employee,
        reason: str = None,
        auto_generated: bool = False
    ) -> dict:
        """
        Process an employee calling in sick.

        Args:
            employee: Employee object
            reason: Reason for sick day
            auto_generated: Whether this was auto-generated or manual

        Returns:
            Dictionary with call-in results and notification data
        """
        current_time = now()

        # Check if already sick
        if employee.is_sick:
            return {
                "success": False,
                "message": f"{employee.name} is already marked as sick",
                "notification": None
            }

        # Set default reason if not provided
        if not reason:
            reason = random.choice(self.SICK_REASONS)

        # Update employee status
        employee.is_sick = True
        employee.sick_since = current_time
        employee.sick_reason = reason
        employee.activity_state = "sick"
        employee.online_status = "offline"  # Offline in Teams

        # Increment sick day counters
        employee.sick_days_this_month = (employee.sick_days_this_month or 0) + 1
        employee.sick_days_this_year = (employee.sick_days_this_year or 0) + 1

        # If employee is at work, send them home
        if employee.current_room and employee.activity_state not in ["at_home", "sick"]:
            employee.current_room = None
            employee.floor = None
            employee.activity_state = "sick"

        self.db.add(employee)

        # Create activity log
        activity = Activity(
            employee_id=employee.id,
            activity_type="sick_call",
            description=f"{employee.name} called in sick - {reason}"
        )
        self.db.add(activity)

        # Create notification data
        notification = {
            "type": "sick_call",
            "employee_id": employee.id,
            "employee_name": employee.name,
            "department": employee.department,
            "reason": reason,
            "timestamp": current_time.isoformat(),
            "message": f"{employee.name} ({employee.department}) called in sick: {reason}",
            "severity": "info"
        }

        logger.info(f"[SICK CALL] {employee.name} called in sick: {reason}")

        return {
            "success": True,
            "message": f"{employee.name} successfully called in sick",
            "notification": notification,
            "employee_id": employee.id,
            "reason": reason
        }

    async def return_from_sick(self, employee: Employee) -> dict:
        """
        Process an employee returning from sick leave.

        Args:
            employee: Employee object

        Returns:
            Dictionary with return results
        """
        if not employee.is_sick:
            return {
                "success": False,
                "message": f"{employee.name} is not marked as sick"
            }

        # Calculate sick duration
        if employee.sick_since:
            duration = now() - employee.sick_since
            days_sick = duration.total_seconds() / 86400
        else:
            days_sick = 0

        # Clear sick status
        employee.is_sick = False
        old_reason = employee.sick_reason
        employee.sick_reason = None
        employee.sick_since = None
        employee.activity_state = "at_home"  # Start at home
        employee.online_status = "online"  # Back online

        self.db.add(employee)

        # Create activity log
        activity = Activity(
            employee_id=employee.id,
            activity_type="return_from_sick",
            description=f"{employee.name} returned from sick leave (was sick for {days_sick:.1f} days)"
        )
        self.db.add(activity)

        await self.db.commit()

        logger.info(f"[RETURN FROM SICK] {employee.name} returned from sick leave")

        return {
            "success": True,
            "message": f"{employee.name} returned from sick leave",
            "days_sick": days_sick,
            "reason": old_reason
        }

    async def auto_recover_sick_employees(self) -> dict:
        """
        Automatically recover employees who have been sick for 1-3 days.
        This simulates employees getting better and returning to work.

        Returns:
            Dictionary with recovery statistics
        """
        current_time = now()

        # Get all sick employees
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.is_sick == True
                )
            )
        )
        sick_employees = result.scalars().all()

        if not sick_employees:
            return {"recovered": 0, "message": "No sick employees"}

        recovered_count = 0

        for employee in sick_employees:
            if not employee.sick_since:
                continue

            # Calculate how long employee has been sick
            sick_duration = current_time - employee.sick_since
            hours_sick = sick_duration.total_seconds() / 3600

            # Recovery probability based on time sick
            # After 24 hours: 30% chance to recover
            # After 48 hours: 60% chance to recover
            # After 72 hours: 100% chance to recover
            recovery_probability = 0

            if hours_sick >= 72:  # 3 days
                recovery_probability = 1.0
            elif hours_sick >= 48:  # 2 days
                recovery_probability = 0.60
            elif hours_sick >= 24:  # 1 day
                recovery_probability = 0.30

            # Check if employee recovers
            if random.random() < recovery_probability:
                await self.return_from_sick(employee)
                recovered_count += 1

        return {
            "recovered": recovered_count,
            "still_sick": len(sick_employees) - recovered_count,
            "message": f"{recovered_count} employees recovered from illness"
        }

    async def get_sick_employees(self) -> list[dict]:
        """
        Get all currently sick employees.

        Returns:
            List of sick employee data
        """
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.is_sick == True
                )
            ).order_by(Employee.sick_since.desc())
        )
        sick_employees = result.scalars().all()

        current_time = now()
        sick_list = []

        for emp in sick_employees:
            if emp.sick_since:
                duration = current_time - emp.sick_since
                hours_sick = duration.total_seconds() / 3600
                days_sick = hours_sick / 24
            else:
                hours_sick = 0
                days_sick = 0

            sick_list.append({
                "id": emp.id,
                "name": emp.name,
                "title": emp.title,
                "department": emp.department,
                "reason": emp.sick_reason,
                "sick_since": emp.sick_since.isoformat() if emp.sick_since else None,
                "hours_sick": round(hours_sick, 1),
                "days_sick": round(days_sick, 1),
                "sick_days_this_month": emp.sick_days_this_month or 0,
                "sick_days_this_year": emp.sick_days_this_year or 0
            })

        return sick_list

    async def get_sick_day_statistics(self) -> dict:
        """
        Get overall sick day statistics for the company.

        Returns:
            Dictionary with sick day stats
        """
        # Count currently sick
        result = await self.db.execute(
            select(func.count(Employee.id)).where(
                and_(
                    Employee.status == "active",
                    Employee.is_sick == True
                )
            )
        )
        currently_sick = result.scalar()

        # Total active employees
        result = await self.db.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active"
            )
        )
        total_employees = result.scalar()

        # Total sick days this month
        result = await self.db.execute(
            select(func.sum(Employee.sick_days_this_month)).where(
                Employee.status == "active"
            )
        )
        total_sick_days_month = result.scalar() or 0

        # Total sick days this year
        result = await self.db.execute(
            select(func.sum(Employee.sick_days_this_year)).where(
                Employee.status == "active"
            )
        )
        total_sick_days_year = result.scalar() or 0

        # Average sick days per employee this year
        avg_sick_days = total_sick_days_year / total_employees if total_employees > 0 else 0

        return {
            "currently_sick": currently_sick,
            "total_employees": total_employees,
            "sick_rate": f"{(currently_sick / total_employees * 100):.2f}%" if total_employees > 0 else "0%",
            "total_sick_days_month": total_sick_days_month,
            "total_sick_days_year": total_sick_days_year,
            "avg_sick_days_per_employee": round(avg_sick_days, 2)
        }

    async def reset_monthly_counters(self) -> dict:
        """
        Reset monthly sick day counters (run at start of each month).

        Returns:
            Dictionary with reset statistics
        """
        result = await self.db.execute(
            select(Employee).where(
                Employee.status == "active"
            )
        )
        employees = result.scalars().all()

        for emp in employees:
            emp.sick_days_this_month = 0

        await self.db.commit()

        return {
            "reset": len(employees),
            "message": f"Reset monthly sick day counters for {len(employees)} employees"
        }
