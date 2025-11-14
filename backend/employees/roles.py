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
        """Create a new strategic project. If capacity is low, trigger hiring instead of deferring."""
        from business.project_manager import ProjectManager
        from database.models import Activity, Employee
        from sqlalchemy import select
        import random
        project_manager = ProjectManager(self.db)
        
        # Check capacity before creating project
        can_create, reason = await project_manager.check_capacity_for_new_project()
        
        if not can_create:
            # Instead of deferring, trigger hiring initiative!
            # Get current employee count
            result = await self.db.execute(
                select(Employee).where(Employee.status == "active")
            )
            active_employees = result.scalars().all()
            employee_count = len(active_employees)
            
            # Get active projects to calculate needed employees
            active_projects = await project_manager.get_active_projects()
            project_count = len(active_projects)
            
            # Calculate how many employees we need (3 per project)
            employees_needed = project_count * 3
            employees_short = max(0, employees_needed - employee_count)
            
            # Log that we're hiring to support projects
            activity = Activity(
                employee_id=self.employee.id,
                activity_type="decision",
                description=f"{self.employee.name} decided to hire {employees_short} new employee(s) to support {project_count} active projects. New project will proceed once team is expanded.",
                activity_metadata={
                    "decision_type": "strategic",
                    "action": "hiring_initiative",
                    "reason": reason,
                    "employees_needed": employees_short,
                    "current_projects": project_count
                }
            )
            self.db.add(activity)
            print(f"CEO triggered hiring initiative: Need {employees_short} employees for {project_count} projects")
            
            # Note: Actual hiring will happen in the simulator's _manage_employees method
            # We'll still create the project - hiring will catch up!
        
        # Create the project anyway - we'll hire to support it!
        
        project_names = [
            "Market Expansion Initiative",
            "Product Innovation Program",
            "Customer Experience Enhancement",
            "Digital Transformation Project",
            "Strategic Partnership Development"
        ]
        
        project_name = random.choice(project_names)
        project = await project_manager.create_project(
            name=project_name,
            description=f"Strategic project initiated by {self.employee.name}: {decision.get('decision', '')}",
            priority="high",
            budget=random.uniform(50000, 200000)
        )
        
        # Log project creation
        activity = Activity(
            employee_id=self.employee.id,
            activity_type="project_created",
            description=f"{self.employee.name} created new strategic project: {project_name}",
            activity_metadata={
                "project_id": project.id,
                "project_name": project_name,
                "decision_type": "strategic"
            }
        )
        self.db.add(activity)

class ManagerAgent(EmployeeAgent):
    """Manager-specific decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        decision = await super().evaluate_situation(business_context)
        decision["action_type"] = "tactical"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # Managers automatically assign tasks (80% chance per tick)
        # Managers should frequently assign tasks to keep teams working
        if random.random() < 0.8:  # 80% chance to assign tasks
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
                            priority=project.priority,
                            progress=0.0  # Initialize with 0% progress
                        )
                        self.db.add(task)
                    await self.db.flush()
            
            # Now assign tasks to team members - ensure all available employees get tasks
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
                # Assign tasks to ALL team members who don't have a task (not just 2)
                # This ensures teams are always working on projects
                for member in team_members:
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
        from database.models import Activity
        
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
                
                # Create activity for task completion
                task_activity = Activity(
                    employee_id=self.employee.id,
                    activity_type="task_completed",
                    description=f"{self.employee.name} completed task: {task.description}",
                    activity_metadata={
                        "task_id": task.id,
                        "task_description": task.description
                    }
                )
                self.db.add(task_activity)
                
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
                            
                            # Create activity for project activation
                            activation_activity = Activity(
                                employee_id=self.employee.id,
                                activity_type="project_activated",
                                description=f"Project '{project.name}' has been activated",
                                activity_metadata={
                                    "project_id": project.id,
                                    "project_name": project.name
                                }
                            )
                            self.db.add(activation_activity)
                        
                        
                        # Check if all tasks are completed AND at 100% progress
                        result = await self.db.execute(
                            select(Task).where(
                                Task.project_id == project.id,
                                Task.status != "completed"
                            )
                        )
                        remaining_tasks = result.scalars().all()
                        
                        # Also check if all completed tasks are at 100% progress
                        all_tasks_result = await self.db.execute(
                            select(Task).where(Task.project_id == project.id)
                        )
                        all_tasks = all_tasks_result.scalars().all()
                        
                        # Check if all tasks are completed and at 100% progress
                        all_tasks_completed = not remaining_tasks
                        all_tasks_at_100_percent = all(
                            task.status == "completed" and 
                            (task.progress is not None and task.progress >= 100.0)
                            for task in all_tasks
                        ) if all_tasks else False
                        
                        # Also check project-level progress
                        project_progress = await project_manager.calculate_project_progress(project.id)
                        project_at_100_percent = project_progress >= 100.0
                        
                        # Only mark as completed if all conditions are met
                        if all_tasks_completed and all_tasks_at_100_percent and project_at_100_percent:
                            project.status = "completed"
                            project.completed_at = datetime.utcnow()
                            
                            # Create activity for project completion
                            activity = Activity(
                                employee_id=self.employee.id,
                                activity_type="project_completed",
                                description=f"Project '{project.name}' has been completed (100% progress)",
                                activity_metadata={
                                    "project_id": project.id,
                                    "project_name": project.name,
                                    "completed_tasks": len(list(all_tasks)),
                                    "project_progress": project_progress
                                }
                            )
                            self.db.add(activity)

def create_employee_agent(employee: Employee, db: AsyncSession, llm_client: OllamaClient) -> EmployeeAgent:
    """Factory function to create appropriate agent based on role."""
    if employee.role == "CEO":
        return CEOAgent(employee, db, llm_client)
    elif employee.role == "Manager":
        return ManagerAgent(employee, db, llm_client)
    else:
        return EmployeeAgentBase(employee, db, llm_client)

