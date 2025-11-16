import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import async_session_maker
from database.models import Meeting
from sqlalchemy import select
from datetime import datetime

async def check_meetings():
    async with async_session_maker() as db:
        # Check in-progress meetings
        result = await db.execute(
            select(Meeting).where(Meeting.status == 'in_progress')
        )
        in_progress = result.scalars().all()
        
        print(f"\nIn-progress meetings: {len(in_progress)}")
        for m in in_progress:
            print(f"  - ID {m.id}: {m.title}")
            print(f"    Start: {m.start_time}, End: {m.end_time}")
            print(f"    Attendees: {len(m.attendee_ids)}")
            metadata = m.meeting_metadata or {}
            live_messages = metadata.get("live_messages", [])
            print(f"    Live messages: {len(live_messages) if isinstance(live_messages, list) else 0}")
            print(f"    Last update: {metadata.get('last_content_update', 'Never')}")
            print()
        
        # Check scheduled meetings that should be in progress
        now = datetime.utcnow()
        result = await db.execute(
            select(Meeting).where(
                Meeting.status == 'scheduled',
                Meeting.start_time <= now,
                Meeting.end_time > now
            )
        )
        should_be_active = result.scalars().all()
        
        print(f"Scheduled meetings that should be active: {len(should_be_active)}")
        for m in should_be_active:
            print(f"  - ID {m.id}: {m.title} (started at {m.start_time})")
        
        # Test LLM
        print("\nTesting LLM connection...")
        try:
            from llm.ollama_client import OllamaClient
            client = OllamaClient()
            print(f"   Model: {client.model}")
            print(f"   URL: {client.base_url}")
            
            test_response = await client.generate_response("Say 'Hello' in one word")
            print(f"   Test response: {test_response[:50] if test_response else 'FAILED'}")
        except Exception as e:
            print(f"   ❌ LLM test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_meetings())

