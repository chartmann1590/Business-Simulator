"""Script to generate meetings immediately - for last week, today, and an in-progress meeting."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import async_session_maker
from business.meeting_manager import MeetingManager
from database.models import Meeting
from sqlalchemy import select
from datetime import datetime, timedelta
from config import now as local_now


async def generate_meetings_now():
    """Generate meetings for last week, today, and an in-progress meeting."""
    async with async_session_maker() as db:
        meeting_manager = MeetingManager(db)
        now = local_now()
        
        # Generate meetings for last week (7 days ago to today)
        last_week_start = now - timedelta(days=7)
        last_week_start = last_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Check existing meetings in this range
        result = await db.execute(
            select(Meeting).where(
                Meeting.start_time >= last_week_start,
                Meeting.start_time < tomorrow_start
            )
        )
        existing_meetings = result.scalars().all()
        
        print(f"Found {len(existing_meetings)} existing meetings in the date range")
        
        # Generate meetings for last week
        print("\nGenerating meetings for the past week...")
        past_meetings = await meeting_manager.generate_meetings_for_date_range(
            last_week_start, today_start
        )
        print(f"✅ Generated {past_meetings} meetings for the past week")
        
        # Generate meetings for today
        print("\nGenerating meetings for today...")
        today_meetings = await meeting_manager.generate_meetings()
        print(f"✅ Generated {today_meetings} meetings for today")
        
        # Always generate an in-progress meeting if one doesn't exist
        result = await db.execute(
            select(Meeting).where(Meeting.status == "in_progress")
        )
        in_progress_meetings = result.scalars().all()
        
        if len(in_progress_meetings) == 0:
            print("\nGenerating an in-progress meeting...")
            in_progress_meeting = await meeting_manager.generate_in_progress_meeting()
            if in_progress_meeting:
                print(f"✅ Generated in-progress meeting: {in_progress_meeting.title}")
            else:
                print("❌ Could not generate in-progress meeting (may need more employees)")
        else:
            print(f"\nℹ️  {len(in_progress_meetings)} in-progress meeting(s) already exist")
            for meeting in in_progress_meetings:
                print(f"   - {meeting.title} (ID: {meeting.id})")
        
        print("\n✅ Meeting generation complete!")
        print(f"   Total meetings: {len(existing_meetings) + past_meetings + today_meetings}")


if __name__ == "__main__":
    print("Generating meetings now...")
    asyncio.run(generate_meetings_now())

