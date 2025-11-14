from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from database.database import get_db
from database.models import Employee, Project, Task, Activity, Financial, BusinessMetric, Email, ChatMessage, BusinessSettings
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from business.goal_system import GoalSystem
from typing import List
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/employees")
async def get_employees(db: AsyncSession = Depends(get_db)):
    """Get all employees with termination reasons if applicable."""
    from database.models import Activity
    
    result = await db.execute(select(Employee).order_by(Employee.hierarchy_level, Employee.name))
    employees = result.scalars().all()
    
    # Get all firing activities to map termination reasons
    firing_result = await db.execute(
        select(Activity)
        .where(Activity.activity_type == "firing")
        .order_by(Activity.timestamp.desc())
    )
    firing_activities = firing_result.scalars().all()
    
    # Create a map of employee_id -> termination_reason
    termination_reasons = {}
    for activity in firing_activities:
        if activity.activity_metadata and isinstance(activity.activity_metadata, dict):
            emp_id = activity.activity_metadata.get("employee_id")
            if emp_id and emp_id not in termination_reasons:
                termination_reasons[emp_id] = activity.activity_metadata.get("termination_reason")
    
    employee_list = []
    for emp in employees:
        termination_reason = None
        # Get termination reason from map if employee is fired
        if (emp.status == "fired" or emp.fired_at) and emp.id in termination_reasons:
            termination_reason = termination_reasons[emp.id]
        
        employee_list.append({
            "id": emp.id,
            "name": emp.name,
            "title": emp.title,
            "role": emp.role,
            "hierarchy_level": emp.hierarchy_level,
            "department": emp.department,
            "status": emp.status,
            "current_task_id": emp.current_task_id,
            "personality_traits": emp.personality_traits,
            "backstory": emp.backstory,
            "avatar_path": emp.avatar_path if hasattr(emp, 'avatar_path') else None,
            "current_room": emp.current_room if hasattr(emp, 'current_room') else None,
            "home_room": emp.home_room if hasattr(emp, 'home_room') else None,
            "activity_state": emp.activity_state if hasattr(emp, 'activity_state') else "idle",
            "hired_at": emp.hired_at.isoformat() if hasattr(emp, 'hired_at') and emp.hired_at else None,
            "fired_at": emp.fired_at.isoformat() if hasattr(emp, 'fired_at') and emp.fired_at else None,
            "termination_reason": termination_reason,
            "created_at": emp.created_at.isoformat() if emp.created_at else None
        })
    
    return employee_list

