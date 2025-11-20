"""
Sleep Manager - Handles employee and family member sleep schedules
Bedtime: 10pm-12am (staggered)
Wake-up: Employees 5:30am-6:45am, Family 7:30am-9am
"""
import random
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, FamilyMember, HomePet, Activity
from config import now


class SleepManager:
    """Manages sleep schedules for employees, family members, and pets."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_bedtime(self) -> dict:
        """
        Process bedtime transitions (10pm-12am).
        Employees, family members, and pets gradually go to sleep.

        Returns:
            Dictionary with sleep statistics
        """
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute

        # Only run between 10pm (22:00) and 12am (00:00)
        # Handle midnight rollover (hour 0 = 12am)
        if not (current_hour >= 22 or current_hour == 0):
            return {"went_to_sleep": 0, "message": "Not in bedtime window"}

        # Get all active employees who are awake
        result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.sleep_state == "awake"
                )
            )
        )
        employees = result.scalars().all()

        sleep_count = 0
        activities_created = []

        # Stagger bedtime:
        # 10pm-10:30pm (22:00-22:30): 30% go to sleep
        # 10:30pm-11pm (22:30-23:00): 40% go to sleep
        # 11pm-11:30pm (23:00-23:30): 20% go to sleep
        # 11:30pm-12am (23:30-00:00): Everyone remaining goes to sleep
        for employee in employees:
            should_sleep = False

            if current_hour == 22 and current_minute < 30:
                # 10pm-10:30pm: 30% chance to sleep
                should_sleep = random.random() < 0.30
            elif current_hour == 22 and current_minute >= 30:
                # 10:30pm-10:59pm: 40% chance to sleep
                should_sleep = random.random() < 0.40
            elif current_hour == 23 and current_minute < 30:
                # 11pm-11:29pm: 20% chance to sleep
                should_sleep = random.random() < 0.20
            elif current_hour == 23 and current_minute >= 30:
                # 11:30pm-11:59pm: Everyone remaining sleeps
                should_sleep = True
            elif current_hour == 0:
                # 12am-12:59am: Everyone remaining sleeps (midnight rollover)
                should_sleep = True

            if should_sleep:
                # Update employee to sleeping state
                employee.sleep_state = "sleeping"
                employee.activity_state = "sleeping"

                # Create activity log
                activity = Activity(
                    employee_id=employee.id,
                    activity_type="sleep",
                    description=f"{employee.name} went to bed for the night",
                    impact="neutral"
                )
                self.db.add(activity)
                activities_created.append(activity)
                sleep_count += 1

                # Also put family members to sleep (if they have any)
                family_result = await self.db.execute(
                    select(FamilyMember).where(
                        and_(
                            FamilyMember.employee_id == employee.id,
                            FamilyMember.sleep_state == "awake"
                        )
                    )
                )
                family_members = family_result.scalars().all()

                for family_member in family_members:
                    family_member.sleep_state = "sleeping"

                # Also put pets to sleep (if they have any)
                pets_result = await self.db.execute(
                    select(HomePet).where(
                        and_(
                            HomePet.employee_id == employee.id,
                            HomePet.sleep_state == "awake"
                        )
                    )
                )
                pets = pets_result.scalars().all()

                for pet in pets:
                    pet.sleep_state = "sleeping"

        if sleep_count > 0:
            await self.db.commit()

        return {
            "went_to_sleep": sleep_count,
            "message": f"{sleep_count} employees and their families went to sleep",
            "activities_created": len(activities_created)
        }

    async def process_wake_up(self) -> dict:
        """
        Process morning wake-ups.
        - Employees: 5:30am-6:45am (need time to prepare for 7am work start)
        - Family members: 7:30am-9am (wake after employees leave)
        - Pets: Wake with employees

        Returns:
            Dictionary with wake-up statistics
        """
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday

        woke_employees = 0
        woke_family = 0

        # Process employee wake-ups (5:30am-6:45am) on weekdays
        if current_weekday < 5:  # Weekday
            if (current_hour == 5 and current_minute >= 30) or (current_hour == 6 and current_minute < 45):
                # Get all active employees who are sleeping
                result = await self.db.execute(
                    select(Employee).where(
                        and_(
                            Employee.status == "active",
                            Employee.sleep_state == "sleeping"
                        )
                    )
                )
                employees = result.scalars().all()

                # Stagger employee wake-ups:
                # 5:30am-6:00am: 40% wake up (early birds)
                # 6:00am-6:30am: 50% wake up (normal)
                # 6:30am-6:45am: Everyone remaining wakes up (last minute)
                for employee in employees:
                    should_wake = False

                    if current_hour == 5 and current_minute >= 30:
                        # 5:30am-5:59am: 40% chance to wake
                        should_wake = random.random() < 0.40
                    elif current_hour == 6 and current_minute < 30:
                        # 6:00am-6:29am: 50% chance to wake
                        should_wake = random.random() < 0.50
                    elif current_hour == 6 and current_minute >= 30:
                        # 6:30am-6:44am: Everyone remaining wakes
                        should_wake = True

                    if should_wake:
                        # Wake up employee
                        employee.sleep_state = "awake"
                        employee.activity_state = "at_home"  # At home preparing for work

                        # Create activity log
                        activity = Activity(
                            employee_id=employee.id,
                            activity_type="wake_up",
                            description=f"{employee.name} woke up and is preparing for work",
                            impact="neutral"
                        )
                        self.db.add(activity)
                        woke_employees += 1

                        # Wake up pets too (they need to be fed)
                        pets_result = await self.db.execute(
                            select(HomePet).where(
                                and_(
                                    HomePet.employee_id == employee.id,
                                    HomePet.sleep_state == "sleeping"
                                )
                            )
                        )
                        pets = pets_result.scalars().all()

                        for pet in pets:
                            pet.sleep_state = "awake"

        # Process family member wake-ups (7:30am-9am) on all days
        if (current_hour == 7 and current_minute >= 30) or (current_hour == 8) or (current_hour == 9 and current_minute == 0):
            # Get all family members who are sleeping
            family_result = await self.db.execute(
                select(FamilyMember).where(
                    FamilyMember.sleep_state == "sleeping"
                )
            )
            family_members = family_result.scalars().all()

            # Stagger family wake-ups:
            # 7:30am-8:00am: 30% wake up
            # 8:00am-8:30am: 50% wake up
            # 8:30am-9:00am: Everyone remaining wakes up
            for family_member in family_members:
                should_wake = False

                if current_hour == 7 and current_minute >= 30:
                    # 7:30am-7:59am: 30% chance to wake
                    should_wake = random.random() < 0.30
                elif current_hour == 8 and current_minute < 30:
                    # 8:00am-8:29am: 50% chance to wake
                    should_wake = random.random() < 0.50
                elif current_hour == 8 and current_minute >= 30:
                    # 8:30am-8:59am: Everyone remaining wakes
                    should_wake = True
                elif current_hour == 9 and current_minute == 0:
                    # 9:00am: Ensure everyone is awake
                    should_wake = True

                if should_wake:
                    family_member.sleep_state = "awake"
                    woke_family += 1

        if woke_employees > 0 or woke_family > 0:
            await self.db.commit()

        return {
            "woke_employees": woke_employees,
            "woke_family": woke_family,
            "message": f"{woke_employees} employees and {woke_family} family members woke up"
        }

    async def get_sleeping_stats(self) -> dict:
        """
        Get current sleep statistics.

        Returns:
            Dictionary with sleep stats
        """
        # Count sleeping employees
        employees_result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.sleep_state == "sleeping"
                )
            )
        )
        sleeping_employees = len(employees_result.scalars().all())

        # Count awake employees
        awake_result = await self.db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.sleep_state == "awake"
                )
            )
        )
        awake_employees = len(awake_result.scalars().all())

        # Count sleeping family members
        family_result = await self.db.execute(
            select(FamilyMember).where(
                FamilyMember.sleep_state == "sleeping"
            )
        )
        sleeping_family = len(family_result.scalars().all())

        return {
            "sleeping_employees": sleeping_employees,
            "awake_employees": awake_employees,
            "sleeping_family": sleeping_family,
            "total_employees": sleeping_employees + awake_employees
        }
