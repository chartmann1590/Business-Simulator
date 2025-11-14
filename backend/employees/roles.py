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
        # CEO makes strategic decisions focused on business success and profitability
        # Add profitability and business metrics to context for decision-making
        from business.financial_manager import FinancialManager
        financial_manager = FinancialManager(self.db)
        
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Enhance business context with profitability focus
        enhanced_context = business_context.copy()
        enhanced_context["profit"] = profit
        enhanced_context["revenue"] = revenue
        enhanced_context["profit_margin"] = profit_margin
        enhanced_context["focus"] = "profitability and business success"
        
        decision = await super().evaluate_situation(enhanced_context)
        decision["action_type"] = "strategic"
        decision["business_focus"] = "profitability"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # CEO can create new projects
        # Also proactively create projects when there's capacity
        should_create_project = False
        
        # Check if decision mentions new project
        if "new project" in decision.get("decision", "").lower() or "launch" in decision.get("decision", "").lower():
            should_create_project = True
        
        # Proactively create projects when we have capacity and need workload
        if not should_create_project:
            from business.project_manager import ProjectManager
            from sqlalchemy import select
            project_manager = ProjectManager(self.db)
            
            # Check current capacity
            can_create, reason = await project_manager.check_capacity_for_new_project()
            active_projects = await project_manager.get_active_projects()
            project_count = len(active_projects)
            
            # Get employee count
            result = await self.db.execute(
                select(Employee).where(Employee.status == "active")
            )
            active_employees = result.scalars().all()
            employee_count = len(active_employees)
            max_projects = max(1, int(employee_count / 3))
            
            # CEO focuses on profitable projects and business success
            # Check profitability before creating projects
            from business.financial_manager import FinancialManager
            financial_manager = FinancialManager(self.db)
            profit = await financial_manager.get_profit()
            revenue = await financial_manager.get_total_revenue()
            profit_margin = (profit / revenue * 100) if revenue > 0 else 0
            
            # If we have capacity and not many projects, create one proactively
            # But prioritize profitability - if profit margin is low, be more selective
            if can_create and project_count < max_projects * 0.8:  # Using less than 80% of capacity
                # Higher chance to create projects if profitable, lower if not
                if profit_margin > 20:
                    create_chance = 0.5  # 50% chance if very profitable
                elif profit_margin > 10:
                    create_chance = 0.4  # 40% chance if moderately profitable
                elif profit > 0:
                    create_chance = 0.3  # 30% chance if barely profitable
                else:
                    create_chance = 0.2  # 20% chance if losing money - focus on existing projects
                
                if random.random() < create_chance:
                    should_create_project = True
                    print(f"CEO proactively creating project (focus on profitability): {project_count}/{max_projects} projects, {employee_count} employees, profit margin: {profit_margin:.1f}%")
        
        if should_create_project:
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
        # Managers make tactical decisions focused on business operations and success
        # Add profitability and operational metrics to context
        from business.financial_manager import FinancialManager
        financial_manager = FinancialManager(self.db)
        
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Enhance business context with operational focus
        enhanced_context = business_context.copy()
        enhanced_context["profit"] = profit
        enhanced_context["revenue"] = revenue
        enhanced_context["profit_margin"] = profit_margin
        enhanced_context["focus"] = "business operations and profitability"
        
        decision = await super().evaluate_situation(enhanced_context)
        decision["action_type"] = "tactical"
        decision["business_focus"] = "operations"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # Managers focus on business operations: task assignment AND business decisions
        # Check for task overload - if severe, always assign tasks
        from sqlalchemy import select
        from database.models import Task, Employee
        
        result = await self.db.execute(
            select(Task).where(
                Task.employee_id.is_(None),
                Task.status.in_(["pending", "in_progress"])
            )
        )
        unassigned_count = len(list(result.scalars().all()))
        
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employee_count = len(list(result.scalars().all()))
        
        # Calculate task overload ratio
        tasks_per_employee = unassigned_count / max(1, employee_count)
        
        # Always assign tasks if there's significant overload (>2 tasks per employee)
        # Otherwise, 95% chance (increased from 70% to ensure better coverage)
        should_assign = tasks_per_employee > 2.0 or random.random() < 0.95
        
        if should_assign:
            await self._assign_tasks()
        
        # Managers also focus on business success and profitability
        if random.random() < 0.5:  # 50% chance to make business-focused decisions
            await self._focus_on_business_operations(business_context)
        
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
                # Get unassigned tasks from ALL projects (not just manager's department)
                # This ensures we can assign tasks across departments if needed
                result = await self.db.execute(
                    select(Task).where(
                        Task.employee_id.is_(None),
                        Task.status == "pending"
                    )
                )
                unassigned_tasks = result.scalars().all()
                
                # If no unassigned tasks but we have employees without tasks, create more tasks
                if not unassigned_tasks:
                    # Create additional tasks for active projects to ensure workload
                    for project in projects:
                        if project.status in ["planning", "active"]:
                            # Create 1-2 more tasks per project if employees are idle
                            idle_count = sum(1 for m in team_members if m.current_task_id is None)
                            if idle_count > 0:
                                task_descriptions = [
                                    f"Additional work on {project.name}",
                                    f"Follow-up tasks for {project.name}",
                                    f"Quality assurance for {project.name}",
                                    f"Documentation for {project.name}",
                                    f"Optimization for {project.name}"
                                ]
                                num_new_tasks = min(idle_count, random.randint(1, 2))
                                for i in range(num_new_tasks):
                                    task = Task(
                                        employee_id=None,
                                        project_id=project.id,
                                        description=random.choice(task_descriptions),
                                        status="pending",
                                        priority=project.priority,
                                        progress=0.0
                                    )
                                    self.db.add(task)
                                await self.db.flush()
                                
                                # Re-fetch unassigned tasks
                                result = await self.db.execute(
                                    select(Task).where(
                                        Task.employee_id.is_(None),
                                        Task.status == "pending"
                                    )
                                )
                                unassigned_tasks = result.scalars().all()
                                break  # Created tasks, now assign them
                
                unassigned_list = list(unassigned_tasks)
                # Assign tasks to ALL team members who don't have a task
                # IMPORTANT: Do NOT assign tasks to employees who are still in training
                assigned_count = 0
                from datetime import datetime, timedelta
                from employees.room_assigner import ROOM_TRAINING_ROOM
                
                for member in team_members:
                    # Skip employees who are in training
                    is_in_training = False
                    
                    # Check if activity_state is "training"
                    if hasattr(member, 'activity_state') and member.activity_state == "training":
                        is_in_training = True
                    
                    # Check if they're in any training room (floors 1, 2, or 4)
                    current_room = getattr(member, 'current_room', None)
                    if (current_room == ROOM_TRAINING_ROOM or 
                        current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                        current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                        current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                        current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                        current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                        current_room == f"{ROOM_TRAINING_ROOM}_floor4_5"):
                        is_in_training = True
                    
                    # Check if they were hired recently (within last hour = still in training)
                    hired_at = getattr(member, 'hired_at', None)
                    if hired_at:
                        try:
                            if hasattr(hired_at, 'replace'):
                                if hired_at.tzinfo is not None:
                                    hired_at_naive = hired_at.replace(tzinfo=None)
                                else:
                                    hired_at_naive = hired_at
                            else:
                                hired_at_naive = hired_at
                            
                            time_since_hire = datetime.utcnow() - hired_at_naive
                            if time_since_hire <= timedelta(hours=1):
                                is_in_training = True
                        except Exception:
                            pass
                    
                    # Only assign tasks if not in training and doesn't have a task
                    if not is_in_training and member.current_task_id is None and unassigned_list:
                        task = random.choice(unassigned_list)
                        task.employee_id = member.id
                        task.status = "in_progress"
                        member.current_task_id = task.id
                        unassigned_list.remove(task)
                        assigned_count += 1
                        
                        # Update project activity and activate if in planning
                        await project_manager.update_project_activity(task.project_id)
                        result = await self.db.execute(
                            select(Project).where(Project.id == task.project_id)
                        )
                        project = result.scalar_one_or_none()
                        if project and project.status == "planning":
                            project.status = "active"
                
                # Also assign tasks to employees outside this manager's department if they're idle
                # IMPORTANT: Do NOT assign tasks to employees who are still in training
                # This ensures all employees are working (except those in training)
                if unassigned_list:
                    result = await self.db.execute(
                        select(Employee).where(
                            Employee.status == "active",
                            Employee.current_task_id.is_(None),
                            Employee.id.notin_([m.id for m in team_members])
                        )
                    )
                    other_idle_employees = result.scalars().all()
                    
                    for employee in other_idle_employees[:min(len(other_idle_employees), len(unassigned_list))]:
                        # Skip employees who are in training
                        is_in_training = False
                        
                        # Check if activity_state is "training"
                        if hasattr(employee, 'activity_state') and employee.activity_state == "training":
                            is_in_training = True
                        
                        # Check if they're in any training room (floors 1, 2, or 4)
                        current_room = getattr(employee, 'current_room', None)
                        if (current_room == ROOM_TRAINING_ROOM or 
                            current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_5"):
                            is_in_training = True
                        
                        # Check if they were hired recently (within last hour = still in training)
                        hired_at = getattr(employee, 'hired_at', None)
                        if hired_at:
                            try:
                                if hasattr(hired_at, 'replace'):
                                    if hired_at.tzinfo is not None:
                                        hired_at_naive = hired_at.replace(tzinfo=None)
                                    else:
                                        hired_at_naive = hired_at
                                else:
                                    hired_at_naive = hired_at
                                
                                time_since_hire = datetime.utcnow() - hired_at_naive
                                if time_since_hire <= timedelta(hours=1):
                                    is_in_training = True
                            except Exception:
                                pass
                        
                        # Only assign tasks if not in training
                        if not is_in_training and unassigned_list:
                            task = random.choice(unassigned_list)
                            task.employee_id = employee.id
                            task.status = "in_progress"
                            employee.current_task_id = task.id
                            unassigned_list.remove(task)
                            assigned_count += 1
                            
                            await project_manager.update_project_activity(task.project_id)
                            result = await self.db.execute(
                                select(Project).where(Project.id == task.project_id)
                            )
                            project = result.scalar_one_or_none()
                            if project and project.status == "planning":
                                project.status = "active"
                
                if assigned_count > 0:
                    print(f"Manager {self.employee.name} assigned {assigned_count} task(s) to ensure workload")
    
    async def _focus_on_business_operations(self, business_context: Dict):
        """Managers focus on business operations, profitability, and making everything work."""
        from business.financial_manager import FinancialManager
        from database.models import Activity
        from sqlalchemy import select
        import random
        
        financial_manager = FinancialManager(self.db)
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get project count and status
        from business.project_manager import ProjectManager
        project_manager = ProjectManager(self.db)
        active_projects = await project_manager.get_active_projects()
        project_count = len(active_projects)
        
        # Get employee count
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Managers make business-focused decisions
        business_actions = []
        
        # If profitability is low, focus on improving it
        if profit_margin < 15 and revenue > 0:
            business_actions.append("Reviewing operations to improve profitability")
            business_actions.append("Analyzing costs and revenue streams")
            business_actions.append("Identifying opportunities to increase profit margins")
        
        # If we have many employees but low revenue, focus on project efficiency
        if employee_count > 20 and revenue < employee_count * 5000:
            business_actions.append("Optimizing project allocation for better revenue")
            business_actions.append("Ensuring all employees are contributing to profitable work")
        
        # If we have many projects, focus on completion and quality
        if project_count > 10:
            business_actions.append("Prioritizing high-value projects for completion")
            business_actions.append("Ensuring project quality and timely delivery")
        
        # General business operations focus
        business_actions.extend([
            "Reviewing business operations and workflow efficiency",
            "Ensuring all systems are working smoothly",
            "Focusing on what's best for business success",
            "Optimizing resource allocation for maximum efficiency",
            "Making strategic decisions to improve business outcomes"
        ])
        
        if business_actions:
            action = random.choice(business_actions)
            activity = Activity(
                employee_id=self.employee.id,
                activity_type="business_operations",
                description=f"{self.employee.name} (Manager): {action}",
                activity_metadata={
                    "action_type": "business_focus",
                    "profit": profit,
                    "revenue": revenue,
                    "profit_margin": profit_margin,
                    "project_count": project_count,
                    "employee_count": employee_count
                }
            )
            self.db.add(activity)
            await self.db.flush()

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

