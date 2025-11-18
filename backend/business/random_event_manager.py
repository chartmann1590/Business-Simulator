from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import RandomEvent, Employee, Activity, Notification
from sqlalchemy import select
from datetime import datetime, timedelta
from config import now as local_now
import random

class RandomEventManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_for_random_event(self) -> Optional[RandomEvent]:
        """Check if a random event should occur (5% chance per check)."""
        if random.random() > 0.05:
            return None
        
        # Check if there's already an active event
        result = await self.db.execute(
            select(RandomEvent)
            .where(RandomEvent.resolved == False)
        )
        active_event = result.scalar_one_or_none()
        if active_event:
            return None  # Don't create multiple events
        
        # Generate random event
        event_types = [
            ("power_outage", "Power Outage", "The office experienced a brief power outage. Everyone had to stop working.", "high", 0.0, 30),
            ("internet_down", "Internet Down", "The internet connection went down. IT is working on it.", "high", 0.2, 60),
            ("fire_drill", "Fire Drill", "Fire drill! Everyone evacuated the building.", "medium", 0.0, 15),
            ("coffee_machine_broken", "Coffee Machine Broken", "The coffee machine broke down. Morale is low.", "low", 0.9, 120),
            ("pizza_party", "Pizza Party", "Surprise pizza party in the breakroom!", "low", 1.2, 60),
            ("printer_jam", "Printer Jam", "The main printer is jammed. Everyone is frustrated.", "low", 0.95, 30),
            ("surprise_visit", "Surprise Visit", "Important clients are visiting the office unexpectedly.", "medium", 1.1, 90),
            ("air_conditioning_broken", "AC Broken", "The air conditioning stopped working. It's getting hot in here.", "medium", 0.85, 180)
        ]
        
        event_type, title, description, impact, modifier, duration_minutes = random.choice(event_types)
        
        # Get affected employees (random selection)
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        num_affected = random.randint(min(3, len(all_employees)), min(len(all_employees), 10))
        affected = random.sample(all_employees, num_affected)
        affected_ids = [emp.id for emp in affected]
        
        now = local_now()
        end_time = now + timedelta(minutes=duration_minutes)
        
        event = RandomEvent(
            event_type=event_type,
            title=title,
            description=description,
            impact=impact,
            affected_employees=affected_ids,
            productivity_modifier=modifier,
            start_time=now,
            end_time=end_time,
            resolved=False
        )
        self.db.add(event)
        
        # Create activity for each affected employee
        for emp in affected:
            activity = Activity(
                employee_id=emp.id,
                activity_type="random_event",
                description=f"⚠️ {title}: {description}",
                activity_metadata={
                    "event_id": event.id,
                    "event_type": event_type,
                    "impact": impact
                }
            )
            self.db.add(activity)
        
        # Create notification with duplicate prevention
        from business.notification_helper import create_notification_if_not_duplicate
        notification = await create_notification_if_not_duplicate(
            self.db,
            notification_type="random_event",
            title=title,
            message=description,
            employee_id=None,
            duplicate_window_minutes=5  # 5 minute window for random events
        )
        # Only add if not a duplicate (notification will be None if duplicate)
        if notification:
            # Already added to session by helper function
            pass
        
        await self.db.commit()
        await self.db.refresh(event)
        
        return event
    
    async def resolve_expired_events(self):
        """Resolve events that have passed their end time."""
        now = local_now()
        
        result = await self.db.execute(
            select(RandomEvent)
            .where(RandomEvent.resolved == False)
            .where(RandomEvent.end_time <= now)
        )
        expired_events = result.scalars().all()
        
        for event in expired_events:
            event.resolved = True
            self.db.add(event)
        
        await self.db.commit()
    
    async def get_active_events(self) -> List[RandomEvent]:
        """Get all active random events."""
        result = await self.db.execute(
            select(RandomEvent)
            .where(RandomEvent.resolved == False)
            .order_by(RandomEvent.start_time.desc())
        )
        return result.scalars().all()



