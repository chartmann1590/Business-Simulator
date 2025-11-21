"""
Clock In/Out Manager - Handles employee arrival, departure, and time tracking

All times are in New York timezone (America/New_York) as configured in config.py.
The 'now()' function from config returns timezone-aware datetimes in New York time.
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
        Process end-of-day departures (5:00pm-7:15pm).
        Employees gradually leave the office and transition to going home.

        Returns:
            Dictionary with departure statistics
        """
        import logging
        logger = logging.getLogger(__name__)
        
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday
        time_str = current_time.strftime("%I:%M %p")

        # Only run on weekdays between 5:00pm (17:00) and 7:15pm (19:15)
        if current_weekday >= 5:  # Weekend
            logger.debug(f"[CLOCK OUT] {time_str} - Weekend - no departures")
            return {"departed": 0, "message": "Weekend - no departures"}

        # Check if we're in the departure window (5:00pm - 7:15pm)
        if not (17 <= current_hour <= 19):
            logger.debug(f"[CLOCK OUT] {time_str} - Not in departure window (5:00pm-7:15pm)")
            return {"departed": 0, "message": "Not in departure window"}

        if current_hour == 17:
            # 5:00pm-5:59pm: Allow departures
            pass
        elif current_hour == 18:
            # 6:00pm-6:59pm: Allow departures
            pass
        elif current_hour == 19 and current_minute > 15:
            logger.debug(f"[CLOCK OUT] {time_str} - Too late - after 7:15pm")
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
            logger.debug(f"[CLOCK OUT] {time_str} - No employees at work to clock out")
            return {"departed": 0, "message": "No employees at work"}

        departed_count = 0
        activities_created = []

        # Stagger departures - not everyone leaves at once
        # Between 5:00-5:30pm: 25% leave (early birds)
        # Between 5:30-6:00pm: 40% leave
        # Between 6:00-6:30pm: 50% leave
        # Between 6:30-6:45pm: 60% leave
        # Between 6:45-7:00pm: 80% leave (most people leave by now)
        # Between 7:00-7:10pm: 90% leave (almost everyone)
        # Between 7:10-7:15pm: Everyone remaining leaves (100%)
        for employee in employees:
            should_leave = False

            if current_hour == 17:
                # 5:00pm-5:29pm: 25% chance to leave
                if current_minute < 30:
                    should_leave = random.random() < 0.25
                # 5:30pm-5:59pm: 40% chance to leave
                else:
                    should_leave = random.random() < 0.40
            elif current_hour == 18:
                # 6:00pm-6:29pm: 50% chance to leave
                if current_minute < 30:
                    should_leave = random.random() < 0.50
                # 6:30pm-6:44pm: 70% chance to leave
                elif current_minute < 45:
                    should_leave = random.random() < 0.70
                # 6:45pm-6:49pm: 85% chance to leave
                elif current_minute < 50:
                    should_leave = random.random() < 0.85
                # 6:50pm-6:54pm: 95% chance to leave (almost everyone)
                elif current_minute < 55:
                    should_leave = random.random() < 0.95
                # 6:55pm-6:59pm: 98% chance to leave (nearly everyone)
                else:
                    should_leave = random.random() < 0.98
            elif current_hour == 19:
                # 7:00pm-7:09pm: 90% chance to leave (almost everyone)
                if current_minute < 10:
                    should_leave = random.random() < 0.90
                # 7:10pm-7:15pm: Everyone remaining leaves (100%)
                elif current_minute >= 10:
                    should_leave = True

            if should_leave:
                # Check if already clocked out today
                # Use timezone-aware datetime for comparison (New York timezone)
                # current_time is already timezone-aware from now() function
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                # Ensure timezone is preserved (should already be set from now() but double-check)
                if today_start.tzinfo is None:
                    from config import get_timezone
                    tz = get_timezone()  # This returns America/New_York timezone
                    today_start = tz.localize(today_start)
                
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
                    logger.debug(f"[CLOCK OUT] {time_str} - Employee {employee.name} already clocked out today, skipping")
                    continue  # Already clocked out today

                # Update employee state to leaving work
                employee.activity_state = "leaving_work"
                employee.target_room = None
                employee.online_status = "offline"  # Set offline in Teams

                # Log clock out event
                clock_event = await self.log_clock_event(
                    employee_id=employee.id,
                    event_type="clock_out",
                    location="office",
                    notes="End of work day"
                )
                logger.debug(f"[CLOCK OUT] {time_str} - Created clock out event for {employee.name} (event_id: {clock_event.id})")

                # Create activity log
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="clock_out",
                    description=f"{employee.name} clocked out and is leaving work for the day"
                )
                self.db.add(activity)
                activities_created.append(activity)
                logger.debug(f"[CLOCK OUT] {time_str} - Created activity log for {employee.name}")

                departed_count += 1

        # Always commit if we made any changes (even if departed_count is 0, we might have checked employees)
        # But only commit if we actually made changes to the database
        if departed_count > 0 or len(activities_created) > 0:
            try:
                await self.db.commit()
                logger.info(f"[CLOCK OUT] {time_str} - ✅ COMMITTED: {departed_count} employees left work, {len(activities_created)} activities created (out of {len(employees)} at work)")
            except Exception as e:
                logger.error(f"[CLOCK OUT] {time_str} - ❌ COMMIT FAILED: {e}", exc_info=True)
                await self.db.rollback()
        else:
            # Log at info level if it's after 6:30pm so we can see what's happening
            log_level = logger.info if (current_hour == 18 and current_minute >= 30) or current_hour == 19 else logger.debug
            log_level(f"[CLOCK OUT] {time_str} - No employees left yet (checked {len(employees)} employees at work)")

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

        # Get all active employees currently at home (excluding sick employees)
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.in_(["at_home", "sleeping"]),
                    Employee.is_sick == False  # Sick employees stay home
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
                # Use timezone-aware datetime (New York timezone)
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                # Ensure timezone is preserved
                if today_start.tzinfo is None:
                    from config import get_timezone
                    tz = get_timezone()  # America/New_York
                    today_start = tz.localize(today_start)
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
        Uses New York timezone for "today" calculation.

        Returns:
            List of ClockInOut events for today
        """
        # now() returns timezone-aware datetime in configured timezone (America/New_York)
        current_time = now()
        today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        # Ensure timezone is preserved
        if today_start.tzinfo is None:
            from config import get_timezone
            tz = get_timezone()  # America/New_York
            today_start = tz.localize(today_start)

        result = await self.db.execute(
            select(ClockInOut).where(
                ClockInOut.timestamp >= today_start
            ).order_by(ClockInOut.timestamp.desc())
        )

        return result.scalars().all()

    async def backfill_missing_clock_outs(self) -> dict:
        """
        Backfill missing clock-out events for employees who are already at home or leaving
        but don't have a clock-out event for today.
        
        Returns:
            Dictionary with backfill statistics
        """
        import logging
        logger = logging.getLogger(__name__)
        
        current_time = now()
        time_str = current_time.strftime("%I:%M %p")
        
        # Get today's start in New York timezone
        today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if today_start.tzinfo is None:
            from config import get_timezone
            tz = get_timezone()
            today_start = tz.localize(today_start)
        
        # Find employees who are at home, leaving, or commuting but don't have a clock-out for today
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.in_(["at_home", "sleeping", "leaving_work", "commuting_home"])
                )
            )
        )
        employees_at_home = result.scalars().all()
        
        if not employees_at_home:
            return {"backfilled": 0, "message": "No employees at home to check"}
        
        backfilled_count = 0
        activities_created = []
        
        for employee in employees_at_home:
            # Check if they already have a clock-out for today
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
                continue  # Already has clock-out for today
            
            # Check if they have a clock-in for today (to estimate when they left)
            clock_in_result = await self.db.execute(
                select(ClockInOut).where(
                    and_(
                        ClockInOut.employee_id == employee.id,
                        ClockInOut.event_type == "clock_in",
                        ClockInOut.timestamp >= today_start
                    )
                ).order_by(ClockInOut.timestamp.desc())
            )
            clock_in = clock_in_result.scalar_one_or_none()
            
            # Estimate clock-out time: if they clocked in, use 8-10 hours later, otherwise use 6:30pm as default
            if clock_in and clock_in.timestamp:
                # Estimate they left 8-10 hours after clocking in (typical work day)
                from datetime import timedelta
                estimated_leave_time = clock_in.timestamp + timedelta(hours=9)  # 9 hours average
                # Don't set it later than current time
                if estimated_leave_time > current_time:
                    estimated_leave_time = current_time - timedelta(minutes=30)  # 30 minutes ago
            else:
                # No clock-in found, estimate they left around 6:30pm today
                estimated_leave_time = today_start.replace(hour=18, minute=30)  # 6:30pm
                if estimated_leave_time.tzinfo is None:
                    from config import get_timezone
                    tz = get_timezone()
                    estimated_leave_time = tz.localize(estimated_leave_time)
                # Don't set it later than current time
                if estimated_leave_time > current_time:
                    estimated_leave_time = current_time - timedelta(minutes=30)
            
            # Create clock-out event with estimated timestamp
            clock_event = ClockInOut(
                employee_id=employee.id,
                event_type="clock_out",
                location="office",
                notes="Backfilled - End of work day",
                timestamp=estimated_leave_time
            )
            self.db.add(clock_event)
            await self.db.flush()
            
            # Create activity log
            activity = Activity(
                employee_id=employee.id,
                activity_type="clock_out",
                description=f"{employee.name} clocked out and left work for the day (backfilled)"
            )
            self.db.add(activity)
            activities_created.append(activity)
            
            backfilled_count += 1
            logger.info(f"[CLOCK OUT BACKFILL] {time_str} - Backfilled clock-out for {employee.name} (estimated time: {estimated_leave_time.strftime('%I:%M %p')})")
        
        if backfilled_count > 0:
            try:
                await self.db.commit()
                logger.info(f"[CLOCK OUT BACKFILL] {time_str} - ✅ COMMITTED: {backfilled_count} clock-out events backfilled, {len(activities_created)} activities created")
            except Exception as e:
                logger.error(f"[CLOCK OUT BACKFILL] {time_str} - ❌ COMMIT FAILED: {e}", exc_info=True)
                await self.db.rollback()
                return {"backfilled": 0, "message": f"Error committing backfill: {e}"}
        
        return {
            "backfilled": backfilled_count,
            "total_checked": len(employees_at_home),
            "message": f"Backfilled {backfilled_count} missing clock-out events",
            "activities_created": len(activities_created)
        }
