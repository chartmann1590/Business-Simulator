from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, HolidayCelebration, Activity, Notification
from sqlalchemy import select, func
from datetime import datetime, timedelta
from config import now as local_now
import random
import holidays

class HolidayManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Initialize US holidays
        # Initialize US holidays for a wide range of years (2020-2035)
        # This ensures we can generate meetings for holidays many years ahead
        self.us_holidays = holidays.UnitedStates(years=range(2020, 2036))
    
    def is_holiday_today(self) -> Optional[str]:
        """Check if today is a US holiday. Returns the holiday name if it is, None otherwise."""
        today = local_now()
        holiday_name = self.us_holidays.get(today.date())
        return holiday_name
    
    async def check_holiday_today(self) -> Optional[str]:
        """Check if today is a holiday and if we haven't celebrated it yet."""
        holiday_name = self.is_holiday_today()
        if not holiday_name:
            return None
        
        today = local_now()
        
        # Check if we already celebrated this holiday today
        result = await self.db.execute(
            select(HolidayCelebration)
            .where(func.date(HolidayCelebration.celebration_date) == today.date())
            .where(HolidayCelebration.holiday_name == holiday_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return None  # Already celebrated today
        
        return holiday_name
    
    async def celebrate_holiday(self, holiday_name: str) -> Optional[HolidayCelebration]:
        """Create a holiday celebration and organize a party in breakroom."""
        from engine.movement_system import update_employee_location
        from employees.room_assigner import ROOM_BREAKROOM
        today = local_now()
        
        # Check if we already celebrated today
        result = await self.db.execute(
            select(HolidayCelebration)
            .where(func.date(HolidayCelebration.celebration_date) == today.date())
            .where(HolidayCelebration.holiday_name == holiday_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return None  # Already celebrated today
        
        # Get all active employees for the party (exclude terminated employees)
        all_employees_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
        )
        all_employees = all_employees_result.scalars().all()
        
        # For holidays, invite more people - up to 20 employees
        num_attendees = min(20, len(all_employees))
        attendees = random.sample(all_employees, num_attendees) if all_employees else []
        attendee_ids = [emp.id for emp in attendees]
        
        # Choose a breakroom for the party (prefer larger ones)
        breakrooms = [
            (f"{ROOM_BREAKROOM}_floor2", 2),  # Floor 2 breakroom (capacity 10)
            (ROOM_BREAKROOM, 1),  # Floor 1 breakroom (capacity 8)
        ]
        party_breakroom, party_floor = random.choice(breakrooms)
        
        # Schedule party time (within the next hour)
        party_time = today + timedelta(minutes=random.randint(5, 60))
        
        # Create celebration message based on holiday
        celebration_messages = {
            "New Year's Day": f"🎉 Happy New Year! Let's celebrate {holiday_name} together!",
            "Martin Luther King Jr. Day": f"✊ Honoring {holiday_name} - a day of reflection and celebration!",
            "Presidents' Day": f"🇺🇸 Celebrating {holiday_name} with the team!",
            "Memorial Day": f"🇺🇸 Honoring {holiday_name} - remembering those who served!",
            "Independence Day": f"🎆 Happy {holiday_name}! Let's celebrate America's birthday!",
            "Labor Day": f"💼 Celebrating {holiday_name} - honoring the American worker!",
            "Columbus Day": f"🌎 Celebrating {holiday_name} with the office!",
            "Veterans Day": f"🇺🇸 Honoring {holiday_name} - thank you to all who served!",
            "Thanksgiving": f"🦃 Happy {holiday_name}! Let's give thanks together!",
            "Christmas": f"🎄 Merry {holiday_name}! Time for holiday cheer!",
        }
        
        celebration_message = celebration_messages.get(
            holiday_name, 
            f"🎉 Happy {holiday_name}! Let's celebrate together!"
        )
        
        # Create celebration with party details
        celebration = HolidayCelebration(
            holiday_name=holiday_name,
            celebration_date=today,
            attendees=attendee_ids,
            celebration_message=celebration_message,
            party_room=party_breakroom,
            party_floor=party_floor,
            party_time=party_time
        )
        self.db.add(celebration)
        
        # Move all attendees to the breakroom
        for attendee in attendees:
            await update_employee_location(attendee, party_breakroom, "meeting", self.db)
            attendee.floor = party_floor
        
        # Create activity for each attendee
        for attendee in attendees:
            activity = Activity(
                employee_id=attendee.id,
                activity_type="holiday_celebration",
                description=f"🎉 Celebrating {holiday_name} in the breakroom with {len(attendees)} colleagues!",
                activity_metadata={
                    "celebration_id": celebration.id,
                    "holiday_name": holiday_name,
                    "party_room": party_breakroom,
                    "party_floor": party_floor
                }
            )
            self.db.add(activity)
        
        # Create notifications for all employees about the holiday party
        all_employees_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
        )
        all_employees = all_employees_result.scalars().all()
        
        room_name = party_breakroom.replace("_floor2", "").replace("_", " ").title()
        # Create notifications with duplicate prevention
        from business.notification_helper import create_notification_if_not_duplicate
        for emp in all_employees:
            notification = await create_notification_if_not_duplicate(
                self.db,
                notification_type="holiday_party",
                title=f"🎉 Holiday Celebration: {holiday_name}!",
                message=f"Office holiday party for {holiday_name} is happening now in the {room_name} on Floor {party_floor}!",
                employee_id=emp.id,
                duplicate_window_minutes=10  # 10 minute window for holiday parties
            )
            # Only add if not a duplicate (notification will be None if duplicate)
            if notification:
                # Already added to session by helper function
                pass
        
        await self.db.commit()
        await self.db.refresh(celebration)
        
        return celebration
    
    async def get_upcoming_holidays(self, days: int = 30) -> List[dict]:
        """Get upcoming US holidays in the next N days."""
        today = local_now()
        upcoming = []
        
        for i in range(days):
            check_date = today.date() + timedelta(days=i)
            holiday_name = self.us_holidays.get(check_date)
            if holiday_name:
                upcoming.append({
                    "holiday_name": holiday_name,
                    "date": check_date,
                    "days_until": i
                })
        
        return sorted(upcoming, key=lambda x: x["days_until"])
    
    async def get_scheduled_holiday_parties(self) -> List[dict]:
        """Get all scheduled holiday parties with room information."""
        today = local_now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        week_from_now = today_start + timedelta(days=7)
        
        # Get celebrations from today and next week
        result = await self.db.execute(
            select(HolidayCelebration)
            .where(HolidayCelebration.celebration_date >= today_start)
            .where(HolidayCelebration.celebration_date <= week_from_now)
            .order_by(HolidayCelebration.celebration_date)
        )
        celebrations = result.scalars().all()
        
        parties = []
        for celebration in celebrations:
            # Format room name
            room_name = "Breakroom"
            if celebration.party_room:
                room_name = celebration.party_room.replace("_floor2", "").replace("_", " ").title()
            
            parties.append({
                "id": celebration.id,
                "holiday_name": celebration.holiday_name,
                "celebration_date": celebration.celebration_date.isoformat() if celebration.celebration_date else None,
                "party_time": (celebration.party_time or celebration.celebration_date).isoformat() if (celebration.party_time or celebration.celebration_date) else None,
                "party_room": celebration.party_room or "breakroom",
                "party_floor": celebration.party_floor or 1,
                "room_name": room_name,
                "attendees_count": len(celebration.attendees) if celebration.attendees else 0
            })
        
        return parties
    
    async def generate_holiday_meetings(self, days_ahead: int = 365) -> int:
        """Generate holiday party meetings for upcoming US holidays and ensure they appear on the calendar.
        
        This creates Meeting records for holiday parties so they appear on the calendar.
        Only creates meetings for active employees (excludes terminated employees).
        """
        from database.models import Meeting
        from employees.room_assigner import ROOM_BREAKROOM
        
        today = local_now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today_start + timedelta(days=days_ahead)
        
        # Get all active employees (exclude terminated employees)
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) == 0:
            print("⚠️ WARNING: No active employees found! Holiday parties cannot be generated.")
            return 0
        
        print(f"📋 Generating holiday meetings for next {days_ahead} days ({days_ahead // 365} years)...")
        print(f"📅 Today: {today_start.strftime('%Y-%m-%d %H:%M:%S %Z') if today_start.tzinfo else today_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 End date: {end_date.strftime('%Y-%m-%d %H:%M:%S %Z') if end_date.tzinfo else end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌍 Timezone: {today.tzinfo if today.tzinfo else 'America/New_York'}")
        
        meetings_created = 0
        skipped_existing = 0
        errors = 0
        
        # Get all holidays in the date range
        for i in range(days_ahead):
            check_date = today_start.date() + timedelta(days=i)
            holiday_name = self.us_holidays.get(check_date)
            
            if not holiday_name:
                continue
            
            try:
                # Create holiday start time (2 PM party) in NY timezone
                # Use the same timezone as the current time to ensure consistency
                holiday_start = datetime(check_date.year, check_date.month, check_date.day, 14, 0, 0)
                if today.tzinfo:
                    # Ensure timezone is set correctly (NY timezone)
                    holiday_start = holiday_start.replace(tzinfo=today.tzinfo)
                else:
                    # If no timezone info, use NY timezone from config
                    from config import get_timezone
                    ny_tz = get_timezone()
                    holiday_start = ny_tz.localize(holiday_start)
                holiday_end = holiday_start + timedelta(hours=1)
                
                # Check if a meeting already exists for this holiday
                # Use a wider time window to catch any existing meetings on the same date
                check_start = holiday_start - timedelta(hours=24)  # Check 24 hours before
                check_end = holiday_start + timedelta(hours=24)    # Check 24 hours after
                existing_result = await self.db.execute(
                    select(Meeting)
                    .where(Meeting.start_time >= check_start)
                    .where(Meeting.start_time <= check_end)
                )
                existing_meetings = existing_result.scalars().all()
                existing = None
                for meeting in existing_meetings:
                    meta = meeting.meeting_metadata
                    if meta and isinstance(meta, dict):
                        # Check if it's a holiday party and matches the holiday name
                        if meta.get('is_holiday_party') and meta.get('holiday_name') == holiday_name:
                            existing = meeting
                            break
                    # Also check the title for holiday party indicators
                    if meeting.title and ('Office Party' in meeting.title or '🎉' in meeting.title):
                        if holiday_name in meeting.title:
                            existing = meeting
                            break
                
                if existing:
                    skipped_existing += 1
                    if skipped_existing <= 5:  # Only log first few to avoid spam
                        print(f"  ⏭️  Skipped {holiday_name} on {check_date.strftime('%Y-%m-%d')} (meeting already exists)")
                    continue
                
                # Get attendees (up to 20 employees for holidays)
                num_attendees = min(20, len(all_employees))
                attendees = random.sample(all_employees, num_attendees) if all_employees else []
                attendee_ids = [int(emp.id) for emp in attendees]
                
                # Choose a breakroom for the party
                breakrooms = [
                    (f"{ROOM_BREAKROOM}_floor2", 2),  # Floor 2 breakroom
                    (ROOM_BREAKROOM, 1),  # Floor 1 breakroom
                ]
                party_breakroom, party_floor = random.choice(breakrooms)
                room_name = party_breakroom.replace("_floor2", "").replace("_", " ").title()
                
                # Create celebration message based on holiday
                celebration_messages = {
                    "New Year's Day": "🎉 Happy New Year! Let's celebrate together!",
                    "Martin Luther King Jr. Day": "✊ Honoring MLK Day - a day of reflection and celebration!",
                    "Presidents' Day": "🇺🇸 Celebrating Presidents' Day with the team!",
                    "Washington's Birthday": "🇺🇸 Celebrating Presidents' Day with the team!",
                    "Memorial Day": "🇺🇸 Honoring Memorial Day - remembering those who served!",
                    "Independence Day": "🎆 Happy Independence Day! Let's celebrate America's birthday!",
                    "Independence Day (Observed)": "🎆 Happy Independence Day! Let's celebrate America's birthday!",
                    "Labor Day": "💼 Celebrating Labor Day - honoring the American worker!",
                    "Columbus Day": "🌎 Celebrating Columbus Day with the office!",
                    "Veterans Day": "🇺🇸 Honoring Veterans Day - thank you to all who served!",
                    "Thanksgiving": "🦃 Happy Thanksgiving! Let's give thanks together!",
                    "Christmas": "🎄 Merry Christmas! Time for holiday cheer!",
                    "Christmas Day": "🎄 Merry Christmas! Time for holiday cheer!",
                    "Juneteenth National Independence Day": "🎉 Celebrating Juneteenth - freedom and equality for all!",
                }
                
                celebration_message = celebration_messages.get(
                    holiday_name, 
                    f"🎉 Happy {holiday_name}! Let's celebrate together!"
                )
                
                # Create meeting description
                attendee_names = [e.name for e in attendees]
                description = f"🎉 Office Holiday Party: {holiday_name}!\n\n"
                description += f"{celebration_message}\n"
                description += f"📍 Location: {room_name} on Floor {party_floor}\n"
                description += f"👥 Attendees: {', '.join(attendee_names[:5])}"
                if len(attendee_names) > 5:
                    description += f", and {len(attendee_names) - 5} more"
                description += f"\n\n"
                description += "✨ All employees are welcome to join the celebration!"
                
                # Get a random employee as organizer (or first employee if none)
                organizer = random.choice(all_employees) if all_employees else None
                
                # Create the meeting
                meeting = Meeting(
                    title=f"🎉 {holiday_name} Office Party",
                    description=description,
                    organizer_id=organizer.id if organizer else None,
                    attendee_ids=attendee_ids,
                    start_time=holiday_start,
                    end_time=holiday_end,
                    status="scheduled",
                    agenda=f"Office holiday celebration for {holiday_name}",
                    outline=f"1. Welcome and holiday greetings\n2. Refreshments and snacks\n3. Team activities\n4. Holiday celebration",
                    meeting_metadata={
                        "is_holiday_party": True,
                        "holiday_name": holiday_name,
                        "party_room": party_breakroom,
                        "party_floor": party_floor,
                        "room_name": room_name,
                        "celebration_message": celebration_message
                    }
                )
                
                # Final duplicate check right before adding (prevents race conditions)
                final_check = await self.db.execute(
                    select(Meeting)
                    .where(Meeting.start_time >= check_start)
                    .where(Meeting.start_time <= check_end)
                    .where(Meeting.title.like(f"%{holiday_name}%"))
                )
                final_existing = final_check.scalars().first()
                if final_existing:
                    skipped_existing += 1
                    if skipped_existing <= 5:
                        print(f"  ⏭️  Skipped {holiday_name} on {check_date.strftime('%Y-%m-%d')} (duplicate detected in final check)")
                    continue
                
                self.db.add(meeting)
                meetings_created += 1
                if meetings_created <= 15:
                    tz_str = f" {holiday_start.strftime('%Z')}" if holiday_start.tzinfo else ""
                    print(f"  ✅ Created holiday party for {holiday_name} on {holiday_start.strftime('%Y-%m-%d')} at {holiday_start.strftime('%H:%M')}{tz_str}")
                
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"❌ Error generating holiday meeting for {holiday_name}: {e}")
                    import traceback
                    traceback.print_exc()
                continue
        
        # Commit the transaction
        try:
            if meetings_created > 0:
                await self.db.commit()
                print(f"✅ Committed {meetings_created} new holiday party meetings to database")
                print(f"   No duplicates created - all meetings are unique.")
            else:
                await self.db.commit()
                print(f"ℹ️ No new meetings to commit (all holidays already scheduled - no duplicates)")
        except Exception as commit_error:
            print(f"❌ Error committing meetings: {commit_error}")
            await self.db.rollback()
            import traceback
            traceback.print_exc()
            return 0
        
        if skipped_existing > 0:
            print(f"ℹ️ Skipped {skipped_existing} holidays (meetings already exist)")
        
        print(f"📊 Summary: Created {meetings_created} holiday meetings, Skipped {skipped_existing}, Errors {errors}")
        if meetings_created > 0:
            print(f"✅ All holiday parties are scheduled with proper NY timezone and will appear on the calendar.")
        return meetings_created

