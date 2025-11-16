"""
Meeting Manager - Handles meeting generation, scheduling, and live meeting transcripts.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Employee, Meeting
from datetime import datetime, timedelta
import random
import json
import httpx
from typing import List, Optional, Dict
from llm.ollama_client import OllamaClient


class MeetingManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = OllamaClient()
    
    async def generate_meetings(self) -> int:
        """Generate important meetings for the day with employees and managers."""
        # Get all active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) < 2:
            return 0
        
        now = datetime.utcnow()
        
        # Check if there are already meetings scheduled for today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.start_time >= today_start,
                Meeting.start_time < tomorrow_start
            )
        )
        existing_meetings = result.scalars().all()
        
        # If there are already 3+ meetings for today, don't generate more
        if len(existing_meetings) >= 3:
            return 0
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        meetings_created = 0
        
        # Generate 3-8 meetings throughout the day (but only if we don't have enough)
        target_meetings = random.randint(3, 8)
        num_meetings = max(0, target_meetings - len(existing_meetings))
        
        if num_meetings == 0:
            return 0
        
        # Meeting types and topics
        meeting_types = [
            ("Team Standup", "Daily team synchronization and progress updates"),
            ("Project Review", "Review project milestones and deliverables"),
            ("Strategy Session", "Strategic planning and decision-making"),
            ("One-on-One", "Manager-employee performance discussion"),
            ("Department Meeting", "Department-wide updates and coordination"),
            ("Client Presentation", "Present project progress to stakeholders"),
            ("Sprint Planning", "Plan upcoming sprint tasks and priorities"),
            ("Retrospective", "Review past sprint and identify improvements"),
            ("Budget Review", "Review financial performance and budget allocation"),
            ("Performance Review", "Quarterly performance evaluation"),
            ("All-Hands", "Company-wide updates and announcements"),
            ("Training Session", "Team training and skill development"),
        ]
        
        for i in range(num_meetings):
            # Schedule meetings throughout the day (9 AM to 5 PM)
            # If it's before 9 AM, start from 9 AM. If it's after 5 PM, schedule for tomorrow
            if now.hour < 9:
                day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
            elif now.hour >= 17:
                # Schedule for tomorrow at 9 AM
                day_start = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            else:
                # We're in the middle of the day, start from now or 9 AM (whichever is later)
                day_start = max(now, now.replace(hour=9, minute=0, second=0, microsecond=0))
            
            # End of business day is 5 PM
            day_end = day_start.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # If we're scheduling for today and it's already past 5 PM, schedule for tomorrow
            if day_start.hour >= 17:
                day_start = (day_start + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
                day_end = day_start.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # Random time between day_start and day_end (with room for meeting duration)
            available_hours = (day_end - day_start).total_seconds() / 3600
            hours_offset = random.uniform(0, max(0.5, available_hours - 1.5))  # Leave at least 1.5 hours for meeting
            start_time = day_start + timedelta(hours=hours_offset)
            duration = random.choice([30, 45, 60, 90])  # Meeting duration in minutes
            end_time = start_time + timedelta(minutes=duration)
            
            # Make sure end_time doesn't go past 5 PM
            if end_time > day_end:
                end_time = day_end
                start_time = end_time - timedelta(minutes=duration)
            
            # Select meeting type
            meeting_type, meeting_description = random.choice(meeting_types)
            
            # Select organizer (prefer managers/executives)
            managers = [e for e in all_employees if e.role in ["CEO", "Manager"]]
            if managers:
                organizer = random.choice(managers)
            else:
                organizer = random.choice(all_employees)
            
            # Select attendees (2-8 people, including organizer)
            num_attendees = random.randint(2, min(8, len(all_employees)))
            attendees = [organizer]
            available = [e for e in all_employees if e.id != organizer.id]
            random.shuffle(available)
            attendees.extend(available[:num_attendees - 1])
            attendee_ids = [e.id for e in attendees]
            
            # Generate meeting title
            title = f"{meeting_type}: {organizer.department or 'General'}"
            
            # Generate agenda and outline using LLM
            agenda, outline = await self._generate_meeting_agenda(
                meeting_type, meeting_description, organizer, attendees, business_context
            )
            
            # Ensure agenda and outline are strings (not lists/dicts)
            if isinstance(agenda, (list, dict)):
                agenda = json.dumps(agenda) if isinstance(agenda, dict) else "\n".join(str(item) for item in agenda)
            if isinstance(outline, (list, dict)):
                outline = json.dumps(outline) if isinstance(outline, dict) else "\n".join(str(item) for item in outline)
            
            # Create meeting
            meeting = Meeting(
                title=title,
                description=meeting_description,
                organizer_id=organizer.id,
                attendee_ids=attendee_ids,
                start_time=start_time,
                end_time=end_time,
                status="scheduled",
                agenda=str(agenda) if agenda else None,
                outline=str(outline) if outline else None,
                meeting_metadata={"live_messages": []}
            )
            
            self.db.add(meeting)
            meetings_created += 1
        
        await self.db.commit()
        return meetings_created
    
    async def generate_meetings_for_date_range(self, start_date: datetime, end_date: datetime) -> int:
        """Generate meetings for a specific date range (e.g., last week)."""
        # Get all active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) < 2:
            return 0
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        meetings_created = 0
        current_date = datetime(start_date.year, start_date.month, start_date.day, 9, 0)  # Start at 9 AM
        
        # Meeting types and topics
        meeting_types = [
            ("Team Standup", "Daily team synchronization and progress updates"),
            ("Project Review", "Review project milestones and deliverables"),
            ("Strategy Session", "Strategic planning and decision-making"),
            ("One-on-One", "Manager-employee performance discussion"),
            ("Department Meeting", "Department-wide updates and coordination"),
            ("Client Presentation", "Present project progress to stakeholders"),
            ("Sprint Planning", "Plan upcoming sprint tasks and priorities"),
            ("Retrospective", "Review past sprint and identify improvements"),
            ("Budget Review", "Review financial performance and budget allocation"),
            ("Performance Review", "Quarterly performance evaluation"),
            ("All-Hands", "Company-wide updates and announcements"),
            ("Training Session", "Team training and skill development"),
        ]
        
        # Generate meetings for each day in the range
        while current_date < end_date:
            # Generate 2-5 meetings per day
            num_meetings = random.randint(2, 5)
            
            for i in range(num_meetings):
                # Schedule meetings throughout the day (9 AM to 5 PM)
                hours_offset = random.uniform(0, 8)
                start_time = current_date + timedelta(hours=hours_offset)
                duration = random.choice([30, 45, 60, 90])  # Meeting duration in minutes
                end_time = start_time + timedelta(minutes=duration)
                
                # Skip if end time goes past end_date
                if end_time > end_date:
                    break
                
                # Select meeting type
                meeting_type, meeting_description = random.choice(meeting_types)
                
                # Select organizer (prefer managers/executives)
                managers = [e for e in all_employees if e.role in ["CEO", "Manager"]]
                if managers:
                    organizer = random.choice(managers)
                else:
                    organizer = random.choice(all_employees)
                
                # Select attendees (2-8 people, including organizer)
                num_attendees = random.randint(2, min(8, len(all_employees)))
                attendees = [organizer]
                available = [e for e in all_employees if e.id != organizer.id]
                random.shuffle(available)
                attendees.extend(available[:num_attendees - 1])
                attendee_ids = [e.id for e in attendees]
                
                # Generate meeting title
                title = f"{meeting_type}: {organizer.department or 'General'}"
                
                # Generate agenda and outline using LLM
                agenda, outline = await self._generate_meeting_agenda(
                    meeting_type, meeting_description, organizer, attendees, business_context
                )
                
                # Ensure agenda and outline are strings (not lists/dicts)
                if isinstance(agenda, (list, dict)):
                    agenda = json.dumps(agenda) if isinstance(agenda, dict) else "\n".join(str(item) for item in agenda)
                if isinstance(outline, (list, dict)):
                    outline = json.dumps(outline) if isinstance(outline, dict) else "\n".join(str(item) for item in outline)
                
                # Determine status based on time
                now = datetime.utcnow()
                if end_time < now:
                    status = "completed"
                    # Generate transcript for completed meetings
                    transcript = await self._generate_final_transcript_for_meeting(
                        title, meeting_description, organizer, attendees, start_time, end_time
                    )
                elif start_time <= now < end_time:
                    status = "in_progress"
                    transcript = None
                else:
                    status = "scheduled"
                    transcript = None
                
                # Create meeting
                meeting = Meeting(
                    title=title,
                    description=meeting_description,
                    organizer_id=organizer.id,
                    attendee_ids=attendee_ids,
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    agenda=str(agenda) if agenda else None,
                    outline=str(outline) if outline else None,
                    transcript=str(transcript) if transcript else None,
                    meeting_metadata={"live_messages": []}
                )
                
                self.db.add(meeting)
                meetings_created += 1
            
            # Move to next day
            current_date += timedelta(days=1)
            current_date = current_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        await self.db.commit()
        return meetings_created
    
    async def generate_in_progress_meeting(self) -> Optional[Meeting]:
        """Generate an in-progress meeting happening right now."""
        # Get all active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) < 2:
            return None
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        now = datetime.utcnow()
        
        # Meeting types
        meeting_types = [
            ("Team Standup", "Daily team synchronization and progress updates"),
            ("Project Review", "Review project milestones and deliverables"),
            ("Strategy Session", "Strategic planning and decision-making"),
            ("Department Meeting", "Department-wide updates and coordination"),
        ]
        
        meeting_type, meeting_description = random.choice(meeting_types)
        
        # Select organizer (prefer managers/executives)
        managers = [e for e in all_employees if e.role in ["CEO", "Manager"]]
        if managers:
            organizer = random.choice(managers)
        else:
            organizer = random.choice(all_employees)
        
        # Select attendees (3-6 people, including organizer)
        num_attendees = random.randint(3, min(6, len(all_employees)))
        attendees = [organizer]
        available = [e for e in all_employees if e.id != organizer.id]
        random.shuffle(available)
        attendees.extend(available[:num_attendees - 1])
        attendee_ids = [e.id for e in attendees]
        
        # Generate meeting title
        title = f"{meeting_type}: {organizer.department or 'General'}"
        
        # Start time was 15-30 minutes ago, end time is 15-45 minutes from now
        start_time = now - timedelta(minutes=random.randint(15, 30))
        duration = random.randint(30, 60)
        end_time = now + timedelta(minutes=random.randint(15, duration))
        
        # Generate agenda and outline using LLM
        agenda, outline = await self._generate_meeting_agenda(
            meeting_type, meeting_description, organizer, attendees, business_context
        )
        
        # Ensure agenda and outline are strings (not lists/dicts)
        if isinstance(agenda, (list, dict)):
            agenda = json.dumps(agenda) if isinstance(agenda, dict) else "\n".join(str(item) for item in agenda)
        if isinstance(outline, (list, dict)):
            outline = json.dumps(outline) if isinstance(outline, dict) else "\n".join(str(item) for item in outline)
        
        # Initialize live transcript
        live_transcript = f"Meeting started at {start_time.strftime('%H:%M')}\n"
        
        # Create meeting
        meeting = Meeting(
            title=title,
            description=meeting_description,
            organizer_id=organizer.id,
            attendee_ids=attendee_ids,
            start_time=start_time,
            end_time=end_time,
            status="in_progress",
            agenda=str(agenda) if agenda else None,
            outline=str(outline) if outline else None,
            live_transcript=live_transcript,
            meeting_metadata={"live_messages": []}  # No last_content_update so it generates immediately
        )
        
        self.db.add(meeting)
        await self.db.commit()
        
        # Generate initial live content
        await self._generate_live_meeting_content(meeting)
        await self.db.commit()
        
        return meeting
    
    async def _generate_final_transcript_for_meeting(
        self, title: str, description: str, organizer: Employee,
        attendees: List[Employee], start_time: datetime, end_time: datetime
    ) -> str:
        """Generate a final transcript for a completed meeting."""
        attendee_list = ", ".join([f"{e.name} ({e.title})" for e in attendees])
        
        prompt = f"""Generate a meeting transcript for a {title} meeting.

