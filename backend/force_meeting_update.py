"""Force update a meeting to test if the system works."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import async_session_maker
from business.meeting_manager import MeetingManager
from database.models import Meeting
from sqlalchemy import select

async def force_update():
    async with async_session_maker() as db:
        # Get the in-progress meeting
        result = await db.execute(
            select(Meeting).where(Meeting.status == 'in_progress')
        )
        meetings = result.scalars().all()
        
        if not meetings:
            print("No in-progress meetings found!")
            return
        
        meeting = meetings[0]
        print(f"Found meeting: {meeting.id} - {meeting.title}")
        print(f"Current live messages: {len((meeting.meeting_metadata or {}).get('live_messages', []))}")
        
        # Force update
        meeting_manager = MeetingManager(db)
        print("\nForcing meeting status update...")
        await meeting_manager.update_meeting_status()
        
        # Refresh and check
        await db.refresh(meeting)
        metadata = meeting.meeting_metadata or {}
        live_messages = metadata.get("live_messages", [])
        print(f"\nAfter update:")
        print(f"  Live messages: {len(live_messages) if isinstance(live_messages, list) else 0}")
        print(f"  Last update: {metadata.get('last_content_update', 'Never')}")
        
        if isinstance(live_messages, list) and len(live_messages) > 0:
            print(f"\nLatest messages:")
            for msg in live_messages[-3:]:
                print(f"  - {msg.get('sender_name', 'Unknown')}: {msg.get('message', '')[:60]}...")

if __name__ == "__main__":
    asyncio.run(force_update())





