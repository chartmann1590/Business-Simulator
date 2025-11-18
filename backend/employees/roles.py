from .base import EmployeeAgent
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Task, Project
from llm.ollama_client import OllamaClient
from sqlalchemy import select
from config import now as local_now
import random

class CEOAgent(EmployeeAgent):
    """CEO-specific decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        # CEO makes strategic decisions focused on business success and profitability
        # Add profitability and business metrics to context for decision-making
        from business.financial_manager import FinancialManager
        from business.project_manager import ProjectManager
        from sqlalchemy import select
        
        financial_manager = FinancialManager(self.db)
        project_manager = ProjectManager(self.db)
        
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get project completion metrics
        active_projects = await project_manager.get_active_projects()
        result = await self.db.execute(
            select(Project).where(Project.status == "completed")
        )
        completed_projects = result.scalars().all()
        completed_count = len(completed_projects)
        
        # Check for stalled or near-completion projects
        stalled_count = 0
        near_completion_count = 0
        for project in active_projects:
            is_stalled = await project_manager.is_project_stalled(project.id)
            if is_stalled:
                stalled_count += 1
            else:
                progress = await project_manager.calculate_project_progress(project.id)
                if progress >= 75:
                    near_completion_count += 1
        
        # Enhance business context with profitability and project completion focus
        enhanced_context = business_context.copy()
        enhanced_context["profit"] = profit
        enhanced_context["revenue"] = revenue
        enhanced_context["profit_margin"] = profit_margin
        enhanced_context["active_projects"] = len(active_projects)
        enhanced_context["completed_projects"] = completed_count
        enhanced_context["stalled_projects"] = stalled_count
        enhanced_context["near_completion_projects"] = near_completion_count
        enhanced_context["focus"] = "profitability, project completion, and continuous growth"
        enhanced_context["priority"] = "Complete active projects and launch new ones to grow the company"
        
        decision = await super().evaluate_situation(enhanced_context)
        decision["action_type"] = "strategic"
        decision["business_focus"] = "profitability and growth through project completion"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # PRIORITY 1: Make strategic business decisions (increased frequency - 80% chance)
        if random.random() < 0.8:
            await self._make_strategic_business_decision(business_context)
        
        # PRIORITY 2: Check for recently completed projects and create new ones immediately
        await self._handle_project_completions()
        
        # PRIORITY 3: Monitor and focus on getting active projects completed
        await self._focus_on_project_completion()
        
        # PRIORITY 4: CEO can create new projects
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
                    create_chance = 0.6  # Increased from 50% to 60%
                elif profit_margin > 10:
                    create_chance = 0.5  # Increased from 40% to 50%
                elif profit > 0:
                    create_chance = 0.4  # Increased from 30% to 40%
                else:
                    create_chance = 0.3  # Increased from 20% to 30% - still focus on growth even when struggling
                
                if random.random() < create_chance:
                    should_create_project = True
                    print(f"CEO proactively creating project (focus on profitability): {project_count}/{max_projects} projects, {employee_count} employees, profit margin: {profit_margin:.1f}%")
        
        if should_create_project:
            await self._create_strategic_project(decision)
        
        return activity
    
    async def _handle_project_completions(self):
        """Check for recently completed projects and immediately create new ones to maintain growth."""
        from business.project_manager import ProjectManager
        from database.models import Activity
        from datetime import datetime, timedelta
        from config import now as local_now
        from sqlalchemy import select
        
        project_manager = ProjectManager(self.db)
        
        # Check for projects completed in the last hour (recently completed)
        cutoff_time = local_now() - timedelta(hours=1)
        result = await self.db.execute(
            select(Project).where(
                Project.status == "completed",
                Project.completed_at >= cutoff_time
            )
        )
        recently_completed = result.scalars().all()
        
        # For each recently completed project, create a new one to maintain growth
        for completed_project in recently_completed:
            # Check if we already created a replacement project for this one
            # (to avoid creating multiple projects for the same completion)
            result = await self.db.execute(
                select(Project).where(
                    Project.status.in_(["planning", "active"]),
                    Project.created_at >= completed_project.completed_at
                )
            )
            replacement_projects = result.scalars().all()
            
            # Only create if we haven't already created a replacement recently
            if len(replacement_projects) == 0 or random.random() < 0.3:  # 30% chance even if replacement exists
                # Check capacity
                can_create, reason = await project_manager.check_capacity_for_new_project()
                
                if can_create:
                    # Create new project to replace completed one
                    project_names = [
                        "Next Phase Expansion",
                        "Growth Initiative",
                        "Market Development Project",
                        "Innovation Drive",
                        "Strategic Growth Program",
                        "Business Expansion Initiative",
                        "Revenue Growth Project",
                        "Market Penetration Strategy"
                    ]
                    
                    project_name = random.choice(project_names)
                    project = await project_manager.create_project(
                        name=project_name,
                        description=f"New project launched following completion of '{completed_project.name}' to maintain company growth",
                        priority="high",
                        budget=random.uniform(50000, 200000)
                    )
                    
                    # Log project creation
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="project_created",
                        description=f"{self.employee.name} launched new project '{project_name}' following completion of '{completed_project.name}' to drive company growth",
                        activity_metadata={
                            "project_id": project.id,
                            "project_name": project_name,
                            "triggered_by": "project_completion",
                            "completed_project_id": completed_project.id,
                            "completed_project_name": completed_project.name
                        }
                    )
                    self.db.add(activity)
                    print(f"CEO created new project '{project_name}' following completion of '{completed_project.name}' to maintain growth")
                else:
                    # Even if at capacity, create activity showing intent to grow
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} is planning new project following completion of '{completed_project.name}'. Hiring additional staff to support growth.",
                        activity_metadata={
                            "decision_type": "growth_focus",
                            "action": "planning_new_project",
                            "completed_project_id": completed_project.id,
                            "reason": reason
                        }
                    )
                    self.db.add(activity)
                    print(f"CEO planning new project after '{completed_project.name}' completion (at capacity, will hire)")
    
    async def _focus_on_project_completion(self):
        """Focus leadership attention on getting active projects completed."""
        from business.project_manager import ProjectManager
        from database.models import Activity, Task
        from sqlalchemy import select
        
        project_manager = ProjectManager(self.db)
        active_projects = await project_manager.get_active_projects()
        
        if not active_projects:
            return
        
        # Check for stalled or slow-moving projects
        stalled_projects = []
        slow_projects = []
        
        for project in active_projects:
            # Check if project is stalled
            is_stalled = await project_manager.is_project_stalled(project.id)
            if is_stalled:
                stalled_projects.append(project)
            
            # Check project progress
            progress = await project_manager.calculate_project_progress(project.id)
            if progress < 50 and project.status == "active":
                # Project is active but less than 50% complete - might be slow
                # Check how long it's been active
                from datetime import datetime
                if hasattr(project, 'last_activity_at') and project.last_activity_at:
                    from config import utc_to_local
                    from datetime import timezone as tz
                    last_activity = project.last_activity_at
                    # Normalize to timezone-aware datetime
                    if last_activity.tzinfo is None:
                        # If naive, assume it's UTC and convert to local timezone
                        last_activity = utc_to_local(last_activity.replace(tzinfo=tz.utc))
                    else:
                        # If already timezone-aware, convert to local timezone
                        last_activity = utc_to_local(last_activity)
                    days_since_activity = (local_now() - last_activity).days
                    if days_since_activity > 3:  # No activity in 3+ days
                        slow_projects.append(project)
        
        # Create activities to focus on completion
        if stalled_projects or slow_projects:
            focus_chance = 0.4  # 40% chance to create focus activity
            if random.random() < focus_chance:
                if stalled_projects:
                    project = random.choice(stalled_projects)
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} is focusing on getting stalled project '{project.name}' back on track and completed",
                        activity_metadata={
                            "decision_type": "project_completion_focus",
                            "action": "unstalling_project",
                            "project_id": project.id,
                            "project_name": project.name
                        }
                    )
                    self.db.add(activity)
                elif slow_projects:
                    project = random.choice(slow_projects)
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} is prioritizing completion of project '{project.name}' to drive company growth",
                        activity_metadata={
                            "decision_type": "project_completion_focus",
                            "action": "accelerating_project",
                            "project_id": project.id,
                            "project_name": project.name
                        }
                    )
                    self.db.add(activity)
        
        # Also check for projects near completion and push them over the finish line
        near_completion = []
        for project in active_projects:
            progress = await project_manager.calculate_project_progress(project.id)
            if progress >= 75:  # 75% or more complete
                near_completion.append((project, progress))
        
        if near_completion:
            # Focus on getting near-completion projects finished
            if random.random() < 0.3:  # 30% chance
                project, progress = random.choice(near_completion)
                activity = Activity(
                    employee_id=self.employee.id,
                    activity_type="decision",
                    description=f"{self.employee.name} is ensuring project '{project.name}' ({progress:.1f}% complete) gets finished to enable new project launches",
                    activity_metadata={
                        "decision_type": "project_completion_focus",
                        "action": "completing_project",
                        "project_id": project.id,
                        "project_name": project.name,
                        "progress": progress
                    }
                )
                self.db.add(activity)
    
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
    
    async def _make_strategic_business_decision(self, business_context: Dict):
        """CEO makes strategic business decisions to improve company performance."""
        from business.financial_manager import FinancialManager
        from database.models import Activity
        from sqlalchemy import select
        import random
        
        financial_manager = FinancialManager(self.db)
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get project and employee metrics
        from business.project_manager import ProjectManager
        project_manager = ProjectManager(self.db)
        active_projects = await project_manager.get_active_projects()
        project_count = len(active_projects)
        
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Strategic decisions based on company state
        strategic_actions = []
        
        # Cost optimization strategies
        if profit_margin < 15 and revenue > 0:
            strategic_actions.extend([
                ("cost_optimization", "Implementing cost reduction initiatives to improve profitability"),
                ("efficiency_review", "Reviewing operational efficiency to reduce waste and improve margins"),
                ("resource_optimization", "Optimizing resource allocation to maximize ROI"),
                ("process_improvement", "Streamlining processes to reduce operational costs")
            ])
        
        # Growth strategies when profitable
        if profit_margin > 15 and revenue > 0:
            strategic_actions.extend([
                ("market_expansion", "Exploring market expansion opportunities to grow revenue"),
                ("investment_in_innovation", "Investing in innovation and R&D to stay competitive"),
                ("talent_acquisition", "Planning strategic hiring to support growth initiatives"),
                ("technology_upgrade", "Evaluating technology investments to improve efficiency")
            ])
        
        # Efficiency improvements
        if project_count > 5:
            strategic_actions.extend([
                ("project_prioritization", "Prioritizing high-value projects to maximize returns"),
                ("workflow_optimization", "Optimizing workflows to accelerate project delivery"),
                ("quality_improvement", "Focusing on quality improvements to reduce rework and costs")
            ])
        
        # Resource management
        if employee_count > 10:
            strategic_actions.extend([
                ("team_optimization", "Optimizing team structure for maximum productivity"),
                ("skill_development", "Investing in employee development to improve capabilities"),
                ("cross_functional_collaboration", "Enhancing cross-functional collaboration for better outcomes")
            ])
        
        # Always available strategic actions
        strategic_actions.extend([
            ("strategic_planning", "Reviewing long-term strategic goals and company direction"),
            ("performance_analysis", "Analyzing business performance metrics to identify improvement areas"),
            ("competitive_analysis", "Analyzing market position and competitive landscape"),
            ("risk_management", "Assessing and mitigating business risks"),
            ("revenue_optimization", "Identifying opportunities to increase revenue streams"),
            ("customer_focus", "Strengthening customer relationships and satisfaction"),
            ("operational_excellence", "Driving operational excellence across all departments")
        ])
        
        if strategic_actions:
            action_type, description = random.choice(strategic_actions)
            
            # Create financial impact for strategic decisions
            financial_impact = 0.0
            if action_type in ["cost_optimization", "efficiency_review", "process_improvement"]:
                # Cost savings
                financial_impact = -random.uniform(5000, 25000)  # Negative = expense reduction
            elif action_type in ["market_expansion", "revenue_optimization"]:
                # Revenue increase potential
                financial_impact = random.uniform(10000, 50000)
            
            activity = Activity(
                employee_id=self.employee.id,
                activity_type="strategic_decision",
                description=f"{self.employee.name} (CEO): {description}",
                activity_metadata={
                    "decision_type": "strategic",
                    "action_type": action_type,
                    "profit": profit,
                    "revenue": revenue,
                    "profit_margin": profit_margin,
                    "project_count": project_count,
                    "employee_count": employee_count,
                    "financial_impact": financial_impact,
                    "strategic_priority": "high"
                }
            )
            self.db.add(activity)
            
            # Apply financial impact if significant
            if abs(financial_impact) > 1000:
                if financial_impact > 0:
                    # Revenue opportunity - record as potential income
                    await financial_manager.record_income(
                        amount=financial_impact,
                        description=f"Revenue opportunity from {action_type.replace('_', ' ')}"
                    )
                # Note: Cost savings (negative impact) are tracked in metadata but not recorded as expenses
                # since they represent reduced costs rather than actual transactions
            
            await self.db.flush()
            print(f"CEO strategic decision: {description}")

class ManagerAgent(EmployeeAgent):
    """Manager-specific decision making."""
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        # Managers make tactical decisions focused on business operations and success
        # Add profitability and operational metrics to context
        from business.financial_manager import FinancialManager
        from business.project_manager import ProjectManager
        from sqlalchemy import select
        
        financial_manager = FinancialManager(self.db)
        project_manager = ProjectManager(self.db)
        
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get project completion metrics
        active_projects = await project_manager.get_active_projects()
        result = await self.db.execute(
            select(Project).where(Project.status == "completed")
        )
        completed_projects = result.scalars().all()
        completed_count = len(completed_projects)
        
        # Check for projects needing attention
        stalled_count = 0
        near_completion_count = 0
        for project in active_projects:
            is_stalled = await project_manager.is_project_stalled(project.id)
            if is_stalled:
                stalled_count += 1
            else:
                progress = await project_manager.calculate_project_progress(project.id)
                if progress >= 75:
                    near_completion_count += 1
        
        # Enhance business context with operational and project completion focus
        enhanced_context = business_context.copy()
        enhanced_context["profit"] = profit
        enhanced_context["revenue"] = revenue
        enhanced_context["profit_margin"] = profit_margin
        enhanced_context["active_projects"] = len(active_projects)
        enhanced_context["completed_projects"] = completed_count
        enhanced_context["stalled_projects"] = stalled_count
        enhanced_context["near_completion_projects"] = near_completion_count
        enhanced_context["focus"] = "business operations, project completion, and profitability"
        enhanced_context["priority"] = "Get projects completed to enable company growth"
        
        decision = await super().evaluate_situation(enhanced_context)
        decision["action_type"] = "tactical"
        decision["business_focus"] = "operations and project completion"
        return decision
    
    async def execute_decision(self, decision: Dict, business_context: Dict):
        activity = await super().execute_decision(decision, business_context)
        
        # PRIORITY 0: Check for employees on break longer than 30 minutes and return them to work
        try:
            from business.coffee_break_manager import CoffeeBreakManager
            break_manager = CoffeeBreakManager(self.db)
            returned_employees = await break_manager.check_and_return_long_breaks(
                manager_id=self.employee.id,
                manager_name=self.employee.name
            )
            if returned_employees:
                print(f"⏰ Manager {self.employee.name} returned {len(returned_employees)} employee(s) to work from extended breaks")
        except Exception as e:
            import traceback
            print(f"❌ Error checking long breaks: {e}")
            print(traceback.format_exc())
        
        # PRIORITY 1: Focus on getting projects completed
        await self._focus_on_project_completion()
        
        # PRIORITY 2: Managers focus on business operations: task assignment AND business decisions
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
        
        # PRIORITY 3: Managers make strategic operational decisions (increased to 70% chance)
        if random.random() < 0.7:  # Increased from 50% to 70%
            await self._focus_on_business_operations(business_context)
        
        # PRIORITY 4: Managers make strategic improvements (60% chance)
        if random.random() < 0.6:
            await self._make_strategic_operational_decision(business_context)
        
        return activity
    
    async def _focus_on_project_completion(self):
        """Managers focus on getting active projects completed to enable growth."""
        from business.project_manager import ProjectManager
        from database.models import Activity, Task
        from sqlalchemy import select
        
        project_manager = ProjectManager(self.db)
        active_projects = await project_manager.get_active_projects()
        
        if not active_projects:
            return
        
        # Check for projects that need attention to get completed
        stalled_projects = []
        slow_projects = []
        near_completion = []
        
        for project in active_projects:
            # Check if project is stalled
            is_stalled = await project_manager.is_project_stalled(project.id)
            if is_stalled:
                stalled_projects.append(project)
            
            # Check project progress
            progress = await project_manager.calculate_project_progress(project.id)
            
            if progress >= 75:  # Near completion
                near_completion.append((project, progress))
            elif progress < 50 and project.status == "active":
                # Check how long it's been active
                from datetime import datetime
                if hasattr(project, 'last_activity_at') and project.last_activity_at:
                    from config import utc_to_local
                    from datetime import timezone as tz
                    last_activity = project.last_activity_at
                    # Normalize to timezone-aware datetime
                    if last_activity.tzinfo is None:
                        # If naive, assume it's UTC and convert to local timezone
                        last_activity = utc_to_local(last_activity.replace(tzinfo=tz.utc))
                    else:
                        # If already timezone-aware, convert to local timezone
                        last_activity = utc_to_local(last_activity)
                    days_since_activity = (local_now() - last_activity).days
                    if days_since_activity > 3:  # No activity in 3+ days
                        slow_projects.append(project)
        
        # Managers focus on completion - higher chance than CEO since they're more hands-on
        focus_chance = 0.5  # 50% chance to create focus activity
        
        if stalled_projects or slow_projects or near_completion:
            if random.random() < focus_chance:
                if stalled_projects:
                    project = random.choice(stalled_projects)
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} (Manager) is taking action to get stalled project '{project.name}' completed",
                        activity_metadata={
                            "decision_type": "project_completion_focus",
                            "action": "unstalling_project",
                            "project_id": project.id,
                            "project_name": project.name
                        }
                    )
                    self.db.add(activity)
                elif near_completion:
                    # Prioritize near-completion projects
                    project, progress = random.choice(near_completion)
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} (Manager) is pushing to complete project '{project.name}' ({progress:.1f}% done) to free up resources for new projects",
                        activity_metadata={
                            "decision_type": "project_completion_focus",
                            "action": "completing_project",
                            "project_id": project.id,
                            "project_name": project.name,
                            "progress": progress
                        }
                    )
                    self.db.add(activity)
                elif slow_projects:
                    project = random.choice(slow_projects)
                    activity = Activity(
                        employee_id=self.employee.id,
                        activity_type="decision",
                        description=f"{self.employee.name} (Manager) is accelerating work on project '{project.name}' to get it completed",
                        activity_metadata={
                            "decision_type": "project_completion_focus",
                            "action": "accelerating_project",
                            "project_id": project.id,
                            "project_name": project.name
                        }
                    )
                    self.db.add(activity)
    
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
                
                # PRIORITY: Sort tasks by: 1) Project priority (high > medium > low), 2) Revenue, 3) Progress
                # This ensures we focus on high-priority, high-revenue projects first
                task_priorities = []
                priority_weights = {"high": 3, "medium": 2, "low": 1}
                
                for task in unassigned_tasks:
                    if task.project_id:
                        result = await self.db.execute(
                            select(Project).where(Project.id == task.project_id)
                        )
                        project = result.scalar_one_or_none()
                        
                        if project:
                            project_progress = await project_manager.calculate_project_progress(task.project_id)
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
                unassigned_list = [task for task, _, _, _, _ in task_priorities]
                
                # Assign tasks to ALL team members who don't have a task
                # IMPORTANT: Do NOT assign tasks to employees who are still in training
                assigned_count = 0
                from datetime import datetime, timedelta
                from config import now as local_now
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
                            
                            time_since_hire = local_now() - hired_at_naive
                            if time_since_hire <= timedelta(hours=1):
                                is_in_training = True
                        except Exception:
                            pass
                    
                    # Only assign tasks if not in training and doesn't have a task
                    # FOCUS: Employees must complete their current task to 100% before getting a new one
                    if not is_in_training and member.current_task_id is None and unassigned_list:
                        # Take highest priority task (from project closest to 100% completion)
                        task = unassigned_list[0]
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
                                
                                time_since_hire = local_now() - hired_at_naive
                                if time_since_hire <= timedelta(hours=1):
                                    is_in_training = True
                            except Exception:
                                pass
                        
                        # Only assign tasks if not in training
                        if not is_in_training and unassigned_list:
                            # Prioritize tasks from projects near completion (already sorted by progress)
                            task = unassigned_list[0]  # Take highest priority task (from project closest to 100%)
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
    
    async def _make_strategic_operational_decision(self, business_context: Dict):
        """Managers make strategic operational decisions to improve efficiency and outcomes."""
        from business.financial_manager import FinancialManager
        from database.models import Activity
        from sqlalchemy import select
        import random
        
        financial_manager = FinancialManager(self.db)
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        # Get operational metrics
        from business.project_manager import ProjectManager
        project_manager = ProjectManager(self.db)
        active_projects = await project_manager.get_active_projects()
        project_count = len(active_projects)
        
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        
        # Get task metrics
        from database.models import Task
        result = await self.db.execute(
            select(Task).where(
                Task.employee_id.is_(None),
                Task.status.in_(["pending", "in_progress"])
            )
        )
        unassigned_tasks = result.scalars().all()
        unassigned_count = len(unassigned_tasks)
        
        # Strategic operational decisions
        strategic_actions = []
        
        # Efficiency improvements
        if unassigned_count > employee_count:
            strategic_actions.extend([
                ("workload_balancing", "Reallocating workload to balance team capacity"),
                ("task_prioritization", "Prioritizing critical tasks to improve delivery"),
                ("process_streamlining", "Streamlining processes to reduce bottlenecks")
            ])
        
        # Quality and performance
        if project_count > 3:
            strategic_actions.extend([
                ("quality_assurance", "Implementing quality checks to reduce errors"),
                ("performance_monitoring", "Monitoring team performance and providing feedback"),
                ("best_practices", "Establishing best practices for consistent delivery")
            ])
        
        # Resource optimization
        if employee_count > 5:
            strategic_actions.extend([
                ("skill_matching", "Matching employee skills to project needs"),
                ("team_collaboration", "Improving team collaboration and communication"),
                ("knowledge_sharing", "Facilitating knowledge sharing across teams")
            ])
        
        # Cost and efficiency
        if profit_margin < 20:
            strategic_actions.extend([
                ("operational_efficiency", "Improving operational efficiency to reduce costs"),
                ("waste_reduction", "Identifying and eliminating waste in processes"),
                ("time_management", "Optimizing time management to increase productivity")
            ])
        
        # Always available strategic actions
        strategic_actions.extend([
            ("continuous_improvement", "Identifying opportunities for continuous improvement"),
            ("team_development", "Developing team capabilities for better performance"),
            ("stakeholder_alignment", "Ensuring alignment with business objectives"),
            ("risk_mitigation", "Identifying and mitigating operational risks"),
            ("innovation_encouragement", "Encouraging innovation and creative problem-solving"),
            ("customer_focus", "Maintaining focus on customer value delivery")
        ])
        
        if strategic_actions:
            action_type, description = random.choice(strategic_actions)
            
            # Create operational impact
            operational_impact = {
                "efficiency_gain": random.uniform(5, 15),  # Percentage improvement
                "cost_savings": random.uniform(1000, 10000),
                "quality_improvement": random.uniform(3, 10)
            }
            
            activity = Activity(
                employee_id=self.employee.id,
                activity_type="strategic_operational_decision",
                description=f"{self.employee.name} (Manager): {description}",
                activity_metadata={
                    "decision_type": "strategic_operational",
                    "action_type": action_type,
                    "profit": profit,
                    "revenue": revenue,
                    "profit_margin": profit_margin,
                    "project_count": project_count,
                    "employee_count": employee_count,
                    "unassigned_tasks": unassigned_count,
                    "operational_impact": operational_impact,
                    "strategic_priority": "medium"
                }
            )
            self.db.add(activity)
            
            # Note: Cost savings are tracked in metadata to show operational improvements
            # They represent efficiency gains rather than actual financial transactions
            
            await self.db.flush()
            print(f"Manager strategic decision: {description}")

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
        from business.project_manager import ProjectManager
        
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            task = result.scalar_one_or_none()
            
            if task and task.status != "completed":
                # Determine work amount based on decision quality and employee role
                # INCREASED base progress to focus on completing projects to 100%
                base_progress = 8.0  # Increased from 5% to 8% per work session to complete faster
                
                # Managers and C-level executives work faster
                if self.employee.role in ["CTO", "COO", "CFO"]:
                    base_progress *= 1.5  # C-level executives work at manager speed
                elif self.employee.role == "Manager":
                    base_progress *= 1.5
                elif self.employee.role == "CEO":
                    base_progress *= 2.0
                
                # If task is close to completion (>80%), work faster to reach 100%
                if task.progress and task.progress >= 80.0:
                    base_progress *= 1.5  # 50% faster when near completion
                
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
                
                # IMPORTANT: Update project activity whenever work is done on a task
                # This ensures projects show as actively being worked on
                if task.project_id:
                    project_manager = ProjectManager(self.db)
                    await project_manager.update_project_activity(task.project_id)
                    
                    # Ensure project is activated if it's in planning status
                    result = await self.db.execute(
                        select(Project).where(Project.id == task.project_id)
                    )
                    project = result.scalar_one_or_none()
                    if project and project.status == "planning":
                        project.status = "active"
                
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
                task.completed_at = local_now()
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
                        
                        
                        # Check if all tasks are completed
                        result = await self.db.execute(
                            select(Task).where(
                                Task.project_id == project.id,
                                Task.status != "completed"
                            )
                        )
                        remaining_tasks = result.scalars().all()
                        
                        # Get all tasks for the project
                        all_tasks_result = await self.db.execute(
                            select(Task).where(Task.project_id == project.id)
                        )
                        all_tasks = list(all_tasks_result.scalars().all())
                        
                        # Ensure all completed tasks have progress = 100.0
                        for task in all_tasks:
                            if task.status == "completed" and (task.progress is None or task.progress < 100.0):
                                task.progress = 100.0
                        
                        # Check if all tasks are completed
                        all_tasks_completed = len(all_tasks) > 0 and not remaining_tasks
                        
                        # Calculate project-level progress
                        project_progress = await project_manager.calculate_project_progress(project.id)
                        
                        # Mark as completed if: (all tasks completed) OR (progress >= 100%)
                        # Only complete at 100% progress
                        should_complete = (all_tasks_completed and len(all_tasks) > 0) or (project_progress >= 100.0)
                        
                        if should_complete:
                            project.status = "completed"
                            project.completed_at = local_now()
                            
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
                            
                            # Create notification for project completion
                            from database.models import Notification
                            notification = Notification(
                                notification_type="project_completed",
                                title=f"Project Completed: {project.name}",
                                message=f"Project '{project.name}' has been successfully completed with {len(list(all_tasks))} tasks finished.",
                                employee_id=None,
                                review_id=None,
                                read=False
                            )
                            self.db.add(notification)

def create_employee_agent(employee: Employee, db: AsyncSession, llm_client: OllamaClient) -> EmployeeAgent:
    """Factory function to create appropriate agent based on role."""
    if employee.role == "CEO":
        return CEOAgent(employee, db, llm_client)
    elif employee.role in ["Manager", "CTO", "COO", "CFO"]:
        return ManagerAgent(employee, db, llm_client)
    else:
        return EmployeeAgentBase(employee, db, llm_client)

