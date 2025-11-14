from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from database.database import get_db
from database.models import Employee, Project, Task, Activity, Financial, BusinessMetric, Email, ChatMessage, BusinessSettings, Decision, EmployeeReview, Notification
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from business.goal_system import GoalSystem
from typing import List
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter()

class SendChatRequest(BaseModel):
    employee_id: int
    message: str

class CreateReviewRequest(BaseModel):
    manager_id: int = None
    overall_rating: float
    performance_rating: float = None
    teamwork_rating: float = None
    communication_rating: float = None
    productivity_rating: float = None
    comments: str = None
    strengths: str = None
    areas_for_improvement: str = None
    review_period_start: str = None
    review_period_end: str = None

@router.get("/employees")
async def get_employees(db: AsyncSession = Depends(get_db)):
    """Get all employees with termination reasons if applicable."""
    from database.models import Activity, EmployeeReview
    
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
    
    # Get review counts for all employees
    review_count_result = await db.execute(
        select(
            EmployeeReview.employee_id,
            func.count(EmployeeReview.id).label('review_count')
        )
        .group_by(EmployeeReview.employee_id)
    )
    review_counts = {row.employee_id: row.review_count for row in review_count_result.all()}
    
    # Get latest review info for each employee (using subquery to get the most recent review)
    # We'll get all reviews ordered by date and then pick the latest for each employee
    all_reviews_result = await db.execute(
        select(EmployeeReview)
        .order_by(desc(EmployeeReview.review_date))
    )
    all_reviews = all_reviews_result.scalars().all()
    
    # Create maps for latest review information (only keep the first/latest for each employee)
    latest_review_dates = {}
    latest_ratings = {}
    seen_employees = set()
    for review in all_reviews:
        if review.employee_id not in seen_employees:
            latest_review_dates[review.employee_id] = review.review_date
            latest_ratings[review.employee_id] = review.overall_rating
            seen_employees.add(review.employee_id)
    
    employee_list = []
    for emp in employees:
        termination_reason = None
        # Get termination reason from map if employee is fired
        if (emp.status == "fired" or emp.fired_at) and emp.id in termination_reasons:
            termination_reason = termination_reasons[emp.id]
        
        # Get review information
        review_count = review_counts.get(emp.id, 0)
        latest_review_date = latest_review_dates.get(emp.id)
        latest_rating = latest_ratings.get(emp.id)
        
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
            "created_at": emp.created_at.isoformat() if emp.created_at else None,
            "review_count": review_count,
            "latest_review_date": latest_review_date.isoformat() if latest_review_date else None,
            "latest_rating": float(latest_rating) if latest_rating else None
        })
    
    return employee_list

@router.get("/employees/waiting-status")
async def get_waiting_status(db: AsyncSession = Depends(get_db)):
    """Get diagnostic information about employees in waiting state."""
    from employees.room_assigner import ROOM_TRAINING_ROOM
    
    # Get all waiting employees
    result = await db.execute(
        select(Employee).where(
            Employee.status == "active",
            Employee.activity_state == "waiting"
        )
    )
    waiting_employees = result.scalars().all()
    
    # Get all employees in training rooms
    result = await db.execute(
        select(Employee).where(
            Employee.status == "active",
            Employee.current_room.like(f"%{ROOM_TRAINING_ROOM}%")
        )
    )
    training_room_employees = result.scalars().all()
    
    waiting_details = []
    for emp in waiting_employees:
        is_in_training_room = (emp.current_room == ROOM_TRAINING_ROOM or 
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                             emp.current_room == f"{ROOM_TRAINING_ROOM}_floor4_5")
        
        waiting_details.append({
            "id": emp.id,
            "name": emp.name,
            "activity_state": emp.activity_state,
            "current_room": emp.current_room,
            "home_room": emp.home_room,
            "is_in_training_room": is_in_training_room,
            "hired_at": emp.hired_at.isoformat() if emp.hired_at else None
        })
    
    training_room_details = []
    for emp in training_room_employees:
        training_room_details.append({
            "id": emp.id,
            "name": emp.name,
            "activity_state": emp.activity_state,
            "current_room": emp.current_room,
            "hired_at": emp.hired_at.isoformat() if emp.hired_at else None
        })
    
    return {
        "waiting_employees": waiting_details,
        "training_room_employees": training_room_details,
        "waiting_count": len(waiting_employees),
        "training_room_count": len(training_room_employees)
    }

async def _calculate_next_review_info(employee: Employee, db: AsyncSession) -> dict:
    """Calculate when the next review is scheduled and which manager will conduct it."""
    from datetime import datetime, timedelta
    
    # Check if employee is eligible for reviews (not executives)
    if employee.role in ["CEO", "Manager", "CTO", "COO", "CFO"] or employee.hierarchy_level < 3:
        return {
            "scheduled_at": None,
            "manager_id": None,
            "manager_name": None,
            "manager_title": None,
            "eligible": False,
            "reason": "Executives and managers do not receive performance reviews."
        }
    
    # Get the most recent review
    result = await db.execute(
        select(EmployeeReview)
        .where(EmployeeReview.employee_id == employee.id)
        .order_by(desc(EmployeeReview.review_date))
        .limit(1)
    )
    last_review = result.scalar_one_or_none()
    
    # Calculate when next review should be scheduled
    if last_review and last_review.review_date:
        # Next review is 6 hours after last review
        review_date = last_review.review_date.replace(tzinfo=None) if last_review.review_date.tzinfo else last_review.review_date
        next_review_time = review_date + timedelta(hours=6)
    elif employee.hired_at:
        # First review is 6 hours after hire
        hired_at = employee.hired_at.replace(tzinfo=None) if employee.hired_at.tzinfo else employee.hired_at
        next_review_time = hired_at + timedelta(hours=6)
    else:
        # Fallback: 6 hours from now
        next_review_time = datetime.utcnow() + timedelta(hours=6)
    
    # Find manager who will conduct the review (prefer same department)
    result = await db.execute(
        select(Employee).where(
            Employee.role.in_(["Manager", "CEO", "CTO", "COO", "CFO"]),
            Employee.status == "active"
        )
    )
    managers = result.scalars().all()
    
    if not managers:
        return {
            "scheduled_at": next_review_time.isoformat(),
            "manager_id": None,
            "manager_name": None,
            "manager_title": None,
            "eligible": True,
            "reason": "No active managers available"
        }
    
    # Prefer manager in same department
    manager = next((m for m in managers if m.department == employee.department), None)
    if not manager:
        manager = managers[0]
    
    return {
        "scheduled_at": next_review_time.isoformat(),
        "manager_id": manager.id,
        "manager_name": manager.name,
        "manager_title": manager.title,
        "eligible": True,
        "reason": None
    }

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
    
    # Calculate next review information
    next_review_info = await _calculate_next_review_info(emp, db)
    
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
        ],
        "next_review": next_review_info
    }

