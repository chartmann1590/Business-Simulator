from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Gossip, Activity, ChatMessage
from sqlalchemy import select, func
from datetime import datetime, timedelta
from config import now as local_now
import random

class GossipManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_gossip(self, originator: Employee, recipient: Employee) -> Optional[Gossip]:
        """Generate gossip between two employees."""
        # 10% chance of generating gossip
        if random.random() > 0.1:
            return None
        
        topics = [
            "office_romance",
            "promotion_rumor",
            "project_secret",
            "management_change",
            "new_hire",
            "budget_cuts",
            "office_party",
            "team_conflict",
            "performance_review",
            "company_acquisition"
        ]
        
        topic = random.choice(topics)
        
        # Generate gossip content based on topic
        content_templates = {
            "office_romance": f"Did you hear about {originator.name} and someone from accounting?",
            "promotion_rumor": f"I heard {originator.name} might be getting promoted soon!",
            "project_secret": f"{originator.name} told me about a secret project they're working on.",
            "management_change": f"Rumor has it there might be some management changes coming.",
            "new_hire": f"I heard we're hiring someone new for the {originator.department or 'team'}.",
            "budget_cuts": f"Word is there might be budget cuts coming.",
            "office_party": f"Did you hear about the office party plans?",
            "team_conflict": f"There's some tension between {originator.name} and another team member.",
            "performance_review": f"{originator.name} got a really good review, apparently.",
            "company_acquisition": f"I heard we might be getting acquired."
        }
        
        content = content_templates.get(topic, f"{originator.name} shared some interesting news.")
        credibility = random.uniform(0.3, 0.8)  # Gossip is usually not very credible
        
        # Check if similar gossip already exists
        existing_result = await self.db.execute(
            select(Gossip)
            .where(Gossip.topic == topic)
            .where(func.date(Gossip.created_at) == local_now().date())
            .order_by(Gossip.created_at.desc())
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Spread existing gossip instead of creating new
            existing.spread_count += 1
            existing.recipient_id = recipient.id
            existing.spreader_id = originator.id
            # Credibility decreases with each spread
            existing.credibility = max(0.1, existing.credibility - 0.1)
            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        
        # Create new gossip
        gossip = Gossip(
            originator_id=originator.id,
            spreader_id=originator.id,
            recipient_id=recipient.id,
            topic=topic,
            content=content,
            credibility=credibility,
            spread_count=1
        )
        self.db.add(gossip)
        
        # Create activity
        activity = Activity(
            employee_id=originator.id,
            activity_type="gossip",
            description=f"💬 {originator.name} shared some gossip with {recipient.name}",
            activity_metadata={
                "gossip_id": gossip.id,
                "topic": topic,
                "recipient_id": recipient.id
            }
        )
        self.db.add(activity)
        
        await self.db.commit()
        await self.db.refresh(gossip)
        
        return gossip
    
    async def get_recent_gossip(self, limit: int = 20) -> List[Gossip]:
        """Get recent gossip."""
        result = await self.db.execute(
            select(Gossip)
            .order_by(Gossip.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()





