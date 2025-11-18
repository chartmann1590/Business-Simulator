from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Newsletter, Employee, Activity, Notification
from sqlalchemy import select, func
from datetime import datetime, timedelta
from config import now as local_now
import random

class NewsletterManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def should_publish_newsletter(self) -> bool:
        """Check if it's time to publish a newsletter (weekly on Fridays)."""
        today = local_now()
        
        # Publish on Fridays
        if today.weekday() != 4:  # Friday is 4
            return False
        
        # Check if we already published this week
        week_start = today - timedelta(days=today.weekday())
        result = await self.db.execute(
            select(Newsletter)
            .where(Newsletter.published_date >= week_start)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return False
        
        return True
    
    async def publish_newsletter(self) -> Optional[Newsletter]:
        """Publish a new company newsletter."""
        # Get a random employee to be the author (prefer managers/executives)
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.hierarchy_level.in_([1, 2]))  # CEO or Manager
        )
        managers = result.scalars().all()
        
        if not managers:
            result = await self.db.execute(
                select(Employee)
                .where(Employee.status == "active")
            )
            managers = result.scalars().all()
        
        if not managers:
            return None
        
        author = random.choice(managers)
        
        # Get latest issue number
        result = await self.db.execute(
            select(func.max(Newsletter.issue_number))
        )
        max_issue = result.scalar()
        issue_number = (max_issue or 0) + 1
        
        # Generate newsletter content
        today = local_now()
        title = f"Weekly Newsletter - Issue #{issue_number}"
        
        # Get recent activities for content
        from database.models import Activity, Project, Financial
        from sqlalchemy import desc
        
        # Get recent projects
        projects_result = await self.db.execute(
            select(Project)
            .order_by(desc(Project.created_at))
            .limit(3)
        )
        recent_projects = projects_result.scalars().all()
        
        # Get recent financial highlights
        financial_result = await self.db.execute(
            select(Financial)
            .order_by(desc(Financial.timestamp))
            .limit(5)
        )
        recent_financials = financial_result.scalars().all()
        
        # Build content
        content_parts = [
            f"# Weekly Newsletter - Issue #{issue_number}",
            f"\n**Published:** {today.strftime('%B %d, %Y')}",
            f"\n**Editor:** {author.name}",
            "\n## Company Updates",
            "\n### Recent Projects",
        ]
        
        if recent_projects:
            for project in recent_projects:
                content_parts.append(f"- **{project.name}**: {project.description[:100]}...")
        else:
            content_parts.append("- No new projects this week.")
        
        content_parts.append("\n### Financial Highlights")
        if recent_financials:
            total_income = sum(f.amount for f in recent_financials if f.type == "income")
            total_expenses = sum(f.amount for f in recent_financials if f.type == "expense")
            content_parts.append(f"- Total Income: ${total_income:,.2f}")
            content_parts.append(f"- Total Expenses: ${total_expenses:,.2f}")
        else:
            content_parts.append("- No financial updates this week.")
        
        content_parts.append("\n## Announcements")
        content_parts.append("- Keep up the great work, team!")
        content_parts.append("- Don't forget about the upcoming team meeting.")
        
        content = "\n".join(content_parts)
        
        newsletter = Newsletter(
            title=title,
            content=content,
            author_id=author.id,
            issue_number=issue_number,
            published_date=today,
            read_count=0
        )
        self.db.add(newsletter)
        
        # Create notification for all employees
        all_employees_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
        )
        all_employees = all_employees_result.scalars().all()
        
        # Create notifications with duplicate prevention
        from business.notification_helper import create_notification_if_not_duplicate
        for emp in all_employees:
            notification = await create_notification_if_not_duplicate(
                self.db,
                notification_type="newsletter",
                title=f"📰 New Newsletter Published",
                message=f"Issue #{issue_number} is now available!",
                employee_id=emp.id,
                duplicate_window_minutes=60  # 1 hour window for newsletters
            )
            # Only add if not a duplicate (notification will be None if duplicate)
            if notification:
                # Already added to session by helper function
                pass
        
        # Create activity
        activity = Activity(
            employee_id=author.id,
            activity_type="newsletter_published",
            description=f"📰 Published Weekly Newsletter Issue #{issue_number}",
            activity_metadata={
                "newsletter_id": newsletter.id,
                "issue_number": issue_number
            }
        )
        self.db.add(activity)
        
        await self.db.commit()
        await self.db.refresh(newsletter)
        
        return newsletter
    
    async def get_latest_newsletters(self, limit: int = 10) -> List[Newsletter]:
        """Get the latest newsletters."""
        from sqlalchemy import desc
        result = await self.db.execute(
            select(Newsletter)
            .order_by(desc(Newsletter.issue_number))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def mark_as_read(self, newsletter_id: int):
        """Mark a newsletter as read (increment read count)."""
        result = await self.db.execute(
            select(Newsletter)
            .where(Newsletter.id == newsletter_id)
        )
        newsletter = result.scalar_one_or_none()
        if newsletter:
            newsletter.read_count += 1
            self.db.add(newsletter)
            await self.db.commit()