@router.get("/employees/{employee_id}/reviews")
async def get_employee_reviews(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get all reviews for a specific employee."""
    result = await db.execute(
        select(EmployeeReview)
        .where(EmployeeReview.employee_id == employee_id)
        .order_by(desc(EmployeeReview.review_date))
    )
    reviews = result.scalars().all()
    
    # Get employee names
    result = await db.execute(select(Employee))
    all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    
    return [
        {
            "id": review.id,
            "employee_id": review.employee_id,
            "manager_id": review.manager_id,
            "manager_name": all_employees.get(review.manager_id, "Unknown"),
            "review_date": review.review_date.isoformat() if review.review_date else None,
            "overall_rating": review.overall_rating,
            "performance_rating": review.performance_rating,
            "teamwork_rating": review.teamwork_rating,
            "communication_rating": review.communication_rating,
            "productivity_rating": review.productivity_rating,
            "comments": review.comments,
            "strengths": review.strengths,
            "areas_for_improvement": review.areas_for_improvement,
            "review_period_start": review.review_period_start.isoformat() if review.review_period_start else None,
            "review_period_end": review.review_period_end.isoformat() if review.review_period_end else None,
            "created_at": review.created_at.isoformat() if review.created_at else None
        }
        for review in reviews
    ]

@router.post("/employees/{employee_id}/reviews")
async def create_employee_review(employee_id: int, review_data: CreateReviewRequest, db: AsyncSession = Depends(get_db)):
    """Create a new review for an employee (for manual creation or system-generated)."""
    # Verify employee exists
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Get manager_id from review_data or find a manager
    manager_id = review_data.manager_id
    if not manager_id:
        # Find a manager for this employee (preferably in same department or any manager)
        result = await db.execute(
            select(Employee).where(
                Employee.role.in_(["Manager", "CEO", "CTO", "COO", "CFO"]),
                Employee.status == "active"
            )
        )
        managers = result.scalars().all()
        if managers:
            # Prefer manager in same department
            dept_manager = next((m for m in managers if m.department == employee.department), None)
            manager_id = dept_manager.id if dept_manager else managers[0].id
        else:
            raise HTTPException(status_code=400, detail="No active managers found to conduct review")
    
    # Verify manager exists
    result = await db.execute(select(Employee).where(Employee.id == manager_id))
    manager = result.scalar_one_or_none()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    # Create review
    review = EmployeeReview(
        employee_id=employee_id,
        manager_id=manager_id,
        overall_rating=review_data.overall_rating,
        performance_rating=review_data.performance_rating,
        teamwork_rating=review_data.teamwork_rating,
        communication_rating=review_data.communication_rating,
        productivity_rating=review_data.productivity_rating,
        comments=review_data.comments,
        strengths=review_data.strengths,
        areas_for_improvement=review_data.areas_for_improvement,
        review_period_start=datetime.fromisoformat(review_data.review_period_start) if review_data.review_period_start else None,
        review_period_end=datetime.fromisoformat(review_data.review_period_end) if review_data.review_period_end else None
    )
    
    db.add(review)
    await db.commit()
    await db.refresh(review)
    
    return {
        "id": review.id,
        "employee_id": review.employee_id,
        "manager_id": review.manager_id,
        "manager_name": manager.name,
        "review_date": review.review_date.isoformat() if review.review_date else None,
        "overall_rating": review.overall_rating,
        "performance_rating": review.performance_rating,
        "teamwork_rating": review.teamwork_rating,
        "communication_rating": review.communication_rating,
        "productivity_rating": review.productivity_rating,
        "comments": review.comments,
        "strengths": review.strengths,
        "areas_for_improvement": review.areas_for_improvement,
        "review_period_start": review.review_period_start.isoformat() if review.review_period_start else None,
        "review_period_end": review.review_period_end.isoformat() if review.review_period_end else None,
        "created_at": review.created_at.isoformat() if review.created_at else None
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

@router.get("/tasks")
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """Get all tasks with employee and project information."""
    # Get all tasks
    result = await db.execute(
        select(Task).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    
    # Get all employees and projects for lookup
    employees_result = await db.execute(select(Employee))
    employees = {emp.id: emp for emp in employees_result.scalars().all()}
    
    projects_result = await db.execute(select(Project))
    projects = {proj.id: proj for proj in projects_result.scalars().all()}
    
    task_list = []
    for task in tasks:
        task_data = {
            "id": task.id,
            "employee_id": task.employee_id,
            "project_id": task.project_id,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "progress": task.progress if hasattr(task, 'progress') else (100.0 if task.status == "completed" else 0.0),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "employee": None,
            "project": None
        }
        
        # Add employee information if assigned
        if task.employee_id and task.employee_id in employees:
            employee = employees[task.employee_id]
            task_data["employee"] = {
                "id": employee.id,
                "name": employee.name,
                "title": employee.title,
                "department": employee.department,
                "role": employee.role
            }
        
        # Add project information if associated
        if task.project_id and task.project_id in projects:
            project = projects[task.project_id]
            task_data["project"] = {
                "id": project.id,
                "name": project.name,
                "status": project.status
            }
        
        task_list.append(task_data)
    
    return task_list

@router.get("/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Get task details."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get employee information if assigned
    employee = None
    if task.employee_id:
        emp_result = await db.execute(select(Employee).where(Employee.id == task.employee_id))
        emp = emp_result.scalar_one_or_none()
        if emp:
            employee = {
                "id": emp.id,
                "name": emp.name,
                "title": emp.title,
                "department": emp.department,
                "role": emp.role
            }
    
    # Get project information if associated
    project = None
    if task.project_id:
        proj_result = await db.execute(select(Project).where(Project.id == task.project_id))
        proj = proj_result.scalar_one_or_none()
        if proj:
            project = {
                "id": proj.id,
                "name": proj.name,
                "status": proj.status,
                "description": proj.description
            }
    
    return {
        "id": task.id,
        "employee_id": task.employee_id,
        "project_id": task.project_id,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress if hasattr(task, 'progress') else (100.0 if task.status == "completed" else 0.0),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "employee": employee,
        "project": project
    }

@router.get("/tasks/{task_id}/activities")
async def get_task_activities(task_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get activities related to a task."""
    # First verify task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get activities from the employee assigned to this task
    all_activities = []
    
    if task.employee_id:
        # Get activities from the employee working on this task
        employee_activities_result = await db.execute(
            select(Activity)
            .where(Activity.employee_id == task.employee_id)
            .order_by(desc(Activity.timestamp))
            .limit(limit * 2)
        )
        employee_activities = employee_activities_result.scalars().all()
        all_activities.extend(employee_activities)
    
    # Get activities that mention this task in metadata or description
    result = await db.execute(
        select(Activity)
        .where(
            Activity.description.contains(task.description[:50])  # First 50 chars for matching
        )
        .order_by(desc(Activity.timestamp))
        .limit(limit * 2)
    )
    description_activities = result.scalars().all()
    all_activities.extend(description_activities)
    
    # Filter activities that are related to this task
    # Check metadata for task_id or if employee matches and activity is task-related
    filtered_activities = []
    seen_ids = set()
    
    for act in all_activities:
        if act.id in seen_ids:
            continue
        seen_ids.add(act.id)
        
        # Check if activity metadata contains this task_id
        if act.activity_metadata and isinstance(act.activity_metadata, dict):
            metadata_task_id = act.activity_metadata.get("task_id")
            if metadata_task_id == task_id:
                filtered_activities.append(act)
                continue
        
        # Check if activity is from the assigned employee and is task-related
        if act.employee_id == task.employee_id:
            if act.activity_type in ["task_completed", "decision"]:
                # For task_completed, check metadata
                if act.activity_type == "task_completed":
                    if act.activity_metadata and isinstance(act.activity_metadata, dict):
                        metadata_task_id = act.activity_metadata.get("task_id")
                        if metadata_task_id == task_id:
                            filtered_activities.append(act)
                            continue
                else:
                    # For other task-related activities, include if employee matches
                    filtered_activities.append(act)
                    continue
    
    # Sort by timestamp descending and limit
    filtered_activities.sort(key=lambda x: x.timestamp, reverse=True)
    filtered_activities = filtered_activities[:limit]
    
    # Get employee names for activities
    employee_ids = {act.employee_id for act in filtered_activities if act.employee_id}
    employees = {}
    if employee_ids:
        emp_result = await db.execute(
            select(Employee).where(Employee.id.in_(employee_ids))
        )
        for emp in emp_result.scalars().all():
            employees[emp.id] = emp.name
    
    return [
        {
            "id": act.id,
            "employee_id": act.employee_id,
            "employee_name": employees.get(act.employee_id) if act.employee_id else None,
            "activity_type": act.activity_type,
            "description": act.description,
            "timestamp": act.timestamp.isoformat() if act.timestamp else None,
            "activity_metadata": act.activity_metadata
        }
        for act in filtered_activities
    ]

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
        
        # Get leadership team (CEO, C-level executives, and Managers)
        leadership_roles = ["CEO", "CTO", "COO", "CFO", "Manager"]
        leadership_employees = [emp for emp in active_employees if emp.role in leadership_roles or emp.hierarchy_level <= 2]
        
        # Get recent leadership decisions
        leadership_employee_ids = [emp.id for emp in leadership_employees]
        leadership_decisions = []
        if leadership_employee_ids:
            # Get decisions from Decision table
            result = await db.execute(
                select(Decision)
                .where(Decision.employee_id.in_(leadership_employee_ids))
                .order_by(desc(Decision.timestamp))
                .limit(10)
            )
            decisions = result.scalars().all()
            leadership_decisions = [
                {
                    "id": d.id,
                    "employee_id": d.employee_id,
                    "employee_name": next((emp.name for emp in leadership_employees if emp.id == d.employee_id), "Unknown"),
                    "employee_role": next((emp.role for emp in leadership_employees if emp.id == d.employee_id), "Unknown"),
                    "decision_type": d.decision_type,
                    "description": d.description,
                    "reasoning": d.reasoning,
                    "timestamp": (d.timestamp or datetime.utcnow()).isoformat()
                }
                for d in decisions
            ]
            
            # Also get strategic decisions from Activities table
            result = await db.execute(
                select(Activity)
                .where(
                    Activity.employee_id.in_(leadership_employee_ids),
                    Activity.activity_type.in_(["strategic_decision", "strategic_operational_decision"])
                )
                .order_by(desc(Activity.timestamp))
                .limit(10)
            )
            strategic_activities = result.scalars().all()
            for act in strategic_activities:
                # Extract decision type from activity metadata or activity_type
                decision_type = "strategic"
                if act.activity_metadata and isinstance(act.activity_metadata, dict):
                    decision_type = act.activity_metadata.get("decision_type", "strategic")
                elif act.activity_type == "strategic_operational_decision":
                    decision_type = "strategic_operational"
                
                leadership_decisions.append({
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "employee_name": next((emp.name for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "employee_role": next((emp.role for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "decision_type": decision_type,
                    "description": act.description,
                    "reasoning": act.activity_metadata.get("reasoning", "") if act.activity_metadata and isinstance(act.activity_metadata, dict) else "",
                    "timestamp": (act.timestamp or datetime.utcnow()).isoformat()
                })
            
            # Sort by timestamp descending and limit to 10
            leadership_decisions.sort(key=lambda x: x["timestamp"], reverse=True)
            leadership_decisions = leadership_decisions[:10]
        
        # Get recent leadership activities
        leadership_activities = []
        if leadership_employee_ids:
            result = await db.execute(
                select(Activity)
                .where(Activity.employee_id.in_(leadership_employee_ids))
                .order_by(desc(Activity.timestamp))
                .limit(15)
            )
            activities = result.scalars().all()
            leadership_activities = [
                {
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "employee_name": next((emp.name for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "employee_role": next((emp.role for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "activity_type": act.activity_type,
                    "description": act.description,
                    "timestamp": (act.timestamp or datetime.utcnow()).isoformat()
                }
                for act in activities
            ]
        
        # Calculate leadership metrics
        # Get projects with leadership involvement
        leadership_employee_ids_set = set(leadership_employee_ids)
        result = await db.execute(
            select(Task).where(Task.employee_id.in_(leadership_employee_ids_set))
        )
        leadership_tasks = result.scalars().all()
        projects_with_leadership = set(task.project_id for task in leadership_tasks if task.project_id)
        
        # Count strategic decisions (from both Decision table and Activity table)
        # Count from Decision table
        result = await db.execute(
            select(Decision)
            .where(
                Decision.employee_id.in_(leadership_employee_ids),
                Decision.decision_type == "strategic"
            )
        )
        strategic_decisions_from_table = result.scalars().all()
        
        # Count from Activity table
        result = await db.execute(
            select(Activity)
            .where(
                Activity.employee_id.in_(leadership_employee_ids),
                Activity.activity_type.in_(["strategic_decision", "strategic_operational_decision"])
            )
        )
        strategic_activities = result.scalars().all()
        
        strategic_count = len(strategic_decisions_from_table) + len(strategic_activities)
        
        # Get employee review statistics
        # Completed reviews: reviews with all fields filled (comments, strengths, areas_for_improvement)
        result = await db.execute(
            select(EmployeeReview)
            .where(
                EmployeeReview.comments.isnot(None),
                EmployeeReview.strengths.isnot(None),
                EmployeeReview.areas_for_improvement.isnot(None)
            )
        )
        completed_reviews = result.scalars().all()
        completed_reviews_count = len(completed_reviews)
        
        # In progress reviews: reviews that exist but are missing some optional fields
        result = await db.execute(
            select(EmployeeReview)
            .where(
                or_(
                    EmployeeReview.comments.is_(None),
                    EmployeeReview.strengths.is_(None),
                    EmployeeReview.areas_for_improvement.is_(None)
                )
            )
        )
        in_progress_reviews = result.scalars().all()
        in_progress_reviews_count = len(in_progress_reviews)
        
        leadership_metrics = {
            "total_leadership_count": len(leadership_employees),
            "ceo_count": len([emp for emp in leadership_employees if emp.role == "CEO"]),
            "manager_count": len([emp for emp in leadership_employees if emp.role == "Manager"]),
            "cto_count": len([emp for emp in leadership_employees if emp.role == "CTO"]),
            "coo_count": len([emp for emp in leadership_employees if emp.role == "COO"]),
            "cfo_count": len([emp for emp in leadership_employees if emp.role == "CFO"]),
            "strategic_decisions_count": strategic_count,
            "projects_led_by_leadership": len(projects_with_leadership),
            "reviews_completed": completed_reviews_count,
            "reviews_in_progress": in_progress_reviews_count
        }
        
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
            },
            # Leadership insights
            "leadership_insights": {
                "leadership_team": [
                    {
                        "id": emp.id,
                        "name": emp.name,
                        "title": emp.title,
                        "role": emp.role,
                        "department": emp.department,
                        "hierarchy_level": emp.hierarchy_level,
                        "status": emp.status,
                        "hired_at": emp.hired_at.isoformat() if emp.hired_at else None
                    }
                    for emp in sorted(leadership_employees, key=lambda x: (x.hierarchy_level, x.name))
                ],
                "recent_decisions": leadership_decisions,
                "recent_activities": leadership_activities,
                "metrics": leadership_metrics
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
            },
            "leadership_insights": {
                "leadership_team": [],
                "recent_decisions": [],
                "recent_activities": [],
                "metrics": {
                    "total_leadership_count": 0,
                    "ceo_count": 0,
                    "manager_count": 0,
                    "strategic_decisions_count": 0,
                    "projects_led_by_leadership": 0
                }
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
    # CEO: $150k/year, CTO/COO/CFO: $120k/year, Manager: $100k/year, Employee: $60k/year
    payroll_by_role = {}
    total_payroll = 0.0
    payroll_by_department = {}
    
    for emp in employees:
        # Calculate annual salary based on role
        if emp.role == "CEO" or emp.hierarchy_level == 1:
            annual_salary = 150000
        elif emp.role in ["CTO", "COO", "CFO"]:
            annual_salary = 120000  # C-level executives get higher salary than managers
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
                "estimated_annual_salary": 150000 if (emp.role == "CEO" or emp.hierarchy_level == 1) else (120000 if emp.role in ["CTO", "COO", "CFO"] else (100000 if (emp.role == "Manager" or emp.hierarchy_level == 2) else 60000)),
                "period_salary": (150000 if (emp.role == "CEO" or emp.hierarchy_level == 1) else (120000 if emp.role in ["CTO", "COO", "CFO"] else (100000 if (emp.role == "Manager" or emp.hierarchy_level == 2) else 60000))) / 12 * (days / 30.44)
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
    """Get chat messages between the user and a specific employee only."""
    try:
        from employees.base import generate_thread_id
        
        # Only show messages in the thread between user (0/None) and this employee
        user_employee_thread_id = generate_thread_id(0, employee_id)
        
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.thread_id == user_employee_thread_id
            )
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
                "sender_name": "You" if chat.sender_id is None or chat.sender_id == 0 else all_employees.get(chat.sender_id, "Unknown"),
                "recipient_id": chat.recipient_id,
                "recipient_name": "You" if chat.recipient_id is None or chat.recipient_id == 0 else all_employees.get(chat.recipient_id, "Unknown"),
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
                "sender_name": "You" if chat.sender_id is None or chat.sender_id == 0 else all_employees.get(chat.sender_id, "Unknown"),
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

@router.post("/chats/send")
async def send_chat_message(request: SendChatRequest, db: AsyncSession = Depends(get_db)):
    """Send a chat message from the user/manager to an employee and get an automatic response."""
    try:
        from employees.base import generate_thread_id
        from llm.ollama_client import OllamaClient
        from engine.office_simulator import get_business_context
        
        # Verify employee exists and is not terminated
        result = await db.execute(
            select(Employee).where(Employee.id == request.employee_id)
        )
        employee = result.scalar_one_or_none()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        if employee.status == "fired" or employee.fired_at:
            raise HTTPException(status_code=400, detail="Cannot send messages to terminated employees")
        
        # Use sender_id = None to represent messages from the user/manager
        # We'll use 0 in the thread_id generation for consistency
        thread_id = generate_thread_id(0, request.employee_id)
        
        # Save the user's message
        user_chat = ChatMessage(
            sender_id=None,  # None represents messages from the user/manager
            recipient_id=request.employee_id,
            message=request.message,
            thread_id=thread_id
        )
        db.add(user_chat)
        await db.flush()  # Flush to get the timestamp
        
        # Get employee's work context
        project_context = None
        task_description = None
        if employee.current_task_id:
            result = await db.execute(
                select(Task).where(Task.id == employee.current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task:
                task_description = current_task.description
                if current_task.project_id:
                    result = await db.execute(
                        select(Project).where(Project.id == current_task.project_id)
                    )
                    project = result.scalar_one_or_none()
                    if project:
                        project_context = project.name
        
        # Get business context
        business_context = await get_business_context(db)
        
        # Generate employee response using Ollama
        llm_client = OllamaClient()
        
        # Build work context string
        work_context_parts = []
        if project_context:
            work_context_parts.append(f"working on the {project_context} project")
        if task_description:
            work_context_parts.append(f"task: {task_description}")
        if employee.status:
            work_context_parts.append(f"status: {employee.status}")
        if employee.activity_state:
            work_context_parts.append(f"currently: {employee.activity_state}")
        
        work_context_str = ". ".join(work_context_parts) if work_context_parts else "available for work"
        
        # Generate response
        response_text = await llm_client.generate_chat_response(
            recipient_name=employee.name,
            recipient_title=employee.title,
            recipient_role=employee.role,
            recipient_personality=employee.personality_traits or [],
            sender_name="Manager",
            sender_title="Manager",
            original_message=request.message,
            project_context=work_context_str,
            business_context=business_context
        )
        
        # Save employee's response
        employee_response = ChatMessage(
            sender_id=employee.id,
            recipient_id=None,  # None represents the user/manager
            message=response_text,
            thread_id=thread_id
        )
        db.add(employee_response)
        await db.commit()
        
        return {
            "success": True,
            "message": "Chat message sent successfully",
            "user_message": {
                "id": user_chat.id,
                "sender_id": user_chat.sender_id,
                "sender_name": "You",
                "recipient_id": user_chat.recipient_id,
                "recipient_name": employee.name,
                "message": user_chat.message,
                "thread_id": user_chat.thread_id,
                "timestamp": user_chat.timestamp.isoformat() if user_chat.timestamp else None
            },
            "employee_response": {
                "id": employee_response.id,
                "sender_id": employee_response.sender_id,
                "sender_name": employee.name,
                "recipient_id": employee_response.recipient_id,
                "recipient_name": "You",
                "message": employee_response.message,
                "thread_id": employee_response.thread_id,
                "timestamp": employee_response.timestamp.isoformat() if employee_response.timestamp else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error sending chat message: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error sending chat message: {str(e)}")

@router.post("/employees/fix-waiting")
async def fix_waiting_employees(db: AsyncSession = Depends(get_db)):
    """Batch fix all employees stuck in waiting state, especially those waiting for training."""
    try:
        from engine.movement_system import find_available_training_room, update_employee_location, check_room_has_space
        from employees.room_assigner import ROOM_TRAINING_ROOM
        from datetime import datetime, timedelta
        
        # Initialize counters
        fixed_count = 0
        training_fixed = 0
        training_completed = 0
        status_fixed = 0  # Fixed status without moving
        other_fixed = 0
        
        # First, find and fix all employees in training rooms with "waiting" status
        # Query for them and update individually (more reliable than bulk SQL)
        training_rooms = [
            ROOM_TRAINING_ROOM,
            f"{ROOM_TRAINING_ROOM}_floor2",
            f"{ROOM_TRAINING_ROOM}_floor4",
            f"{ROOM_TRAINING_ROOM}_floor4_2",
            f"{ROOM_TRAINING_ROOM}_floor4_3",
            f"{ROOM_TRAINING_ROOM}_floor4_4",
            f"{ROOM_TRAINING_ROOM}_floor4_5"
        ]
        
        # Get all employees in training rooms with waiting status
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.activity_state == "waiting",
                Employee.current_room.in_(training_rooms)
            )
        )
        waiting_in_training = result.scalars().all()
        
        # Update each one
        for emp in waiting_in_training:
            emp.activity_state = "training"
            status_fixed += 1
            fixed_count += 1
        
        await db.flush()  # Flush immediately to ensure update is applied
        
        # Now handle employees who should complete training (hired >1 hour ago)
        # Get employees in training rooms (now with "training" status after our update)
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.activity_state == "training",
                Employee.current_room.in_(training_rooms)
            )
        )
        training_complete_employees = result.scalars().all()
        
        for employee in training_complete_employees:
            try:
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
                        if time_since_hire > timedelta(hours=1):
                            employee.activity_state = "idle"
                            if employee.home_room:
                                await update_employee_location(employee, employee.home_room, "idle", db)
                            from database.models import Activity
                            activity = Activity(
                                employee_id=employee.id,
                                activity_type="training_completed",
                                description=f"{employee.name} completed training and reported to work area ({employee.home_room or 'home room'})",
                                activity_metadata={"note": "Batch fix: Training completed"}
                            )
                            db.add(activity)
                            training_completed += 1
                            fixed_count += 1
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error completing training for employee {employee.id}: {e}")
                continue
        
        # Get remaining waiting employees (not in training rooms)
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.activity_state == "waiting",
                ~Employee.current_room.in_(training_rooms)
            )
        )
        other_waiting = result.scalars().all()
        
        # Process remaining waiting employees (not in training rooms)
        for employee in other_waiting:
            try:
                # Check if they should be in training (recently hired)
                hired_at = getattr(employee, 'hired_at', None)
                is_new_hire = False
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
                            is_new_hire = True
                    except Exception:
                        pass
                
                if is_new_hire:
                    # New hire waiting - find training room
                    available_training_room = await find_available_training_room(db, exclude_employee_id=employee.id)
                    if available_training_room:
                        await update_employee_location(employee, available_training_room, "training", db)
                        training_fixed += 1
                        fixed_count += 1
                    else:
                        # No training room - move to home room anyway
                        if employee.home_room:
                            await update_employee_location(employee, employee.home_room, "idle", db)
                            other_fixed += 1
                            fixed_count += 1
                else:
                    # Not a new hire - just move to home room
                    if employee.home_room:
                        await update_employee_location(employee, employee.home_room, "idle", db)
                        other_fixed += 1
                        fixed_count += 1
            except Exception as e:
                print(f"Error fixing employee {employee.id} ({getattr(employee, 'name', 'unknown')}): {e}")
                import traceback
                traceback.print_exc()
                continue
        
        await db.commit()
        
        # Count total waiting for response
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.activity_state == "waiting"
            )
        )
        total_waiting = len(result.scalars().all())
        
        return {
            "message": f"Fixed {fixed_count} waiting employees",
            "details": {
                "total_fixed": fixed_count,
                "training_room_fixed": training_fixed,
                "training_completed": training_completed,
                "status_fixed": status_fixed,
                "other_waiting_fixed": other_fixed,
                "total_waiting": total_waiting
            }
        }
    except Exception as e:
        await db.rollback()
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error in fix_waiting_employees: {e}")
        print(error_msg)
        raise HTTPException(status_code=500, detail=f"Error fixing waiting employees: {str(e)}")

@router.get("/office-layout")
async def get_office_layout(db: AsyncSession = Depends(get_db)):
    """Get office layout with all rooms and employees in each room for all floors."""
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
    ROOM_EXECUTIVE_SUITE = "executive_suite"
    ROOM_HR_ROOM = "hr_room"
    ROOM_SALES_ROOM = "sales_room"
    ROOM_INNOVATION_LAB = "innovation_lab"
    ROOM_HOTDESK = "hotdesk"
    ROOM_FOCUS_PODS = "focus_pods"
    ROOM_COLLAB_LOUNGE = "collab_lounge"
    ROOM_WAR_ROOM = "war_room"
    ROOM_DESIGN_STUDIO = "design_studio"
    ROOM_HR_WELLNESS = "hr_wellness"
    ROOM_THEATER = "theater"
    ROOM_HUDDLE = "huddle"
    ROOM_CORNER_EXEC = "corner_exec"
    
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
    
    # Floor 2 layout (using new floor 2 models)
    floor2_rooms = [
            {
                "id": f"{ROOM_EXECUTIVE_SUITE}_floor2",
                "name": "Executive Suite",
                "image_path": "/office_layout/floor2_room01_execsuite.png",
                "capacity": 8,
                "floor": 2
            },
            {
                "id": f"{ROOM_CUBICLES}_floor2",
                "name": "Cubicles",
                "image_path": "/office_layout/floor2_room02_cubicles.png",
                "capacity": 20,
                "floor": 2
            },
            {
                "id": f"{ROOM_BREAKROOM}_floor2",
                "name": "Breakroom",
                "image_path": "/office_layout/floor2_room03_breakroom.png",
                "capacity": 10,
                "floor": 2
            },
            {
                "id": f"{ROOM_CONFERENCE_ROOM}_floor2",
                "name": "Conference Room",
                "image_path": "/office_layout/floor2_room04_conference.png",
                "capacity": 12,
                "floor": 2
            },
            {
                "id": f"{ROOM_TRAINING_ROOM}_floor2",
                "name": "Training Room",
                "image_path": "/office_layout/floor2_room05_training.png",
                "capacity": 15,
                "floor": 2
            },
            {
                "id": f"{ROOM_IT_ROOM}_floor2",
                "name": "IT Room",
                "image_path": "/office_layout/floor2_room06_itroom.png",
                "capacity": 6,
                "floor": 2
            },
            {
                "id": f"{ROOM_STORAGE}_floor2",
                "name": "Storage",
                "image_path": "/office_layout/floor2_room07_storage.png",
                "capacity": 3,
                "floor": 2
            },
            {
                "id": f"{ROOM_LOUNGE}_floor2",
                "name": "Lounge",
                "image_path": "/office_layout/floor2_room08_lounge.png",
                "capacity": 12,
                "floor": 2
            },
            {
                "id": f"{ROOM_HR_ROOM}_floor2",
                "name": "HR Room",
                "image_path": "/office_layout/floor2_room09_hr.png",
                "capacity": 6,
                "floor": 2
            },
            {
                "id": f"{ROOM_SALES_ROOM}_floor2",
                "name": "Sales Room",
                "image_path": "/office_layout/floor2_room10_sales.png",
                "capacity": 10,
                "floor": 2
            }
        ]
    
    # Floor 3 layout (using floor 3 models)
    floor3_rooms = [
            {
                "id": f"{ROOM_INNOVATION_LAB}_floor3",
                "name": "Innovation Lab",
                "image_path": "/office_layout/floor3_room01_innovation_lab.png",
                "capacity": 12,
                "floor": 3
            },
            {
                "id": f"{ROOM_HOTDESK}_floor3",
                "name": "Hotdesk",
                "image_path": "/office_layout/floor3_room02_hotdesk.png",
                "capacity": 18,
                "floor": 3
            },
            {
                "id": f"{ROOM_FOCUS_PODS}_floor3",
                "name": "Focus Pods",
                "image_path": "/office_layout/floor3_room03_focus_pods.png",
                "capacity": 8,
                "floor": 3
            },
            {
                "id": f"{ROOM_COLLAB_LOUNGE}_floor3",
                "name": "Collaboration Lounge",
                "image_path": "/office_layout/floor3_room04_collab_lounge.png",
                "capacity": 15,
                "floor": 3
            },
            {
                "id": f"{ROOM_WAR_ROOM}_floor3",
                "name": "War Room",
                "image_path": "/office_layout/floor3_room05_war_room.png",
                "capacity": 10,
                "floor": 3
            },
            {
                "id": f"{ROOM_DESIGN_STUDIO}_floor3",
                "name": "Design Studio",
                "image_path": "/office_layout/floor3_room06_design_studio.png",
                "capacity": 8,
                "floor": 3
            },
            {
                "id": f"{ROOM_HR_WELLNESS}_floor3",
                "name": "HR Wellness",
                "image_path": "/office_layout/floor3_room07_hr_wellness.png",
                "capacity": 6,
                "floor": 3
            },
            {
                "id": f"{ROOM_THEATER}_floor3",
                "name": "Theater",
                "image_path": "/office_layout/floor3_room08_theater.png",
                "capacity": 20,
                "floor": 3
            },
            {
                "id": f"{ROOM_HUDDLE}_floor3",
                "name": "Huddle",
                "image_path": "/office_layout/floor3_room09_huddle.png",
                "capacity": 6,
                "floor": 3
            },
            {
                "id": f"{ROOM_CORNER_EXEC}_floor3",
                "name": "Corner Executive",
                "image_path": "/office_layout/floor3_room10_corner_exec.png",
                "capacity": 4,
                "floor": 3
            }
        ]
    
    # Floor 4 layout - Training overflow floor (5 training rooms and 5 cubicles)
    floor4_rooms = [
        {
            "id": f"{ROOM_TRAINING_ROOM}_floor4",
            "name": "Training Room 1",
            "image_path": "/office_layout/layout08_training_room.png",
            "capacity": 20,
            "floor": 4
        },
        {
            "id": f"{ROOM_CUBICLES}_floor4",
            "name": "Cubicles 1",
            "image_path": "/office_layout/layout02_cubicles.png",
            "capacity": 25,
            "floor": 4
        },
        {
            "id": f"{ROOM_TRAINING_ROOM}_floor4_2",
            "name": "Training Room 2",
            "image_path": "/office_layout/layout08_training_room.png",
            "capacity": 20,
            "floor": 4
        },
        {
            "id": f"{ROOM_CUBICLES}_floor4_2",
            "name": "Cubicles 2",
            "image_path": "/office_layout/layout02_cubicles.png",
            "capacity": 25,
            "floor": 4
        },
        {
            "id": f"{ROOM_TRAINING_ROOM}_floor4_3",
            "name": "Training Room 3",
            "image_path": "/office_layout/layout08_training_room.png",
            "capacity": 18,
            "floor": 4
        },
        {
            "id": f"{ROOM_CUBICLES}_floor4_3",
            "name": "Cubicles 3",
            "image_path": "/office_layout/layout02_cubicles.png",
            "capacity": 22,
            "floor": 4
        },
        {
            "id": f"{ROOM_TRAINING_ROOM}_floor4_4",
            "name": "Training Room 4",
            "image_path": "/office_layout/layout08_training_room.png",
            "capacity": 20,
            "floor": 4
        },
        {
            "id": f"{ROOM_CUBICLES}_floor4_4",
            "name": "Cubicles 4",
            "image_path": "/office_layout/layout02_cubicles.png",
            "capacity": 25,
            "floor": 4
        },
        {
            "id": f"{ROOM_TRAINING_ROOM}_floor4_5",
            "name": "Training Room 5",
            "image_path": "/office_layout/layout08_training_room.png",
            "capacity": 18,
            "floor": 4
        },
        {
            "id": f"{ROOM_CUBICLES}_floor4_5",
            "name": "Cubicles 5",
            "image_path": "/office_layout/layout02_cubicles.png",
            "capacity": 22,
            "floor": 4
        }
    ]
    
    # Combine all rooms
    rooms = floor1_rooms + floor2_rooms + floor3_rooms + floor4_rooms
    
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
                # If room already has _floor2, _floor3, or _floor4 suffix, use it as-is
                if room.endswith('_floor2') or room.endswith('_floor3') or room.endswith('_floor4'):
                    room_key = room
                # For floor 2, add _floor2 suffix if not already present
                elif floor == 2:
                    # Check if this is a base room that should be on floor 2
                    base_room = room
                    room_key = f"{base_room}_floor2"
                # For floor 3, add _floor3 suffix if not already present
                elif floor == 3:
                    # Check if this is a base room that should be on floor 3
                    base_room = room
                    room_key = f"{base_room}_floor3"
                # For floor 4, add _floor4 suffix if not already present
                elif floor == 4:
                    # Check if this is a base room that should be on floor 4
                    base_room = room
                    room_key = f"{base_room}_floor4"
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
            2: [r for r in rooms if r["floor"] == 2],
            3: [r for r in rooms if r["floor"] == 3],
            4: [r for r in rooms if r["floor"] == 4]
        }
        
        return {
            "rooms": rooms,
            "rooms_by_floor": rooms_by_floor,
            "floors": [1, 2, 3, 4],
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

class BoardroomDiscussionRequest(BaseModel):
    executive_ids: List[int] = None

@router.post("/boardroom/generate-discussions")
async def generate_boardroom_discussions(
    request: BoardroomDiscussionRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """Generate strategic boardroom discussions between executives."""
    import random
    import asyncio
    from llm.ollama_client import OllamaClient
    from employees.base import generate_thread_id
    from sqlalchemy.exc import OperationalError
    
    async def commit_with_retry(session, max_retries=5):
        """Commit with retry logic and exponential backoff."""
        for attempt in range(max_retries):
            try:
                await session.commit()
                return True
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Exponential backoff: wait 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    wait_time = 0.1 * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        return False
    
    try:
        # Get executives - use provided IDs if available, otherwise get all leadership
        executive_ids = request.executive_ids if request and request.executive_ids else None
        if executive_ids and len(executive_ids) > 0:
            result = await db.execute(
                select(Employee).where(
                    Employee.id.in_(executive_ids),
                    Employee.status == "active"
                )
            )
            executives = result.scalars().all()
        else:
            # Fallback: Get all leadership team (CEO and Managers)
            result = await db.execute(
                select(Employee).where(
                    Employee.role.in_(["CEO", "Manager"]),
                    Employee.status == "active"
                )
            )
            executives = result.scalars().all()
        
        if len(executives) < 2:
            return {
                "success": False,
                "message": "Not enough executives for boardroom discussions",
                "chats_created": 0
            }
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(db)
        
        llm_client = OllamaClient()
        chats_created = 0
        
        # Create list of all executives in the room for context
        executives_in_room = [f"{e.name} ({e.title})" for e in executives]
        room_context = ", ".join(executives_in_room)
        
        # Generate diverse strategic boardroom discussion topics
        # Much larger pool of topics to ensure variety
        discussion_topics = [
            "strategic planning for Q4 revenue growth",
            "resource allocation for upcoming projects",
            "market expansion opportunities",
            "operational efficiency improvements",
            "team performance and productivity",
            "budget optimization strategies",
            "technology investment priorities",
            "customer acquisition initiatives",
            "competitive positioning analysis",
            "risk management and mitigation",
            "quarterly financial performance review",
            "hiring and talent acquisition strategy",
            "product development roadmap",
            "customer retention programs",
            "supply chain optimization",
            "digital transformation initiatives",
            "partnership and alliance opportunities",
            "brand positioning and marketing strategy",
            "workplace culture and employee engagement",
            "sustainability and corporate responsibility",
            "merger and acquisition opportunities",
            "international expansion plans",
            "innovation and R&D investments",
            "cost reduction initiatives",
            "sales strategy and pipeline management",
            "customer service improvements",
            "data analytics and business intelligence",
            "cybersecurity and data protection",
            "regulatory compliance and governance",
            "vendor and supplier relationships",
            "project portfolio management",
            "quality assurance and process improvement",
            "employee training and development",
            "succession planning and leadership development",
            "market research and customer insights",
            "pricing strategy and revenue optimization",
            "channel partner relationships",
            "product launch planning",
            "customer feedback and satisfaction",
            "operational metrics and KPIs",
            "strategic partnerships",
            "workforce planning and optimization",
            "customer experience enhancement",
            "business continuity planning",
            "change management initiatives"
        ]
        
        # Shuffle topics to ensure variety
        available_topics = discussion_topics.copy()
        random.shuffle(available_topics)
        topic_index = 0
        
        # Generate more discussions - at least 3-6 between random pairs
        # More discussions = more activity in the boardroom
        num_discussions = random.randint(3, min(6, max(3, len(executives))))
        used_pairs = set()
        used_topics_in_batch = set()
        
        for _ in range(num_discussions):
            # Select two different executives
            if len(executives) < 2:
                break
                
            sender, recipient = random.sample(executives, 2)
            pair_key = tuple(sorted([sender.id, recipient.id]))
            
            # Avoid duplicate pairs in same batch
            if pair_key in used_pairs:
                continue
            used_pairs.add(pair_key)
            
            # Select a topic that hasn't been used in this batch
            # Cycle through available topics to ensure variety
            topic = None
            attempts = 0
            while topic is None or topic in used_topics_in_batch:
                if topic_index >= len(available_topics):
                    # Reset and reshuffle if we've gone through all topics
                    available_topics = discussion_topics.copy()
                    random.shuffle(available_topics)
                    topic_index = 0
                    used_topics_in_batch.clear()  # Clear used topics when we reset
                
                topic = available_topics[topic_index]
                topic_index += 1
                attempts += 1
                
                # Safety check to avoid infinite loop
                if attempts > len(discussion_topics):
                    # Just use any topic if we can't find a unique one
                    topic = random.choice(discussion_topics)
                    break
            
            used_topics_in_batch.add(topic)
            
            # Generate message using LLM
            personality_str = ", ".join(sender.personality_traits or ["strategic", "analytical"])
            recipient_personality = ", ".join(recipient.personality_traits or ["strategic", "analytical"])
            
            prompt = f"""You are {sender.name}, {sender.title} at a company. You are currently in a boardroom meeting with the following executives: {room_context}.

You are directly addressing {recipient.name} ({recipient.title}) who is sitting across the table from you in this boardroom meeting. You're discussing {topic} together.

Your personality traits: {personality_str}
Your role: {sender.role}
{recipient.name}'s personality traits: {recipient_personality}
{recipient.name}'s role: {recipient.role}

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}
- Employees: {business_context.get('employee_count', 0)}

Write a brief, direct boardroom discussion message (1-2 sentences) to {recipient.name} about {topic}. The message should:
1. Be conversational and direct, as if speaking face-to-face in the boardroom
2. Address {recipient.name} directly by name
3. Be strategic and business-focused
4. Match your executive role and personality
5. Be appropriate for a boardroom setting where you can see each other
6. Reference the business context naturally
7. Feel like a natural conversation between colleagues in the same room

Write only the message, nothing else. Make it feel like you're talking directly to them in person."""

            try:
                client = await llm_client._get_client()
                response = await client.post(
                    f"{llm_client.base_url}/api/generate",
                    json={
                        "model": llm_client.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message = result.get("response", "").strip()
                    
                    # Clean up the message (remove quotes, extra whitespace)
                    message = message.strip('"').strip("'").strip()
                    
                    if not message:
                        # Fallback message - more direct and conversational
                        message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
                else:
                    # Fallback message - more direct and conversational
                    message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
            except Exception as e:
                print(f"Error generating boardroom message: {e}")
                # Fallback message - more direct and conversational
                message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
            
            # Create chat message
            thread_id = generate_thread_id(sender.id, recipient.id)
            chat = ChatMessage(
                sender_id=sender.id,
                recipient_id=recipient.id,
                message=message,
                thread_id=thread_id
            )
            db.add(chat)
            chats_created += 1
        
        # Commit all messages with retry logic
        await commit_with_retry(db)
        
        return {
            "success": True,
            "message": f"Generated {chats_created} boardroom discussions",
            "chats_created": chats_created
        }
        
    except Exception as e:
        try:
            await db.rollback()
        except:
            pass  # Ignore rollback errors
        print(f"Error generating boardroom discussions: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "chats_created": 0
        }

@router.get("/notifications")
async def get_notifications(limit: int = 50, unread_only: bool = False, db: AsyncSession = Depends(get_db)):
    """Get all notifications, optionally filtered to unread only."""
    query = select(Notification).order_by(desc(Notification.created_at))
    
    if unread_only:
        query = query.where(Notification.read == False)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # Get employee names
    result = await db.execute(select(Employee))
    all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    
    return [
        {
            "id": notif.id,
            "notification_type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "employee_id": notif.employee_id,
            "employee_name": all_employees.get(notif.employee_id, "Unknown") if notif.employee_id else None,
            "review_id": notif.review_id,
            "read": notif.read,
            "created_at": notif.created_at.isoformat() if notif.created_at else None
        }
        for notif in notifications
    ]

@router.get("/notifications/unread-count")
async def get_unread_notification_count(db: AsyncSession = Depends(get_db)):
    """Get count of unread notifications."""
    result = await db.execute(
        select(func.count(Notification.id)).where(Notification.read == False)
    )
    count = result.scalar() or 0
    return {"count": count}

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a notification as read."""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.read = True
    await db.commit()
    
    return {"success": True, "message": "Notification marked as read"}

@router.post("/notifications/read-all")
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db)):
    """Mark all notifications as read."""
    result = await db.execute(select(Notification).where(Notification.read == False))
    notifications = result.scalars().all()
    
    for notification in notifications:
        notification.read = True
    
    await db.commit()
    
    return {"success": True, "message": f"Marked {len(notifications)} notifications as read"}