Meeting Description: {description}
Organizer: {organizer.name} ({organizer.title})
Attendees: {attendee_list}
Duration: {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}

Generate a realistic meeting transcript showing a conversation between the attendees. Include:
- Opening remarks
- Discussion of agenda items
- Questions and responses
- Action items and next steps
- Closing remarks

Format as a transcript with timestamps and speaker names. Make it 15-20 lines of dialogue.

Format:
[HH:MM] Speaker Name: Message
[HH:MM] Another Speaker: Response"""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get("response", "").strip()
                # Clean transcript to handle encoding issues
                try:
                    transcript = transcript.encode('utf-8', errors='ignore').decode('utf-8')
                except:
                    pass
                return transcript
        except Exception as e:
            print(f"Error generating final transcript: {e}")
        
        # Fallback
        return f"Meeting transcript for {title}\nAttendees: {attendee_list}\nAgenda items were discussed and action items were assigned."
    
    async def _generate_meeting_agenda(
        self, meeting_type: str, description: str, organizer: Employee,
        attendees: List[Employee], business_context: Dict
    ) -> tuple[str, str]:
        """Generate meeting agenda and outline using LLM."""
        attendee_names = ", ".join([f"{e.name} ({e.title})" for e in attendees])
        
        prompt = f"""Generate a meeting agenda and outline for a {meeting_type} meeting.

