"""Test script to verify sleep enforcement and timezone"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import async_session_maker
from business.sleep_manager import SleepManager
from config import now, TIMEZONE_NAME

async def test_sleep_enforcement():
    """Test sleep enforcement with current time"""
    async with async_session_maker() as db:
        current_time = now()
        
        print(f"\n{'='*70}")
        print(f"Testing Sleep Enforcement")
        print(f"{'='*70}")
        print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Timezone: {TIMEZONE_NAME}")
        print(f"Hour: {current_time.hour}, Minute: {current_time.minute}")
        print(f"Weekday: {current_time.strftime('%A')} (0=Monday, 6=Sunday)")
        print(f"{'='*70}\n")
        
        sleep_manager = SleepManager(db)
        
        # Get stats before enforcement
        stats_before = await sleep_manager.get_sleeping_stats()
        print(f"BEFORE ENFORCEMENT:")
        print(f"  Sleeping Employees: {stats_before['sleeping_employees']}")
        print(f"  Awake Employees: {stats_before['awake_employees']}")
        print(f"  Sleeping Family: {stats_before['sleeping_family']}\n")
        
        # Enforce sleep rules
        print("Enforcing sleep rules...")
        enforce_result = await sleep_manager.enforce_sleep_rules()
        print(f"\nENFORCEMENT RESULT:")
        print(f"  Enforced to Sleep: {enforce_result['enforced_sleep']}")
        print(f"  Enforced to Wake: {enforce_result['enforced_wake']}")
        print(f"  Is Sleep Period: {enforce_result['is_sleep_period']}")
        print(f"  Message: {enforce_result['message']}\n")
        
        # Get stats after enforcement
        stats_after = await sleep_manager.get_sleeping_stats()
        print(f"AFTER ENFORCEMENT:")
        print(f"  Sleeping Employees: {stats_after['sleeping_employees']}")
        print(f"  Awake Employees: {stats_after['awake_employees']}")
        print(f"  Sleeping Family: {stats_after['sleeping_family']}\n")
        
        # Show change
        sleep_change = stats_after['sleeping_employees'] - stats_before['sleeping_employees']
        wake_change = stats_after['awake_employees'] - stats_before['awake_employees']
        
        if sleep_change != 0 or wake_change != 0:
            print(f"CHANGES:")
            if sleep_change > 0:
                print(f"  +{sleep_change} employees went to sleep")
            elif sleep_change < 0:
                print(f"  {sleep_change} employees woke up")
            if wake_change > 0:
                print(f"  +{wake_change} employees woke up")
            elif wake_change < 0:
                print(f"  {wake_change} employees went to sleep")
        else:
            print("No changes - sleep states are correct for current time")
        
        print(f"\n{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(test_sleep_enforcement())

