from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Project, Task
from sqlalchemy import select
from datetime import datetime, timedelta
import random

class ProjectManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_project(
        self,
        name: str,
        description: str = "",
        priority: str = "medium",
        budget: float = 0.0
    ) -> Project:
        """Create a new project."""
        now = datetime.utcnow()
        project = Project(
            name=name,
            description=description,
            status="planning",
            priority=priority,
            budget=budget,
            deadline=now + timedelta(days=random.randint(30, 90)),
            last_activity_at=now
        )
        self.db.add(project)
        await self.db.flush()
        return project
    
    async def get_active_projects(self) -> list[Project]:
        """Get all active projects."""
        result = await self.db.execute(
            select(Project).where(Project.status.in_(["planning", "active"]))
        )
        return list(result.scalars().all())
    
    async def get_project_by_id(self, project_id: int) -> Project:
        """Get project by ID."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
    
    async def update_project_status(self, project_id: int, status: str):
        """Update project status."""
        project = await self.get_project_by_id(project_id)
        if project:
            project.status = status
    
    async def calculate_project_progress(self, project_id: int) -> float:
        """Calculate project completion percentage."""
        try:
            result = await self.db.execute(
                select(Task).where(Task.project_id == project_id)
            )
            tasks = list(result.scalars().all())
            
            if not tasks:
                return 0.0
            
            # Use task progress if available, otherwise use completion status
            total_progress = 0.0
            for task in tasks:
                try:
                    if hasattr(task, 'progress') and task.progress is not None:
                        total_progress += float(task.progress)
                    elif task.status == "completed":
                        total_progress += 100.0
                except (AttributeError, TypeError, ValueError) as e:
                    # If progress field doesn't exist or is invalid, use status
                    if task.status == "completed":
                        total_progress += 100.0
            
            return total_progress / len(tasks) if tasks else 0.0
        except Exception as e:
            print(f"Error calculating project progress for {project_id}: {e}")
            return 0.0
    
    async def is_project_stalled(self, project_id: int, days_threshold: int = 7) -> bool:
        """Check if a project is stalled (no activity in X days)."""
        try:
            project = await self.get_project_by_id(project_id)
            if not project:
                return False
            
            now = datetime.utcnow()
            
            # Check if project has no tasks at all
            result = await self.db.execute(
                select(Task).where(Task.project_id == project_id)
            )
            tasks = list(result.scalars().all())
            
            if not tasks:
                # Project with no tasks is considered stalled if created more than threshold days ago
                if project.created_at:
                    created = project.created_at
                    if hasattr(created, 'replace'):
                        created = created.replace(tzinfo=None)
                    elif hasattr(created, 'tzinfo') and created.tzinfo:
                        created = created.replace(tzinfo=None)
                    days_since_creation = (now - created).days
                    return days_since_creation >= days_threshold
                return True
            
            # Check last activity (if column exists)
            if hasattr(project, 'last_activity_at') and project.last_activity_at:
                last_activity = project.last_activity_at
                if hasattr(last_activity, 'replace'):
                    last_activity = last_activity.replace(tzinfo=None)
                elif hasattr(last_activity, 'tzinfo') and last_activity.tzinfo:
                    last_activity = last_activity.replace(tzinfo=None)
                days_since_activity = (now - last_activity).days
                return days_since_activity >= days_threshold
            
            # If no last_activity_at, check task timestamps
            if tasks:
                latest_task = max(tasks, key=lambda t: t.created_at if t.created_at else datetime.min)
                if latest_task.created_at:
                    task_created = latest_task.created_at
                    if hasattr(task_created, 'replace'):
                        task_created = task_created.replace(tzinfo=None)
                    elif hasattr(task_created, 'tzinfo') and task_created.tzinfo:
                        task_created = task_created.replace(tzinfo=None)
                    days_since_task = (now - task_created).days
                    return days_since_task >= days_threshold
            
            return False
        except Exception as e:
            # If there's an error (e.g., column doesn't exist), return False
            print(f"Error checking if project is stalled: {e}")
            return False
    
    async def update_project_activity(self, project_id: int):
        """Update the last_activity_at timestamp for a project."""
        project = await self.get_project_by_id(project_id)
        if project:
            project.last_activity_at = datetime.utcnow()