Meeting Description: {description}
Organizer: {organizer.name} ({organizer.title})
Attendees: {attendee_names}

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}
- Employees: {business_context.get('employee_count', 0)}

Generate:
1. A detailed agenda (3-5 bullet points) covering what will be discussed
2. A meeting outline (structured format with main topics and sub-topics)

Respond in JSON format:
{{
    "agenda": "bullet point 1\\nbullet point 2\\n...",
    "outline": "I. Main Topic 1\\n   A. Subtopic 1\\n   B. Subtopic 2\\nII. Main Topic 2\\n..."
}}"""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                
                try:
                    if response_text.strip().startswith("{"):
                        data = json.loads(response_text)
                    else:
                        import re
                        json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                        else:
                            raise ValueError("No JSON found")
                    
                    agenda = data.get("agenda", f"1. Review {meeting_type} objectives\n2. Discuss key topics\n3. Action items")
                    outline = data.get("outline", f"I. Introduction\nII. Main Discussion\nIII. Action Items")
                    return agenda, outline
                except:
                    pass
            
            # Fallback
            agenda = f"1. Review {meeting_type} objectives\n2. Discuss key topics\n3. Action items and next steps"
            outline = f"I. Introduction\nII. Main Discussion Points\nIII. Action Items and Follow-up"
            return agenda, outline
        except Exception as e:
            print(f"Error generating meeting agenda: {e}")
            agenda = f"1. Review {meeting_type} objectives\n2. Discuss key topics\n3. Action items"
            outline = f"I. Introduction\nII. Main Discussion\nIII. Action Items"
            return agenda, outline
    
    async def update_meeting_status(self):
        """Update meeting status based on current time (scheduled -> in_progress -> completed)."""
        now = datetime.utcnow()
        
        # Update meetings that should be in progress
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.status == "scheduled",
                Meeting.start_time <= now,
                Meeting.end_time > now
            )
        )
        in_progress_meetings = result.scalars().all()
        
        print(f"🔍 Checking for meetings to start: found {len(in_progress_meetings)} meeting(s) that should be in progress")
        
        for meeting in in_progress_meetings:
            print(f"🔄 Starting meeting {meeting.id}: {meeting.title} (scheduled for {meeting.start_time}, current time: {now})")
            # CRITICAL: Explicitly set status and ensure it's tracked
            meeting.status = "in_progress"
            # Force SQLAlchemy to track this change
            from sqlalchemy.orm.attributes import flag_modified
            # Status is a regular column, not JSON, so we don't need flag_modified for it
            # But we do need to ensure the object is in the session
            self.db.add(meeting)  # Ensure it's tracked
            # Initialize live transcript if not exists
            if not meeting.live_transcript:
                meeting.live_transcript = f"Meeting started at {now.strftime('%H:%M')}\n"
            # Initialize metadata if needed
            if not meeting.meeting_metadata:
                meeting.meeting_metadata = {"live_messages": []}
            # Generate initial live messages immediately
            try:
                await self._generate_live_meeting_content(meeting)
                meeting.meeting_metadata["last_content_update"] = now.isoformat()
                print(f"✅ Initialized and generated content for new in-progress meeting {meeting.id}: {meeting.title}")
            except Exception as e:
                print(f"❌ Error generating initial content for meeting {meeting.id}: {e}")
                import traceback
                traceback.print_exc()
        
        # Commit status changes BEFORE continuing with other updates
        if in_progress_meetings:
            # CRITICAL: Refresh each meeting to ensure changes are tracked
            for meeting in in_progress_meetings:
                await self.db.refresh(meeting)
            await self.db.commit()
            # Refresh again after commit to verify
            for meeting in in_progress_meetings:
                await self.db.refresh(meeting)
            print(f"✅ Committed status changes for {len(in_progress_meetings)} meeting(s) starting")
            for meeting in in_progress_meetings:
                print(f"   ✅ Meeting {meeting.id} status is now: {meeting.status}")
        
        # Update live content for in-progress meetings (generate new messages periodically)
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.status == "in_progress",
                Meeting.end_time > now
            )
        )
        active_meetings = result.scalars().all()
        
        if len(active_meetings) > 0:
            print(f"Found {len(active_meetings)} active meeting(s) to update")
        
        for meeting in active_meetings:
            # Refresh meeting to get latest state
            await self.db.refresh(meeting)
            
            # Check if we should generate new content (every 5 seconds for active meetings)
            metadata = meeting.meeting_metadata or {}
            if not isinstance(metadata, dict):
                metadata = {}
                meeting.meeting_metadata = metadata
            last_update = metadata.get("last_content_update")
            should_update = False
            
            # Check if last_update is None, empty string, or "Never"
            if not last_update or last_update == "Never":
                # No previous update - generate immediately
                should_update = True
                print(f"🔄 Meeting {meeting.id} ({meeting.title}) has no previous update - generating content immediately")
            else:
                try:
                    if isinstance(last_update, str):
                        last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    else:
                        last_update_time = last_update
                    
                    # Handle timezone-aware datetime
                    if last_update_time.tzinfo:
                        last_update_time = last_update_time.replace(tzinfo=None)
                    
                    time_since_update = (now - last_update_time).total_seconds()
                    # Generate new content every 10-15 seconds for active meetings (slower pace, one at a time)
                    if time_since_update >= 10:
                        should_update = True
                        print(f"🔄 Meeting {meeting.id} ({meeting.title}): {time_since_update:.1f}s since last update - generating new content")
                    else:
                        print(f"⏸️ Meeting {meeting.id} ({meeting.title}): {time_since_update:.1f}s since last update - waiting (need 10s)")
                except Exception as e:
                    # If parsing fails, update anyway
                    print(f"⚠️ Error parsing last_update for meeting {meeting.id}: {e}")
                    should_update = True
            
            if should_update:
                try:
                    # Refresh meeting to get latest state
                    await self.db.refresh(meeting)
                    # Update metadata to ensure it's a dict
                    if not meeting.meeting_metadata:
                        meeting.meeting_metadata = {}
                    metadata = meeting.meeting_metadata
                    if not isinstance(metadata, dict):
                        metadata = {}
                        meeting.meeting_metadata = metadata
                    
                    # Update last_content_update timestamp in metadata BEFORE generating
                    metadata["last_content_update"] = now.isoformat()
                    meeting.meeting_metadata = metadata
                    # Commit the metadata update first
                    await self.db.commit()
                    
                    # Now generate content (which will also commit and update last_content_update)
                    await self._generate_live_meeting_content(meeting)
                    
                    # Refresh again to get the updated metadata
                    await self.db.refresh(meeting)
                    
                    # Double-check that last_content_update is set
                    final_metadata = meeting.meeting_metadata or {}
                    if "last_content_update" not in final_metadata:
                        final_metadata["last_content_update"] = datetime.utcnow().isoformat()
                        meeting.meeting_metadata = final_metadata
                        await self.db.commit()
                    
                    print(f"✅ Generated live content for meeting {meeting.id}: {meeting.title}")
                except Exception as e:
                    print(f"❌ Error generating live content for meeting {meeting.id}: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Update meetings that should be completed
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.status == "in_progress",
                Meeting.end_time <= now
            )
        )
        completed_meetings = result.scalars().all()
        
        for meeting in completed_meetings:
            # Refresh to get latest state
            await self.db.refresh(meeting)
            
            # Generate closing sequence before marking as completed (only if not already generated)
            metadata = meeting.meeting_metadata or {}
            if not isinstance(metadata, dict):
                metadata = {}
            if not metadata.get("closing_generated", False):
                await self._generate_meeting_closing(meeting)
                await self.db.refresh(meeting)
            
            meeting.status = "completed"
            
            # CRITICAL: Ensure transcript and live_transcript are synchronized
            # Sync live_transcript from live_messages if needed
            if meeting.meeting_metadata:
                live_messages = meeting.meeting_metadata.get("live_messages", [])
                if live_messages and isinstance(live_messages, list):
                    transcript_lines = []
                    for msg in live_messages:
                        timestamp = msg.get("timestamp", "")
                        try:
                            if isinstance(timestamp, str):
                                msg_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                msg_time = timestamp
                            if msg_time.tzinfo:
                                msg_time = msg_time.replace(tzinfo=None)
                            time_str = msg_time.strftime('%H:%M:%S')
                        except:
                            time_str = datetime.utcnow().strftime('%H:%M:%S')
                        sender_name = msg.get("sender_name", "Unknown")
                        message_text = msg.get("message", "")
                        transcript_lines.append(f"[{time_str}] {sender_name}: {message_text}")
                    meeting.live_transcript = "\n".join(transcript_lines) + "\n"
            
            # Generate final transcript - use live_transcript as the source of truth
            if meeting.live_transcript:
                meeting.transcript = meeting.live_transcript
            elif not meeting.transcript:
                meeting.transcript = await self._generate_final_transcript(meeting)
        
        await self.db.commit()
    
    async def _generate_meeting_closing(self, meeting: Meeting):
        """Generate closing sequence: organizer summary, thank you, and attendee goodbyes."""
        print(f"🎬 Generating closing sequence for meeting {meeting.id}: {meeting.title}")
        
        # Get attendees
        result = await self.db.execute(
            select(Employee).where(Employee.id.in_(meeting.attendee_ids))
        )
        attendees = result.scalars().all()
        
        if len(attendees) < 2:
            return
        
        # Get organizer
        organizer = next((e for e in attendees if e.id == meeting.organizer_id), attendees[0])
        other_attendees = [e for e in attendees if e.id != organizer.id]
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        # Get existing live messages for context
        metadata = meeting.meeting_metadata or {}
        if not isinstance(metadata, dict):
            metadata = {}
        live_messages = metadata.get("live_messages", [])
        if not isinstance(live_messages, list):
            live_messages = []
        
        # Get recent conversation context
        recent_messages = live_messages[-10:] if len(live_messages) > 10 else live_messages
        conversation_summary = ""
        if recent_messages:
            conversation_summary = "\n\nRecent discussion points:\n"
            for msg in recent_messages[-5:]:
                conversation_summary += f"- {msg.get('sender_name', 'Someone')}: {msg.get('message', '')}\n"
        
        attendee_list = ", ".join([f"{e.name} ({e.title})" for e in attendees])
        
        # 1. Generate organizer's meeting summary
        summary_prompt = f"""You are {organizer.name}, {organizer.title}, the organizer of a {meeting.title} meeting.

