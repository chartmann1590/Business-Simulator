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
                progress = await project_manager.calculate_project_progress(proj.id)
                is_stalled = await project_manager.is_project_stalled(proj.id)
            except Exception as e:
                print(f"Error calculating progress for project {proj.id}: {e}")
                progress = 0.0
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
            "timestamp": act.timestamp.isoformat() if act.timestamp else None
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
        
        # Get business name
        result = await db.execute(
            select(BusinessSettings).where(BusinessSettings.setting_key == "business_name")
        )
        business_setting = result.scalar_one_or_none()
        business_name = business_setting.setting_value if business_setting else "TechFlow Solutions"
        
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
                    "timestamp": act.timestamp.isoformat() if act.timestamp else None
                }
                for act in recent_activities
            ],
            "goals": goals,
            "goal_progress": goal_progress
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
            "goal_progress": {}
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
    """Get office layout with all rooms and employees in each room."""
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
    
    rooms = [
            {
                "id": ROOM_OPEN_OFFICE,
                "name": "Open Office",
                "image_path": "/office_layout/layout01_open_office.png",
                "capacity": 20
            },
            {
                "id": ROOM_CUBICLES,
                "name": "Cubicles",
                "image_path": "/office_layout/layout02_cubicles.png",
                "capacity": 15
            },
            {
                "id": ROOM_CONFERENCE_ROOM,
                "name": "Conference Room",
                "image_path": "/office_layout/layout03_conference_room.png",
                "capacity": 10
            },
            {
                "id": ROOM_BREAKROOM,
                "name": "Breakroom",
                "image_path": "/office_layout/layout04_breakroom.png",
                "capacity": 8
            },
            {
                "id": ROOM_RECEPTION,
                "name": "Reception",
                "image_path": "/office_layout/layout05_reception.png",
                "capacity": 3
            },
            {
                "id": ROOM_IT_ROOM,
                "name": "IT Room",
                "image_path": "/office_layout/layout06_it_room.png",
                "capacity": 5
            },
            {
                "id": ROOM_MANAGER_OFFICE,
                "name": "Manager Office",
                "image_path": "/office_layout/layout07_manager_office.png",
                "capacity": 6
            },
            {
                "id": ROOM_TRAINING_ROOM,
                "name": "Training Room",
                "image_path": "/office_layout/layout08_training_room.png",
                "capacity": 12
            },
            {
                "id": ROOM_LOUNGE,
                "name": "Lounge",
                "image_path": "/office_layout/layout09_lounge.png",
                "capacity": 10
            },
            {
                "id": ROOM_STORAGE,
                "name": "Storage",
                "image_path": "/office_layout/layout10_storage.png",
                "capacity": 2
            }
        ]
    
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
        
        # Group active employees by room (only include those with a room assigned)
        employees_by_room = {}
        active_with_rooms = []
        for employee in active_employees:
            # Safely get room fields (they might not exist in old database)
            current_room = getattr(employee, 'current_room', None)
            home_room = getattr(employee, 'home_room', None)
            activity_state = getattr(employee, 'activity_state', 'idle')
            
            room = current_room or home_room
            if room:
                if room not in employees_by_room:
                    employees_by_room[room] = []
                employees_by_room[room].append({
                    "id": employee.id,
                    "name": employee.name,
                    "title": employee.title,
                    "role": employee.role,
                    "department": employee.department,
                    "status": employee.status,
                    "current_room": current_room,
                    "home_room": home_room,
                    "activity_state": activity_state,
                    "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None
                })
                active_with_rooms.append(employee)
        
        # Add active employees to each room
        for room in rooms:
            room["employees"] = employees_by_room.get(room["id"], [])
        
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
        
        return {
            "rooms": rooms,
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

