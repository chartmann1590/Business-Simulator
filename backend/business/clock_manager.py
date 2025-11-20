"""
Clock In/Out Manager - Handles employee arrival, departure, and time tracking
"""
import random
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, ClockInOut, Activity
from config import now, is_work_hours


class ClockManager:
    """Manages employee clock in/out events and transitions between office and home."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_clock_event(
        self,
        employee_id: int,
        event_type: str,
        location: str = None,
        notes: str = None
    ) -> ClockInOut:
        """
        Log a clock in/out event for an employee.

        Args:
            employee_id: Employee ID
            event_type: Type of event ("clock_in", "clock_out", "arrived_home", "left_home")
            location: Location ("office" or "home")
            notes: Additional context

        Returns:
            ClockInOut event record
        """
        clock_event = ClockInOut(
            employee_id=employee_id,
            event_type=event_type,
            location=location,
            notes=notes
        )
        self.db.add(clock_event)
        await self.db.flush()
        return clock_event

    async def process_end_of_day_departures(self) -> dict:
        """
        Process end-of-day departures (6:45pm-7pm).
        Employees gradually leave the office and transition to going home.

        Returns:
            Dictionary with departure statistics
        """
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday

        # Only run on weekdays between 6:45pm (18:45) and 7:15pm (19:15)
        if current_weekday >= 5:  # Weekend
            return {"departed": 0, "message": "Weekend - no departures"}

        # Check if we're in the departure window (6:45pm - 7:15pm)
        if not (18 <= current_hour <= 19):
            return {"departed": 0, "message": "Not in departure window"}

        if current_hour == 18 and current_minute < 45:
            return {"departed": 0, "message": "Too early - before 6:45pm"}

        if current_hour == 19 and current_minute > 15:
            return {"departed": 0, "message": "Too late - after 7:15pm"}

        # Get all active employees currently at work (not already at home or leaving)
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.notin_(["at_home", "sleeping", "leaving_work", "commuting_home"])
                )
            )
        )
        employees = result.scalars().all()

        if not employees:
            return {"departed": 0, "message": "No employees at work"}

        departed_count = 0
        activities_created = []

        # Stagger departures - not everyone leaves at once
        # Between 6:45-7:00pm: 40% leave
        # Between 7:00-7:10pm: 50% leave
        # Between 7:10-7:15pm: remaining 10% leave
        for employee in employees:
            should_leave = False

            if current_hour == 18 and current_minute >= 45:
                # 6:45pm-6:59pm: 40% chance to leave
                should_leave = random.random() < 0.40
            elif current_hour == 19 and current_minute < 10:
                # 7:00pm-7:09pm: 50% chance to leave
                should_leave = random.random() < 0.50
            elif current_hour == 19 and current_minute >= 10:
                # 7:10pm-7:15pm: Everyone remaining leaves
                should_leave = True

            if should_leave:
                # Check if already clocked out today
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                existing_clock_out = await self.db.execute(
                    select(ClockInOut).where(
                        and_(
                            ClockInOut.employee_id == employee.id,
                            ClockInOut.event_type == "clock_out",
                            ClockInOut.timestamp >= today_start
                        )
                    )
                )
                if existing_clock_out.scalar_one_or_none():
                    continue  # Already clocked out today

                # Update employee state to leaving work
                employee.activity_state = "leaving_work"
                employee.target_room = None
                employee.online_status = "offline"  # Set offline in Teams

                # Log clock out event
                await self.log_clock_event(
                    employee_id=employee.id,
                    event_type="clock_out",
                    location="office",
                    notes="End of work day"
                )

                # Create activity log
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="clock_out",
                    description=f"{employee.name} clocked out and is leaving work for the day",
                    impact="neutral"
                )
                self.db.add(activity)
                activities_created.append(activity)

                departed_count += 1

        if departed_count > 0:
            await self.db.commit()

        return {
            "departed": departed_count,
            "total_employees": len(employees),
            "message": f"{departed_count} employees left work",
            "activities_created": len(activities_created)
        }

    async def process_commuting_employees(self) -> dict:
        """
        Process employees who are leaving work and transition them to commuting home.
        After a brief period (simulating commute), they arrive home.

        Returns:
            Dictionary with commute statistics
        """
        # Get all employees in "leaving_work" state
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state == "leaving_work"
                )
            )
        )
        leaving_employees = result.scalars().all()

        if not leaving_employees:
            return {"commuting": 0, "arrived_home": 0}

        commuting_count = 0
        arrived_home_count = 0

        for employee in leaving_employees:
            # Transition to commuting (happens immediately after leaving_work)
            employee.activity_state = "commuting_home"
            employee.current_room = None
            employee.floor = None
            commuting_count += 1

            # Immediately transition to home (simplified - no actual commute time in simulation)
            # In a more complex system, you could track commute duration
            employee.activity_state = "at_home"

            # Log arrival at home
            await self.log_clock_event(
                employee_id=employee.id,
                event_type="arrived_home",
                location="home",
                notes="Arrived home after work"
            )

            # Create activity log
            activity = Activity(
                employee_id=employee.id,
                activity_type="arrived_home",
                description=f"{employee.name} arrived home and is relaxing with family",
                impact="positive"
            )
            self.db.add(activity)
            arrived_home_count += 1

        if arrived_home_count > 0:
            await self.db.commit()

        return {
            "commuting": commuting_count,
            "arrived_home": arrived_home_count,
            "message": f"{arrived_home_count} employees arrived home"
        }

    async def process_morning_arrivals(self) -> dict:
        """
        Process morning arrivals (7:00am-7:30am).
        Employees transition from home to office at start of day.

        Returns:
            Dictionary with arrival statistics
        """
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday

        # Only run on weekdays between 6:45am and 7:45am
        if current_weekday >= 5:  # Weekend
            return {"arrived": 0, "message": "Weekend - no arrivals"}

        # Check if we're in the arrival window (6:45am - 7:45am)
        if current_hour != 6 and current_hour != 7:
            return {"arrived": 0, "message": "Not in arrival window"}

        if current_hour == 6 and current_minute < 45:
            return {"arrived": 0, "message": "Too early - before 6:45am"}

        if current_hour == 7 and current_minute > 45:
            return {"arrived": 0, "message": "Too late - after 7:45am"}

        # Get all active employees currently at home
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.in_(["at_home", "sleeping"])
                )
            )
        )
        employees = result.scalars().all()

        if not employees:
            return {"arrived": 0, "message": "No employees at home"}

        arrived_count = 0
        activities_created = []

        # Stagger arrivals
        # 6:45am-7:00am: 30% arrive
        # 7:00am-7:30am: 60% arrive
        # 7:30am-7:45am: remaining 10% arrive (latecomers)
        for employee in employees:
            should_arrive = False

            if current_hour == 6 and current_minute >= 45:
                # 6:45am-6:59am: 30% chance to arrive
                should_arrive = random.random() < 0.30
            elif current_hour == 7 and current_minute < 30:
                # 7:00am-7:29am: 60% chance to arrive
                should_arrive = random.random() < 0.60
            elif current_hour == 7 and current_minute >= 30:
                # 7:30am-7:45am: Everyone remaining arrives
                should_arrive = True

            if should_arrive:
                # Check if already clocked in today
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                existing_clock_in = await self.db.execute(
                    select(ClockInOut).where(
                        and_(
                            ClockInOut.employee_id == employee.id,
                            ClockInOut.event_type == "clock_in",
                            ClockInOut.timestamp >= today_start
                        )
                    )
                )
                if existing_clock_in.scalar_one_or_none():
                    continue  # Already clocked in today

                # Log leaving home
                await self.log_clock_event(
                    employee_id=employee.id,
                    event_type="left_home",
                    location="home",
                    notes="Leaving for work"
                )

                # Transition employee to office
                if employee.home_room:
                    employee.current_room = employee.home_room
                    employee.floor = 1
                else:
                    employee.current_room = "Open Workspace"
                    employee.floor = 1

                employee.activity_state = "working"
                employee.target_room = None
                employee.online_status = "online"  # Set online in Teams

                # Log clock in event
                await self.log_clock_event(
                    employee_id=employee.id,
                    event_type="clock_in",
                    location="office",
                    notes="Morning arrival"
                )

                # Create activity log
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="clock_in",
                    description=f"{employee.name} clocked in and started work",
                    impact="positive"
                )
                self.db.add(activity)
                activities_created.append(activity)

                arrived_count += 1

        if arrived_count > 0:
            await self.db.commit()

        return {
            "arrived": arrived_count,
            "total_employees": len(employees),
            "message": f"{arrived_count} employees arrived at work",
            "activities_created": len(activities_created)
        }

    async def get_employee_clock_history(
        self,
        employee_id: int,
        days: int = 7
    ) -> list[ClockInOut]:
        """
        Get clock in/out history for an employee.

        Args:
            employee_id: Employee ID
            days: Number of days of history to retrieve

        Returns:
            List of ClockInOut events
        """
        cutoff_time = now() - timedelta(days=days)

        result = await self.db.execute(
            select(ClockInOut).where(
                and_(
                    ClockInOut.employee_id == employee_id,
                    ClockInOut.timestamp >= cutoff_time
                )
            ).order_by(ClockInOut.timestamp.desc())
        )

        return result.scalars().all()

    async def get_all_clock_events_today(self) -> list[ClockInOut]:
        """
        Get all clock events for today across all employees.

        Returns:
            List of ClockInOut events for today
        """
        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(ClockInOut).where(
                ClockInOut.timestamp >= today_start
            ).order_by(ClockInOut.timestamp.desc())
        )

        return result.scalars().all()
