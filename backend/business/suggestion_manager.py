from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Suggestion, Employee, Activity, Notification, SuggestionVote
from sqlalchemy import select, desc
from datetime import datetime
from config import now as local_now
from llm.ollama_client import OllamaClient
from engine.office_simulator import get_business_context
import random

class SuggestionManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = OllamaClient()
    
    async def generate_suggestion(self, employee: Employee) -> Optional[Suggestion]:
        """Generate a random suggestion from an employee (5% chance)."""
        if random.random() > 0.05:
            return None
        
        categories = [
            "office_improvement",
            "process",
            "culture",
            "technology",
            "communication",
            "benefits"
        ]
        
        category = random.choice(categories)
        
        suggestions_by_category = {
            "office_improvement": [
                ("Better Coffee", "We should get a better coffee machine in the breakroom."),
                ("More Plants", "The office would benefit from more plants."),
                ("Standing Desks", "I think we should offer standing desks."),
                ("Better Lighting", "The lighting in the office could be improved."),
                ("Quiet Spaces", "We need more quiet spaces for focused work.")
            ],
            "process": [
                ("Streamline Meetings", "We should have shorter, more focused meetings."),
                ("Better Documentation", "Our documentation process could be improved."),
                ("Faster Approvals", "The approval process takes too long."),
                ("Clearer Workflows", "Workflows need to be clearer."),
                ("Better Tools", "We should invest in better project management tools.")
            ],
            "culture": [
                ("Team Building", "We should do more team building activities."),
                ("Recognition", "We need better employee recognition programs."),
                ("Work-Life Balance", "We should promote better work-life balance."),
                ("Diversity", "We should focus more on diversity and inclusion."),
                ("Open Communication", "We need more open communication channels.")
            ],
            "technology": [
                ("Better Software", "We should upgrade our software tools."),
                ("Security Training", "We need better cybersecurity training."),
                ("Cloud Migration", "We should migrate more to the cloud."),
                ("Automation", "We should automate more repetitive tasks."),
                ("Better Hardware", "Our hardware needs updating.")
            ],
            "communication": [
                ("Better Slack Usage", "We should use Slack more effectively."),
                ("Regular Updates", "We need more regular company updates."),
                ("Feedback Channels", "We need better feedback channels."),
                ("Transparency", "We should be more transparent about company decisions."),
                ("Cross-Team Communication", "We need better cross-team communication.")
            ],
            "benefits": [
                ("More PTO", "We should offer more paid time off."),
                ("Health Benefits", "Our health benefits could be better."),
                ("Remote Work", "We should offer more remote work options."),
                ("Learning Budget", "We should have a learning and development budget."),
                ("Wellness Program", "We should start a wellness program.")
            ]
        }
        
        suggestions = suggestions_by_category.get(category, [])
        if not suggestions:
            return None
        
        title, content = random.choice(suggestions)
        
        suggestion = Suggestion(
            employee_id=employee.id,
            category=category,
            title=title,
            content=content,
            status="pending",
            upvotes=0
        )
        self.db.add(suggestion)
        
        # Create activity
        activity = Activity(
            employee_id=employee.id,
            activity_type="suggestion_submitted",
            description=f"💡 Submitted suggestion: {title}",
            activity_metadata={
                "suggestion_id": suggestion.id,
                "category": category
            }
        )
        self.db.add(activity)
        
        # Notify managers
        managers_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.hierarchy_level == 2)  # Managers
        )
        managers = managers_result.scalars().all()
        
        for manager in managers:
            notification = Notification(
                notification_type="suggestion",
                title=f"💡 New Suggestion from {employee.name}",
                message=f"{title}: {content[:50]}...",
                employee_id=manager.id
            )
            self.db.add(notification)
        
        await self.db.commit()
        await self.db.refresh(suggestion)
        
        return suggestion
    
    async def get_pending_suggestions(self) -> List[Suggestion]:
        """Get all pending suggestions."""
        result = await self.db.execute(
            select(Suggestion)
            .where(Suggestion.status == "pending")
            .order_by(desc(Suggestion.upvotes), desc(Suggestion.created_at))
        )
        return result.scalars().all()
    
    async def upvote_suggestion(self, suggestion_id: int):
        """Upvote a suggestion."""
        result = await self.db.execute(
            select(Suggestion)
            .where(Suggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()
        if suggestion:
            suggestion.upvotes += 1
            self.db.add(suggestion)
            await self.db.commit()
    
    async def process_suggestion_votes(self):
        """Process votes on suggestions using AI to decide if employees would vote."""
        # Get all pending suggestions that are at least 1 hour old
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        result = await self.db.execute(
            select(Suggestion)
            .where(Suggestion.status == "pending")
            .where(Suggestion.created_at <= cutoff_time)
        )
        suggestions = result.scalars().all()
        
        if not suggestions:
            return
        
        # Get all active employees (excluding the suggestion authors)
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        business_context = await get_business_context(self.db)
        
        votes_added = 0
        for suggestion in suggestions:
            # Get employees who haven't voted yet
            result = await self.db.execute(
                select(SuggestionVote)
                .where(SuggestionVote.suggestion_id == suggestion.id)
            )
            existing_votes = result.scalars().all()
            voted_employee_ids = {vote.employee_id for vote in existing_votes}
            
            # Get the employee who submitted the suggestion
            result = await self.db.execute(
                select(Employee).where(Employee.id == suggestion.employee_id)
            )
            author = result.scalar_one_or_none()
            
            # Get potential voters (all employees except the author)
            potential_voters = [
                emp for emp in all_employees 
                if emp.id != suggestion.employee_id 
                and emp.id not in voted_employee_ids
            ]
            
            # Process a random subset of potential voters (10-30% chance per employee)
            for employee in potential_voters:
                if random.random() > 0.15:  # 15% chance to consider voting
                    continue
                
                # Use AI to decide if this employee would vote
                should_vote = await self._should_employee_vote(
                    employee, suggestion, author, business_context
                )
                
                if should_vote:
                    # Check if vote already exists (race condition protection)
                    result = await self.db.execute(
                        select(SuggestionVote)
                        .where(SuggestionVote.suggestion_id == suggestion.id)
                        .where(SuggestionVote.employee_id == employee.id)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if not existing:
                        vote = SuggestionVote(
                            suggestion_id=suggestion.id,
                            employee_id=employee.id
                        )
                        self.db.add(vote)
                        suggestion.upvotes += 1
                        votes_added += 1
        
        if votes_added > 0:
            await self.db.commit()
            print(f"✅ Added {votes_added} votes to suggestions")
    
    async def _should_employee_vote(
        self, employee: Employee, suggestion: Suggestion, 
        author: Optional[Employee], business_context: dict
    ) -> bool:
        """Use AI to determine if an employee would vote on a suggestion."""
        personality_str = ", ".join(employee.personality_traits or [])
        author_name = author.name if author else "Unknown"
        
        prompt = f"""You are {employee.name}, {employee.title} at a company.

Your personality traits: {personality_str}
Your role: {employee.role}
Your department: {employee.department or "General"}

A colleague named {author_name} submitted a suggestion:

Title: {suggestion.title}
Content: {suggestion.content}
Category: {suggestion.category.replace('_', ' ')}

Current company status:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
- Employee count: {business_context.get('employee_count', 0)}

Based on your personality, role, and the suggestion content, would you vote/upvote this suggestion?

Consider:
1. Does it align with your values and interests?
2. Would it benefit you or your team?
3. Is it relevant to your work?
4. Does it match your personality (e.g., if you're analytical, do you see merit in it)?

Respond with ONLY "yes" or "no", nothing else."""

        try:
            response = await self.llm_client.generate_response(prompt)
            response_lower = response.strip().lower()
            return response_lower.startswith("yes") or response_lower == "y"
        except Exception as e:
            print(f"Error in AI vote decision for {employee.name}: {e}")
            # Fallback: 30% chance to vote
            return random.random() < 0.3
    
    async def process_manager_comments(self):
        """Process manager comments and status updates on suggestions using AI."""
        # Get all pending suggestions that are at least 2 hours old and don't have comments
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        result = await self.db.execute(
            select(Suggestion)
            .where(Suggestion.status == "pending")
            .where(Suggestion.created_at <= cutoff_time)
            .where(Suggestion.manager_comments.is_(None))
        )
        suggestions = result.scalars().all()
        
        if not suggestions:
            return
        
        # Get all managers
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.hierarchy_level == 2)  # Managers
        )
        managers = result.scalars().all()
        
        if not managers:
            return
        
        business_context = await get_business_context(self.db)
        
        comments_added = 0
        status_updates = 0
        for suggestion in suggestions:
            # Randomly assign a manager to comment (30% chance per suggestion)
            if random.random() > 0.3:
                continue
            
            manager = random.choice(managers)
            
            # Get the employee who submitted the suggestion
            result = await self.db.execute(
                select(Employee).where(Employee.id == suggestion.employee_id)
            )
            author = result.scalar_one_or_none()
            
            # Generate comment using AI
            comment = await self._generate_manager_comment(
                manager, suggestion, author, business_context
            )
            
            if comment:
                old_status = suggestion.status
                
                # Determine new status using AI
                new_status = await self._determine_suggestion_status(
                    manager, suggestion, author, business_context
                )
                
                suggestion.manager_comments = comment
                suggestion.reviewed_by_id = manager.id
                suggestion.reviewed_at = datetime.utcnow()
                
                # Update status if it changed
                if new_status and new_status != old_status:
                    suggestion.status = new_status
                    status_updates += 1
                    
                    # Create notification for the employee who submitted the suggestion
                    if author:
                        status_emoji = {
                            "reviewed": "👀",
                            "implemented": "✅",
                            "rejected": "❌"
                        }.get(new_status, "📋")
                        
                        notification = Notification(
                            notification_type="suggestion_status_update",
                            title=f"{status_emoji} Suggestion Status Updated: {suggestion.title}",
                            message=f"{manager.name} reviewed your suggestion '{suggestion.title}' and updated the status to '{new_status}'. {comment[:100]}{'...' if len(comment) > 100 else ''}",
                            employee_id=author.id,
                            read=False
                        )
                        self.db.add(notification)
                
                comments_added += 1
        
        if comments_added > 0:
            await self.db.commit()
            print(f"✅ Added {comments_added} manager comments to suggestions")
            if status_updates > 0:
                print(f"✅ Updated status for {status_updates} suggestions")
    
    async def _generate_manager_comment(
        self, manager: Employee, suggestion: Suggestion,
        author: Optional[Employee], business_context: dict
    ) -> Optional[str]:
        """Generate a manager comment on a suggestion using AI."""
        personality_str = ", ".join(manager.personality_traits or [])
        author_name = author.name if author else "Unknown"
        author_title = author.title if author else "Employee"
        
        prompt = f"""You are {manager.name}, {manager.title} (Manager) at a company.

Your personality traits: {personality_str}
Your role: {manager.role}
Your department: {manager.department or "General"}

An employee named {author_name} ({author_title}) submitted a suggestion:

Title: {suggestion.title}
Content: {suggestion.content}
Category: {suggestion.category.replace('_', ' ')}
Current upvotes: {suggestion.upvotes}

Current company status:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
- Employee count: {business_context.get('employee_count', 0)}

As a manager, write a brief, professional comment on this suggestion (2-4 sentences). The comment should:
1. Acknowledge the suggestion
2. Provide thoughtful feedback (positive, constructive, or neutral)
3. Consider feasibility, impact, and alignment with company goals
4. Match your personality and management style
5. Be professional but approachable

Write only the comment text, nothing else."""

        try:
            response = await self.llm_client.generate_response(prompt)
            comment = response.strip()
            
            # Clean up the response
            if comment.startswith('"') and comment.endswith('"'):
                comment = comment[1:-1]
            if comment.startswith("'") and comment.endswith("'"):
                comment = comment[1:-1]
            
            # Ensure we have meaningful content
            if len(comment) < 20:
                return None
            
            # Limit length
            if len(comment) > 500:
                comment = comment[:497] + "..."
            
            return comment
        except Exception as e:
            print(f"Error generating manager comment for {manager.name}: {e}")
            return None
    
    async def _determine_suggestion_status(
        self, manager: Employee, suggestion: Suggestion,
        author: Optional[Employee], business_context: dict
    ) -> Optional[str]:
        """Use AI to determine the appropriate status for a suggestion."""
        personality_str = ", ".join(manager.personality_traits or [])
        author_name = author.name if author else "Unknown"
        author_title = author.title if author else "Employee"
        
        prompt = f"""You are {manager.name}, {manager.title} (Manager) at a company.

Your personality traits: {personality_str}
Your role: {manager.role}
Your department: {manager.department or "General"}

An employee named {author_name} ({author_title}) submitted a suggestion:

Title: {suggestion.title}
Content: {suggestion.content}
Category: {suggestion.category.replace('_', ' ')}
Current upvotes: {suggestion.upvotes}

Current company status:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
- Employee count: {business_context.get('employee_count', 0)}

As a manager, you need to decide the status for this suggestion. The possible statuses are:
- "pending": Still under review or needs more information
- "reviewed": You've reviewed it and acknowledged it, but haven't decided on implementation yet
- "implemented": The suggestion has been or will be implemented
- "rejected": The suggestion is not feasible, not aligned with company goals, or not a priority

Consider:
1. Feasibility - Can this be realistically implemented?
2. Alignment - Does it align with company goals and current priorities?
3. Impact - Will it have positive impact on the company/employees?
4. Resources - Do we have the resources to implement it?
5. Your management style and personality
6. Current company situation (revenue, projects, etc.)

Based on your analysis, respond with ONLY one of these exact words: pending, reviewed, implemented, or rejected.
Do not include any explanation, just the status word."""

        try:
            response = await self.llm_client.generate_response(prompt)
            status = response.strip().lower()
            
            # Clean up the response
            status = status.strip('"').strip("'").strip()
            
            # Validate status
            valid_statuses = ["pending", "reviewed", "implemented", "rejected"]
            if status in valid_statuses:
                return status
            else:
                # Try to extract status from response
                for valid_status in valid_statuses:
                    if valid_status in status:
                        return valid_status
                
                # Fallback: use "reviewed" as default
                print(f"Warning: AI returned invalid status '{status}', defaulting to 'reviewed'")
                return "reviewed"
        except Exception as e:
            print(f"Error determining suggestion status for {manager.name}: {e}")
            # Fallback: use "reviewed" as default
            return "reviewed"