@router.get("/employees/{employee_id}")
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get employee details."""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Get recent activities
    result = await db.execute(
        select(Activity)
        .where(Activity.employee_id == employee_id)
        .order_by(desc(Activity.timestamp))
        .limit(10)
    )
    activities = result.scalars().all()
    
    # Get recent decisions
    from database.models import Decision
    result = await db.execute(
        select(Decision)
        .where(Decision.employee_id == employee_id)
        .order_by(desc(Decision.timestamp))
        .limit(5)
    )
    decisions = result.scalars().all()
    
    return {
        "id": emp.id,
        "name": emp.name,
        "title": emp.title,
        "role": emp.role,
        "hierarchy_level": emp.hierarchy_level,
        "department": emp.department,
        "status": emp.status,
        "current_task_id": emp.current_task_id,
        "personality_traits": emp.personality_traits,
        "backstory": emp.backstory,
        "avatar_path": emp.avatar_path if hasattr(emp, 'avatar_path') else None,
        "current_room": emp.current_room if hasattr(emp, 'current_room') else None,
        "home_room": emp.home_room if hasattr(emp, 'home_room') else None,
        "activity_state": emp.activity_state if hasattr(emp, 'activity_state') else "idle",
        "hired_at": emp.hired_at.isoformat() if hasattr(emp, 'hired_at') and emp.hired_at else None,
        "fired_at": emp.fired_at.isoformat() if hasattr(emp, 'fired_at') and emp.fired_at else None,
        "activities": [
            {
                "id": act.id,
                "activity_type": act.activity_type,
                "description": act.description,
                "timestamp": act.timestamp.isoformat() if act.timestamp else None
            }
            for act in activities
        ],
        "decisions": [
            {
                "id": dec.id,
                "decision_type": dec.decision_type,
                "description": dec.description,
                "reasoning": dec.reasoning,
                "timestamp": dec.timestamp.isoformat() if dec.timestamp else None
            }
            for dec in decisions
        ]
    }

@router.get("/projects")
async def get_projects(db: AsyncSession = Depends(get_db)):
    """Get all projects."""
    try:
        result = await db.execute(select(Project).order_by(desc(Project.created_at)))
        projects = result.scalars().all()
        
        project_manager = ProjectManager(db)
        
        project_list = []
        for proj in projects:
            try:
                # If project is completed, it should always show 100% progress
                if proj.status == "completed":
                    progress = 100.0
                else:
                    progress = await project_manager.calculate_project_progress(proj.id)
                is_stalled = await project_manager.is_project_stalled(proj.id)
            except Exception as e:
                print(f"Error calculating progress for project {proj.id}: {e}")
                # If completed, still show 100%, otherwise 0%
                progress = 100.0 if proj.status == "completed" else 0.0
                is_stalled = False
            
            # Safely get last_activity_at if it exists
            last_activity = None
            if hasattr(proj, 'last_activity_at') and proj.last_activity_at:
                last_activity = proj.last_activity_at.isoformat() if hasattr(proj.last_activity_at, 'isoformat') else str(proj.last_activity_at)
            
            project_list.append({
                "id": proj.id,
                "name": proj.name,
                "description": proj.description,
                "status": proj.status,
                "priority": proj.priority,
                "budget": proj.budget,
                "revenue": proj.revenue,
                "deadline": proj.deadline.isoformat() if proj.deadline else None,
                "created_at": proj.created_at.isoformat() if proj.created_at else None,
                "completed_at": proj.completed_at.isoformat() if hasattr(proj, 'completed_at') and proj.completed_at else None,
                "last_activity_at": last_activity,
                "progress": progress,
                "is_stalled": is_stalled
            })
        
        return project_list
    except Exception as e:
        print(f"Error fetching projects: {e}")
        import traceback
        traceback.print_exc()
        return []

@router.get("/projects/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get project details."""
    project_manager = ProjectManager(db)
    project = await project_manager.get_project_by_id(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get tasks
    result = await db.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    
    # If project is completed, it should always show 100% progress
    if project.status == "completed":
        progress = 100.0
    else:
        progress = await project_manager.calculate_project_progress(project_id)
    
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "priority": project.priority,
        "budget": project.budget,
        "revenue": project.revenue,
        "deadline": project.deadline.isoformat() if project.deadline else None,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "completed_at": project.completed_at.isoformat() if hasattr(project, 'completed_at') and project.completed_at else None,
        "last_activity_at": project.last_activity_at.isoformat() if hasattr(project, 'last_activity_at') and project.last_activity_at else None,
        "progress": progress,
        "is_stalled": await project_manager.is_project_stalled(project_id),
        "tasks": [
            {
                "id": task.id,
                "employee_id": task.employee_id,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "progress": task.progress if hasattr(task, 'progress') else (100.0 if task.status == "completed" else 0.0),
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            for task in tasks
        ]
    }

@router.get("/projects/{project_id}/activities")
async def get_project_activities(project_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get activities related to a project."""
    # First verify project exists
    project = await ProjectManager(db).get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get activities from employees working on project tasks
    result = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = result.scalars().all()
    employee_ids = [task.employee_id for task in tasks if task.employee_id]
    
    all_activities = []
    
    # Get activities from employees working on this project
    if employee_ids:
        employee_activities_result = await db.execute(
            select(Activity)
            .where(Activity.employee_id.in_(employee_ids))
            .order_by(desc(Activity.timestamp))
            .limit(limit * 2)  # Get more to filter
        )
        employee_activities = employee_activities_result.scalars().all()
        all_activities.extend(employee_activities)
    
    # Get activities that mention the project name in description
    result = await db.execute(
        select(Activity)
        .where(Activity.description.contains(project.name))
        .order_by(desc(Activity.timestamp))
        .limit(limit * 2)
    )
    name_activities = result.scalars().all()
    all_activities.extend(name_activities)
    
    # Filter activities that are related to this project
    # Check metadata for project_id or description contains project name
    filtered_activities = []
    seen_ids = set()
    for act in all_activities:
        if act.id in seen_ids:
            continue
        seen_ids.add(act.id)
        
        # Check if activity metadata contains project_id
        is_related = False
        if act.activity_metadata and isinstance(act.activity_metadata, dict):
            if act.activity_metadata.get("project_id") == project_id:
                is_related = True
        
        # Check if description mentions project name
        if project.name.lower() in act.description.lower():
            is_related = True
        
        # Include activities from employees working on project (they're likely related)
        if act.employee_id in employee_ids:
            is_related = True
        
        if is_related:
            filtered_activities.append(act)
    
    # Sort by timestamp and limit
    filtered_activities.sort(key=lambda x: x.timestamp if x.timestamp else datetime.min, reverse=True)
    activities = filtered_activities[:limit]
    
    # Get employee names
    result = await db.execute(select(Employee))
    all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    
    return [
        {
            "id": act.id,
            "employee_id": act.employee_id,
            "employee_name": all_employees.get(act.employee_id, "Unknown") if act.employee_id else None,
            "activity_type": act.activity_type,
            "description": act.description,
            "metadata": act.activity_metadata,
            "timestamp": (act.timestamp or datetime.utcnow()).isoformat()
        }
        for act in activities
    ]

@router.get("/activities")
async def get_activities(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent activities."""
    result = await db.execute(
        select(Activity)
        .order_by(desc(Activity.timestamp))
        .limit(limit)
    )
    activities = result.scalars().all()
    
    return [
        {
            "id": act.id,
            "employee_id": act.employee_id,
            "activity_type": act.activity_type,
            "description": act.description,
            "metadata": act.activity_metadata,
            "timestamp": (act.timestamp or datetime.utcnow()).isoformat()
        }
        for act in activities
    ]

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Get business metrics."""
    result = await db.execute(
        select(BusinessMetric)
        .order_by(desc(BusinessMetric.timestamp))
        .limit(100)
    )
    metrics = result.scalars().all()
    
    # Group by metric name and get latest
    metric_dict = {}
    for metric in metrics:
        if metric.metric_name not in metric_dict:
            metric_dict[metric.metric_name] = metric.value
    
    return metric_dict

@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get dashboard data."""
    try:
        financial_manager = FinancialManager(db)
        project_manager = ProjectManager(db)
        goal_system = GoalSystem(db)
        
        revenue = await financial_manager.get_total_revenue()
        profit = await financial_manager.get_profit()
        expenses = await financial_manager.get_total_expenses()
        
        active_projects = await project_manager.get_active_projects()
        
        # Get only active employees (not terminated)
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        
        # Get recent activities
        result = await db.execute(
            select(Activity)
            .order_by(desc(Activity.timestamp))
            .limit(20)
        )
        recent_activities = result.scalars().all()
        
        goals = await goal_system.get_business_goals()
        goal_progress = await goal_system.evaluate_goals()
        
        # Get business settings
        result = await db.execute(select(BusinessSettings))
        business_settings = result.scalars().all()
        settings_dict = {setting.setting_key: setting.setting_value for setting in business_settings}
        
        business_name = settings_dict.get("business_name", "TechFlow Solutions")
        business_mission = settings_dict.get("business_mission", "To deliver innovative technology solutions that empower businesses to achieve their goals through cutting-edge software development and consulting services.")
        business_industry = settings_dict.get("business_industry", "Technology & Software Development")
        business_founded = settings_dict.get("business_founded", "2024")
        business_location = settings_dict.get("business_location", "San Francisco, CA")
        
        # Get all projects for company overview
        result = await db.execute(select(Project).order_by(desc(Project.created_at)))
        all_projects = result.scalars().all()
        
        # Calculate project statistics
        completed_projects = [p for p in all_projects if p.status == "completed"]
        total_projects = len(all_projects)
        total_project_revenue = sum(p.revenue or 0.0 for p in all_projects)
        
        # Get employee statistics by department
        departments = {}
        role_distribution = {}
        for emp in active_employees:
            dept = emp.department or "Unassigned"
            departments[dept] = departments.get(dept, 0) + 1
            role = emp.role or "Employee"
            role_distribution[role] = role_distribution.get(role, 0) + 1
        
        # Get CEO for company leadership info
        result = await db.execute(
            select(Employee).where(Employee.role == "CEO", Employee.status == "active")
        )
        ceo = result.scalar_one_or_none()
        ceo_name = ceo.name if ceo else "Not Assigned"
        
        # Calculate average project budget
        projects_with_budget = [p for p in all_projects if p.budget and p.budget > 0]
        avg_project_budget = sum(p.budget for p in projects_with_budget) / len(projects_with_budget) if projects_with_budget else 0.0
        
        return {
            "business_name": business_name,
            "revenue": revenue or 0.0,
            "profit": profit or 0.0,
            "expenses": expenses or 0.0,
            "active_projects": len(active_projects),
            "employee_count": len(active_employees),
            "recent_activities": [
                {
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "activity_type": act.activity_type,
                    "description": act.description,
                    "timestamp": (act.timestamp or datetime.utcnow()).isoformat()
                }
                for act in recent_activities
            ],
            "goals": goals,
            "goal_progress": goal_progress,
            # Company overview data
            "company_overview": {
                "business_name": business_name,
                "mission": business_mission,
                "industry": business_industry,
                "founded": business_founded,
                "location": business_location,
                "ceo": ceo_name,
                "total_projects": total_projects,
                "completed_projects": len(completed_projects),
                "active_projects_count": len(active_projects),
                "total_project_revenue": total_project_revenue,
                "average_project_budget": avg_project_budget,
                "departments": departments,
                "role_distribution": role_distribution,
                "products_services": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description or "No description available",
                        "status": p.status,
                        "revenue": p.revenue or 0.0,
                        "budget": p.budget or 0.0,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                        "completed_at": p.completed_at.isoformat() if p.completed_at else None
                    }
                    for p in all_projects[:20]  # Limit to 20 most recent projects
                ]
            }
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in dashboard endpoint: {e}")
        print(error_details)
        # Return default values instead of crashing
        return {
            "business_name": "TechFlow Solutions",
            "revenue": 0.0,
            "profit": 0.0,
            "expenses": 0.0,
            "active_projects": 0,
            "employee_count": 0,
            "recent_activities": [],
            "goals": [],
            "goal_progress": {},
            "company_overview": {
                "business_name": "TechFlow Solutions",
                "mission": "To deliver innovative technology solutions that empower businesses to achieve their goals through cutting-edge software development and consulting services.",
                "industry": "Technology & Software Development",
                "founded": "2024",
                "location": "San Francisco, CA",
                "ceo": "Not Assigned",
                "total_projects": 0,
                "completed_projects": 0,
                "active_projects_count": 0,
                "total_project_revenue": 0.0,
                "average_project_budget": 0.0,
                "departments": {},
                "role_distribution": {},
                "products_services": []
            }
        }

@router.get("/financials")
async def get_financials(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get financial data."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Financial)
        .where(Financial.timestamp >= cutoff)
        .order_by(desc(Financial.timestamp))
    )
    financials = result.scalars().all()
    
    return [
        {
            "id": fin.id,
            "type": fin.type,
            "amount": fin.amount,
            "description": fin.description,
            "project_id": fin.project_id,
            "timestamp": fin.timestamp.isoformat() if fin.timestamp else None
        }
        for fin in financials
    ]

@router.get("/financials/analytics")
async def get_financial_analytics(days: int = 90, db: AsyncSession = Depends(get_db)):
    """Get detailed financial analytics including payroll, trends, and breakdowns."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get all financial transactions
    result = await db.execute(
        select(Financial)
        .where(Financial.timestamp >= cutoff)
        .order_by(Financial.timestamp)
    )
    financials = result.scalars().all()
    
    # Get all active employees for payroll calculation
    result = await db.execute(
        select(Employee).where(Employee.status == "active")
    )
    employees = result.scalars().all()
    
    # Calculate payroll based on hierarchy level and role
    # CEO: $150k/year, Manager: $100k/year, Employee: $60k/year
    payroll_by_role = {}
    total_payroll = 0.0
    payroll_by_department = {}
    
    for emp in employees:
        # Calculate annual salary based on role
        if emp.role == "CEO" or emp.hierarchy_level == 1:
            annual_salary = 150000
        elif emp.role == "Manager" or emp.hierarchy_level == 2:
            annual_salary = 100000
        else:
            annual_salary = 60000
        
        # Calculate monthly salary
        monthly_salary = annual_salary / 12
        # Calculate for the period (days / 30.44 average days per month)
        period_salary = monthly_salary * (days / 30.44)
        
        total_payroll += period_salary
        
        # Group by role
        role = emp.role or "Employee"
        if role not in payroll_by_role:
            payroll_by_role[role] = 0.0
        payroll_by_role[role] += period_salary
        
        # Group by department
        dept = emp.department or "Unassigned"
        if dept not in payroll_by_department:
            payroll_by_department[dept] = 0.0
        payroll_by_department[dept] += period_salary
    
    # Categorize expenses
    expense_categories = {}
    income_sources = {}
    
    for fin in financials:
        desc = (fin.description or "").lower()
        amount = fin.amount
        
        if fin.type == "expense":
            # Categorize expenses
            if "salary" in desc or "payroll" in desc or "wage" in desc:
                category = "Payroll"
            elif "rent" in desc or "office" in desc or "facility" in desc:
                category = "Facilities"
            elif "equipment" in desc or "hardware" in desc or "software" in desc or "license" in desc:
                category = "Equipment & Software"
            elif "marketing" in desc or "advertising" in desc or "promotion" in desc:
                category = "Marketing"
            elif "travel" in desc or "transport" in desc:
                category = "Travel"
            elif "utilities" in desc or "electric" in desc or "water" in desc or "internet" in desc:
                category = "Utilities"
            elif "project" in desc:
                category = "Project Costs"
            else:
                category = "Other Expenses"
            
            if category not in expense_categories:
                expense_categories[category] = 0.0
            expense_categories[category] += amount
        else:
            # Categorize income
            if "project" in desc:
                category = "Project Revenue"
            elif "sale" in desc or "product" in desc:
                category = "Product Sales"
            elif "service" in desc or "consulting" in desc:
                category = "Services"
            else:
                category = "Other Income"
            
            if category not in income_sources:
                income_sources[category] = 0.0
            income_sources[category] += amount
    
    # Add payroll to expenses if not already there
    if total_payroll > 0:
        if "Payroll" not in expense_categories:
            expense_categories["Payroll"] = 0.0
        expense_categories["Payroll"] += total_payroll
    
    # Calculate daily trends
    daily_data = {}
    for fin in financials:
        date_key = fin.timestamp.date().isoformat() if fin.timestamp else datetime.utcnow().date().isoformat()
        if date_key not in daily_data:
            daily_data[date_key] = {"income": 0.0, "expenses": 0.0}
        
        if fin.type == "income":
            daily_data[date_key]["income"] += fin.amount
        else:
            daily_data[date_key]["expenses"] += fin.amount
    
    # Convert to sorted list
    daily_trends = [
        {
            "date": date,
            "income": data["income"],
            "expenses": data["expenses"],
            "profit": data["income"] - data["expenses"]
        }
        for date, data in sorted(daily_data.items())
    ]
    
    # Calculate totals
    total_income = sum(f.amount for f in financials if f.type == "income")
    total_expenses = sum(f.amount for f in financials if f.type == "expense") + total_payroll
    net_profit = total_income - total_expenses
    
    return {
        "summary": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "payroll": total_payroll,
            "period_days": days
        },
        "payroll": {
            "total": total_payroll,
            "by_role": payroll_by_role,
            "by_department": payroll_by_department,
            "employee_count": len(employees)
        },
        "expense_categories": expense_categories,
        "income_sources": income_sources,
        "daily_trends": daily_trends,
        "employee_details": [
            {
                "id": emp.id,
                "name": emp.name,
                "role": emp.role,
                "department": emp.department,
                "hierarchy_level": emp.hierarchy_level,
                "estimated_annual_salary": 150000 if (emp.role == "CEO" or emp.hierarchy_level == 1) else (100000 if (emp.role == "Manager" or emp.hierarchy_level == 2) else 60000),
                "period_salary": (150000 if (emp.role == "CEO" or emp.hierarchy_level == 1) else (100000 if (emp.role == "Manager" or emp.hierarchy_level == 2) else 60000)) / 12 * (days / 30.44)
            }
            for emp in employees
        ]
    }

@router.get("/employees/{employee_id}/emails")
async def get_employee_emails(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get emails for a specific employee."""
    try:
        result = await db.execute(
            select(Email)
            .where((Email.sender_id == employee_id) | (Email.recipient_id == employee_id))
            .order_by(desc(Email.timestamp))
            .limit(50)
        )
        emails = result.scalars().all()
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        return [
            {
                "id": email.id,
                "sender_id": email.sender_id,
                "sender_name": all_employees.get(email.sender_id, "Unknown"),
                "recipient_id": email.recipient_id,
                "recipient_name": all_employees.get(email.recipient_id, "Unknown"),
                "subject": email.subject,
                "body": email.body,
                "read": email.read,
                "thread_id": email.thread_id,
                "timestamp": email.timestamp.isoformat() if email.timestamp else None
            }
            for email in emails
        ]
    except Exception as e:
        # If Email table doesn't exist yet, return empty list
        print(f"Error fetching emails: {e}")
        return []

@router.get("/employees/{employee_id}/chats")
async def get_employee_chats(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get chat messages for a specific employee."""
    try:
        result = await db.execute(
            select(ChatMessage)
            .where((ChatMessage.sender_id == employee_id) | (ChatMessage.recipient_id == employee_id))
            .order_by(desc(ChatMessage.timestamp))
            .limit(100)
        )
        chats = result.scalars().all()
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        return [
            {
                "id": chat.id,
                "sender_id": chat.sender_id,
                "sender_name": all_employees.get(chat.sender_id, "Unknown"),
                "recipient_id": chat.recipient_id,
                "recipient_name": all_employees.get(chat.recipient_id, "Unknown"),
                "message": chat.message,
                "thread_id": chat.thread_id,
                "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
            }
            for chat in chats
        ]
    except Exception as e:
        # If ChatMessage table doesn't exist yet, return empty list
        print(f"Error fetching chats: {e}")
        return []

@router.get("/emails")
async def get_all_emails(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Get all emails (Outlook view)."""
    try:
        result = await db.execute(
            select(Email)
            .order_by(desc(Email.timestamp))
            .limit(limit)
        )
        emails = result.scalars().all()
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        return [
            {
                "id": email.id,
                "sender_id": email.sender_id,
                "sender_name": all_employees.get(email.sender_id, "Unknown"),
                "recipient_id": email.recipient_id,
                "recipient_name": all_employees.get(email.recipient_id, "Unknown"),
                "subject": email.subject,
                "body": email.body,
                "read": email.read,
                "thread_id": email.thread_id,
                "timestamp": email.timestamp.isoformat() if email.timestamp else None
            }
            for email in emails
        ]
    except Exception as e:
        # If Email table doesn't exist yet, return empty list
        print(f"Error fetching all emails: {e}")
        return []

@router.get("/chats")
async def get_all_chats(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """Get all chat messages (Teams view)."""
    try:
        result = await db.execute(
            select(ChatMessage)
            .order_by(desc(ChatMessage.timestamp))
            .limit(limit)
        )
        chats = result.scalars().all()
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        return [
            {
                "id": chat.id,
                "sender_id": chat.sender_id,
                "sender_name": all_employees.get(chat.sender_id, "Unknown"),
                "recipient_id": chat.recipient_id,
                "recipient_name": all_employees.get(chat.recipient_id, "Unknown"),
                "message": chat.message,
                "thread_id": chat.thread_id,
                "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
            }
            for chat in chats
        ]
    except Exception as e:
        # If ChatMessage table doesn't exist yet, return empty list
        print(f"Error fetching all chats: {e}")
        return []

@router.get("/office-layout")
async def get_office_layout(db: AsyncSession = Depends(get_db)):
    """Get office layout with all rooms and employees in each room for both floors."""
    # Define room metadata (outside try block so it's always available)
    ROOM_OPEN_OFFICE = "open_office"
    ROOM_CUBICLES = "cubicles"
    ROOM_CONFERENCE_ROOM = "conference_room"
    ROOM_BREAKROOM = "breakroom"
    ROOM_RECEPTION = "reception"
    ROOM_IT_ROOM = "it_room"
    ROOM_MANAGER_OFFICE = "manager_office"
    ROOM_TRAINING_ROOM = "training_room"
    ROOM_LOUNGE = "lounge"
    ROOM_STORAGE = "storage"
    
    # Floor 1 layout (original)
    floor1_rooms = [
            {
                "id": ROOM_OPEN_OFFICE,
                "name": "Open Office",
                "image_path": "/office_layout/layout01_open_office.png",
                "capacity": 20,
                "floor": 1
            },
            {
                "id": ROOM_CUBICLES,
                "name": "Cubicles",
                "image_path": "/office_layout/layout02_cubicles.png",
                "capacity": 15,
                "floor": 1
            },
            {
                "id": ROOM_CONFERENCE_ROOM,
                "name": "Conference Room",
                "image_path": "/office_layout/layout03_conference_room.png",
                "capacity": 10,
                "floor": 1
            },
            {
                "id": ROOM_BREAKROOM,
                "name": "Breakroom",
                "image_path": "/office_layout/layout04_breakroom.png",
                "capacity": 8,
                "floor": 1
            },
            {
                "id": ROOM_RECEPTION,
                "name": "Reception",
                "image_path": "/office_layout/layout05_reception.png",
                "capacity": 3,
                "floor": 1
            },
            {
                "id": ROOM_IT_ROOM,
                "name": "IT Room",
                "image_path": "/office_layout/layout06_it_room.png",
                "capacity": 5,
                "floor": 1
            },
            {
                "id": ROOM_MANAGER_OFFICE,
                "name": "Manager Office",
                "image_path": "/office_layout/layout07_manager_office.png",
                "capacity": 6,
                "floor": 1
            },
            {
                "id": ROOM_TRAINING_ROOM,
                "name": "Training Room",
                "image_path": "/office_layout/layout08_training_room.png",
                "capacity": 12,
                "floor": 1
            },
            {
                "id": ROOM_LOUNGE,
                "name": "Lounge",
                "image_path": "/office_layout/layout09_lounge.png",
                "capacity": 10,
                "floor": 1
            },
            {
                "id": ROOM_STORAGE,
                "name": "Storage",
                "image_path": "/office_layout/layout10_storage.png",
                "capacity": 2,
                "floor": 1
            }
        ]
    
    # Floor 2 layout (different arrangement - same 10 rooms but different layout)
    floor2_rooms = [
            {
                "id": f"{ROOM_OPEN_OFFICE}_floor2",
                "name": "Open Office",
                "image_path": "/office_layout/layout01_open_office.png",
                "capacity": 25,
                "floor": 2
            },
            {
                "id": f"{ROOM_CUBICLES}_floor2",
                "name": "Cubicles",
                "image_path": "/office_layout/layout02_cubicles.png",
                "capacity": 20,
                "floor": 2
            },
            {
                "id": f"{ROOM_CONFERENCE_ROOM}_floor2",
                "name": "Conference Room",
                "image_path": "/office_layout/layout03_conference_room.png",
                "capacity": 12,
                "floor": 2
            },
            {
                "id": f"{ROOM_BREAKROOM}_floor2",
                "name": "Breakroom",
                "image_path": "/office_layout/layout04_breakroom.png",
                "capacity": 10,
                "floor": 2
            },
            {
                "id": f"{ROOM_RECEPTION}_floor2",
                "name": "Reception",
                "image_path": "/office_layout/layout05_reception.png",
                "capacity": 3,
                "floor": 2
            },
            {
                "id": f"{ROOM_IT_ROOM}_floor2",
                "name": "IT Room",
                "image_path": "/office_layout/layout06_it_room.png",
                "capacity": 6,
                "floor": 2
            },
            {
                "id": f"{ROOM_MANAGER_OFFICE}_floor2",
                "name": "Manager Office",
                "image_path": "/office_layout/layout07_manager_office.png",
                "capacity": 8,
                "floor": 2
            },
            {
                "id": f"{ROOM_TRAINING_ROOM}_floor2",
                "name": "Training Room",
                "image_path": "/office_layout/layout08_training_room.png",
                "capacity": 15,
                "floor": 2
            },
            {
                "id": f"{ROOM_LOUNGE}_floor2",
                "name": "Lounge",
                "image_path": "/office_layout/layout09_lounge.png",
                "capacity": 12,
                "floor": 2
            },
            {
                "id": f"{ROOM_STORAGE}_floor2",
                "name": "Storage",
                "image_path": "/office_layout/layout10_storage.png",
                "capacity": 3,
                "floor": 2
            }
        ]
    
    # Combine all rooms
    rooms = floor1_rooms + floor2_rooms
    
    try:
        # Get ALL employees
        result = await db.execute(select(Employee))
        all_employees = result.scalars().all()
        
        # Separate active and terminated employees
        active_employees = []
        terminated_employees = []
        
        for employee in all_employees:
            if employee.status == "fired" or employee.status == "terminated":
                terminated_employees.append(employee)
            else:
                active_employees.append(employee)
        
        # Get recent activities for employees in conference rooms (to show meeting info)
        from database.models import Activity, Task
        from sqlalchemy import desc
        from datetime import datetime, timedelta
        
        # Get activities from the last 2 hours for employees (broader time window)
        recent_cutoff = datetime.utcnow() - timedelta(hours=2)
        result = await db.execute(
            select(Activity).where(
                Activity.timestamp >= recent_cutoff
            ).order_by(desc(Activity.timestamp))
        )
        recent_activities = result.scalars().all()
        
        # Map employee IDs to their recent activities (prioritize meeting-related)
        employee_activities = {}
        for activity in recent_activities:
            if activity.employee_id:
                if activity.employee_id not in employee_activities:
                    employee_activities[activity.employee_id] = []
                employee_activities[activity.employee_id].append({
                    "description": activity.description,
                    "activity_type": activity.activity_type,
                    "timestamp": activity.timestamp.isoformat() if activity.timestamp else None
                })
        
        # Also get current tasks for employees
        result = await db.execute(
            select(Task).where(
                Task.status.in_(["pending", "in_progress"])
            )
        )
        active_tasks = result.scalars().all()
        employee_tasks = {task.employee_id: task for task in active_tasks if task.employee_id}
        
        # Group active employees by floor and room (only include those with a room assigned)
        employees_by_room = {}
        active_with_rooms = []
        for employee in active_employees:
            # Safely get room fields (they might not exist in old database)
            current_room = getattr(employee, 'current_room', None)
            home_room = getattr(employee, 'home_room', None)
            activity_state = getattr(employee, 'activity_state', 'idle')
            floor = getattr(employee, 'floor', 1)  # Default to floor 1 if not set
            
            room = current_room or home_room
            if room:
                # Create room key with floor suffix if needed
                # If room already has _floor2 suffix, use it as-is
                if room.endswith('_floor2'):
                    room_key = room
                # For floor 2, add _floor2 suffix if not already present
                elif floor == 2:
                    # Check if this is a base room that should be on floor 2
                    base_room = room
                    room_key = f"{base_room}_floor2"
                # For floor 1, use room as-is (no suffix)
                elif floor == 1:
                    room_key = room
                else:
                    # Fallback: use room as-is
                    room_key = room
                
                if room_key not in employees_by_room:
                    employees_by_room[room_key] = []
                
                # Get recent activity for this employee if they're in a conference room
                employee_activity_info = None
                if "conference_room" in room_key.lower():
                    # Check if employee is in a meeting state
                    if activity_state == "meeting":
                        # Get the most recent activity (prioritize meeting-related, but use any meaningful activity)
                        if employee.id in employee_activities:
                            activities = employee_activities[employee.id]
                            # Prefer meeting activities, but use any recent activity that might indicate meeting topic
                            meeting_activities = [a for a in activities if "meeting" in a.get("activity_type", "").lower() or "meeting" in a.get("description", "").lower()]
                            if meeting_activities:
                                employee_activity_info = meeting_activities[0]
                            elif activities:
                                # Use most recent activity - it might be about what they're discussing
                                employee_activity_info = activities[0]  # Most recent
                        
                        # If no activity but has a task, use task description to infer meeting topic
                        if not employee_activity_info and employee.id in employee_tasks:
                            task = employee_tasks[employee.id]
                            # Try to get project name if task is associated with a project
                            project_name = ""
                            if task.project_id:
                                from database.models import Project
                                result = await db.execute(select(Project).where(Project.id == task.project_id))
                                project = result.scalar_one_or_none()
                                if project:
                                    project_name = f" for {project.name}"
                            employee_activity_info = {
                                "description": f"Discussing {task.description}{project_name}",
                                "activity_type": "meeting",
                                "timestamp": None
                            }
                
                employees_by_room[room_key].append({
                    "id": employee.id,
                    "name": employee.name,
                    "title": employee.title,
                    "role": employee.role,
                    "department": employee.department,
                    "status": employee.status,
                    "current_room": current_room,
                    "home_room": home_room,
                    "floor": floor,
                    "activity_state": activity_state,
                    "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None,
                    "recent_activity": employee_activity_info
                })
                active_with_rooms.append(employee)
        
        # Add active employees to each room and gather meeting information for conference rooms
        # Also add fallback matching for reception and storage employees
        # First, collect all employee IDs that are already assigned to rooms
        assigned_employee_ids = set()
        for room in rooms:
            room["employees"] = employees_by_room.get(room["id"], [])
            for emp in room["employees"]:
                assigned_employee_ids.add(emp["id"])
        
        # Fallback: Match reception and storage employees by title if they're not already assigned
        # This handles cases where employees might not have correct room assignments
        for room in rooms:
            if "reception" in room["id"].lower():
                for employee in active_employees:
                    # Skip if already assigned to any room
                    if employee.id in assigned_employee_ids:
                        continue
                    
                    title = (employee.title or "").lower()
                    home_room = getattr(employee, 'home_room', None)
                    current_room = getattr(employee, 'current_room', None)
                    floor = getattr(employee, 'floor', 1)
                    
                    # Check if employee is a receptionist and should be in this room
                    is_receptionist = "reception" in title or "receptionist" in title
                    if is_receptionist:
                        # Check if this room matches their floor
                        room_floor = room.get("floor", 1)
                        if floor == room_floor:
                            # Check if their home_room or current_room matches this room type
                            emp_room = current_room or home_room
                            if not emp_room or "reception" in emp_room.lower():
                                # Add to this room
                                room["employees"].append({
                                    "id": employee.id,
                                    "name": employee.name,
                                    "title": employee.title,
                                    "role": employee.role,
                                    "department": employee.department,
                                    "status": employee.status,
                                    "current_room": current_room,
                                    "home_room": home_room,
                                    "floor": floor,
                                    "activity_state": getattr(employee, 'activity_state', 'idle'),
                                    "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None,
                                    "recent_activity": None
                                })
                                assigned_employee_ids.add(employee.id)
            
            # Similar fallback for storage employees
            if "storage" in room["id"].lower():
                for employee in active_employees:
                    # Skip if already assigned to any room
                    if employee.id in assigned_employee_ids:
                        continue
                    
                    title = (employee.title or "").lower()
                    home_room = getattr(employee, 'home_room', None)
                    current_room = getattr(employee, 'current_room', None)
                    floor = getattr(employee, 'floor', 1)
                    
                    # Check if employee is storage staff and should be in this room
                    is_storage = ("storage" in title or "warehouse" in title or 
                                 "inventory" in title or "stock" in title)
                    if is_storage:
                        # Check if this room matches their floor
                        room_floor = room.get("floor", 1)
                        if floor == room_floor:
                            # Check if their home_room or current_room matches this room type
                            emp_room = current_room or home_room
                            if not emp_room or "storage" in emp_room.lower():
                                # Add to this room
                                room["employees"].append({
                                    "id": employee.id,
                                    "name": employee.name,
                                    "title": employee.title,
                                    "role": employee.role,
                                    "department": employee.department,
                                    "status": employee.status,
                                    "current_room": current_room,
                                    "home_room": home_room,
                                    "floor": floor,
                                    "activity_state": getattr(employee, 'activity_state', 'idle'),
                                    "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None,
                                    "recent_activity": None
                                })
                                assigned_employee_ids.add(employee.id)
            
            # For conference rooms, collect meeting information
            if "conference_room" in room["id"].lower():
                # Get employees who are actually in a meeting (activity_state == "meeting")
                meeting_employees = [e for e in room["employees"] if e.get("activity_state") == "meeting"]
                
                meeting_info = []
                seen_descriptions = set()
                
                # If there are employees in meeting state, collect their meeting info
                if meeting_employees:
                    # Group employees by their meeting description
                    meeting_groups = {}
                    for emp in meeting_employees:
                        desc = None
                        if emp.get("recent_activity") and emp["recent_activity"].get("description"):
                            desc = emp["recent_activity"]["description"]
                            # Clean up description - remove employee name prefixes if present
                            # e.g., "John decided: ..." -> "..."
                            if " decided: " in desc:
                                desc = desc.split(" decided: ", 1)[1]
                            elif desc.startswith(emp.get("name", "") + " "):
                                # Remove name prefix
                                desc = desc[len(emp.get("name", "")):].strip()
                                if desc.startswith(":"):
                                    desc = desc[1:].strip()
                        
                        # Use description as key to group participants
                        if desc and desc.strip() and not desc.lower().startswith("meeting with"):
                            # Normalize description for grouping (case-insensitive)
                            desc_key = desc.strip()
                            if desc_key not in meeting_groups:
                                meeting_groups[desc_key] = {
                                    "description": desc_key,
                                    "activity_type": emp.get("recent_activity", {}).get("activity_type", "meeting"),
                                    "participants": []
                                }
                            meeting_groups[desc_key]["participants"].append(emp["name"])
                    
                    # Convert to list
                    meeting_info = list(meeting_groups.values())
                    
                    # If we have multiple groups, try to find common themes
                    if len(meeting_info) > 1:
                        # Extract common keywords from descriptions
                        from collections import Counter
                        all_words = []
                        for info in meeting_info:
                            words = info["description"].lower().split()
                            # Filter out common words
                            common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "about", "discussing", "meeting"}
                            words = [w for w in words if w not in common_words and len(w) > 3]
                            all_words.extend(words)
                        
                        if all_words:
                            word_counts = Counter(all_words)
                            common_theme = word_counts.most_common(1)[0][0]
                            # Create a combined meeting description
                            meeting_info = [{
                                "description": f"Team meeting about {common_theme}",
                                "activity_type": "meeting",
                                "participants": [e["name"] for e in meeting_employees]
                            }]
                
                # If no specific meeting info but there are employees in the room, try to infer from their work
                if not meeting_info and len(room["employees"]) > 0:
                    # Try to get meeting topic from employees' tasks and projects
                    meeting_topics = []
                    for emp in room["employees"]:
                        emp_id = emp.get("id")
                        if emp_id and emp_id in employee_tasks:
                            task = employee_tasks[emp_id]
                            topic = task.description
                            # Try to get project name
                            if task.project_id:
                                from database.models import Project
                                result = await db.execute(select(Project).where(Project.id == task.project_id))
                                project = result.scalar_one_or_none()
                                if project:
                                    topic = f"{project.name}: {task.description}"
                            meeting_topics.append(topic)
                    
                    # Also check recent activities
                    all_activities = [e.get("recent_activity", {}).get("description") for e in room["employees"] if e.get("recent_activity")]
                    for act_desc in all_activities:
                        if act_desc and not act_desc.lower().startswith("meeting with"):
                            # Clean up activity descriptions
                            if " decided: " in act_desc:
                                act_desc = act_desc.split(" decided: ", 1)[1]
                            meeting_topics.append(act_desc)
                    
                    if meeting_topics:
                        # Use the most common topic
                        from collections import Counter
                        topic_counts = Counter(meeting_topics)
                        most_common = topic_counts.most_common(1)[0][0]
                        # Clean up the description
                        if most_common.lower().startswith("discussing "):
                            most_common = most_common[11:]  # Remove "discussing " prefix
                        meeting_info.append({
                            "description": most_common,
                            "activity_type": "meeting",
                            "participants": [e["name"] for e in room["employees"]]
                        })
                    else:
                        # Last resort: generic meeting description
                        meeting_info.append({
                            "description": f"Team meeting with {len(room['employees'])} participant(s)",
                            "activity_type": "meeting",
                            "participants": [e["name"] for e in room["employees"]]
                        })
                
                room["meeting_info"] = meeting_info
        
        # Format terminated employees
        terminated_list = []
        for employee in terminated_employees:
            terminated_list.append({
                "id": employee.id,
                "name": employee.name,
                "title": employee.title,
                "role": employee.role,
                "department": employee.department,
                "status": employee.status,
                "current_room": getattr(employee, 'current_room', None),
                "home_room": getattr(employee, 'home_room', None),
                "activity_state": getattr(employee, 'activity_state', 'idle'),
                "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None,
                "fired_at": employee.fired_at.isoformat() if hasattr(employee, 'fired_at') and employee.fired_at else None
            })
        
        # Group rooms by floor
        rooms_by_floor = {
            1: [r for r in rooms if r["floor"] == 1],
            2: [r for r in rooms if r["floor"] == 2]
        }
        
        return {
            "rooms": rooms,
            "rooms_by_floor": rooms_by_floor,
            "floors": [1, 2],
            "terminated_employees": terminated_list,
            "total_employees": len(active_with_rooms),
            "total_terminated": len(terminated_employees),
            "total_all_employees": len(all_employees)
        }
    except Exception as e:
        print(f"Error fetching office layout: {e}")
        import traceback
        traceback.print_exc()
        # Return rooms even on error (just without employees)
        for room in rooms:
            room["employees"] = []
        return {
            "rooms": rooms,
            "total_employees": 0
        }

