from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Project, Task, Employee
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
                    # First check if task has explicit progress value
                    if hasattr(task, 'progress') and task.progress is not None:
                        task_progress = float(task.progress)
                        total_progress += task_progress
                    # If no progress but task is completed, count as 100%
                    elif task.status == "completed":
                        total_progress += 100.0
                    # If task is in progress but no progress value, estimate based on status
                    elif task.status == "in_progress":
                        # Estimate 50% if in progress but no progress value
                        total_progress += 50.0
                    # Pending tasks count as 0%
                    else:
                        total_progress += 0.0
                except (AttributeError, TypeError, ValueError) as e:
                    # If progress field doesn't exist or is invalid, use status
                    if task.status == "completed":
                        total_progress += 100.0
                    elif task.status == "in_progress":
                        total_progress += 50.0
                    else:
                        total_progress += 0.0
            
            calculated_progress = total_progress / len(tasks) if tasks else 0.0
            # Ensure progress is between 0 and 100
            return max(0.0, min(100.0, calculated_progress))
        except Exception as e:
            print(f"Error calculating project progress for {project_id}: {e}")
            import traceback
            traceback.print_exc()
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
    
    async def check_capacity_for_new_project(self):
        """
        Check if there's enough employee capacity to handle a new project.
        Returns (can_create, reason)
        """
        # Get active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Get active projects
        active_projects = await self.get_active_projects()
        project_count = len(active_projects)
        
        # Calculate capacity: each employee can handle approximately 0.2-0.3 projects
        # (assuming employees work on multiple tasks across projects)
        # Minimum: need at least 3 employees per project on average
        max_projects = max(1, int(employee_count / 3))
        
        if project_count >= max_projects:
            return False, f"Too many active projects ({project_count}) for current employee count ({employee_count}). Maximum capacity: {max_projects} projects."
        
        # Also check unassigned tasks
        result = await self.db.execute(
            select(Task).where(
                Task.employee_id.is_(None),
                Task.status.in_(["pending", "in_progress"])
            )
        )
        unassigned_tasks = result.scalars().all()
        unassigned_count = len(unassigned_tasks)
        
        # If there are many unassigned tasks, we're overloaded
        if unassigned_count > employee_count * 2:
            return False, f"Too many unassigned tasks ({unassigned_count}) for current employee count ({employee_count})."
        
        return True, "Capacity available"
    
    async def manage_project_overload(self) -> dict:
        """
        Check project overload and return information about hiring needs.
        NO LONGER cancels projects - instead returns hiring recommendations.
        Returns dict with hiring_needed, employees_short, etc.
        """
        # Get active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Calculate max capacity
        max_projects = max(1, int(employee_count / 3))
        
        # Get active projects
        active_projects = await self.get_active_projects()
        project_count = len(active_projects)
        
        # Calculate hiring needs instead of canceling
        employees_needed_for_projects = project_count * 3
        employees_short = max(0, employees_needed_for_projects - employee_count)
        is_over_capacity = project_count > max_projects
        
        return {
            "is_over_capacity": is_over_capacity,
            "project_count": project_count,
            "employee_count": employee_count,
            "max_projects": max_projects,
            "employees_needed": employees_needed_for_projects,
            "employees_short": employees_short,
            "should_hire": is_over_capacity and employees_short > 0
        }

