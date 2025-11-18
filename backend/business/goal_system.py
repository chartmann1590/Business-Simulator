from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BusinessMetric, BusinessGoal, Employee, Project, CustomerReview
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from config import now as local_now

class GoalSystem:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.financial_manager = FinancialManager(db)
        self.project_manager = ProjectManager(db)
    
    async def get_business_goals(self) -> List[str]:
        """Get current business goals from database."""
        # Clean up duplicates first
        await self.cleanup_duplicate_goals()
        
        result = await self.db.execute(
            select(BusinessGoal)
            .where(BusinessGoal.is_active == True)
            .order_by(BusinessGoal.last_updated_date.desc(), BusinessGoal.id)
        )
        goals = result.scalars().all()
        
        if not goals:
            # If no goals exist, generate initial goals
            await self.generate_daily_goals()
            result = await self.db.execute(
                select(BusinessGoal)
                .where(BusinessGoal.is_active == True)
                .order_by(BusinessGoal.last_updated_date.desc(), BusinessGoal.id)
            )
            goals = result.scalars().all()
        
        # Ensure uniqueness by goal_key (keep first occurrence)
        seen_keys = set()
        unique_goals = []
        for goal in goals:
            goal_key = goal.goal_key or f"goal_{goal.id}"
            if goal_key not in seen_keys:
                seen_keys.add(goal_key)
                unique_goals.append(goal)
        
        return [goal.goal_text for goal in unique_goals]
    
    async def get_business_goals_with_keys(self) -> List[Dict]:
        """Get current business goals with their keys from database."""
        # Clean up duplicates first
        await self.cleanup_duplicate_goals()
        
        result = await self.db.execute(
            select(BusinessGoal)
            .where(BusinessGoal.is_active == True)
            .order_by(BusinessGoal.last_updated_date.desc(), BusinessGoal.id)
        )
        goals = result.scalars().all()
        
        if not goals:
            # If no goals exist, generate initial goals
            await self.generate_daily_goals()
            result = await self.db.execute(
                select(BusinessGoal)
                .where(BusinessGoal.is_active == True)
                .order_by(BusinessGoal.last_updated_date.desc(), BusinessGoal.id)
            )
            goals = result.scalars().all()
        
        # Ensure uniqueness by goal_key (keep first occurrence)
        seen_keys = set()
        unique_goals = []
        for goal in goals:
            goal_key = goal.goal_key or f"goal_{goal.id}"
            if goal_key not in seen_keys:
                seen_keys.add(goal_key)
                unique_goals.append(goal)
        
        return [{"text": goal.goal_text, "key": goal.goal_key or f"goal_{goal.id}"} for goal in unique_goals]
    
    async def should_update_goals_today(self) -> bool:
        """Check if goals need to be updated today."""
        from datetime import date
        
        # Check if there are any active goals first
        result = await self.db.execute(
            select(BusinessGoal).where(BusinessGoal.is_active == True)
        )
        active_goals = result.scalars().all()
        
        if not active_goals:
            return True  # No active goals exist, need to create them
        
        # Get the most recent goal update date from active goals only
        result = await self.db.execute(
            select(func.max(BusinessGoal.last_updated_date))
            .where(BusinessGoal.is_active == True)
        )
        last_update_date = result.scalar()
        
        if last_update_date is None:
            return True  # No update date found, need to update
        
        # Convert to date (remove time component)
        if isinstance(last_update_date, datetime):
            last_update = last_update_date.date()
        else:
            last_update = last_update_date
        
        today = date.today()
        return last_update < today
    
    async def cleanup_duplicate_goals(self, commit: bool = True):
        """Remove duplicate active goals, keeping only the most recent ones."""
        # Get all active goals grouped by goal_key
        result = await self.db.execute(
            select(BusinessGoal)
            .where(BusinessGoal.is_active == True)
            .order_by(BusinessGoal.last_updated_date.desc(), BusinessGoal.id.desc())
        )
        all_active_goals = result.scalars().all()
        
        # Track seen goal_keys and deactivate duplicates
        seen_keys = {}
        duplicates_found = 0
        
        for goal in all_active_goals:
            goal_key = goal.goal_key or f"goal_{goal.id}"
            if goal_key in seen_keys:
                # This is a duplicate - deactivate it
                goal.is_active = False
                duplicates_found += 1
            else:
                seen_keys[goal_key] = goal
        
        if duplicates_found > 0:
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
            print(f"🧹 Cleaned up {duplicates_found} duplicate active goals")
        
        return duplicates_found
    
    async def generate_daily_goals(self):
        """Generate or update business goals based on current business metrics."""
        from datetime import date
        
        # First, clean up any duplicate active goals (don't commit yet, we'll commit at the end)
        await self.cleanup_duplicate_goals(commit=False)
        
        # Get current business metrics
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        active_projects = await self.project_manager.get_active_projects()
        active_projects_count = len(active_projects)
        
        # Get employee count
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Get completed projects this quarter
        quarter_start = local_now() - timedelta(days=90)
        result = await self.db.execute(
            select(Project)
            .where(
                Project.status == "completed",
                Project.completed_at >= quarter_start
            )
        )
        completed_projects_quarter = len(list(result.scalars().all()))
        
        # Get average customer review rating
        result = await self.db.execute(
            select(func.avg(CustomerReview.rating))
        )
        avg_rating = result.scalar() or 0.0
        
        # Calculate revenue growth target (15% increase from current)
        revenue_target = revenue * 1.15
        
        # Generate dynamic goals based on current metrics
        goals_data = []
        
        # Revenue goal - adjust based on current revenue
        if revenue > 0:
            growth_percent = 15
            if revenue > 1000000:
                growth_percent = 10  # Lower growth target for larger companies
            elif revenue < 100000:
                growth_percent = 25  # Higher growth target for smaller companies
            goals_data.append({
                "goal_text": f"Increase monthly revenue by {growth_percent}%",
                "goal_key": "revenue_growth"
            })
        else:
            goals_data.append({
                "goal_text": "Establish revenue stream and secure first client",
                "goal_key": "revenue_growth"
            })
        
        # Profitability goal - adjust threshold based on current margin
        if profit_margin > 0:
            target_margin = max(20, int(profit_margin * 0.9))  # Aim for at least 90% of current or 20%
            goals_data.append({
                "goal_text": f"Maintain profitability above {target_margin}%",
                "goal_key": "profitability"
            })
        else:
            goals_data.append({
                "goal_text": "Achieve positive profitability",
                "goal_key": "profitability"
            })
        
        # Project completion goal - adjust based on current activity
        if completed_projects_quarter >= 3:
            target_projects = completed_projects_quarter + 1
        else:
            target_projects = max(3, completed_projects_quarter + 1)
        goals_data.append({
            "goal_text": f"Complete {target_projects}+ projects per quarter",
            "goal_key": "project_completion"
        })
        
        # Team expansion goal - adjust based on current team size
        if employee_count < 50:
            goals_data.append({
                "goal_text": "Expand team capabilities and hire key talent",
                "goal_key": "team_expansion"
            })
        elif employee_count < 100:
            goals_data.append({
                "goal_text": "Optimize team structure and improve efficiency",
                "goal_key": "team_expansion"
            })
        else:
            goals_data.append({
                "goal_text": "Maintain team excellence and develop leadership",
                "goal_key": "team_expansion"
            })
        
        # Customer satisfaction goal - adjust based on current ratings
        if avg_rating >= 4.5:
            goals_data.append({
                "goal_text": "Maintain exceptional customer satisfaction (4.5+ rating)",
                "goal_key": "customer_satisfaction"
            })
        elif avg_rating >= 4.0:
            goals_data.append({
                "goal_text": "Improve customer satisfaction to 4.5+ rating",
                "goal_key": "customer_satisfaction"
            })
        else:
            goals_data.append({
                "goal_text": "Improve customer satisfaction and service quality",
                "goal_key": "customer_satisfaction"
            })
        
        # Deactivate old goals first
        today = local_now().date()
        result = await self.db.execute(
            select(BusinessGoal).where(BusinessGoal.is_active == True)
        )
        old_goals = result.scalars().all()
        for old_goal in old_goals:
            old_goal.is_active = False
        
        # Flush to ensure deactivation is saved before creating new goals
        await self.db.flush()
        
        # Create new goals
        for goal_data in goals_data:
            new_goal = BusinessGoal(
                goal_text=goal_data["goal_text"],
                goal_key=goal_data["goal_key"],
                is_active=True,
                last_updated_date=local_now().replace(hour=0, minute=0, second=0, microsecond=0)
            )
            self.db.add(new_goal)
        
        await self.db.commit()
        print(f"✅ Updated business goals for {today} - deactivated {len(old_goals)} old goals, created {len(goals_data)} new goals")
    
    async def evaluate_goals(self) -> Dict[str, bool]:
        """Evaluate progress towards goals."""
        # Get active goals from database
        result = await self.db.execute(
            select(BusinessGoal)
            .where(BusinessGoal.is_active == True)
        )
        active_goals = result.scalars().all()
        
        if not active_goals:
            return {}
        
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get completed projects this quarter
        quarter_start = local_now() - timedelta(days=90)
        result = await self.db.execute(
            select(Project)
            .where(
                Project.status == "completed",
                Project.completed_at >= quarter_start
            )
        )
        completed_projects_quarter = len(list(result.scalars().all()))
        
        # Get average customer review rating
        result = await self.db.execute(
            select(func.avg(CustomerReview.rating))
        )
        avg_rating = result.scalar() or 0.0
        
        # Get employee count
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employee_count = len(list(result.scalars().all()))
        
        # Evaluate each goal based on its goal_key
        goal_progress = {}
        for goal in active_goals:
            goal_key = goal.goal_key or f"goal_{goal.id}"
            
            if goal_key == "revenue_growth":
                # Revenue growth: check if revenue is increasing
                goal_progress[goal_key] = revenue > 0
            elif goal_key == "profitability":
                # Profitability: check if profit margin meets threshold
                # Extract target from goal text or use default
                target_margin = 20
                if "above" in goal.goal_text.lower():
                    try:
                        # Try to extract number from goal text like "Maintain profitability above 20%"
                        import re
                        match = re.search(r'above\s+(\d+)', goal.goal_text.lower())
                        if match:
                            target_margin = int(match.group(1))
                    except:
                        pass
                goal_progress[goal_key] = profit_margin >= target_margin
            elif goal_key == "project_completion":
                # Project completion: check if target is met
                target_projects = 3
                try:
                    import re
                    match = re.search(r'(\d+)\+', goal.goal_text)
                    if match:
                        target_projects = int(match.group(1))
                except:
                    pass
                goal_progress[goal_key] = completed_projects_quarter >= target_projects
            elif goal_key == "team_expansion":
                # Team expansion: check if team is growing or optimized
                goal_progress[goal_key] = employee_count > 0  # Basic check
            elif goal_key == "customer_satisfaction":
                # Customer satisfaction: check if rating meets target
                target_rating = 4.0
                if "4.5" in goal.goal_text:
                    target_rating = 4.5
                goal_progress[goal_key] = avg_rating >= target_rating
            else:
                # Default: mark as in progress
                goal_progress[goal_key] = False
        
        return goal_progress
    
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
                        
                        time_since_hire = local_now() - hired_at_naive
                        if time_since_hire <= timedelta(hours=1):
                            is_in_training = True
                    except Exception:
                        pass
                
                if not is_in_training:
                    idle_employees.append(employee)
        
        # PRIORITY: Sort tasks by: 1) Project priority (high > medium > low), 2) Revenue, 3) Progress
        # This ensures we focus on high-priority, high-revenue projects first
        from sqlalchemy import select
        from database.models import Project
        
        task_priorities = []
        priority_weights = {"high": 3, "medium": 2, "low": 1}
        
        for task in unassigned_list:
            if task.project_id:
                result = await self.db.execute(
                    select(Project).where(Project.id == task.project_id)
                )
                project = result.scalar_one_or_none()
                
                if project:
                    project_progress = await self.project_manager.calculate_project_progress(task.project_id)
                    priority_weight = priority_weights.get(project.priority, 1)
                    revenue = project.revenue or 0.0
                    
                    # Calculate priority score: priority (0-3) * 1000 + revenue + progress
                    # This ensures high-priority projects always come first, then by revenue, then by progress
                    priority_score = (priority_weight * 1000) + (revenue / 1000) + project_progress
                    task_priorities.append((task, priority_score, project.priority, revenue, project_progress))
                else:
                    task_priorities.append((task, 0.0, "low", 0.0, 0.0))
            else:
                task_priorities.append((task, 0.0, "low", 0.0, 0.0))
        
        # Sort by priority score (descending) - high-priority, high-revenue projects get priority
        task_priorities.sort(key=lambda x: x[1], reverse=True)
        prioritized_tasks = [task for task, _, _, _, _ in task_priorities]
        
        # Assign tasks to idle employees (prioritizing high-priority, high-revenue projects)
        for employee in idle_employees:
            if prioritized_tasks:
                # Take highest priority task (from highest priority, highest revenue project)
                task = prioritized_tasks[0]
                task.employee_id = employee.id
                task.status = "in_progress"
                employee.current_task_id = task.id
                prioritized_tasks.remove(task)
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


