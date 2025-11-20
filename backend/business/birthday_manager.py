from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, BirthdayCelebration, Activity, Notification
from sqlalchemy import select, func
from datetime import datetime, timedelta
from config import now as local_now, get_timezone
import random
import json

def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware, adding default timezone if naive."""
    if dt.tzinfo is None:
        # If datetime is naive, add the configured timezone
        return get_timezone().localize(dt)
    return dt

class BirthdayManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_birthdays_today(self) -> List[Employee]:
        """Check if any employees have birthdays today. Excludes terminated employees."""
        today = local_now()
        month = today.month
        day = today.day
        
        result = await self.db.execute(
            select(Employee)
            .where(Employee.birthday_month == month)
            .where(Employee.birthday_day == day)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
        )
        return result.scalars().all()
    
    async def celebrate_birthday(self, employee: Employee) -> Optional[BirthdayCelebration]:
        """Create a birthday celebration for an employee and organize a party in breakroom."""
        from engine.movement_system import update_employee_location
        from employees.room_assigner import ROOM_BREAKROOM
        today = ensure_timezone_aware(local_now())
        
        # Check if we already celebrated today
        result = await self.db.execute(
            select(BirthdayCelebration)
            .where(BirthdayCelebration.employee_id == employee.id)
            .where(func.date(BirthdayCelebration.celebration_date) == today.date())
        )
        existing = result.scalar_one_or_none()
        if existing:
            return None  # Already celebrated today
        
        # Calculate age (rough estimate based on hired_at)
        age = 25  # Default age
        if employee.hired_at:
            # Ensure hired_at is timezone-aware for comparison
            hired_at_aware = ensure_timezone_aware(employee.hired_at)
            years_employed = (today - hired_at_aware).days / 365.25
            age = int(25 + years_employed)
        
        # Get 14 employees + birthday person = 15 total for the party
        # Exclude terminated employees
        all_employees_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
            .where(Employee.id != employee.id)
        )
        all_employees = all_employees_result.scalars().all()
        num_attendees = min(14, len(all_employees))
        attendees = random.sample(all_employees, num_attendees)
        attendee_ids = [emp.id for emp in attendees]
        
        # Choose a breakroom for the party (prefer larger ones)
        breakrooms = [
            (f"{ROOM_BREAKROOM}_floor2", 2),  # Floor 2 breakroom (capacity 10)
            (ROOM_BREAKROOM, 1),  # Floor 1 breakroom (capacity 8)
        ]
        party_breakroom, party_floor = random.choice(breakrooms)
        
        # Schedule party time (within the next hour)
        party_time = today + timedelta(minutes=random.randint(5, 60))
        
        # Create celebration with party details
        celebration = BirthdayCelebration(
            employee_id=employee.id,
            celebration_date=today,
            year=age,
            attendees=attendee_ids,
            celebration_message=f"Happy {age}th birthday, {employee.name}! 🎉",
            party_room=party_breakroom,
            party_floor=party_floor,
            party_time=party_time
        )
        self.db.add(celebration)
        
        # Move birthday person to breakroom when party time arrives
        # Mark as "break" so they're protected from being kicked out until party ends
        await update_employee_location(employee, party_breakroom, "break", self.db)
        employee.floor = party_floor
        
        # Move all attendees to the breakroom
        # Mark as "break" so they're protected from being kicked out until party ends
        for attendee in attendees:
            await update_employee_location(attendee, party_breakroom, "break", self.db)
            attendee.floor = party_floor
        
        # Create activity for birthday person
        activity = Activity(
            employee_id=employee.id,
            activity_type="birthday_celebration",
            description=f"🎂 Birthday party! {employee.name} turned {age} today! {len(attendees)} colleagues joined the celebration in the breakroom!",
            activity_metadata={
                "celebration_id": celebration.id,
                "attendees": attendee_ids,
                "age": age,
                "party_room": party_breakroom,
                "party_floor": party_floor
            }
        )
        self.db.add(activity)
        await self.db.flush()
        # Broadcast activity
        try:
            from business.activity_broadcaster import broadcast_activity
            await broadcast_activity(activity, self.db, employee)
        except:
            pass  # Don't fail if broadcasting fails
        
        # Create activities for attendees
        for attendee in attendees:
            attendee_activity = Activity(
                employee_id=attendee.id,
                activity_type="birthday_party",
                description=f"🎉 Attending {employee.name}'s birthday party in the breakroom!",
                activity_metadata={
                    "celebration_id": celebration.id,
                    "birthday_person_id": employee.id,
                    "party_room": party_breakroom
                }
            )
            self.db.add(attendee_activity)
            await self.db.flush()
            # Broadcast activity
            try:
                from business.activity_broadcaster import broadcast_activity
                await broadcast_activity(attendee_activity, self.db, attendee)
            except:
                pass  # Don't fail if broadcasting fails
        
        # Create notifications for all employees about the party
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
                notification_type="birthday_party",
                title=f"🎉 Birthday Party: {employee.name}!",
                message=f"{employee.name}'s birthday party is happening now in the {room_name} on Floor {party_floor}!",
                employee_id=emp.id,
                duplicate_window_minutes=10  # 10 minute window for birthday parties
            )
            # Only add if not a duplicate (notification will be None if duplicate)
            if notification:
                # Already added to session by helper function
                pass
        
        await self.db.commit()
        await self.db.refresh(celebration)
        
        return celebration
    
    async def get_upcoming_birthdays(self, days: int = 7) -> List[dict]:
        """Get employees with birthdays in the next N days. Excludes terminated employees."""
        from datetime import timezone
        today = ensure_timezone_aware(local_now())
        upcoming = []
        
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
            .where(Employee.birthday_month.isnot(None))
            .where(Employee.birthday_day.isnot(None))
        )
        employees = result.scalars().all()
        
        for emp in employees:
            # Create a date for this year
            try:
                # Create timezone-aware datetime with explicit timezone
                tz = today.tzinfo if today.tzinfo else get_timezone()
                birthday_this_year = tz.localize(datetime(today.year, emp.birthday_month, emp.birthday_day))
                # If birthday already passed this year, use next year
                if birthday_this_year < today:
                    birthday_this_year = tz.localize(datetime(today.year + 1, emp.birthday_month, emp.birthday_day))
                
                days_until = (birthday_this_year.date() - today.date()).days
                if 0 <= days_until <= days:
                    upcoming.append({
                        "employee": emp,
                        "days_until": days_until,
                        "date": birthday_this_year
                    })
            except (ValueError, AttributeError) as e:
                # Invalid date (e.g., Feb 30) or timezone issue
                print(f"⚠️  Error processing birthday for {emp.name}: {e}")
                continue
        
        return sorted(upcoming, key=lambda x: x["days_until"])
    
    async def get_scheduled_parties(self) -> List[dict]:
        """Get all scheduled birthday parties with room information."""
        from datetime import datetime, timedelta
        today = ensure_timezone_aware(local_now())
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        week_from_now = today_start + timedelta(days=7)
        
        # Get celebrations from today and next week
        result = await self.db.execute(
            select(BirthdayCelebration)
            .where(BirthdayCelebration.celebration_date >= today_start)
            .where(BirthdayCelebration.celebration_date <= week_from_now)
            .order_by(BirthdayCelebration.celebration_date)
        )
        celebrations = result.scalars().all()
        
        parties = []
        for celebration in celebrations:
            # Get employee info
            emp_result = await self.db.execute(
                select(Employee)
                .where(Employee.id == celebration.employee_id)
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                continue
            
            # Format room name
            room_name = "Breakroom"
            if celebration.party_room:
                room_name = celebration.party_room.replace("_floor2", "").replace("_", " ").title()
            
            parties.append({
                "id": celebration.id,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "celebration_date": celebration.celebration_date.isoformat() if celebration.celebration_date else None,
                "party_time": (celebration.party_time or celebration.celebration_date).isoformat() if (celebration.party_time or celebration.celebration_date) else None,
                "party_room": celebration.party_room or "breakroom",
                "party_floor": celebration.party_floor or 1,
                "room_name": room_name,
                "attendees_count": len(celebration.attendees) if celebration.attendees else 0,
                "age": celebration.year
            })
        
        return parties
    
    async def generate_birthday_party_for_employee(self, employee: Employee) -> Optional[dict]:
        """Generate a birthday party meeting for a specific employee if their birthday is within 90 days.
        
        Returns the meeting if created, None if not needed or already exists.
        """
        from database.models import Meeting
        from employees.room_assigner import ROOM_BREAKROOM
        
        if not employee.birthday_month or not employee.birthday_day:
            return None
        
        today = ensure_timezone_aware(local_now())
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today_start + timedelta(days=90)
        
        try:
            # Calculate birthday date for this year with proper timezone
            tz = today.tzinfo if today.tzinfo else get_timezone()
            birthday_this_year = tz.localize(datetime(today.year, employee.birthday_month, employee.birthday_day))
            
            # If birthday already passed this year, use next year
            if birthday_this_year < today_start:
                birthday_this_year = tz.localize(datetime(today.year + 1, employee.birthday_month, employee.birthday_day))
            
            # Only create meetings for birthdays within the date range
            if birthday_this_year > end_date:
                return None
            
            # Check if a meeting already exists for this birthday
            birthday_start = birthday_this_year.replace(hour=14, minute=0, second=0, microsecond=0)  # 2 PM party
            birthday_end = birthday_start + timedelta(hours=1)  # 1 hour party
            
            # Check for existing birthday meeting - use more precise matching
            # First check by title and date
            existing_result = await self.db.execute(
                select(Meeting)
                .where(Meeting.title.like(f"%{employee.name}%Birthday%"))
                .where(Meeting.start_time >= birthday_start - timedelta(days=1))
                .where(Meeting.start_time <= birthday_start + timedelta(days=1))
            )
            existing = existing_result.scalar_one_or_none()
            
            # Also check by metadata if no title match
            if not existing:
                all_meetings_result = await self.db.execute(
                    select(Meeting)
                    .where(Meeting.start_time >= birthday_start - timedelta(days=1))
                    .where(Meeting.start_time <= birthday_start + timedelta(days=1))
                )
                all_meetings = all_meetings_result.scalars().all()
                for meeting in all_meetings:
                    metadata = meeting.meeting_metadata or {}
                    if (metadata.get('is_birthday_party') and 
                        metadata.get('birthday_employee_id') == employee.id):
                        existing = meeting
                        break
            
            if existing:
                return None  # Meeting already exists
            
            # Calculate age
            age = 25  # Default age
            if employee.hired_at:
                years_employed = (birthday_this_year - employee.hired_at).days / 365.25
                age = int(25 + years_employed)
            
            # Get attendees (14 employees + birthday person = 15 total)
            all_employees_result = await self.db.execute(
                select(Employee)
                .where(Employee.status == "active")
                .where(Employee.status != "fired")
                .where(Employee.fired_at.is_(None))
                .where(Employee.id != employee.id)
            )
            all_employees = all_employees_result.scalars().all()
            num_attendees = min(14, len(all_employees))
            attendees = random.sample(all_employees, num_attendees) if all_employees else []
            attendee_ids = [e.id for e in attendees]
            attendee_ids.append(employee.id)  # Include birthday person
            
            # Choose a breakroom for the party
            breakrooms = [
                (f"{ROOM_BREAKROOM}_floor2", 2),  # Floor 2 breakroom
                (ROOM_BREAKROOM, 1),  # Floor 1 breakroom
            ]
            party_breakroom, party_floor = random.choice(breakrooms)
            room_name = party_breakroom.replace("_floor2", "").replace("_", " ").title()
            
            # Determine if it's a milestone birthday
            is_milestone = age % 10 == 0 or age in [18, 21, 25, 30, 40, 50, 60]
            special_notes = []
            if is_milestone:
                special_notes.append(f"🎉 Milestone birthday - {age} years old!")
            if age >= 50:
                special_notes.append("🎂 Special cake ordered")
            if employee.has_performance_award:
                special_notes.append("⭐ Performance award winner - extra celebration!")
            
            # Create meeting description with all details
            attendee_names = [e.name for e in attendees]
            description = f"🎂 Birthday Party for {employee.name}!\n\n"
            description += f"🎂 Turning {age} years old!\n"
            description += f"📍 Location: {room_name} on Floor {party_floor}\n"
            description += f"👥 Attendees: {employee.name}, {', '.join(attendee_names[:5])}"
            if len(attendee_names) > 5:
                description += f", and {len(attendee_names) - 5} more"
            description += f"\n\n"
            if special_notes:
                description += "✨ Special Notes:\n"
                for note in special_notes:
                    description += f"  • {note}\n"
            
            # Create the meeting
            meeting = Meeting(
                title=f"🎂 {employee.name}'s Birthday Party",
                description=description,
                organizer_id=employee.id,  # Birthday person is the organizer
                attendee_ids=attendee_ids,
                start_time=birthday_start,
                end_time=birthday_end,
                status="scheduled",
                agenda=f"Birthday celebration for {employee.name}",
                outline=f"1. Welcome and birthday wishes\n2. Cake and refreshments\n3. Birthday song\n4. Gifts and cards",
                meeting_metadata={
                    "is_birthday_party": True,
                    "birthday_employee_id": employee.id,
                    "age": age,
                    "party_room": party_breakroom,
                    "party_floor": party_floor,
                    "room_name": room_name,
                    "special_notes": special_notes
                }
            )
            
            self.db.add(meeting)
            await self.db.commit()
            await self.db.refresh(meeting)
            
            return {
                "meeting": meeting,
                "created": True
            }
            
        except ValueError:
            # Invalid date (e.g., Feb 30)
            return None
        except Exception as e:
            print(f"Error generating birthday party for {employee.name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_birthday_party_meetings(self, days_ahead: int = 90) -> int:
        """Generate birthday party meetings for upcoming birthdays and ensure they appear on the calendar.
        
        This creates Meeting records for birthday parties so they appear on the calendar.
        Only creates meetings for active employees (excludes terminated employees).
        This function ensures ALL birthdays within the date range have scheduled parties.
        """
        from database.models import Meeting
        from employees.room_assigner import ROOM_BREAKROOM
        
        today = ensure_timezone_aware(local_now())
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today_start + timedelta(days=days_ahead)
        tz = today.tzinfo if today.tzinfo else get_timezone()
        
        # Get all active employees with birthdays (exclude terminated employees)
        # Use simpler query - just check status and birthday fields
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.fired_at.is_(None))
            .where(Employee.birthday_month.isnot(None))
            .where(Employee.birthday_day.isnot(None))
        )
        employees = result.scalars().all()
        
        # Debug: Check total employees
        total_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.status != "fired")
            .where(Employee.fired_at.is_(None))
        )
        total_employees = total_result.scalars().all()
        
        print(f"🔍 Total active employees: {len(total_employees)}")
        print(f"🔍 Employees with birthday data: {len(employees)}")
        print(f"📅 Today: {today_start}, End date: {end_date}")
        
        if len(employees) == 0:
            print("⚠️ WARNING: No employees found with birthday data! Birthday parties cannot be generated.")
            return 0
        
        print(f"📋 Processing {len(employees)} employees...")
        meetings_created = 0
        skipped_existing = 0
        skipped_out_of_range = 0
        processed = 0
        errors = 0
        in_range_count = 0
        
        for emp in employees:
            processed += 1
            if processed % 50 == 0:
                print(f"  📊 Processed {processed}/{len(employees)} employees...")
            try:
                # Calculate birthday date for this year with proper timezone
                try:
                    birthday_this_year = tz.localize(datetime(today.year, emp.birthday_month, emp.birthday_day))
                except ValueError:
                    errors += 1
                    continue
                
                # If birthday already passed this year, use next year
                if birthday_this_year < today_start:
                    birthday_this_year = tz.localize(datetime(today.year + 1, emp.birthday_month, emp.birthday_day))
                
                # Only create meetings for birthdays within the date range
                birthday_date = birthday_this_year.date()
                end_date_only = end_date.date()
                days_until = (birthday_date - today_start.date()).days
                
                if birthday_date > end_date_only:
                    skipped_out_of_range += 1
                    continue
                
                in_range_count += 1
                if in_range_count <= 5:
                    print(f"  ✓ {emp.name}: birthday in {days_until} days (within range)")
                
                # Check if a meeting already exists - SIMPLIFIED: just check by employee ID in metadata
                birthday_start = birthday_this_year.replace(hour=14, minute=0, second=0, microsecond=0)
                birthday_end = birthday_start + timedelta(hours=1)
                
                # Quick check: look for any meeting with this employee's ID in metadata on this date
                check_start = birthday_start - timedelta(hours=12)
                check_end = birthday_start + timedelta(hours=12)
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
                        if meta.get('is_birthday_party') and meta.get('birthday_employee_id') == emp.id:
                            existing = meeting
                            break
                
                if existing:
                    skipped_existing += 1
                    continue
                
                # Calculate age
                age = 25  # Default age
                if emp.hired_at:
                    years_employed = (birthday_this_year - emp.hired_at).days / 365.25
                    age = int(25 + years_employed)
                
                # Get attendees (14 employees + birthday person = 15 total)
                all_employees_result = await self.db.execute(
                    select(Employee)
                    .where(Employee.status == "active")
                    .where(Employee.status != "fired")
                    .where(Employee.fired_at.is_(None))
                    .where(Employee.id != emp.id)
                )
                all_employees = all_employees_result.scalars().all()
                # Always get exactly 14 other employees (or as many as available if less than 14)
                num_attendees = min(14, len(all_employees))
                if num_attendees > 0:
                    attendees = random.sample(all_employees, num_attendees)
                else:
                    attendees = []
                # Create attendee_ids list: 14 colleagues + birthday person = 15 total
                # IMPORTANT: Create as a new list to ensure it's properly stored
                attendee_ids = [int(e.id) for e in attendees]  # Convert to int list
                attendee_ids.append(int(emp.id))  # Include birthday person (total = 15)
                
                # Ensure we have exactly 15 (or as many as possible)
                if len(attendee_ids) < 15 and len(all_employees) < 14:
                    # If we have fewer than 14 other employees, just use all of them + birthday person
                    attendee_ids = [int(e.id) for e in all_employees] + [int(emp.id)]
                
                # Verify we have the right count
                if len(attendee_ids) != 15 and len(all_employees) >= 14:
                    print(f"⚠️ Warning: {emp.name}'s party has {len(attendee_ids)} attendees, expected 15")
                    # Fix it
                    if len(attendee_ids) < 15:
                        # Add more if we can
                        remaining = [e.id for e in all_employees if e.id not in attendee_ids]
                        needed = 15 - len(attendee_ids)
                        if len(remaining) >= needed:
                            attendee_ids.extend([int(e.id) for e in random.sample(remaining, needed)])
                
                # Final verification
                if len(attendee_ids) != 15:
                    print(f"❌ ERROR: {emp.name}'s party still has {len(attendee_ids)} attendees after fix!")
                
                # Choose a breakroom for the party
                breakrooms = [
                    (f"{ROOM_BREAKROOM}_floor2", 2),  # Floor 2 breakroom
                    (ROOM_BREAKROOM, 1),  # Floor 1 breakroom
                ]
                party_breakroom, party_floor = random.choice(breakrooms)
                room_name = party_breakroom.replace("_floor2", "").replace("_", " ").title()
                
                # Determine if it's a milestone birthday
                is_milestone = age % 10 == 0 or age in [18, 21, 25, 30, 40, 50, 60]
                special_notes = []
                if is_milestone:
                    special_notes.append(f"🎉 Milestone birthday - {age} years old!")
                if age >= 50:
                    special_notes.append("🎂 Special cake ordered")
                if emp.has_performance_award:
                    special_notes.append("⭐ Performance award winner - extra celebration!")
                
                # Create meeting description with all details
                attendee_names = [e.name for e in attendees]
                description = f"🎂 Birthday Party for {emp.name}!\n\n"
                description += f"🎂 Turning {age} years old!\n"
                description += f"📍 Location: {room_name} on Floor {party_floor}\n"
                description += f"👥 Attendees: {emp.name}, {', '.join(attendee_names[:5])}"
                if len(attendee_names) > 5:
                    description += f", and {len(attendee_names) - 5} more"
                description += f"\n\n"
                if special_notes:
                    description += "✨ Special Notes:\n"
                    for note in special_notes:
                        description += f"  • {note}\n"
                
                # Create the meeting
                meeting = Meeting(
                    title=f"🎂 {emp.name}'s Birthday Party",
                    description=description,
                    organizer_id=emp.id,  # Birthday person is the organizer
                    attendee_ids=attendee_ids,
                    start_time=birthday_start,
                    end_time=birthday_end,
                    status="scheduled",
                    agenda=f"Birthday celebration for {emp.name}",
                    outline=f"1. Welcome and birthday wishes\n2. Cake and refreshments\n3. Birthday song\n4. Gifts and cards",
                    meeting_metadata={
                        "is_birthday_party": True,
                        "birthday_employee_id": emp.id,
                        "age": age,
                        "party_room": party_breakroom,
                        "party_floor": party_floor,
                        "room_name": room_name,
                        "special_notes": special_notes
                    }
                )
                
                self.db.add(meeting)
                meetings_created += 1
                if meetings_created <= 20:
                    print(f"  ✅ Created birthday party for {emp.name} on {birthday_start.strftime('%Y-%m-%d')} at {birthday_start.strftime('%H:%M')}")
                
            except ValueError as ve:
                # Invalid date (e.g., Feb 30)
                errors += 1
                if errors <= 5:  # Only print first 5 errors
                    print(f"⚠️ Invalid birthday date for {emp.name}: {emp.birthday_month}/{emp.birthday_day} - {ve}")
                continue
            except Exception as e:
                errors += 1
                if errors <= 5:  # Only print first 5 errors
                    print(f"❌ Error generating birthday party for {emp.name}: {e}")
                    import traceback
                    traceback.print_exc()
                continue
        
        # Commit the transaction
        try:
            if meetings_created > 0:
                await self.db.commit()
                print(f"✅ Committed {meetings_created} new birthday party meetings to database")
            else:
                # Still commit to ensure transaction completes
                await self.db.commit()
                print(f"ℹ️ No new meetings to commit (all may already exist or be out of range)")
        except Exception as commit_error:
            print(f"❌ Error committing meetings: {commit_error}")
            await self.db.rollback()
            import traceback
            traceback.print_exc()
            return 0
        
        if skipped_existing > 0:
            print(f"ℹ️ Skipped {skipped_existing} birthdays (meetings already exist)")
        if skipped_out_of_range > 0:
            print(f"ℹ️ Skipped {skipped_out_of_range} birthdays (outside {days_ahead} day range)")
        
        print(f"📊 Summary: Processed {processed} employees")
        print(f"   ✅ Created: {meetings_created}")
        print(f"   ⏭️ Skipped (existing): {skipped_existing}")
        print(f"   📅 Skipped (out of range): {skipped_out_of_range}")
        print(f"   ❌ Errors: {errors}")
        return meetings_created

