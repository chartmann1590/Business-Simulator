"""
Verification script to test the sleep system is working properly.
"""
import asyncio
from database.database import async_session_maker
from database.models import Employee, FamilyMember, Activity
from sqlalchemy import select, desc
from config import now, TIMEZONE_NAME
from datetime import timedelta

async def verify_sleep_system():
    """Verify sleep system is functioning correctly."""
    print("=" * 70)
    print("SLEEP SYSTEM VERIFICATION")
    print("=" * 70)
    print()

    current_time = now()
    print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Timezone: {TIMEZONE_NAME}")
    print(f"Hour: {current_time.hour}")
    print(f"Weekday: {current_time.strftime('%A')}")
    print()

    async with async_session_maker() as db:
        # Check employee sleep states
        print("=" * 70)
        print("EMPLOYEE SLEEP STATES")
        print("=" * 70)

        sleeping_result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.sleep_state == "sleeping"
            )
        )
        sleeping = sleeping_result.scalars().all()

        awake_result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.sleep_state == "awake"
            )
        )
        awake = awake_result.scalars().all()

        print(f"Sleeping: {len(sleeping)} employees")
        print(f"Awake: {len(awake)} employees")
        print()

        # Show sample sleeping employees
        if sleeping:
            print("Sample Sleeping Employees:")
            for emp in sleeping[:5]:
                print(f"  - {emp.name} ({emp.activity_state})")
            if len(sleeping) > 5:
                print(f"  ... and {len(sleeping) - 5} more")
            print()

        # Check family member sleep states
        family_result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.sleep_state == "sleeping"
            )
        )
        sleeping_family = family_result.scalars().all()
        print(f"Sleeping Family Members: {len(sleeping_family)}")
        print()

        # Check recent sleep-related activities (last 24 hours)
        print("=" * 70)
        print("RECENT SLEEP ACTIVITIES (Last 24 Hours)")
        print("=" * 70)

        cutoff = current_time - timedelta(hours=24)

        activities_result = await db.execute(
            select(Activity).where(
                Activity.activity_type.in_(["sleep", "wake_up", "clock_in", "clock_out"])
            ).order_by(desc(Activity.timestamp)).limit(20)
        )
        activities = activities_result.scalars().all()

        if activities:
            sleep_count = sum(1 for a in activities if a.activity_type == "sleep")
            wake_count = sum(1 for a in activities if a.activity_type == "wake_up")
            clock_in_count = sum(1 for a in activities if a.activity_type == "clock_in")

            print(f"Total Activities Found: {len(activities)}")
            print(f"  - Sleep: {sleep_count}")
            print(f"  - Wake Up: {wake_count}")
            print(f"  - Clock In: {clock_in_count}")
            print()

            print("Most Recent Activities:")
            for activity in activities[:10]:
                timestamp = activity.timestamp
                if timestamp:
                    time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    time_str = "Unknown"
                print(f"  [{time_str}] {activity.activity_type}: {activity.description[:60]}")
            print()
        else:
            print("No recent sleep activities found in last 24 hours")
            print("Note: This may be normal if the system just started")
            print()

        # Check expected behavior based on current time
        print("=" * 70)
        print("EXPECTED BEHAVIOR AT CURRENT TIME")
        print("=" * 70)

        hour = current_time.hour
        weekday = current_time.weekday()
        is_weekday = weekday < 5

        if hour >= 22 or hour < 5 or (hour == 5 and current_time.minute < 30):
            print("[SLEEP PERIOD]")
            print("Expected: Most/all employees should be sleeping")
            print(f"Actual: {len(sleeping)}/{len(sleeping) + len(awake)} employees sleeping")
            if len(sleeping) == 0 and (hour >= 23 or hour < 5):
                print("[WARNING] No employees sleeping during sleep period!")
        elif is_weekday and ((hour == 5 and current_time.minute >= 30) or (hour == 6 and current_time.minute < 45)):
            print("[WAKE-UP PERIOD - EMPLOYEES]")
            print("Expected: Employees should be waking up")
            print(f"Actual: {len(awake)} employees awake")
        elif is_weekday and hour == 7 and current_time.minute < 45:
            print("[WORK ARRIVAL PERIOD]")
            print("Expected: Employees arriving at work")
            working_result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.activity_state == "working"
                )
            )
            working = working_result.scalars().all()
            print(f"Actual: {len(working)} employees working")
        elif is_weekday and 7 <= hour < 19:
            print("[WORK HOURS]")
            print("Expected: Employees should be at work")
            working_result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.activity_state == "working"
                )
            )
            working = working_result.scalars().all()
            at_home_result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.activity_state == "at_home"
                )
            )
            at_home = at_home_result.scalars().all()
            print(f"Actual: {len(working)} working, {len(at_home)} at home")
        else:
            print("[NON-WORK HOURS]")
            print("Expected: Employees should be at home")
            at_home_result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.activity_state.in_(["at_home", "sleeping"])
                )
            )
            at_home = at_home_result.scalars().all()
            print(f"Actual: {len(at_home)} employees at home")

        print()
        print("=" * 70)
        print("VERIFICATION COMPLETE")
        print("=" * 70)
        print()
        print("Review the results above to ensure sleep system is working properly.")
        print("If issues are found, check:")
        print("  1. Backend is running")
        print("  2. Sleep background task is running (check logs)")
        print("  3. Timezone is correct (America/New_York)")
        print("  4. System time is accurate")

if __name__ == "__main__":
    asyncio.run(verify_sleep_system())
