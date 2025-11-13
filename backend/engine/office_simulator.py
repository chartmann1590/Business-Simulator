import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Employee, Activity, BusinessMetric, Financial
from database.database import async_session_maker
from employees.roles import create_employee_agent
from employees.room_assigner import assign_home_room, assign_rooms_to_existing_employees
from engine.movement_system import process_employee_movement
from llm.ollama_client import OllamaClient
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from business.goal_system import GoalSystem
from typing import Set
from datetime import datetime, timedelta
import random

class OfficeSimulator:
    def __init__(self):
        self.llm_client = OllamaClient()
        self.running = False
        self.websocket_connections: Set = set()
    
    async def add_websocket(self, websocket):
        """Add a WebSocket connection for real-time updates."""
        self.websocket_connections.add(websocket)
    
    async def remove_websocket(self, websocket):
        """Remove a WebSocket connection."""
        self.websocket_connections.discard(websocket)
    
    async def broadcast_activity(self, activity_data: dict):
        """Broadcast activity to all WebSocket connections."""
        if self.websocket_connections:
            disconnected = set()
            for ws in self.websocket_connections:
                try:
                    await ws.send_json(activity_data)
                except:
                    disconnected.add(ws)
            for ws in disconnected:
                await self.remove_websocket(ws)
    
    async def get_business_context(self, db: AsyncSession) -> dict:
        """Get current business context for decision making."""
        financial_manager = FinancialManager(db)
        project_manager = ProjectManager(db)
        goal_system = GoalSystem(db)
        
        revenue = await financial_manager.get_total_revenue()
        profit = await financial_manager.get_profit()
        active_projects = await project_manager.get_active_projects()
        
        result = await db.execute(select(Employee))
        employees = result.scalars().all()
        
        goals = await goal_system.get_business_goals()
        
        return {
            "revenue": revenue,
            "profit": profit,
            "active_projects": len(active_projects),
            "employee_count": len(employees),
            "goals": goals
        }
    
    async def simulation_tick(self):
        """Execute one simulation tick."""
        async with async_session_maker() as db:
            try:
                # Get all active employees
                result = await db.execute(select(Employee).where(Employee.status == "active"))
                employees = result.scalars().all()
                
                if not employees:
                    return
                
                # Get business context
                business_context = await self.get_business_context(db)
                
                # Process each employee (randomize order for variety)
                employee_list = list(employees)
                random.shuffle(employee_list)
                
                # Process up to 3 employees per tick to avoid overload
                for employee in employee_list[:3]:
                    try:
                        # Create employee agent
                        agent = create_employee_agent(employee, db, self.llm_client)
                        
                        # Evaluate situation and make decision
                        decision = await agent.evaluate_situation(business_context)
                        
                        # Execute decision
                        activity = await agent.execute_decision(decision, business_context)
                        
                        # Process employee movement based on activity
                        try:
                            await process_employee_movement(
                                employee,
                                activity.activity_type,
                                activity.description,
                                db
                            )
                            await db.flush()
                        except Exception as e:
                            print(f"Error processing movement for {employee.name}: {e}")
                        
                        # Broadcast activity with location info
                        activity_data = {
                            "type": "activity",
                            "id": activity.id,
                            "employee_id": activity.employee_id,
                            "employee_name": employee.name,
                            "activity_type": activity.activity_type,
                            "description": activity.description,
                            "timestamp": activity.timestamp.isoformat(),
                            "current_room": employee.current_room,
                            "activity_state": employee.activity_state
                        }
                        await self.broadcast_activity(activity_data)
                        
                        # Also broadcast location update separately for real-time office view
                        location_data = {
                            "type": "location_update",
                            "employee_id": employee.id,
                            "employee_name": employee.name,
                            "current_room": employee.current_room,
                            "home_room": employee.home_room,
                            "activity_state": employee.activity_state
                        }
                        await self.broadcast_activity(location_data)
                        
                        # Update business metrics and goals more frequently
                        if random.random() < 0.3:  # 30% chance per tick
                            goal_system = GoalSystem(db)
                            await goal_system.update_metrics()
                        
                        # Generate revenue from active projects (as they progress)
                        if random.random() < 0.25:  # 25% chance per tick
                            await self._generate_revenue_from_active_projects(db)
                        
                        # Generate revenue from completed projects
                        if random.random() < 0.1:  # 10% chance per tick
                            await self._generate_revenue_from_projects(db)
                        
                        # Generate regular expenses (less frequent, only when needed)
                        if random.random() < 0.05:  # 5% chance per tick (monthly expenses)
                            await self._generate_regular_expenses(db)
                        
                        await db.commit()
                    except Exception as e:
                        print(f"Error processing employee {employee.name}: {e}")
                        await db.rollback()
                        continue
                
                # Handle employee hiring/firing based on business performance
                # Check more frequently if we're below minimum staffing
                result = await db.execute(select(Employee).where(Employee.status == "active"))
                active_check = result.scalars().all()
                active_count_check = len(active_check)
                
                # Always check if below minimum, otherwise check occasionally
                check_interval = 0.5 if active_count_check < 15 else 0.1  # 50% chance if below min, 10% otherwise
                if random.random() < check_interval:
                    try:
                        await self._manage_employees(db, business_context)
                    except Exception as e:
                        print(f"Error managing employees: {e}")
                
            except Exception as e:
                print(f"Error in simulation tick: {e}")
    
    async def _generate_revenue_from_active_projects(self, db: AsyncSession):
        """Generate revenue from active projects as they progress."""
        from database.models import Project, Task
        from sqlalchemy import select, func
        from business.project_manager import ProjectManager
        
        project_manager = ProjectManager(db)
        financial_manager = FinancialManager(db)
        
        # Get active projects with progress
        result = await db.execute(
            select(Project).where(Project.status.in_(["active", "planning"]))
        )
        projects = result.scalars().all()
        
        for project in projects:
            # Calculate project progress
            progress = await project_manager.calculate_project_progress(project.id)
            
            # Generate revenue based on progress (milestone payments)
            if progress > 0:
                # Calculate how much revenue should have been generated
                expected_revenue = project.budget * (progress / 100) * 1.5  # 1.5x budget as revenue
                current_revenue = project.revenue or 0.0
                
                # Generate incremental revenue if project has made progress
                if expected_revenue > current_revenue:
                    incremental = expected_revenue - current_revenue
                    # Only generate a portion to avoid too much at once
                    if incremental > 100:  # Only if significant amount
                        payment = incremental * random.uniform(0.1, 0.3)  # 10-30% of incremental
                        await financial_manager.record_income(
                            payment,
                            f"Milestone payment for {project.name} ({progress:.1f}% complete)",
                            project.id
                        )
        
        await db.commit()
    
    async def _generate_revenue_from_projects(self, db: AsyncSession):
        """Generate final revenue from completed projects."""
        from database.models import Project
        from sqlalchemy import select
        
        result = await db.execute(
            select(Project).where(Project.status == "completed")
        )
        projects = result.scalars().all()
        
        financial_manager = FinancialManager(db)
        
        for project in projects:
            # Calculate final payment (remaining revenue)
            expected_total = project.budget * 1.5  # Projects generate 1.5x budget as revenue
            current_revenue = project.revenue or 0.0
            remaining = expected_total - current_revenue
            
            if remaining > 0:
                await financial_manager.record_income(
                    remaining,
                    f"Final payment for completed project: {project.name}",
                    project.id
                )
        
        await db.commit()
    
    async def _generate_regular_expenses(self, db: AsyncSession):
        """Generate regular business expenses (salaries, overhead, etc.)."""
        from database.models import Employee
        from sqlalchemy import select
        
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employees = result.scalars().all()
        
        if employees:
            financial_manager = FinancialManager(db)
            
            # Calculate salary expenses based on employee count and roles (monthly)
            total_salary = 0
            for employee in employees:
                if employee.role == "CEO":
                    salary = random.uniform(15000, 25000)
                elif employee.role == "Manager":
                    salary = random.uniform(8000, 15000)
                else:
                    salary = random.uniform(4000, 8000)
                total_salary += salary
            
            # Record salary expenses (only if we haven't recorded them recently)
            # Check if we've recorded salaries in the last 30 days
            cutoff = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(Financial).where(
                    Financial.type == "expense",
                    Financial.description.like("%salaries%"),
                    Financial.timestamp >= cutoff
                )
            )
            recent_salary_expenses = result.scalars().all()
            
            if total_salary > 0 and not recent_salary_expenses:
                await financial_manager.record_expense(
                    total_salary,
                    f"Monthly salaries for {len(employees)} employees"
                )
            
            # Record overhead expenses (only if we haven't recorded them recently)
            result = await db.execute(
                select(Financial).where(
                    Financial.type == "expense",
                    Financial.description.like("%overhead%"),
                    Financial.timestamp >= cutoff
                )
            )
            recent_overhead = result.scalars().all()
            
            if not recent_overhead:
                overhead = random.uniform(5000, 15000)
                await financial_manager.record_expense(
                    overhead,
                    "Monthly overhead (rent, utilities, supplies)"
                )
            
            await db.commit()
    
    async def _manage_employees(self, db: AsyncSession, business_context: dict):
        """Manage employee hiring and firing based on business performance."""
        from database.models import Employee, Activity
        from sqlalchemy import select
        from datetime import datetime
        from business.financial_manager import FinancialManager
        
        financial_manager = FinancialManager(db)
        profit = await financial_manager.get_profit()
        revenue = await financial_manager.get_total_revenue()
        
        # Get active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        active_count = len(active_employees)
        
        # Get fired employees
        result = await db.execute(
            select(Employee).where(Employee.status == "fired")
        )
        fired_employees = result.scalars().all()
        
        # Minimum staffing requirement: Office needs at least 15 employees to run
        MIN_EMPLOYEES = 15
        
        # Firing logic: Can fire employees with cause (performance issues, budget cuts, etc.)
        # But we must maintain minimum staffing
        fired_this_tick = False
        if active_count > MIN_EMPLOYEES:
            # Can fire if losing money significantly OR for performance reasons
            should_fire = False
            if profit < -20000:
                # Financial reasons - 40% chance
                should_fire = random.random() < 0.4
            elif profit < 0:
                # Minor losses - 10% chance (performance-based firing)
                should_fire = random.random() < 0.1
            else:
                # Even when profitable, might fire for performance (5% chance)
                should_fire = random.random() < 0.05
            
            if should_fire:
                await self._fire_employee(db, active_employees)
                fired_this_tick = True
                # Re-fetch active count after firing
                result = await db.execute(select(Employee).where(Employee.status == "active"))
                active_employees_after = result.scalars().all()
                active_count = len(active_employees_after)
        
        # Priority 1: Hire to meet minimum staffing requirement (including replacing fired employees)
        if active_count < MIN_EMPLOYEES:
            # Hire multiple employees if we're far below minimum
            employees_needed = MIN_EMPLOYEES - active_count
            # Hire 1-3 employees per tick until we reach minimum
            hires_this_tick = min(employees_needed, random.randint(1, 3))
            for _ in range(hires_this_tick):
                await self._hire_employee(db, business_context)
            print(f"Hiring to meet minimum staffing: {hires_this_tick} new employee(s) hired. Current: {active_count}, Target: {MIN_EMPLOYEES}")
        
        # Priority 2: Project-based hiring (if we have many projects/tasks, hire to support them)
        else:
            from database.models import Task, Project
            from business.project_manager import ProjectManager
            
            project_manager = ProjectManager(db)
            active_projects = await project_manager.get_active_projects()
            
            # Count unassigned tasks
            result = await db.execute(
                select(Task).where(
                    Task.employee_id.is_(None),
                    Task.status.in_(["pending", "in_progress"])
                )
            )
            unassigned_tasks = result.scalars().all()
            unassigned_count = len(unassigned_tasks)
            
            # Count employees without tasks
            result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.current_task_id.is_(None)
                )
            )
            available_employees = result.scalars().all()
            available_count = len(available_employees)
            
            # If we have many unassigned tasks and few available employees, consider hiring
            # Also consider hiring if we have many active projects relative to employee count
            project_count = len(active_projects)
            tasks_per_employee = unassigned_count / max(1, active_count)
            projects_per_employee = project_count / max(1, active_count)
            
            should_hire_for_projects = False
            if unassigned_count > 5 and available_count < 3:
                # Many unassigned tasks, few available employees
                should_hire_for_projects = True
            elif project_count > 3 and projects_per_employee > 0.3:
                # Many projects relative to employees (more than 0.3 projects per employee)
                should_hire_for_projects = True
            elif tasks_per_employee > 2.0 and active_count < 25:
                # More than 2 tasks per employee on average, and we're not at max capacity
                should_hire_for_projects = True
            
            if should_hire_for_projects and active_count < 30:  # Can grow up to 30
                # Higher chance to hire if we're profitable, but still possible if breaking even
                hire_chance = 0.4 if profit > 0 else 0.2
                if random.random() < hire_chance:
                    await self._hire_employee(db, business_context)
                    print(f"Hiring for project workload: {unassigned_count} unassigned tasks, {project_count} active projects, {available_count} available employees")
        
        # Priority 3: Growth hiring (if profitable and growing, can hire beyond minimum)
        if profit > 50000 and revenue > 100000 and active_count < 30:  # Can grow up to 30
            if random.random() < 0.3:  # 30% chance to hire
                await self._hire_employee(db, business_context)
    
    async def _hire_employee(self, db: AsyncSession, business_context: dict):
        """Hire a new employee."""
        from database.models import Employee, Activity
        from datetime import datetime
        import random
        
        departments = ["Engineering", "Product", "Marketing", "Sales", "Operations"]
        roles = ["Employee", "Manager"]
        
        # Generate employee data
        first_names = ["Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Sage", "Blake", "Cameron"]
        last_names = ["Anderson", "Martinez", "Thompson", "Garcia", "Lee", "White", "Harris", "Clark", "Lewis", "Walker"]
        titles_by_role = {
            "Employee": ["Software Engineer", "Product Designer", "Marketing Specialist", "Sales Representative", "Operations Coordinator"],
            "Manager": ["Engineering Manager", "Product Manager", "Marketing Manager", "Sales Manager", "Operations Manager"]
        }
        
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        role = random.choice(roles)
        department = random.choice(departments)
        hierarchy_level = 2 if role == "Manager" else 3
        title = random.choice(titles_by_role[role])
        
        personality_traits = random.sample(
            ["analytical", "creative", "collaborative", "detail-oriented", "innovative", "reliable", "adaptable", "proactive"],
            k=3
        )
        
        new_employee = Employee(
            name=name,
            title=title,
            role=role,
            hierarchy_level=hierarchy_level,
            department=department,
            status="active",
            personality_traits=personality_traits,
            backstory=f"{name} joined the team to help drive growth and innovation.",
            hired_at=datetime.utcnow()
        )
        db.add(new_employee)
        await db.flush()  # Flush to get the employee ID
        
        # Assign home room based on role/department
        home_room = assign_home_room(new_employee)
        new_employee.home_room = home_room
        new_employee.current_room = home_room
        new_employee.activity_state = "idle"
        
        # Create activity
        activity = Activity(
            employee_id=None,
            activity_type="hiring",
            description=f"Hired {name} as {title} in {department}",
            activity_metadata={"employee_id": None, "action": "hire"}
        )
        db.add(activity)
        
        await db.flush()
        activity.activity_metadata["employee_id"] = new_employee.id
        await db.commit()
        print(f"Hired new employee: {name} ({title})")
    
    async def _fire_employee(self, db: AsyncSession, active_employees: list):
        """Fire an underperforming employee (not CEO)."""
        from database.models import Activity
        from datetime import datetime
        
        # Don't fire CEO, and prefer firing regular employees over managers
        candidates = [e for e in active_employees if e.role != "CEO"]
        if not candidates:
            return
        
        # Prefer firing employees over managers (70% chance)
        if random.random() < 0.7:
            candidates = [e for e in candidates if e.role == "Employee"]
        
        if not candidates:
            candidates = [e for e in active_employees if e.role != "CEO"]
        
        employee_to_fire = random.choice(candidates)
        
        # Generate AI termination reason based on business context
        business_context = await self.get_business_context(db)
        termination_reason = await self._generate_termination_reason(
            employee_to_fire, 
            business_context
        )
        
        employee_to_fire.status = "fired"
        employee_to_fire.fired_at = datetime.utcnow()
        
        # Clear current task if any
        employee_to_fire.current_task_id = None
        
        # Create activity with termination reason
        activity = Activity(
            employee_id=None,
            activity_type="firing",
            description=f"Terminated {employee_to_fire.name} ({employee_to_fire.title}). Reason: {termination_reason}",
            activity_metadata={
                "employee_id": employee_to_fire.id, 
                "action": "fire",
                "termination_reason": termination_reason
            }
        )
        db.add(activity)
        
        await db.commit()
        print(f"Fired employee: {employee_to_fire.name} ({employee_to_fire.title}) - Reason: {termination_reason}")
    
    async def _generate_termination_reason(self, employee, business_context: dict) -> str:
        """Generate an AI-based termination reason for an employee."""
        try:
            # Build context about the employee and business situation
            employee_info = f"""
Employee: {employee.name}
Title: {employee.title}
Role: {employee.role}
Department: {employee.department or 'N/A'}
Personality Traits: {', '.join(employee.personality_traits) if employee.personality_traits else 'N/A'}
Backstory: {employee.backstory or 'N/A'}
"""
            
            business_info = f"""
Current Business Status:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}
- Total Employees: {business_context.get('employee_count', 0)}
"""
            
            prompt = f"""You are an HR manager making a termination decision. Based on the employee information and current business situation, generate a realistic, professional termination reason.

{employee_info}

{business_info}

Generate a brief, professional termination reason (1-2 sentences) that:
1. Is realistic and believable
2. Relates to the employee's role, performance, or business needs
3. Is professional and appropriate
4. Could be based on performance issues, budget cuts, restructuring, or other business reasons

Return ONLY the termination reason text, nothing else."""

            response = await self.llm_client.generate_response(prompt)
            termination_reason = response.strip()
            
            # Fallback if AI doesn't return a good reason
            if not termination_reason or len(termination_reason) < 10:
                # Generate a fallback reason based on business context
                if business_context.get('profit', 0) < 0:
                    termination_reason = f"Terminated due to budget constraints and cost-cutting measures during financial difficulties."
                elif employee.role == "Employee":
                    termination_reason = f"Terminated due to performance not meeting expectations in the {employee.department or 'department'}."
                else:
                    termination_reason = f"Terminated as part of organizational restructuring in the {employee.department or 'department'}."
            
            return termination_reason
            
        except Exception as e:
            print(f"Error generating termination reason: {e}")
            # Fallback reason
            if business_context.get('profit', 0) < 0:
                return "Terminated due to budget constraints and cost-cutting measures."
            return f"Terminated due to performance issues in the {employee.department or 'department'}."
    
    async def run(self):
        """Run the simulation loop."""
        self.running = True
        print("Office simulation started...")
        
        while self.running:
            try:
                await self.simulation_tick()
                await asyncio.sleep(8)  # Wait 8 seconds between ticks
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the simulation."""
        self.running = False
        print("Office simulation stopped.")

