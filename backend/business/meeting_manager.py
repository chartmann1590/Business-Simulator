"""
Meeting Manager - Handles meeting generation, scheduling, and live meeting transcripts.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Employee, Meeting
from datetime import datetime, timedelta
import random
import json
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
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        meetings_created = 0
        now = datetime.utcnow()
        
        # Generate 3-8 meetings throughout the day
        num_meetings = random.randint(3, 8)
        
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
            # Schedule meetings throughout the day (next 8 hours)
            hours_ahead = random.uniform(0, 8)
            start_time = now + timedelta(hours=hours_ahead)
            duration = random.choice([30, 45, 60, 90])  # Meeting duration in minutes
            end_time = start_time + timedelta(minutes=duration)
            
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
        
        for meeting in in_progress_meetings:
            meeting.status = "in_progress"
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
        
        # Update live content for in-progress meetings (generate new messages periodically)
        result = await self.db.execute(
            select(Meeting).where(
                Meeting.status == "in_progress",
                Meeting.end_time > now
            )
        )
        active_meetings = result.scalars().all()
        
        for meeting in active_meetings:
            # Check if we should generate new content (every 5 seconds for active meetings)
            metadata = meeting.meeting_metadata or {}
            if not isinstance(metadata, dict):
                metadata = {}
            last_update = metadata.get("last_content_update")
            should_update = False
            
            if not last_update:
                # No previous update - generate immediately
                should_update = True
                print(f"🚀 Meeting {meeting.id} has no previous update - generating content immediately")
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
                    # Generate new content every 5 seconds for active meetings (more frequent for better UX)
                    if time_since_update >= 5:
                        should_update = True
                except Exception as e:
                    # If parsing fails, update anyway
                    print(f"Error parsing last_update for meeting {meeting.id}: {e}")
                    should_update = True
            
            if should_update:
                try:
                    await self._generate_live_meeting_content(meeting)
                    metadata["last_content_update"] = now.isoformat()
                    meeting.meeting_metadata = metadata
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
            meeting.status = "completed"
            # Generate final transcript
            if meeting.live_transcript and not meeting.transcript:
                meeting.transcript = meeting.live_transcript
            elif not meeting.transcript:
                meeting.transcript = await self._generate_final_transcript(meeting)
        
        await self.db.commit()
    
    async def _generate_live_meeting_content(self, meeting: Meeting):
        """Generate live meeting messages and update transcript."""
        print(f"🔄 Generating live content for meeting {meeting.id}: {meeting.title}")
        
        # Get attendees
        result = await self.db.execute(
            select(Employee).where(Employee.id.in_(meeting.attendee_ids))
        )
        attendees = result.scalars().all()
        
        if len(attendees) < 2:
            print(f"⚠️  Meeting {meeting.id} has less than 2 attendees, skipping content generation")
            return
        
        print(f"✅ Meeting {meeting.id} has {len(attendees)} attendees, proceeding with content generation")
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        # Ensure metadata is properly initialized
        if not meeting.meeting_metadata:
            meeting.meeting_metadata = {}
        metadata = meeting.meeting_metadata
        if not isinstance(metadata, dict):
            metadata = {}
            meeting.meeting_metadata = metadata
        
        # Get existing messages - ensure it's a list
        live_messages = metadata.get("live_messages", [])
        if not isinstance(live_messages, list):
            live_messages = []
            metadata["live_messages"] = live_messages
        
        # Generate 3-5 new messages for active conversation (more messages for livelier meetings)
        num_messages = random.randint(3, 5)
        
        for _ in range(num_messages):
            sender = random.choice(attendees)
            recipient = random.choice([a for a in attendees if a.id != sender.id])
            
            # Generate message using LLM
            personality_str = ", ".join(sender.personality_traits or ["professional"])
            recipient_personality = ", ".join(recipient.personality_traits or ["professional"])
            
            attendee_list = ", ".join([f"{e.name} ({e.title})" for e in attendees])
            
            # Get recent conversation context
            recent_messages = live_messages[-5:] if len(live_messages) > 5 else live_messages
            conversation_context = ""
            if recent_messages:
                conversation_context = "\n\nRecent conversation:\n"
                for msg in recent_messages[-3:]:
                    conversation_context += f"- {msg['sender_name']}: {msg['message']}\n"
            
            prompt = f"""You are {sender.name}, {sender.title} in a {meeting.title} meeting.

Meeting Agenda:
{meeting.agenda}
{conversation_context}
Your personality traits: {personality_str}
Your role: {sender.role}
Attendees in the meeting: {attendee_list}

You are speaking directly to {recipient.name} ({recipient.title}) in this meeting.

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}

Write a brief, natural comment or question (1-2 sentences) that {sender.name} would say in this meeting to {recipient.name}. Make it relevant to the meeting agenda and appropriate for the meeting context. Reference the recent conversation if relevant.

Write only the message, nothing else."""

            message_text = None
            try:
                import httpx
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
                    print(f"⚠️  LLM returned status {response.status_code} for meeting {meeting.id}")
            except Exception as e:
                print(f"❌ Error calling LLM for meeting {meeting.id}: {e}")
                import traceback
                traceback.print_exc()
            
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
            
            # Add message to live messages
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
            
            # Track current speaker in metadata (for visual indicators)
            metadata["current_speaker"] = {
                "id": sender.id,
                "name": sender.name,
                "timestamp": now_iso
            }
            
            # Update live transcript
            timestamp = datetime.utcnow().strftime('%H:%M:%S')
            if meeting.live_transcript:
                meeting.live_transcript += f"\n[{timestamp}] {sender.name}: {message_text}\n"
            else:
                meeting.live_transcript = f"[{timestamp}] {sender.name}: {message_text}\n"
        
        # Update metadata - ensure live_messages is always a list
        if not isinstance(metadata.get("live_messages"), list):
            metadata["live_messages"] = []
        metadata["live_messages"] = live_messages
        meeting.meeting_metadata = metadata
        
        # Commit immediately to ensure changes are saved
        await self.db.commit()
        print(f"✅ Successfully generated {len(live_messages)} total messages for meeting {meeting.id}")
    
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

