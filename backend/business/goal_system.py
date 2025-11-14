from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BusinessMetric
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from sqlalchemy import select

class GoalSystem:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.financial_manager = FinancialManager(db)
        self.project_manager = ProjectManager(db)
    
    async def get_business_goals(self) -> List[str]:
        """Get current business goals."""
        return [
            "Increase monthly revenue by 15%",
            "Maintain profitability above 20%",
            "Complete 3+ projects per quarter",
            "Expand team capabilities",
            "Improve customer satisfaction"
        ]
    
    async def evaluate_goals(self) -> Dict[str, bool]:
        """Evaluate progress towards goals."""
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        active_projects = await self.project_manager.get_active_projects()
        completed_projects = await self._get_completed_projects_count()
        
        return {
            "revenue_growth": revenue > 0,
            "profitability": profit_margin >= 20,
            "project_completion": completed_projects >= 3,
            "team_expansion": True,  # Placeholder
            "customer_satisfaction": True  # Placeholder
        }
    
    async def _get_completed_projects_count(self) -> int:
        """Get count of completed projects."""
        from database.models import Project
        result = await self.db.execute(
            select(Project).where(Project.status == "completed")
        )
        return len(list(result.scalars().all()))
    
    async def update_metrics(self):
        """Update business metrics including workload statistics."""
        from database.models import Employee, Task
        
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        active_projects = await self.project_manager.get_active_projects()
        active_projects_count = len(active_projects)
        
        # Get employee statistics
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Count employees with tasks
        employees_with_tasks = sum(1 for e in active_employees if e.current_task_id is not None)
        employees_idle = employee_count - employees_with_tasks
        
        # Count unassigned tasks
        result = await self.db.execute(
            select(Task).where(
                Task.employee_id.is_(None),
                Task.status.in_(["pending", "in_progress"])
            )
        )
        unassigned_tasks = result.scalars().all()
        unassigned_count = len(unassigned_tasks)
        
        # Calculate workload metrics
        workload_ratio = employees_with_tasks / max(1, employee_count)  # % of employees working
        max_projects = max(1, int(employee_count / 3))
        capacity_utilization = active_projects_count / max(1, max_projects)  # % of capacity used
        tasks_per_employee = unassigned_count / max(1, employee_count)
        
        metrics = [
            BusinessMetric(metric_name="total_revenue", value=revenue),
            BusinessMetric(metric_name="total_profit", value=profit),
            BusinessMetric(metric_name="active_projects", value=active_projects_count),
            BusinessMetric(metric_name="active_employees", value=employee_count),
            BusinessMetric(metric_name="employees_with_tasks", value=employees_with_tasks),
            BusinessMetric(metric_name="employees_idle", value=employees_idle),
            BusinessMetric(metric_name="unassigned_tasks", value=unassigned_count),
            BusinessMetric(metric_name="workload_ratio", value=workload_ratio * 100),  # As percentage
            BusinessMetric(metric_name="capacity_utilization", value=capacity_utilization * 100),  # As percentage
            BusinessMetric(metric_name="tasks_per_employee", value=tasks_per_employee)
        ]
        
        for metric in metrics:
            self.db.add(metric)
        
        await self.db.flush()
        
        # Log workload status if there are issues
        if workload_ratio < 0.7:  # Less than 70% of employees working
            print(f"⚠️  WORKLOAD WARNING: Only {workload_ratio:.1%} of employees have tasks ({employees_with_tasks}/{employee_count})")
        if capacity_utilization < 0.5:  # Using less than 50% of capacity
            print(f"⚠️  CAPACITY WARNING: Only {capacity_utilization:.1%} capacity utilized ({active_projects_count}/{max_projects} projects)")
        if unassigned_count > employee_count * 2:  # Too many unassigned tasks
            print(f"⚠️  TASK OVERLOAD: {unassigned_count} unassigned tasks for {employee_count} employees")
        
        # Emergency task assignment if severe overload detected
        if tasks_per_employee > 3.0 or (workload_ratio < 0.5 and unassigned_count > 0):
            await self._emergency_task_assignment(unassigned_tasks, active_employees)
    
    async def _emergency_task_assignment(self, unassigned_tasks: list, active_employees: list):
        """Emergency task assignment when there's severe overload."""
        from database.models import Task, Project
        from datetime import datetime, timedelta
        from employees.room_assigner import ROOM_TRAINING_ROOM
        import random
        
        unassigned_list = list(unassigned_tasks)
        assigned_count = 0
        
        # Get all idle employees (not in training)
        idle_employees = []
        for employee in active_employees:
            if employee.current_task_id is None:
                # Check if in training
                is_in_training = False
                
                if hasattr(employee, 'activity_state') and employee.activity_state == "training":
                    is_in_training = True
                
                current_room = getattr(employee, 'current_room', None)
                if (current_room == ROOM_TRAINING_ROOM or 
                    current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4_5"):
                    is_in_training = True
                
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
                
                if not is_in_training:
                    idle_employees.append(employee)
        
        # Assign tasks to idle employees
        for employee in idle_employees:
            if unassigned_list:
                task = random.choice(unassigned_list)
                task.employee_id = employee.id
                task.status = "in_progress"
                employee.current_task_id = task.id
                unassigned_list.remove(task)
                assigned_count += 1
                
                # Update project activity
                if task.project_id:
                    await self.project_manager.update_project_activity(task.project_id)
                    result = await self.db.execute(
                        select(Project).where(Project.id == task.project_id)
                    )
                    project = result.scalar_one_or_none()
                    if project and project.status == "planning":
                        project.status = "active"
        
        if assigned_count > 0:
            print(f"🚨 EMERGENCY: Assigned {assigned_count} tasks to idle employees")