Meeting Agenda:
{meeting.agenda or 'General discussion'}

Attendees: {attendee_list}
{conversation_summary}

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}

The meeting is ending. Provide a brief 2-3 sentence summary of what was discussed and the key takeaways. Be professional and concise.

Write only the summary, nothing else."""

        organizer_summary = None
        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": summary_prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(30.0, connect=10.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                organizer_summary = result.get("response", "").strip()
                organizer_summary = organizer_summary.strip('"').strip("'").strip()
                if organizer_summary.startswith("```"):
                    import re
                    organizer_summary = re.sub(r'```[^\n]*\n', '', organizer_summary)
                    organizer_summary = re.sub(r'\n```', '', organizer_summary)
                    organizer_summary = organizer_summary.strip()
        except Exception as e:
            print(f"❌ Error generating organizer summary: {e}")
        
        if not organizer_summary or len(organizer_summary) < 20:
            organizer_summary = f"Thank you all for a productive discussion. We've covered the key agenda items and have clear action items moving forward."
        
        # 2. Generate organizer's thank you and goodbye
        goodbye_prompt = f"""You are {organizer.name}, {organizer.title}, the organizer of a {meeting.title} meeting.

Attendees: {attendee_list}

The meeting is ending. Thank all the attendees for their participation and say goodbye in a professional, warm manner. Keep it brief (1-2 sentences).

Write only the thank you message, nothing else."""

        organizer_goodbye = None
        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": goodbye_prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(30.0, connect=10.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                organizer_goodbye = result.get("response", "").strip()
                organizer_goodbye = organizer_goodbye.strip('"').strip("'").strip()
                if organizer_goodbye.startswith("```"):
                    import re
                    organizer_goodbye = re.sub(r'```[^\n]*\n', '', organizer_goodbye)
                    organizer_goodbye = re.sub(r'\n```', '', organizer_goodbye)
                    organizer_goodbye = organizer_goodbye.strip()
        except Exception as e:
            print(f"❌ Error generating organizer goodbye: {e}")
        
        if not organizer_goodbye or len(organizer_goodbye) < 10:
            organizer_goodbye = f"Thank you all for your time and valuable input today. Have a great rest of your day!"
        
        # Add organizer's summary and goodbye to transcript
        now = datetime.utcnow()
        timestamp = now.strftime('%H:%M:%S')
        
        # Add summary
        if meeting.live_transcript:
            meeting.live_transcript += f"\n[{timestamp}] {organizer.name}: {organizer_summary}\n"
        else:
            meeting.live_transcript = f"[{timestamp}] {organizer.name}: {organizer_summary}\n"
        
        # Add goodbye
        timestamp_goodbye = (now + timedelta(seconds=2)).strftime('%H:%M:%S')
        meeting.live_transcript += f"\n[{timestamp_goodbye}] {organizer.name}: {organizer_goodbye}\n"
        
        # Add to live_messages
        summary_message = {
            "sender_id": organizer.id,
            "sender_name": organizer.name,
            "sender_title": organizer.title,
            "recipient_id": None,
            "recipient_name": None,
            "message": organizer_summary,
            "timestamp": now.isoformat()
        }
        
        goodbye_message = {
            "sender_id": organizer.id,
            "sender_name": organizer.name,
            "sender_title": organizer.title,
            "recipient_id": None,
            "recipient_name": None,
            "message": organizer_goodbye,
            "timestamp": (now + timedelta(seconds=2)).isoformat()
        }
        
        live_messages.append(summary_message)
        live_messages.append(goodbye_message)
        
        # Update metadata with closing messages
        metadata["live_messages"] = live_messages
        metadata["closing_generated"] = True
        meeting.meeting_metadata = metadata
        
        # 3. Generate goodbye messages from all other attendees
        for attendee in other_attendees:
            attendee_goodbye_prompt = f"""You are {attendee.name}, {attendee.title} in a {meeting.title} meeting.

