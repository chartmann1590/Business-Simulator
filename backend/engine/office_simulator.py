import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
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
        # Use a separate session to get employee list (read-only)
        async with async_session_maker() as read_db:
            try:
                # Get all active employees
                result = await read_db.execute(select(Employee).where(Employee.status == "active"))
                employees = result.scalars().all()
                
                if not employees:
                    return
                
                # Get business context (read-only)
                business_context = await self.get_business_context(read_db)
                
                # Process each employee (randomize order for variety)
                employee_list = list(employees)
                random.shuffle(employee_list)
                
                # Process up to 3 employees per tick to avoid overload
                for employee in employee_list[:3]:
                    # Use a separate session for each employee to isolate transactions
                    async with async_session_maker() as db:
                        try:
                            # Get fresh employee instance in this session
                            result = await db.execute(select(Employee).where(Employee.id == employee.id))
                            employee_instance = result.scalar_one()
                            
                            # Create employee agent with this session
                            agent = create_employee_agent(employee_instance, db, self.llm_client)
                            
                            # Evaluate situation and make decision
                            decision = await agent.evaluate_situation(business_context)
                            
                            # Execute decision
                            activity = await agent.execute_decision(decision, business_context)
                            
                            # Process employee movement based on activity
                            try:
                                await process_employee_movement(
                                    employee_instance,
                                    activity.activity_type,
                                    activity.description,
                                    db
                                )
                                await db.flush()
                            except Exception as e:
                                print(f"Error processing movement for {employee_instance.name}: {e}")
                                import traceback
                                traceback.print_exc()
                                # Rollback and continue with this employee
                                await db.rollback()
                                continue
                            
                            # Refresh employee instance to get latest state
                            await db.refresh(employee_instance, ["current_room", "home_room", "activity_state"])
                            
                            # Broadcast activity with location info
                            activity_data = {
                                "type": "activity",
                                "id": activity.id,
                                "employee_id": activity.employee_id,
                                "employee_name": employee_instance.name,
                                "activity_type": activity.activity_type,
                                "description": activity.description,
                                "timestamp": (activity.timestamp or datetime.utcnow()).isoformat(),
                                "current_room": employee_instance.current_room,
                                "activity_state": employee_instance.activity_state
                            }
                            await self.broadcast_activity(activity_data)
                            
                            # Also broadcast location update separately for real-time office view
                            location_data = {
                                "type": "location_update",
                                "employee_id": employee_instance.id,
                                "employee_name": employee_instance.name,
                                "current_room": employee_instance.current_room,
                                "home_room": employee_instance.home_room,
                                "activity_state": employee_instance.activity_state,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            await self.broadcast_activity(location_data)
                            
                            # Commit this employee's transaction
                            await db.commit()
                            
                        except Exception as e:
                            employee_name = employee_instance.name if 'employee_instance' in locals() else employee.name
                            print(f"Error processing employee {employee_name}: {e}")
                            import traceback
                            traceback.print_exc()
                            # Rollback this employee's transaction
                            try:
                                await db.rollback()
                            except:
                                pass  # Session may already be closed
                            continue
                        
                        # Update business metrics and goals more frequently (use separate session)
                        # Increased frequency to better track workload
                        if random.random() < 0.4:  # 40% chance per tick (increased from 30%)
                            async with async_session_maker() as metrics_db:
                                try:
                                    goal_system = GoalSystem(metrics_db)
                                    await goal_system.update_metrics()
                                    await metrics_db.commit()
                                except Exception as e:
                                    print(f"Error updating metrics: {e}")
                                    await metrics_db.rollback()
                        
                        # Generate revenue from active projects (as they progress)
                        if random.random() < 0.25:  # 25% chance per tick
                            async with async_session_maker() as revenue_db:
                                try:
                                    await self._generate_revenue_from_active_projects(revenue_db)
                                    await revenue_db.commit()
                                except Exception as e:
                                    print(f"Error generating revenue: {e}")
                                    await revenue_db.rollback()
                        
                        # Generate revenue from completed projects
                        if random.random() < 0.1:  # 10% chance per tick
                            async with async_session_maker() as revenue_db:
                                try:
                                    await self._generate_revenue_from_projects(revenue_db)
                                    await revenue_db.commit()
                                except Exception as e:
                                    print(f"Error generating revenue from projects: {e}")
                                    await revenue_db.rollback()
                        
                        # Generate regular expenses (less frequent, only when needed)
                        if random.random() < 0.05:  # 5% chance per tick (monthly expenses)
                            async with async_session_maker() as expense_db:
                                try:
                                    await self._generate_regular_expenses(expense_db)
                                    await expense_db.commit()
                                except Exception as e:
                                    print(f"Error generating expenses: {e}")
                                    await expense_db.rollback()
                        
                        # Manage project overload periodically (40% chance per tick - more frequent!)
                        if random.random() < 0.4:  # 40% chance per tick
                            async with async_session_maker() as project_db:
                                try:
                                    await self._manage_project_capacity(project_db)
                                    await project_db.commit()
                                except Exception as e:
                                    print(f"Error managing project capacity: {e}")
                                    await project_db.rollback()
                
                # Handle employee hiring/firing based on business performance (use separate session)
                async with async_session_maker() as manage_db:
                    try:
                        # Import Task model for task overload checking
                        from database.models import Task
                        
                        # Check more frequently if we're below minimum staffing or over capacity
                        result = await manage_db.execute(select(Employee).where(Employee.status == "active"))
                        active_check = result.scalars().all()
                        active_count_check = len(active_check)
                        
                        # Check if we're over capacity for projects
                        from business.project_manager import ProjectManager
                        project_manager = ProjectManager(manage_db)
                        active_projects = await project_manager.get_active_projects()
                        project_count = len(active_projects)
                        max_projects = max(1, int(active_count_check / 3))
                        is_over_capacity = project_count > max_projects
                        
                        # Check for extreme task overload - always check if severe
                        result = await manage_db.execute(
                            select(Task).where(
                                Task.employee_id.is_(None),
                                Task.status.in_(["pending", "in_progress"])
                            )
                        )
                        unassigned_check = result.scalars().all()
                        unassigned_count_check = len(unassigned_check)
                        tasks_per_employee_check = unassigned_count_check / max(1, active_count_check)
                        
                        # Always check if below minimum, over capacity, or extreme task overload
                        if active_count_check < 15:
                            check_interval = 0.5  # 50% chance if below min
                        elif tasks_per_employee_check > 10:  # Extreme overload - always check!
                            check_interval = 1.0  # 100% chance - emergency situation
                        elif is_over_capacity or tasks_per_employee_check > 5:
                            check_interval = 0.8  # 80% chance if over capacity or severe task overload
                        elif tasks_per_employee_check > 2:
                            check_interval = 0.6  # 60% chance if moderate task overload
                        else:
                            check_interval = 0.1  # 10% otherwise
                        
                        if random.random() < check_interval:
                            try:
                                await self._manage_employees(manage_db, business_context)
                                await manage_db.commit()
                            except Exception as e:
                                print(f"Error managing employees: {e}")
                                await manage_db.rollback()
                    except Exception as e:
                        print(f"Error in employee management section: {e}")
                        try:
                            await manage_db.rollback()
                        except:
                            pass
                        
            except Exception as e:
                print(f"Error in simulation tick: {e}")
                import traceback
                traceback.print_exc()
    
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
        # Maximum staffing cap: Don't hire beyond 215 employees
        MAX_EMPLOYEES = 215
        
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
        if active_count < MIN_EMPLOYEES and active_count < MAX_EMPLOYEES:
            # Hire multiple employees if we're far below minimum
            employees_needed = MIN_EMPLOYEES - active_count
            # Don't exceed max cap
            employees_needed = min(employees_needed, MAX_EMPLOYEES - active_count)
            # Hire 1-3 employees per tick until we reach minimum
            hires_this_tick = min(employees_needed, random.randint(1, 3))
            for _ in range(hires_this_tick):
                await self._hire_employee(db, business_context)
            print(f"Hiring to meet minimum staffing: {hires_this_tick} new employee(s) hired. Current: {active_count}, Target: {MIN_EMPLOYEES}, Max: {MAX_EMPLOYEES}")
        
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
            
            # Check if we're over capacity for projects
            project_count = len(active_projects)
            max_projects = max(1, int(active_count / 3))
            is_over_capacity = project_count > max_projects
            
            tasks_per_employee = unassigned_count / max(1, active_count)
            projects_per_employee = project_count / max(1, active_count)
            
            # AGGRESSIVE HIRING: If over capacity, hire immediately and multiple employees
            if is_over_capacity and active_count < MAX_EMPLOYEES:
                # Calculate how many employees we need
                # Each project needs ~3 employees, so if we have N projects, we need N*3 employees
                employees_needed_for_projects = project_count * 3
                employees_short = max(0, employees_needed_for_projects - active_count)
                # Don't exceed max cap
                employees_short = min(employees_short, MAX_EMPLOYEES - active_count)
                
                # Hire aggressively: 2-4 employees per tick when over capacity
                # For severe overload, hire more aggressively
                if employees_short > 20:  # Very short on employees
                    hires_needed = min(employees_short, random.randint(5, 8))  # Hire 5-8
                else:
                    hires_needed = min(employees_short, random.randint(2, 4))  # Hire 2-4
                
                if hires_needed > 0:
                    for _ in range(hires_needed):
                        await self._hire_employee(db, business_context)
                    print(f"AGGRESSIVE HIRING: Hired {hires_needed} employee(s) to handle {project_count} projects (capacity: {max_projects}, current: {active_count}, short: {employees_short}, max: {MAX_EMPLOYEES})")
            
            # PROACTIVE HIRING: Hire to maintain strong workload even when not over capacity
            # If we have capacity for more projects, hire to enable growth
            elif project_count < max_projects * 0.7 and active_count < MAX_EMPLOYEES:  # If we're using less than 70% of capacity
                # We have room for more projects - hire to enable growth
                capacity_available = max_projects - project_count
                if capacity_available >= 2:
                    # Hire 1-2 employees to enable project growth (don't exceed max)
                    hire_chance = 0.4 if profit > 0 else 0.2
                    if random.random() < hire_chance:
                        hires = min(MAX_EMPLOYEES - active_count, random.randint(1, 2))
                        if hires > 0:
                            for _ in range(hires):
                                await self._hire_employee(db, business_context)
                            print(f"PROACTIVE HIRING: Hired {hires} employee(s) to enable growth (capacity: {max_projects}, current projects: {project_count}, employees: {active_count}, max: {MAX_EMPLOYEES})")
            
            # EMERGENCY HIRING: If extreme task overload, hire aggressively (but respect max cap)
            # With 1032 tasks and 51 employees, that's ~20 tasks per employee - need to hire NOW!
            if unassigned_count > active_count * 10 and active_count < MAX_EMPLOYEES:  # More than 10 tasks per employee = emergency
                # EMERGENCY: Hire 5-10 employees immediately, but don't exceed max
                hires_needed = min(unassigned_count // 20, 10)  # Hire up to 10 at once
                hires_needed = max(3, hires_needed)  # At least 3
                hires_needed = min(hires_needed, MAX_EMPLOYEES - active_count)  # Don't exceed max
                if hires_needed > 0:
                    for _ in range(hires_needed):
                        await self._hire_employee(db, business_context)
                    print(f"🚨 EMERGENCY HIRING: Hired {hires_needed} employee(s) for extreme task overload ({unassigned_count} tasks, {active_count} employees, {unassigned_count/active_count:.1f} tasks/employee, max: {MAX_EMPLOYEES})")
            
            # Also hire if we have many unassigned tasks
            should_hire_for_tasks = False
            if unassigned_count > 3 and available_count < 2:
                # Many unassigned tasks, few available employees
                should_hire_for_tasks = True
            elif tasks_per_employee > 1.5:  # Removed employee limit check - always hire if overloaded
                # More than 1.5 tasks per employee on average
                should_hire_for_tasks = True
            
            if should_hire_for_tasks and active_count < MAX_EMPLOYEES:
                # Higher chance to hire if we're profitable, but still possible if breaking even
                # More aggressive hiring for severe overload
                if tasks_per_employee > 5:  # Severe overload
                    hire_chance = 1.0  # 100% chance - always hire
                    hires = min(MAX_EMPLOYEES - active_count, random.randint(3, 5))  # Hire 3-5 employees
                elif tasks_per_employee > 2:  # Moderate overload
                    hire_chance = 0.9 if profit > 0 else 0.7
                    hires = min(MAX_EMPLOYEES - active_count, random.randint(2, 4))  # Hire 2-4 employees
                else:  # Mild overload
                    hire_chance = 0.7 if profit > 0 else 0.5
                    hires = min(MAX_EMPLOYEES - active_count, random.randint(1, 2))  # Hire 1-2 employees
                
                if random.random() < hire_chance and hires > 0:
                    for _ in range(hires):
                        await self._hire_employee(db, business_context)
                    print(f"Hiring for task workload: {unassigned_count} unassigned tasks ({tasks_per_employee:.1f} per employee), {available_count} available employees, hired {hires}, max: {MAX_EMPLOYEES}")
            
            # Also hire if projects per employee ratio is high (even if not over capacity)
            if projects_per_employee > 0.25 and active_count < MAX_EMPLOYEES:
                hire_chance = 0.6 if profit > 0 else 0.4  # Increased chances
                if random.random() < hire_chance:
                    await self._hire_employee(db, business_context)
                    print(f"Hiring for project ratio: {projects_per_employee:.2f} projects per employee (current: {active_count}, max: {MAX_EMPLOYEES})")
            
            # ENSURE WORKLOAD: If many employees are idle, we need more projects or tasks
            # This is a signal that we should create more projects or hire more strategically
            idle_ratio = available_count / max(1, active_count)
            if idle_ratio > 0.3 and active_count < MAX_EMPLOYEES:
                # Either create more projects (handled by CEO) or hire to balance workload
                # For now, we'll note this - CEO should create more projects
                if random.random() < 0.3:  # 30% chance to hire anyway to build capacity
                    await self._hire_employee(db, business_context)
                    print(f"Hiring to reduce idle workforce: {available_count}/{active_count} employees idle ({idle_ratio:.1%}), max: {MAX_EMPLOYEES}")
        
        # Priority 3: Ensure we have essential staff (IT, Reception, and Storage) on each floor
        # Count IT employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%IT%") | Employee.title.ilike("%Information Technology%") | 
                 Employee.department.ilike("%IT%"))
            )
        )
        it_employees = result.scalars().all()
        it_count = len(it_employees)
        
        # Count Reception employees by floor
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Reception%") | Employee.title.ilike("%Receptionist%"))
            )
        )
        reception_employees = result.scalars().all()
        reception_count = len(reception_employees)
        
        # Count receptionists on each floor
        reception_floor1 = sum(1 for e in reception_employees if e.floor == 1 or (e.home_room and not e.home_room.endswith('_floor2')))
        reception_floor2 = sum(1 for e in reception_employees if e.floor == 2 or (e.home_room and e.home_room.endswith('_floor2')))
        
        # Count Storage employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Storage%") | Employee.title.ilike("%Warehouse%") | 
                 Employee.title.ilike("%Inventory%") | Employee.title.ilike("%Stock%"))
            )
        )
        storage_employees = result.scalars().all()
        storage_count = len(storage_employees)
        
        # Count storage employees on each floor
        storage_floor1 = sum(1 for e in storage_employees if e.floor == 1 or (e.home_room and not e.home_room.endswith('_floor2')))
        storage_floor2 = sum(1 for e in storage_employees if e.floor == 2 or (e.home_room and e.home_room.endswith('_floor2')))
        
        # Ensure we have at least 1-2 IT employees (hire if we have 0)
        # Essential roles - always ensure we have them, but respect max cap
        if it_count == 0 and active_count < MAX_EMPLOYEES:
            # Force hire IT employee
            await self._hire_employee_specific(db, business_context, department="IT", role="Employee")
            print(f"Hired IT employee to ensure IT coverage (current: {active_count}, max: {MAX_EMPLOYEES})")
        
        # Ensure we have at least one Reception employee on each floor
        if reception_floor1 == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Reception employee for floor 1
            await self._hire_employee_specific(db, business_context, department="Administration", title="Receptionist", role="Employee")
            print(f"Hired Reception employee for floor 1 (current: {active_count}, max: {MAX_EMPLOYEES})")
        elif reception_floor2 == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Reception employee for floor 2
            await self._hire_employee_specific(db, business_context, department="Administration", title="Receptionist", role="Employee")
            print(f"Hired Reception employee for floor 2 (current: {active_count}, max: {MAX_EMPLOYEES})")
        
        # Ensure we have at least one Storage employee on each floor
        if storage_floor1 == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Storage employee for floor 1
            await self._hire_employee_specific(db, business_context, department="Operations", title="Storage Coordinator", role="Employee")
            print(f"Hired Storage employee for floor 1 (current: {active_count}, max: {MAX_EMPLOYEES})")
        elif storage_floor2 == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Storage employee for floor 2
            await self._hire_employee_specific(db, business_context, department="Operations", title="Storage Coordinator", role="Employee")
            print(f"Hired Storage employee for floor 2 (current: {active_count}, max: {MAX_EMPLOYEES})")
        
        # If we have many employees but no IT, hire one
        if it_count == 0 and active_count >= 10 and active_count < MAX_EMPLOYEES:
            if random.random() < 0.5:  # 50% chance
                await self._hire_employee_specific(db, business_context, department="IT", role="Employee")
                print(f"Hired IT employee (office has {active_count} employees but no IT, max: {MAX_EMPLOYEES})")
        
        # If we have many employees but no Reception, hire one
        if reception_count == 0 and active_count >= 10 and active_count < MAX_EMPLOYEES:
            if random.random() < 0.5:  # 50% chance
                await self._hire_employee_specific(db, business_context, department="Administration", title="Receptionist", role="Employee")
                print(f"Hired Reception employee (office has {active_count} employees but no reception, max: {MAX_EMPLOYEES})")
        
        # Count HR employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%HR%") | Employee.title.ilike("%Human Resources%") | 
                 Employee.department.ilike("%HR%"))
            )
        )
        hr_employees = result.scalars().all()
        hr_count = len(hr_employees)
        
        # Count Sales employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Sales%") | Employee.department.ilike("%Sales%"))
            )
        )
        sales_employees = result.scalars().all()
        sales_count = len(sales_employees)
        
        # Count Design employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Design%") | Employee.title.ilike("%Designer%") | 
                 Employee.department.ilike("%Design%"))
            )
        )
        design_employees = result.scalars().all()
        design_count = len(design_employees)
        
        # Count Leadership (Managers, Executives, Directors, VPs)
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                or_(
                    Employee.role == "Manager",
                    Employee.title.ilike("%Director%"),
                    Employee.title.ilike("%VP%"),
                    Employee.title.ilike("%Vice President%"),
                    Employee.title.ilike("%Executive%"),
                    Employee.title.ilike("%Chief%")
                )
            )
        )
        leadership_employees = result.scalars().all()
        leadership_count = len(leadership_employees)
        
        # Ensure we have at least one HR employee (hire if we have 0 or very few)
        # Respect max cap but ensure essential roles
        if hr_count == 0 and active_count < MAX_EMPLOYEES:
            # Force hire HR employee
            await self._hire_employee_specific(db, business_context, department="HR", role="Employee")
            print(f"Hired HR employee (office has {active_count} employees but no HR, max: {MAX_EMPLOYEES})")
        elif hr_count == 1 and active_count >= 20 and active_count < MAX_EMPLOYEES:
            # If we have 20+ employees but only 1 HR, hire another
            if random.random() < 0.5:  # 50% chance
                await self._hire_employee_specific(db, business_context, department="HR", role="Employee")
                print(f"Hired additional HR employee (office has {active_count} employees, {hr_count} HR, max: {MAX_EMPLOYEES})")
        
        # Ensure we have Sales employees (hire if we have 0 or very few)
        if sales_count == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Sales employee
            await self._hire_employee_specific(db, business_context, department="Sales", role="Employee")
            print(f"Hired Sales employee (office has {active_count} employees but no Sales, max: {MAX_EMPLOYEES})")
        elif sales_count < 2 and active_count >= 15 and active_count < MAX_EMPLOYEES:
            # If we have 15+ employees but less than 2 Sales, hire more
            if random.random() < 0.6:  # 60% chance
                await self._hire_employee_specific(db, business_context, department="Sales", role="Employee")
                print(f"Hired Sales employee (office has {active_count} employees, {sales_count} Sales, max: {MAX_EMPLOYEES})")
        
        # Ensure we have Design employees (hire if we have 0 or very few)
        if design_count == 0 and active_count < MAX_EMPLOYEES:
            # Force hire Design employee
            await self._hire_employee_specific(db, business_context, department="Design", role="Employee")
            print(f"Hired Design employee (office has {active_count} employees but no Design, max: {MAX_EMPLOYEES})")
        elif design_count < 2 and active_count >= 15 and active_count < MAX_EMPLOYEES:
            # If we have 15+ employees but less than 2 Design, hire more
            if random.random() < 0.5:  # 50% chance
                await self._hire_employee_specific(db, business_context, department="Design", role="Employee")
                print(f"Hired Design employee (office has {active_count} employees, {design_count} Design, max: {MAX_EMPLOYEES})")
        
        # Ensure we have adequate leadership (hire managers if we have too few)
        # Need at least 1 manager per 10 employees, or at least 2-3 managers minimum
        managers_needed = max(2, int(active_count / 10))
        if leadership_count < managers_needed and active_count >= 10 and active_count < MAX_EMPLOYEES:
            if random.random() < 0.7:  # 70% chance to hire manager
                # Hire a manager - could be any department
                departments_with_managers = ["Engineering", "Product", "Marketing", "Sales", "Operations", "IT", "HR", "Design"]
                dept = random.choice(departments_with_managers)
                await self._hire_employee_specific(db, business_context, department=dept, role="Manager")
                print(f"Hired Manager for {dept} (office has {active_count} employees, {leadership_count} leaders, need {managers_needed}, max: {MAX_EMPLOYEES})")
        
        # Priority 4: Growth hiring (if profitable and growing, can hire beyond minimum)
        # More aggressive growth hiring to ensure strong workforce
        if profit > 50000 and revenue > 100000 and active_count < MAX_EMPLOYEES:
            # Higher chance to hire when profitable - build strong team
            hire_chance = 0.5 if profit > 100000 else 0.3  # 50% chance if very profitable
            if random.random() < hire_chance:
                # Hire 1-2 employees for growth (don't exceed max)
                hires = min(MAX_EMPLOYEES - active_count, random.randint(1, 2))
                if hires > 0:
                    for _ in range(hires):
                        await self._hire_employee(db, business_context)
                    print(f"Growth hiring: Hired {hires} employee(s) (profit: ${profit:,.2f}, revenue: ${revenue:,.2f}, current: {active_count}, max: {MAX_EMPLOYEES})")
        
        # Priority 5: Ensure minimum project workload
        # If we have many employees but few projects, we should have more projects
        # This is handled by CEO creating projects, but we can also hire to prepare for growth
        if active_count >= 20 and project_count < 5 and active_count < MAX_EMPLOYEES:
            # Many employees but few projects - hire strategically to prepare for more projects
            if random.random() < 0.2:  # 20% chance
                await self._hire_employee(db, business_context)
                print(f"Strategic hiring: Preparing for project growth ({active_count} employees, {project_count} projects, max: {MAX_EMPLOYEES})")
    
    async def _hire_employee(self, db: AsyncSession, business_context: dict):
        """Hire a new employee."""
        from database.models import Employee, Activity
        from datetime import datetime
        import random
        
        departments = ["Engineering", "Product", "Marketing", "Sales", "Operations", "IT", "Administration", "HR", "Design"]
        roles = ["Employee", "Manager"]
        
        # Generate employee data
        first_names = ["Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Sage", "Blake", "Cameron"]
        last_names = ["Anderson", "Martinez", "Thompson", "Garcia", "Lee", "White", "Harris", "Clark", "Lewis", "Walker"]
        titles_by_role = {
            "Employee": [
                "Software Engineer", "Product Designer", "Marketing Specialist", "Sales Representative", 
                "Operations Coordinator", "IT Specialist", "IT Support Technician", "Receptionist", 
                "Administrative Assistant", "HR Specialist", "HR Coordinator", "Human Resources Specialist",
                "Designer", "UI Designer", "UX Designer", "Graphic Designer"
            ],
            "Manager": [
                "Engineering Manager", "Product Manager", "Marketing Manager", "Sales Manager", 
                "Operations Manager", "IT Manager", "HR Manager", "Human Resources Manager", "Design Manager"
            ]
        }
        
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        role = random.choice(roles)
        department = random.choice(departments)
        hierarchy_level = 2 if role == "Manager" else 3
        
        # Special handling for IT and Reception to ensure they get appropriate titles
        if department == "IT":
            if role == "Manager":
                title = "IT Manager"
            else:
                title = random.choice(["IT Specialist", "IT Support Technician", "Network Administrator", "Systems Administrator"])
        elif department == "Administration":
            # Sometimes create receptionists
            if random.random() < 0.4:  # 40% chance for receptionist
                title = "Receptionist"
                department = "Administration"
            else:
                title = random.choice(["Administrative Assistant", "Office Coordinator"])
        else:
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
        
        # Assign home room and floor based on role/department
        home_room, floor = await assign_home_room(new_employee, db)
        new_employee.home_room = home_room
        new_employee.floor = floor
        
        # New hires start in training room on their assigned floor
        # Determine training room based on floor - check capacity and use floor 4 for overflow
        from employees.room_assigner import ROOM_TRAINING_ROOM
        from engine.movement_system import get_room_occupancy, get_room_capacity
        
        # Check if training rooms on floors 1-2 are full, use floor 4 for overflow
        floor1_occupancy = await get_room_occupancy(ROOM_TRAINING_ROOM, db)
        floor1_capacity = get_room_capacity(ROOM_TRAINING_ROOM)
        floor2_occupancy = await get_room_occupancy(f"{ROOM_TRAINING_ROOM}_floor2", db)
        floor2_capacity = get_room_capacity(f"{ROOM_TRAINING_ROOM}_floor2")
        
        # If floors 1-2 training rooms are near capacity, use floor 4
        if floor1_occupancy >= floor1_capacity - 2 or floor2_occupancy >= floor2_capacity - 2:
            training_room = f"{ROOM_TRAINING_ROOM}_floor4"
            new_employee.floor = 4  # Update floor to 4 for training
        elif floor == 2:
            training_room = f"{ROOM_TRAINING_ROOM}_floor2"
        elif floor == 3:
            # Floor 3 doesn't have a training room, use floor 1, 2, or 4
            # Check which has space
            if floor1_occupancy < floor1_capacity:
                training_room = ROOM_TRAINING_ROOM
            elif floor2_occupancy < floor2_capacity:
                training_room = f"{ROOM_TRAINING_ROOM}_floor2"
                new_employee.floor = 2
            else:
                training_room = f"{ROOM_TRAINING_ROOM}_floor4"
                new_employee.floor = 4
        elif floor == 4:
            training_room = f"{ROOM_TRAINING_ROOM}_floor4"
        else:
            training_room = ROOM_TRAINING_ROOM
        
        new_employee.current_room = training_room
        new_employee.activity_state = "training"  # Mark as in training
        
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
    
    async def _hire_employee_specific(self, db: AsyncSession, business_context: dict, 
                                     department: str = None, title: str = None, role: str = "Employee"):
        """Hire a specific type of employee (e.g., IT, Reception)."""
        from database.models import Employee, Activity
        from datetime import datetime
        import random
        
        # Generate employee data
        first_names = ["Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Sage", "Blake", "Cameron"]
        last_names = ["Anderson", "Martinez", "Thompson", "Garcia", "Lee", "White", "Harris", "Clark", "Lewis", "Walker"]
        
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        hierarchy_level = 2 if role == "Manager" else 3
        
        # Determine title and department based on parameters
        if title:
            employee_title = title
        elif department == "IT":
            if role == "Manager":
                employee_title = "IT Manager"
            else:
                employee_title = random.choice(["IT Specialist", "IT Support Technician", "Network Administrator", "Systems Administrator"])
        elif department == "Administration" and title is None:
            employee_title = "Receptionist"
        elif title and ("Storage" in title or "Warehouse" in title or "Inventory" in title or "Stock" in title):
            # Storage employee titles
            employee_title = title
        elif department == "Operations" and title and "Storage" in title:
            employee_title = title
        else:
            # Fallback to generic titles
            employee_title = f"{department} {role}" if department else role
        
        if not department:
            department = "Operations"  # Default
        
        personality_traits = random.sample(
            ["analytical", "creative", "collaborative", "detail-oriented", "innovative", "reliable", "adaptable", "proactive"],
            k=3
        )
        
        new_employee = Employee(
            name=name,
            title=employee_title,
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
        
        # Assign home room and floor based on role/department
        home_room, floor = await assign_home_room(new_employee, db)
        new_employee.home_room = home_room
        new_employee.floor = floor
        
        # New hires start in training room on their assigned floor
        # Determine training room based on floor - check capacity and use floor 4 for overflow
        from employees.room_assigner import ROOM_TRAINING_ROOM
        from engine.movement_system import get_room_occupancy, get_room_capacity
        
        # Check if training rooms on floors 1-2 are full, use floor 4 for overflow
        floor1_occupancy = await get_room_occupancy(ROOM_TRAINING_ROOM, db)
        floor1_capacity = get_room_capacity(ROOM_TRAINING_ROOM)
        floor2_occupancy = await get_room_occupancy(f"{ROOM_TRAINING_ROOM}_floor2", db)
        floor2_capacity = get_room_capacity(f"{ROOM_TRAINING_ROOM}_floor2")
        
        # Helper function to find best available training room on floor 4
        async def find_best_floor4_training_room():
            floor4_training_rooms = [
                f"{ROOM_TRAINING_ROOM}_floor4",
                f"{ROOM_TRAINING_ROOM}_floor4_2",
                f"{ROOM_TRAINING_ROOM}_floor4_3",
                f"{ROOM_TRAINING_ROOM}_floor4_4",
                f"{ROOM_TRAINING_ROOM}_floor4_5"
            ]
            
            best_room = None
            most_space = -1
            
            for room_id in floor4_training_rooms:
                occupancy = await get_room_occupancy(room_id, db)
                capacity = get_room_capacity(room_id)
                available_space = capacity - occupancy
                
                if available_space > most_space:
                    most_space = available_space
                    best_room = room_id
            
            return best_room if best_room else f"{ROOM_TRAINING_ROOM}_floor4"  # Fallback
        
        # If floors 1-2 training rooms are near capacity, use floor 4
        if floor1_occupancy >= floor1_capacity - 2 or floor2_occupancy >= floor2_capacity - 2:
            training_room = await find_best_floor4_training_room()
            new_employee.floor = 4  # Update floor to 4 for training
        elif floor == 2:
            training_room = f"{ROOM_TRAINING_ROOM}_floor2"
        elif floor == 3:
            # Floor 3 doesn't have a training room, use floor 1, 2, or 4
            # Check which has space
            if floor1_occupancy < floor1_capacity:
                training_room = ROOM_TRAINING_ROOM
            elif floor2_occupancy < floor2_capacity:
                training_room = f"{ROOM_TRAINING_ROOM}_floor2"
                new_employee.floor = 2
            else:
                training_room = await find_best_floor4_training_room()
                new_employee.floor = 4
        elif floor == 4:
            training_room = await find_best_floor4_training_room()
        else:
            training_room = ROOM_TRAINING_ROOM
        
        new_employee.current_room = training_room
        new_employee.activity_state = "training"  # Mark as in training
        
        # Create activity
        activity = Activity(
            employee_id=None,
            activity_type="hiring",
            description=f"Hired {name} as {employee_title} in {department}",
            activity_metadata={"employee_id": None, "action": "hire"}
        )
        db.add(activity)
        
        await db.flush()
        activity.activity_metadata["employee_id"] = new_employee.id
        await db.commit()
        print(f"Hired specific employee: {name} ({employee_title}) in {department}")
    
    async def _fire_employee(self, db: AsyncSession, active_employees: list):
        """Fire an underperforming employee (not CEO, not last IT/Reception)."""
        from database.models import Activity
        from datetime import datetime
        from sqlalchemy import select
        
        # Don't fire CEO, and prefer firing regular employees over managers
        candidates = [e for e in active_employees if e.role != "CEO"]
        if not candidates:
            return
        
        # Count IT, Reception, and Storage employees to protect them
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%IT%") | Employee.title.ilike("%Information Technology%") | 
                 Employee.department.ilike("%IT%"))
            )
        )
        it_employees = result.scalars().all()
        it_count = len(it_employees)
        
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Reception%") | Employee.title.ilike("%Receptionist%"))
            )
        )
        reception_employees = result.scalars().all()
        reception_count = len(reception_employees)
        
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                (Employee.title.ilike("%Storage%") | Employee.title.ilike("%Warehouse%") | 
                 Employee.title.ilike("%Inventory%") | Employee.title.ilike("%Stock%"))
            )
        )
        storage_employees = result.scalars().all()
        storage_count = len(storage_employees)
        
        # Don't fire IT employees if we only have 1-2
        if it_count <= 2:
            it_titles = ["it", "information technology"]
            candidates = [e for e in candidates if not any(
                it_title in (e.title or "").lower() or it_title in (e.department or "").lower() 
                for it_title in it_titles
            )]
        
        # Don't fire Reception employees if we only have 1-2
        if reception_count <= 2:
            candidates = [e for e in candidates if not (
                "reception" in (e.title or "").lower() or "receptionist" in (e.title or "").lower()
            )]
        
        # Don't fire Storage employees if we only have 1-2
        if storage_count <= 2:
            candidates = [e for e in candidates if not (
                "storage" in (e.title or "").lower() or "warehouse" in (e.title or "").lower() or
                "inventory" in (e.title or "").lower() or "stock" in (e.title or "").lower()
            )]
        
        if not candidates:
            # If we filtered out all candidates, don't fire anyone
            return
        
        # Prefer firing employees over managers (70% chance)
        if random.random() < 0.7:
            candidates = [e for e in candidates if e.role == "Employee"]
        
        if not candidates:
            candidates = [e for e in active_employees if e.role != "CEO"]
            # Re-apply IT/Reception/Storage protection
            if it_count <= 2:
                it_titles = ["it", "information technology"]
                candidates = [e for e in candidates if not any(
                    it_title in (e.title or "").lower() or it_title in (e.department or "").lower() 
                    for it_title in it_titles
                )]
            if reception_count <= 2:
                candidates = [e for e in candidates if not (
                    "reception" in (e.title or "").lower() or "receptionist" in (e.title or "").lower()
                )]
            if storage_count <= 2:
                candidates = [e for e in candidates if not (
                    "storage" in (e.title or "").lower() or "warehouse" in (e.title or "").lower() or
                    "inventory" in (e.title or "").lower() or "stock" in (e.title or "").lower()
                )]
        
        if not candidates:
            return
        
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
    
    async def _manage_project_capacity(self, db: AsyncSession):
        """Periodically review project capacity and hire employees if needed instead of canceling."""
        from business.project_manager import ProjectManager
        from database.models import Activity
        
        project_manager = ProjectManager(db)
        
        # Check project overload (now returns hiring info instead of cancelling)
        overload_info = await project_manager.manage_project_overload()
        
        # If over capacity, hire employees instead of canceling projects!
        if overload_info.get("should_hire", False):
            employees_short = overload_info.get("employees_short", 0)
            project_count = overload_info.get("project_count", 0)
            employee_count = overload_info.get("employee_count", 0)
            max_projects = overload_info.get("max_projects", 0)
            
            # Hire 2-3 employees per check when over capacity
            # Respect max cap of 215 employees
            if employees_short > 0 and employee_count < MAX_EMPLOYEES:
                # For severe overload, hire more aggressively
                if employees_short > 20:
                    hires_needed = min(employees_short, random.randint(5, 8))  # Hire 5-8
                else:
                    hires_needed = min(employees_short, random.randint(2, 3))  # Hire 2-3
                # Don't exceed max cap
                hires_needed = min(hires_needed, MAX_EMPLOYEES - employee_count)
                business_context = await self.get_business_context(db)
                
                if hires_needed > 0:
                    for _ in range(hires_needed):
                        await self._hire_employee(db, business_context)
                
                # Create activity for hiring
                activity = Activity(
                    employee_id=None,
                    activity_type="hiring",
                    description=f"Hired {hires_needed} new employee(s) to support {project_count} active projects (capacity: {max_projects})",
                    activity_metadata={
                        "action": "capacity_hiring",
                        "projects": project_count,
                        "employees_hired": hires_needed,
                        "reason": "project_overload"
                    }
                )
                db.add(activity)
                await db.flush()
                print(f"Capacity management: Hired {hires_needed} employee(s) to support {project_count} projects (was over capacity: {max_projects})")
    
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

