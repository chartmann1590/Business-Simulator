from .base import EmployeeAgent
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Task, Project
from llm.ollama_client import OllamaClient
from sqlalchemy import select
import random

class CEOAgent(EmployeeAgent):
    """CEO-specific decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        # CEO makes strategic decisions
        decision = await super().evaluate_situation(business_context)
        decision["action_type"] = "strategic"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # CEO can create new projects
        if "new project" in decision.get("decision", "").lower() or "launch" in decision.get("decision", "").lower():
            await self._create_strategic_project(decision)
        
        return activity
    
    async def _create_strategic_project(self, decision: Dict):
        """Create a new strategic project."""
        from business.project_manager import ProjectManager
        import random
        project_manager = ProjectManager(self.db)
        
        project_names = [
            "Market Expansion Initiative",
            "Product Innovation Program",
            "Customer Experience Enhancement",
            "Digital Transformation Project",
            "Strategic Partnership Development"
        ]
        
        project_name = random.choice(project_names)
        await project_manager.create_project(
            name=project_name,
            description=f"Strategic project initiated by {self.employee.name}: {decision.get('decision', '')}",
            priority="high",
            budget=random.uniform(50000, 200000)
        )

class ManagerAgent(EmployeeAgent):
    """Manager-specific decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        decision = await super().evaluate_situation(business_context)
        decision["action_type"] = "tactical"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # Managers automatically assign tasks (60% chance per tick)
        if random.random() < 0.6:  # 60% chance to assign tasks
            await self._assign_tasks()
        
        return activity
    
    async def _assign_tasks(self):
        """Assign tasks to team members."""
        from sqlalchemy import select
        
        # Get employees in this manager's department
        result = await self.db.execute(
            select(Employee).where(
                Employee.department == self.employee.department,
                Employee.hierarchy_level > self.employee.hierarchy_level,
                Employee.id != self.employee.id
            )
        )
        team_members = result.scalars().all()
        
        # Get active and planning projects
        result = await self.db.execute(
            select(Project).where(Project.status.in_(["planning", "active"]))
        )
        projects = result.scalars().all()
        
        if projects:
            from business.project_manager import ProjectManager
            from sqlalchemy import select
            project_manager = ProjectManager(self.db)
            
            # First, ensure projects have tasks
            for project in projects:
                # Check if project has any tasks
                result = await self.db.execute(
                    select(Task).where(Task.project_id == project.id)
                )
                existing_tasks = result.scalars().all()
                
                # If no tasks, create some initial tasks
                if not existing_tasks:
                    task_descriptions = [
                        f"Initial planning for {project.name}",
                        f"Research and analysis for {project.name}",
                        f"Design phase for {project.name}",
                        f"Development for {project.name}",
                        f"Testing for {project.name}"
                    ]
                    # Create 2-4 tasks per project
                    num_tasks = random.randint(2, 4)
                    for i in range(num_tasks):
                        task = Task(
                            employee_id=None,  # Unassigned initially
                            project_id=project.id,
                            description=random.choice(task_descriptions),
                            status="pending",
                            priority=project.priority
                        )
                        self.db.add(task)
                    await self.db.flush()
            
            # Now assign tasks to team members
            if team_members:
                # Get unassigned tasks
                result = await self.db.execute(
                    select(Task).where(
                        Task.project_id.in_([p.id for p in projects]),
                        Task.employee_id.is_(None),
                        Task.status == "pending"
                    )
                )
                unassigned_tasks = result.scalars().all()
                
                unassigned_list = list(unassigned_tasks)
                for member in team_members[:2]:  # Assign to up to 2 members
                    if member.current_task_id is None and unassigned_list:
                        task = random.choice(unassigned_list)
                        task.employee_id = member.id
                        task.status = "in_progress"
                        member.current_task_id = task.id
                        unassigned_list.remove(task)
                        
                        # Update project activity and activate if in planning
                        await project_manager.update_project_activity(task.project_id)
                        result = await self.db.execute(
                            select(Project).where(Project.id == task.project_id)
                        )
                        project = result.scalar_one_or_none()
                        if project and project.status == "planning":
                            project.status = "active"

class EmployeeAgentBase(EmployeeAgent):
    """Regular employee decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        decision = await super().evaluate_situation(business_context)
        decision["action_type"] = "operational"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # Employees work on their current task (make progress)
        if self.employee.current_task_id:
            await self._work_on_task(decision)
        
        return activity
    
    async def _work_on_task(self, decision: Dict):
        """Work on current task, making progress based on AI decision."""
        from sqlalchemy import select
        
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            task = result.scalar_one_or_none()
            
            if task and task.status != "completed":
                # Determine work amount based on decision quality and employee role
                base_progress = 5.0  # Base 5% per work session
                
                # Managers work faster
                if self.employee.role == "Manager":
                    base_progress *= 1.5
                elif self.employee.role == "CEO":
                    base_progress *= 2.0
                
                # Add some randomness
                progress_increment = base_progress * random.uniform(0.8, 1.2)
                
                # Initialize progress if needed
                if task.progress is None:
                    task.progress = 0.0
                
                # Increment progress
                task.progress = min(100.0, (task.progress or 0.0) + progress_increment)
                
                # Set status to in_progress if not already
                if task.status == "pending":
                    task.status = "in_progress"
                
                # Complete task if progress reaches 100%
                if task.progress >= 100.0:
                    await self._complete_current_task()
    
    async def _complete_current_task(self):
        """Complete the current task."""
        from sqlalchemy import select
        from datetime import datetime
        
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            task = result.scalar_one_or_none()
            
            if task and task.status != "completed":
                task.status = "completed"
                task.progress = 100.0
                task.completed_at = datetime.utcnow()
                self.employee.current_task_id = None
                
                # Update project progress
                if task.project_id:
                    from business.project_manager import ProjectManager
                    project_manager = ProjectManager(self.db)
                    
                    result = await self.db.execute(
                        select(Project).where(Project.id == task.project_id)
                    )
                    project = result.scalar_one_or_none()
                    if project:
                        # Update project activity and activate if in planning
                        await project_manager.update_project_activity(project.id)
                        if project.status == "planning":
                            project.status = "active"
                        
                        
                        # Check if all tasks are completed
                        result = await self.db.execute(
                            select(Task).where(
                                Task.project_id == project.id,
                                Task.status != "completed"
                            )
                        )
                        remaining_tasks = result.scalars().all()
                        if not remaining_tasks:
                            project.status = "completed"

def create_employee_agent(employee: Employee, db: AsyncSession, llm_client: OllamaClient) -> EmployeeAgent:
    """Factory function to create appropriate agent based on role."""
    if employee.role == "CEO":
        return CEOAgent(employee, db, llm_client)
    elif employee.role == "Manager":
        return ManagerAgent(employee, db, llm_client)
    else:
        return EmployeeAgentBase(employee, db, llm_client)