The meeting organizer {organizer.name} has just thanked everyone and said goodbye. The meeting is ending. Say a brief, professional goodbye (1 sentence).

Write only the goodbye message, nothing else."""

            attendee_goodbye = None
            try:
                client = await self.llm_client._get_client()
                response = await client.post(
                    f"{self.llm_client.base_url}/api/generate",
                    json={
                        "model": self.llm_client.model,
                        "prompt": attendee_goodbye_prompt,
                        "stream": False
                    },
                    timeout=httpx.Timeout(30.0, connect=10.0)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    attendee_goodbye = result.get("response", "").strip()
                    attendee_goodbye = attendee_goodbye.strip('"').strip("'").strip()
                    if attendee_goodbye.startswith("```"):
                        import re
                        attendee_goodbye = re.sub(r'```[^\n]*\n', '', attendee_goodbye)
                        attendee_goodbye = re.sub(r'\n```', '', attendee_goodbye)
                        attendee_goodbye = attendee_goodbye.strip()
            except Exception as e:
                print(f"❌ Error generating goodbye for {attendee.name}: {e}")
            
            if not attendee_goodbye or len(attendee_goodbye) < 5:
                attendee_goodbye = "Thanks everyone, see you later!"
            
            # Add to transcript
            attendee_timestamp = (now + timedelta(seconds=4 + (other_attendees.index(attendee) * 2))).strftime('%H:%M:%S')
            meeting.live_transcript += f"\n[{attendee_timestamp}] {attendee.name}: {attendee_goodbye}\n"
            
            # Add to live_messages
            attendee_message = {
                "sender_id": attendee.id,
                "sender_name": attendee.name,
                "sender_title": attendee.title,
                "recipient_id": None,
                "recipient_name": None,
                "message": attendee_goodbye,
                "timestamp": (now + timedelta(seconds=4 + (other_attendees.index(attendee) * 2))).isoformat()
            }
            live_messages.append(attendee_message)
        
        # Update metadata with closing messages
        metadata["live_messages"] = live_messages
        metadata["closing_generated"] = True
        meeting.meeting_metadata = metadata
        
        # CRITICAL: Force SQLAlchemy to recognize the metadata change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(meeting, "meeting_metadata")
        flag_modified(meeting, "live_transcript")
        
        # Commit the closing sequence
        await self.db.commit()
        print(f"✅ Generated closing sequence for meeting {meeting.id} with {len(live_messages)} total messages")
    
    async def _generate_live_meeting_content(self, meeting: Meeting):
        """Generate live meeting messages and update transcript."""
        print(f"🔄 Generating live content for meeting {meeting.id}: {meeting.title}")
        print(f"   Using LLM model: {self.llm_client.model} at {self.llm_client.base_url}")
        
        # Refresh meeting to get latest state
        await self.db.refresh(meeting)
        
        # Get attendees
        result = await self.db.execute(
            select(Employee).where(Employee.id.in_(meeting.attendee_ids))
        )
        attendees = result.scalars().all()
        
        if len(attendees) < 2:
            print(f"⚠️ Meeting {meeting.id} has less than 2 attendees, skipping content generation")
            return
        
        print(f"✅ Meeting {meeting.id} has {len(attendees)} attendees, proceeding with content generation")
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        # Ensure metadata is properly initialized (preserve existing metadata including last_content_update)
        if not meeting.meeting_metadata:
            meeting.meeting_metadata = {}
        metadata = meeting.meeting_metadata
        if not isinstance(metadata, dict):
            metadata = {}
            meeting.meeting_metadata = metadata
        
        # Get existing messages - ensure it's a list
        # Get the existing messages from metadata BEFORE we start generating new ones
        existing_messages_from_db = metadata.get("live_messages", [])
        if not isinstance(existing_messages_from_db, list):
            existing_messages_from_db = []
        
        # Start with existing messages
        live_messages = list(existing_messages_from_db) if isinstance(existing_messages_from_db, list) else []
        print(f"   📝 Starting with {len(live_messages)} existing messages from database")
        
        # Generate ONLY 1 message at a time - no one talks over each other
        # One person speaks, then wait for the next update cycle
        num_messages = 1
        print(f"   Generating 1 new message for meeting {meeting.id} (one at a time, no overlapping)")
        
        # Track who should speak next to ensure proper turn-taking
        # Get the last message to see who was speaking and to whom
        last_message = live_messages[-1] if live_messages else None
        next_speaker_id = None
        
        # AGGRESSIVE: Track ALL recent speakers (last 8 messages) to force rotation
        recent_speakers = []
        if len(live_messages) >= 2:
            recent_speakers = [msg.get("sender_id") for msg in live_messages[-8:]]
        
        # Track the last 2-3 speakers to ALWAYS exclude them from next selection
        very_recent_speakers = []
        if len(live_messages) >= 2:
            very_recent_speakers = [msg.get("sender_id") for msg in live_messages[-3:]]
        
        if last_message:
            # CRITICAL: Check for loops FIRST before allowing response
            # Detect if the same two people have been talking back and forth
            last_4_messages = live_messages[-4:] if len(live_messages) >= 4 else live_messages
            is_loop = False
            loop_pair = None
            
            # AGGRESSIVE: Check last 2-3 messages for loops (catch them early)
            if len(last_4_messages) >= 2:
                # Check if we have A->B, B->A pattern (same two people talking back and forth)
                last_2 = last_4_messages[-2:]
                speakers = [msg.get("sender_id") for msg in last_2]
                recipients = [msg.get("recipient_id") for msg in last_2]
                
                # Check if it's the same two people alternating (A->B, B->A)
                if len(speakers) == 2 and len(recipients) == 2:
                    # Check if speaker[0] -> recipient[0] and speaker[1] -> recipient[1]
                    # AND if they're talking to each other (speaker[0] == recipient[1] and speaker[1] == recipient[0])
                    if (speakers[0] == recipients[1] and speakers[1] == recipients[0]):
                        is_loop = True
                        loop_pair = tuple(sorted(speakers))
                        print(f"   ⚠️⚠️⚠️ LOOP DETECTED: Same two people ({last_message.get('sender_name')} and {last_message.get('recipient_name')}) talking back and forth - BREAKING IT NOW")
            
            # Also check for 3-message loops (A->B, B->A, A->B)
            if not is_loop and len(last_4_messages) >= 3:
                last_3 = last_4_messages[-3:]
                speakers = [msg.get("sender_id") for msg in last_3]
                recipients = [msg.get("recipient_id") for msg in last_3]
                
                # Check if it's the same two people alternating
                unique_speakers = set(speakers)
                if len(unique_speakers) == 2:
                    # Same two people - check if they're talking to each other
                    pair = tuple(sorted(unique_speakers))
                    if speakers[-1] == recipients[-2] and speakers[-2] == recipients[-1]:
                        is_loop = True
                        loop_pair = pair
                        print(f"   ⚠️⚠️⚠️ LOOP DETECTED (3-message): Same two people ({last_message.get('sender_name')} and {last_message.get('recipient_name')}) talking back and forth - BREAKING IT NOW")
            
            # CRITICAL: If someone was just addressed, they MUST respond next
            # BUT: If we're in a loop, BREAK IT by picking someone else
            if last_message.get("recipient_id"):
                if is_loop:
                    # BREAK THE LOOP - exclude both people in the loop + last 4 speakers
                    excluded = set(loop_pair) if loop_pair else {last_message.get("sender_id"), last_message.get("recipient_id")}
                    if len(live_messages) >= 4:
                        excluded.update([msg.get("sender_id") for msg in live_messages[-4:]])
                    available = [a for a in attendees if a.id not in excluded]
                    if available:
                        next_speaker_id = random.choice(available).id
                        print(f"   ✅✅✅ LOOP BROKEN: Selecting {next((a.name for a in attendees if a.id == next_speaker_id), 'Someone')} instead (forced rotation, breaking loop)")
                    else:
                        # Can't break - at least exclude the two in the loop
                        available = [a for a in attendees if a.id not in loop_pair]
                        if available:
                            next_speaker_id = random.choice(available).id
                            print(f"   ✅ LOOP BROKEN: Selecting {next((a.name for a in attendees if a.id == next_speaker_id), 'Someone')} (minimal exclusion)")
                        else:
                            next_speaker_id = last_message.get("recipient_id")
                            print(f"   ⚠️ Cannot break loop - only 2 attendees")
                else:
                    next_speaker_id = last_message.get("recipient_id")
                    print(f"   Turn-taking: {last_message.get('recipient_name', 'Someone')} was addressed, they will respond next")
            else:
                # If no recipient in last message, pick someone else to continue
                # AGGRESSIVE: Exclude the last 2-3 speakers completely
                last_sender_id = last_message.get("sender_id")
                available = [a for a in attendees if a.id != last_sender_id and a.id not in very_recent_speakers]
                
                if not available:
                    # If we've excluded everyone, just exclude the last speaker
                    available = [a for a in attendees if a.id != last_sender_id]
                
                # Prioritize attendees who haven't spoken recently
                less_recent_speakers = [a for a in available if a.id not in recent_speakers]
                if less_recent_speakers:
                    next_speaker_id = random.choice(less_recent_speakers).id
                    print(f"   Turn-taking: Selecting {next((a.name for a in less_recent_speakers if a.id == next_speaker_id), 'Someone')} (hasn't spoken recently)")
                elif available:
                    # If everyone has spoken recently, just pick someone else
                    next_speaker_id = random.choice(available).id
                    print(f"   Turn-taking: All attendees have spoken recently, selecting random attendee")
                else:
                    # Fallback
                    next_speaker_id = random.choice(attendees).id
        
        messages_generated = 0
        for message_index in range(num_messages):
            # Get the most recent message (updated after each iteration)
            current_last_message = live_messages[-1] if live_messages else None
            
            # Determine who should speak next (only one person at a time)
            if next_speaker_id:
                # The person who should speak next
                sender = next((a for a in attendees if a.id == next_speaker_id), None)
                if not sender:
                    # Fallback if speaker not found
                    sender = random.choice(attendees)
                
                # Check if this person is responding to being addressed
                is_responding = False
                if current_last_message and current_last_message.get("recipient_id") == sender.id:
                    is_responding = True
                    # They should respond to the person who addressed them
                    recipient = next((a for a in attendees if a.id == current_last_message.get("sender_id")), None)
                    if not recipient:
                        # Fallback if recipient not found
                        available_recipients = [a for a in attendees if a.id != sender.id]
                        if not available_recipients:
                            continue
                        recipient = random.choice(available_recipients)
                    
                    # CRITICAL: After responding, we MUST break the loop AGGRESSIVELY
                    # NEVER allow the same two people to continue talking
                    # ALWAYS exclude: the two who just spoke + the last 6-8 speakers (force full rotation)
                    excluded_ids = {sender.id, recipient.id}
                    
                    # Track last 8 messages to see who's been talking - EXCLUDE THEM ALL
                    last_8_speakers = []
                    if len(live_messages) >= 2:
                        last_8_speakers = [msg.get("sender_id") for msg in live_messages[-8:]]
                    excluded_ids.update(last_8_speakers)  # Exclude everyone who spoke in last 8 messages
                    
                    available_next = [a for a in attendees if a.id not in excluded_ids]
                    
                    if available_next:
                        # Perfect - we have someone who hasn't spoken in the last 8 messages
                        next_speaker_id = random.choice(available_next).id
                        print(f"   ✅✅✅ BREAKING LOOP: After response, selecting {next((a.name for a in available_next if a.id == next_speaker_id), 'Someone')} (hasn't spoken in last 8 messages - FORCED ROTATION)")
                    else:
                        # If we've excluded everyone, at least exclude the two who just spoke + last 4
                        minimal_exclude = {sender.id, recipient.id}
                        if len(live_messages) >= 4:
                            minimal_exclude.update([msg.get("sender_id") for msg in live_messages[-4:]])
                        available_next = [a for a in attendees if a.id not in minimal_exclude]
                        if available_next:
                            next_speaker_id = random.choice(available_next).id
                            print(f"   ✅ BREAKING LOOP: After response, selecting {next((a.name for a in available_next if a.id == next_speaker_id), 'Someone')} (minimal exclusion - last 4)")
                        else:
                            # Last resort: exclude just the two who just spoke
                            available_next = [a for a in attendees if a.id not in {sender.id, recipient.id}]
                            if available_next:
                                next_speaker_id = random.choice(available_next).id
                                print(f"   ✅ BREAKING LOOP: After response, selecting {next((a.name for a in available_next if a.id == next_speaker_id), 'Someone')} (only excluding the two who just spoke)")
                            else:
                                # Only two people in meeting - can't break loop
                                print(f"   ⚠️ Only 2 attendees, cannot break loop")
                                next_speaker_id = None  # Don't set it, let it be chosen randomly
                else:
                    # Not responding - sender addresses someone else
                    available_recipients = [a for a in attendees if a.id != sender.id]
                    if not available_recipients:
                        continue  # Skip if no other attendees
                    
                    # CRITICAL: Avoid creating loops by checking recent conversation pairs AGGRESSIVELY
                    # Track recent sender-recipient pairs (last 8 messages)
                    recent_pairs = set()
                    if len(live_messages) >= 2:
                        for msg in live_messages[-8:]:  # Check last 8 messages
                            s_id = msg.get("sender_id")
                            r_id = msg.get("recipient_id")
                            if s_id and r_id:
                                # Add both directions to avoid A->B then B->A loops
                                recent_pairs.add((s_id, r_id))
                                recent_pairs.add((r_id, s_id))
                    
                    # Get recent recipients to avoid same pairs
                    recent_recipients = []
                    if len(live_messages) >= 2:
                        recent_recipients = [msg.get("recipient_id") for msg in live_messages[-4:]]
                    
                    # AGGRESSIVE: Exclude anyone who has spoken in the last 6 messages
                    excluded_recipients = set(recent_speakers)
                    excluded_recipients.update(recent_recipients)
                    
                    # First, try to find recipients who:
                    # 1. Haven't been in a conversation pair with sender recently (last 8 messages)
                    # 2. Haven't been addressed recently (last 4 messages)
                    # 3. Haven't spoken recently (last 8 messages)
                    good_recipients = []
                    for recipient in available_recipients:
                        pair = (sender.id, recipient.id)
                        if (pair not in recent_pairs and 
                            recipient.id not in excluded_recipients):
                            good_recipients.append(recipient)
                    
                    if good_recipients:
                        recipient = random.choice(good_recipients)
                        print(f"   ✅ NO LOOP: Addressing {recipient.name} (no recent pair, hasn't been addressed/spoken recently)")
                    else:
                        # Fallback: prioritize those who haven't been addressed recently
                        less_recent_recipients = [a for a in available_recipients if a.id not in recent_recipients]
                        if less_recent_recipients:
                            recipient = random.choice(less_recent_recipients)
                            print(f"   Turn-taking: Addressing {recipient.name} (hasn't been addressed recently)")
                        else:
                            # Last resort: pick randomly but avoid immediate loop
                            non_loop_recipients = [a for a in available_recipients 
                                                  if (sender.id, a.id) not in recent_pairs]
                            if non_loop_recipients:
                                recipient = random.choice(non_loop_recipients)
                                print(f"   Turn-taking: Addressing {recipient.name} (avoiding immediate loop)")
                            else:
                                recipient = random.choice(available_recipients)
                                print(f"   ⚠️ Addressing {recipient.name} (random, all pairs used - may create loop)")
                    
                    # Next speaker will be the recipient (they should respond)
                    next_speaker_id = recipient.id
            else:
                # No previous context, start with random
                sender = random.choice(attendees)
                available_recipients = [a for a in attendees if a.id != sender.id]
                if not available_recipients:
                    continue
                recipient = random.choice(available_recipients)
                # Next speaker will be the recipient
                next_speaker_id = recipient.id
            
            # Generate message using LLM
            personality_str = ", ".join(sender.personality_traits or ["professional"])
            recipient_personality = ", ".join(recipient.personality_traits or ["professional"])
            
            attendee_list = ", ".join([f"{e.name} ({e.title})" for e in attendees])
            
            # Get recent conversation context for better continuity
            recent_messages = live_messages[-5:] if len(live_messages) > 5 else live_messages
            conversation_context = ""
            if recent_messages:
                conversation_context = "\n\nRecent conversation (in order):\n"
                for msg in recent_messages[-3:]:
                    speaker = msg.get('sender_name', 'Someone')
                    msg_text = msg.get('message', '')
                    conversation_context += f"- {speaker}: {msg_text}\n"
            
            # Check if this is a response to being addressed (use current_last_message from loop)
            is_response = False
            last_question = None
            last_speaker_name = None
            if current_last_message and current_last_message.get("recipient_id") == sender.id:
                is_response = True
                last_speaker_name = current_last_message.get("sender_name", "Someone")
                last_question = current_last_message.get("message", "")
                conversation_context += f"\nCRITICAL: {last_speaker_name} just addressed you directly with: \"{last_question}\"\nYou MUST respond to this specific question or comment. Answer it directly and completely.\n"
            
            # Determine the prompt based on whether this is a response or new statement
            if is_response and last_question:
                prompt = f"""You are {sender.name}, {sender.title} in a {meeting.title} meeting.

Meeting Agenda:
{meeting.agenda}
{conversation_context}
Your personality traits: {personality_str}
Your role: {sender.role}
Attendees in the meeting: {attendee_list}

CRITICAL CONTEXT:
{last_speaker_name} just asked you directly: "{last_question}"

You MUST provide a proper, direct response to this specific question or comment. Your response should:
1. Directly answer what {last_speaker_name} asked or address what they said
2. Be relevant to the meeting agenda and your role
3. Address {last_speaker_name} by name (e.g., "{last_speaker_name}, ..." or "Thanks {last_speaker_name}, ...")
4. Be clear, concise, and complete (1-2 sentences)
5. Show that you understood their question/comment

Do NOT:
- Ignore what they asked
- Give a generic response
- Change the topic
- Ask a new question without answering theirs first

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}

Write only your direct response to {last_speaker_name}'s question, nothing else."""
            else:
                prompt = f"""You are {sender.name}, {sender.title} in a {meeting.title} meeting.

Meeting Agenda:
{meeting.agenda}
{conversation_context}
Your personality traits: {personality_str}
Your role: {sender.role}
Attendees in the meeting: {attendee_list}

You are speaking directly to {recipient.name} ({recipient.title}) in this meeting. You MUST address them by name in your message (e.g., "{recipient.name}, ..." or "Hey {recipient.name}, ...").

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}

Write a brief, natural comment or question (1-2 sentences) that {sender.name} would say in this meeting to {recipient.name}. Make it relevant to the meeting agenda and appropriate for the meeting context. Reference the recent conversation if relevant. IMPORTANT: Include {recipient.name}'s name in your message.

Write only the message, nothing else."""

            message_text = None
            try:
                client = await self.llm_client._get_client()
                response = await client.post(
                    f"{self.llm_client.base_url}/api/generate",
                    json={
                        "model": self.llm_client.model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=httpx.Timeout(30.0, connect=10.0)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_text = result.get("response", "").strip()
                    message_text = message_text.strip('"').strip("'").strip()
                    
                    # Remove markdown code blocks if present
                    if message_text.startswith("```"):
                        import re
                        message_text = re.sub(r'```[^\n]*\n', '', message_text)
                        message_text = re.sub(r'\n```', '', message_text)
                        message_text = message_text.strip()
                    
                    if not message_text or len(message_text) < 10:
                        message_text = None
                else:
                    print(f"LLM returned status {response.status_code} for meeting {meeting.id}")
            except httpx.TimeoutException as e:
                print(f"LLM timeout for meeting {meeting.id}: {e}")
                message_text = None
            except httpx.ConnectError as e:
                print(f"LLM connection error for meeting {meeting.id}: {e}")
                print(f"   Is Ollama running at {self.llm_client.base_url}?")
                message_text = None
            except Exception as e:
                print(f"Error calling LLM for meeting {meeting.id}: {e}")
                print(f"   Model: {self.llm_client.model}, URL: {self.llm_client.base_url}")
                import traceback
                traceback.print_exc()
                message_text = None
            
            # Fallback if LLM failed or returned empty
            if not message_text:
                # Generate contextual fallback based on meeting type
                fallbacks = [
                    f"{recipient.name}, what are your thoughts on this?",
                    f"{recipient.name}, I'd like to get your input on this.",
                    f"{recipient.name}, how do you see us moving forward?",
                    f"{recipient.name}, can you share your perspective?",
                ]
                message_text = random.choice(fallbacks)
                print(f"   Using fallback message for meeting {meeting.id} (LLM failed or returned empty)")
            
            # Add message to live messages
            messages_generated += 1
            now_iso = datetime.utcnow().isoformat()
            message_entry = {
                "sender_id": sender.id,
                "sender_name": sender.name,
                "sender_title": sender.title,
                "recipient_id": recipient.id,
                "recipient_name": recipient.name,
                "message": message_text,
                "timestamp": now_iso
            }
            live_messages.append(message_entry)
            print(f"   Added message {messages_generated}/{num_messages}: {sender.name} -> {recipient.name}: {message_text[:50]}...")
            
            # Track current speaker in metadata (for visual indicators)
            # The sender is currently speaking, recipient will speak next
            metadata["current_speaker"] = {
                "id": sender.id,
                "name": sender.name,
                "timestamp": now_iso
            }
            # Store who should speak next for proper turn-taking
            metadata["next_speaker_id"] = recipient.id
            
            # Note: We'll rebuild the live_transcript from live_messages at the end
            # This ensures they stay in sync
        
        # Update metadata - ensure live_messages is always a list
        # Use the metadata we already have (don't refresh - we've been building live_messages in it)
        # The live_messages list already contains existing + new messages
        print(f"   📊 Final message count: {len(live_messages)} total messages (started with {len(existing_messages_from_db)}, added {len(live_messages) - len(existing_messages_from_db)} new)")
        
        # Refresh meeting one more time to ensure we have latest state
        await self.db.refresh(meeting)
        
        # Get fresh metadata (in case it changed)
        if not meeting.meeting_metadata:
            meeting.meeting_metadata = {}
        metadata = meeting.meeting_metadata
        if not isinstance(metadata, dict):
            metadata = {}
            meeting.meeting_metadata = metadata
        
        # Update the metadata with the complete list
        metadata["live_messages"] = live_messages
        # Always update last_content_update to current time when we generate content
        now_iso = datetime.utcnow().isoformat()
        metadata["last_content_update"] = now_iso
        print(f"   ⏰ Set last_content_update to: {now_iso}")
        
        # CRITICAL: Ensure live_transcript and transcript are synchronized
        # The live_transcript should always match what's in live_messages
        # Update live_transcript to match the current state
        transcript_lines = []
        for msg in live_messages:
            timestamp = msg.get("timestamp", now_iso)
            try:
                if isinstance(timestamp, str):
                    msg_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    msg_time = timestamp
                if msg_time.tzinfo:
                    msg_time = msg_time.replace(tzinfo=None)
                time_str = msg_time.strftime('%H:%M:%S')
            except:
                time_str = datetime.utcnow().strftime('%H:%M:%S')
            sender_name = msg.get("sender_name", "Unknown")
            message_text = msg.get("message", "")
            transcript_lines.append(f"[{time_str}] {sender_name}: {message_text}")
        
        # Update live_transcript to match live_messages
        meeting.live_transcript = "\n".join(transcript_lines) + "\n"
        
        # CRITICAL: Force SQLAlchemy to recognize the metadata change
        # SQLAlchemy JSON columns need explicit flagging when mutated
        from sqlalchemy.orm.attributes import flag_modified
        meeting.meeting_metadata = dict(metadata)  # Create new dict
        flag_modified(meeting, "meeting_metadata")
        flag_modified(meeting, "live_transcript")
        
        # Commit immediately to ensure changes are saved
        await self.db.commit()
        
        # Verify the commit worked by refreshing
        await self.db.refresh(meeting)
        final_metadata = meeting.meeting_metadata or {}
        final_update = final_metadata.get("last_content_update", "NOT SET")
        print(f"   ✅ Verified last_content_update after commit: {final_update}")
        print(f"✅ Successfully generated {messages_generated} new messages ({len(live_messages)} total) for meeting {meeting.id}")
    
    async def _generate_final_transcript(self, meeting: Meeting) -> str:
        """Generate a final meeting transcript."""
        if meeting.live_transcript:
            return meeting.live_transcript
        
        # Get attendees
        result = await self.db.execute(
            select(Employee).where(Employee.id.in_(meeting.attendee_ids))
        )
        attendees = result.scalars().all()
        
        attendee_list = ", ".join([f"{e.name} ({e.title})" for e in attendees])
        
        prompt = f"""Generate a meeting transcript for a {meeting.title} meeting.

Meeting Agenda:
{meeting.agenda}

Meeting Outline:
{meeting.outline}

Attendees: {attendee_list}
Duration: {meeting.start_time} to {meeting.end_time}

Generate a realistic meeting transcript showing a conversation between the attendees discussing the agenda items. Include:
- Opening remarks
- Discussion of agenda items
- Questions and responses
- Action items and next steps
- Closing remarks

Format as a transcript with timestamps and speaker names. Make it 10-15 lines of dialogue.

Format:
[HH:MM] Speaker Name: Message
[HH:MM] Another Speaker: Response"""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get("response", "").strip()
                return transcript
        except Exception as e:
            print(f"Error generating final transcript: {e}")
        
        # Fallback
        return f"Meeting transcript for {meeting.title}\nAttendees: {attendee_list}\nAgenda items were discussed and action items were assigned."

