from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, case
from sqlalchemy.orm import selectinload
from database.database import get_db, async_session_maker
from database.models import Employee, Project, Task, Activity, Financial, BusinessMetric, Email, ChatMessage, BusinessSettings, Decision, EmployeeReview, Notification, CustomerReview, Meeting, Product, ProductTeamMember, SharedDriveFile, SharedDriveFileVersion, TrainingSession, TrainingMaterial, HomeSettings, FamilyMember, HomePet
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from business.goal_system import GoalSystem
from database.query_cache import cached_query, clear_cache
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from config import now as local_now, TIMEZONE_NAME, is_work_hours
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()

# Cache invalidation helper
async def invalidate_cache(pattern: str = None):
    """Invalidate backend cache entries matching a pattern."""
    try:
        await clear_cache(pattern)
        logger.debug(f"Cache invalidated for pattern: {pattern or 'all'}")
    except Exception as e:
        logger.warning(f"Error invalidating cache: {e}", exc_info=True)

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
    try:
        return await _fetch_employees_data(db)
    except Exception as e:
        import traceback
        print(f"Error in get_employees: {e}")
        print(traceback.format_exc())
        return []

@cached_query(cache_duration=15)  # Cache for 15 seconds
async def _fetch_employees_data(db: AsyncSession):
    """Internal function to fetch employees data."""
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
    
    # Optimized: Get latest review info using window function (PostgreSQL-specific)
    # This is much more efficient than loading all reviews and processing in Python
    from sqlalchemy import text
    
    # Use window function with ROW_NUMBER to get latest review per employee
    # This is a PostgreSQL-optimized query that's much faster than Python processing
    latest_reviews_result = await db.execute(text("""
        SELECT DISTINCT ON (employee_id)
            employee_id,
            COALESCE(review_date, created_at) as review_date,
            overall_rating
        FROM employee_reviews
        ORDER BY employee_id, COALESCE(review_date, created_at) DESC
    """))
    latest_reviews = latest_reviews_result.all()
    
    # Create maps for latest review information
    latest_review_dates = {}
    latest_ratings = {}
    for row in latest_reviews:
        latest_review_dates[row.employee_id] = row.review_date
        latest_ratings[row.employee_id] = row.overall_rating
    
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
            "latest_rating": float(latest_rating) if latest_rating else None,
            "has_performance_award": bool(emp.has_performance_award) if hasattr(emp, 'has_performance_award') else False,
            "performance_award_wins": int(emp.performance_award_wins) if hasattr(emp, 'performance_award_wins') else 0
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
    
    # Check if employee is terminated - terminated employees are not eligible for reviews
    if employee.status == "fired" or employee.fired_at:
        return {
            "scheduled_at": None,
            "manager_id": None,
            "manager_name": None,
            "manager_title": None,
            "eligible": False,
            "reason": "Terminated employees are not eligible for performance reviews."
        }
    
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
        next_review_time = local_now() + timedelta(hours=6)
    
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
    
    # Get award history (all times employee won the performance award)
    result = await db.execute(
        select(Activity)
        .where(
            Activity.employee_id == employee_id,
            Activity.activity_type == "performance_award_earned"
        )
        .order_by(desc(Activity.timestamp))
    )
    award_history = result.scalars().all()
    
    # Get recent decisions
    from database.models import Decision
    result = await db.execute(
        select(Decision)
        .where(Decision.employee_id == employee_id)
        .order_by(desc(Decision.timestamp))
        .limit(5)
    )
    decisions = result.scalars().all()
    
    # Get termination reason if employee is terminated
    termination_reason = None
    if emp.status == "fired" or emp.fired_at:
        # Find the firing activity for this employee
        firing_result = await db.execute(
            select(Activity)
            .where(Activity.activity_type == "firing")
            .order_by(desc(Activity.timestamp))
        )
        firing_activities = firing_result.scalars().all()
        # Find the activity for this specific employee
        for activity in firing_activities:
            if activity.activity_metadata and isinstance(activity.activity_metadata, dict):
                emp_id = activity.activity_metadata.get("employee_id")
                if emp_id == employee_id:
                    termination_reason = activity.activity_metadata.get("termination_reason")
                    break
    
    # Calculate next review information
    next_review_info = await _calculate_next_review_info(emp, db)

    # Get manager information
    manager_info = None
    if emp.manager_id:
        manager_result = await db.execute(
            select(Employee).where(Employee.id == emp.manager_id)
        )
        manager = manager_result.scalar_one_or_none()
        if manager:
            manager_info = {
                "id": manager.id,
                "name": manager.name,
                "title": manager.title,
                "role": manager.role,
                "department": manager.department,
                "avatar_path": manager.avatar_path if hasattr(manager, 'avatar_path') else None
            }

    # Get direct reports (if this is a manager)
    direct_reports = []
    if emp.role in ["Manager", "CEO", "CTO", "COO", "CFO"]:
        reports_result = await db.execute(
            select(Employee).where(
                Employee.manager_id == emp.id,
                Employee.status == "active"
            ).order_by(Employee.name)
        )
        reports = reports_result.scalars().all()
        direct_reports = [
            {
                "id": report.id,
                "name": report.name,
                "title": report.title,
                "role": report.role,
                "department": report.department,
                "avatar_path": report.avatar_path if hasattr(report, 'avatar_path') else None
            }
            for report in reports
        ]

    return {
        "id": emp.id,
        "name": emp.name,
        "title": emp.title,
        "role": emp.role,
        "hierarchy_level": emp.hierarchy_level,
        "department": emp.department,
        "status": emp.status,
        "manager": manager_info,
        "direct_reports": direct_reports,
        "direct_reports_count": len(direct_reports),
        "current_task_id": emp.current_task_id,
        "personality_traits": emp.personality_traits,
        "backstory": emp.backstory,
        "avatar_path": emp.avatar_path if hasattr(emp, 'avatar_path') else None,
        "current_room": emp.current_room if hasattr(emp, 'current_room') else None,
        "home_room": emp.home_room if hasattr(emp, 'home_room') else None,
        "target_room": emp.target_room if hasattr(emp, 'target_room') else None,
        "floor": emp.floor if hasattr(emp, 'floor') else None,
        "activity_state": emp.activity_state if hasattr(emp, 'activity_state') else "idle",
        "sleep_state": emp.sleep_state if hasattr(emp, 'sleep_state') else "awake",
        "online_status": emp.online_status if hasattr(emp, 'online_status') else "online",
        "hired_at": emp.hired_at.isoformat() if hasattr(emp, 'hired_at') and emp.hired_at else None,
        "fired_at": emp.fired_at.isoformat() if hasattr(emp, 'fired_at') and emp.fired_at else None,
        "termination_reason": termination_reason,
        "has_performance_award": bool(emp.has_performance_award) if hasattr(emp, 'has_performance_award') else False,
        "performance_award_wins": int(emp.performance_award_wins) if hasattr(emp, 'performance_award_wins') else 0,
        "award_history": [
            {
                "id": award.id,
                "description": award.description,
                "timestamp": award.timestamp.isoformat() if award.timestamp else None,
                "rating": award.activity_metadata.get("rating") if award.activity_metadata and isinstance(award.activity_metadata, dict) else None
            }
            for award in award_history
        ],
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
        "next_review": next_review_info,
        "birthday_month": emp.birthday_month if hasattr(emp, 'birthday_month') else None,
        "birthday_day": emp.birthday_day if hasattr(emp, 'birthday_day') else None
    }

@router.get("/employees/{employee_id}/reviews")
async def get_employee_reviews(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get all reviews for a specific employee."""
    # Query all reviews for this employee, including those without review_date
    result = await db.execute(
        select(EmployeeReview)
        .where(EmployeeReview.employee_id == employee_id)
        .order_by(desc(EmployeeReview.created_at))
    )
    reviews = result.scalars().all()
    
    print(f"📋 API: Found {len(reviews)} review(s) for employee {employee_id}")
    for review in reviews:
        print(f"   - Review ID {review.id}, Date: {review.review_date}, Rating: {review.overall_rating}, Comments: {bool(review.comments)}")
    
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

@router.get("/employees/{employee_id}/thoughts")
async def get_employee_thoughts(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get AI-generated thoughts from the employee's perspective."""
    from llm.ollama_client import OllamaClient
    from engine.office_simulator import get_business_context
    
    # Get employee
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Terminated employees should not have thoughts generated
    if emp.status == "fired" or emp.fired_at:
        raise HTTPException(status_code=403, detail="Terminated employees are not eligible for thoughts generation")
    
    # Get recent activities
    result = await db.execute(
        select(Activity)
        .where(Activity.employee_id == employee_id)
        .order_by(desc(Activity.timestamp))
        .limit(5)
    )
    activities = result.scalars().all()
    
    # Get recent decisions
    result = await db.execute(
        select(Decision)
        .where(Decision.employee_id == employee_id)
        .order_by(desc(Decision.timestamp))
        .limit(3)
    )
    decisions = result.scalars().all()
    
    # Get recent emails
    try:
        result = await db.execute(
            select(Email)
            .where((Email.sender_id == employee_id) | (Email.recipient_id == employee_id))
            .order_by(desc(Email.timestamp))
            .limit(3)
        )
        emails = result.scalars().all()
    except Exception:
        emails = []
    
    # Get recent chats
    try:
        result = await db.execute(
            select(ChatMessage)
            .where((ChatMessage.sender_id == employee_id) | (ChatMessage.recipient_id == employee_id))
            .order_by(desc(ChatMessage.timestamp))
            .limit(3)
        )
        chats = result.scalars().all()
    except Exception:
        chats = []
    
    # Get recent reviews
    result = await db.execute(
        select(EmployeeReview)
        .where(EmployeeReview.employee_id == employee_id)
        .order_by(desc(EmployeeReview.created_at))
        .limit(2)
    )
    reviews = result.scalars().all()
    
    # Get current task if available
    current_task = None
    if emp.current_task_id:
        result = await db.execute(
            select(Task).where(Task.id == emp.current_task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            current_task = task.description
    
    # Get business context
    business_context = await get_business_context(db)
    
    # Prepare data for LLM
    activities_data = [
        {
            "description": act.description,
            "activity_type": act.activity_type,
            "timestamp": act.timestamp.isoformat() if act.timestamp else None
        }
        for act in activities
    ]
    
    decisions_data = [
        {
            "description": dec.description,
            "reasoning": dec.reasoning,
            "decision_type": dec.decision_type,
            "timestamp": dec.timestamp.isoformat() if dec.timestamp else None
        }
        for dec in decisions
    ]
    
    emails_data = [
        {
            "subject": email.subject,
            "body": email.body[:100] if email.body else "",
            "timestamp": email.timestamp.isoformat() if email.timestamp else None
        }
        for email in emails
    ]
    
    chats_data = [
        {
            "message": chat.message,
            "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
        }
        for chat in chats
    ]
    
    reviews_data = [
        {
            "overall_rating": rev.overall_rating,
            "comments": rev.comments or "",
            "review_date": rev.review_date.isoformat() if rev.review_date else None
        }
        for rev in reviews
    ]
    
    # Generate thoughts using LLM
    llm_client = OllamaClient()
    try:
        thoughts = await llm_client.generate_employee_thoughts(
            employee_name=emp.name,
            employee_title=emp.title,
            employee_role=emp.role,
            personality_traits=emp.personality_traits or [],
            backstory=emp.backstory,
            recent_activities=activities_data,
            recent_decisions=decisions_data,
            recent_emails=emails_data,
            recent_chats=chats_data,
            recent_reviews=reviews_data,
            current_status=emp.status or "active",
            current_task=current_task,
            business_context=business_context
        )
    except Exception as e:
        print(f"Error generating employee thoughts: {e}")
        thoughts = "I'm focused on my current work and thinking about how to contribute effectively to the team."
    finally:
        await llm_client.close()
    
    return {
        "thoughts": thoughts,
        "generated_at": datetime.now().isoformat()
    }

@router.get("/employees/{employee_id}/screen-view")
async def get_employee_screen_view(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get real-time screen view of employee's computer when they are in working state."""
    try:
        from llm.ollama_client import OllamaClient
        from engine.office_simulator import get_business_context
        from sqlalchemy.orm import selectinload
        
        # Get employee
        result = await db.execute(
            select(Employee)
            .where(Employee.id == employee_id)
        )
        emp = result.scalar_one_or_none()
        
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check if employee is in working state
        if emp.activity_state != "working" or emp.status != "active":
            raise HTTPException(
                status_code=403, 
                detail=f"Employee is not in working state. Current state: {emp.activity_state}, status: {emp.status}"
            )
        
        # Get current task if exists
        current_task = None
        project_name = None
        project_description = None
        if emp.current_task_id:
            result = await db.execute(
                select(Task)
                .where(Task.id == emp.current_task_id)
                .options(selectinload(Task.project))
            )
            task = result.scalar_one_or_none()
            if task:
                current_task = task.description
                if task.project:
                    project_name = task.project.name
                    project_description = task.project.description
        
        # Get all employees for name lookup
        all_employees_result = await db.execute(select(Employee))
        all_employees = {e.id: e.name for e in all_employees_result.scalars().all()}
        
        # Get recent emails (last 5)
        result = await db.execute(
            select(Email)
            .where(
                (Email.sender_id == employee_id) | (Email.recipient_id == employee_id)
            )
            .order_by(desc(Email.timestamp))
            .limit(5)
        )
        recent_emails = result.scalars().all()
        emails_data = [
            {
                "id": email.id,
                "subject": email.subject,
                "body": email.body or "",
                "sender_id": email.sender_id,
                "sender_name": all_employees.get(email.sender_id, "Unknown"),
                "recipient_id": email.recipient_id,
                "recipient_name": all_employees.get(email.recipient_id, "Unknown"),
                "timestamp": email.timestamp.isoformat() if email.timestamp else None
            }
            for email in recent_emails
        ]
        
        # Get recent chats (last 5)
        result = await db.execute(
            select(ChatMessage)
            .where(
                (ChatMessage.sender_id == employee_id) | (ChatMessage.recipient_id == employee_id)
            )
            .order_by(desc(ChatMessage.timestamp))
            .limit(5)
        )
        recent_chats = result.scalars().all()
        chats_data = [
            {
                "id": chat.id,
                "message": chat.message,
                "sender_id": chat.sender_id,
                "sender_name": all_employees.get(chat.sender_id, "Unknown"),
                "recipient_id": chat.recipient_id,
                "recipient_name": all_employees.get(chat.recipient_id, "Unknown"),
                "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
            }
            for chat in recent_chats
        ]
        
        # Get shared drive files related to employee's project
        shared_drive_files = []
        if project_name or emp.department:
            if project_name:
                # Try to find files for this project (use first() to avoid multiple rows error)
                result = await db.execute(
                    select(Project).where(Project.name == project_name).limit(1)
                )
                project = result.scalars().first()
                if project:
                    result = await db.execute(
                        select(SharedDriveFile)
                        .where(SharedDriveFile.project_id == project.id)
                        .order_by(desc(SharedDriveFile.updated_at))
                        .limit(5)
                    )
                    shared_drive_files = result.scalars().all()
            elif emp.department:
                # Fallback to department files
                result = await db.execute(
                    select(SharedDriveFile)
                    .where(SharedDriveFile.department == emp.department)
                    .order_by(desc(SharedDriveFile.updated_at))
                    .limit(5)
                )
                shared_drive_files = result.scalars().all()
        
        # Get file content for shared drive files
        files_data = []
        for f in shared_drive_files:
            file_data = {
                "id": f.id,
                "file_name": f.file_name,
                "file_type": f.file_type,
                "department": f.department,
                "project_id": f.project_id,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None
            }
            # Get the latest version content if available
            if f.id:
                try:
                    result = await db.execute(
                        select(SharedDriveFileVersion)
                        .where(SharedDriveFileVersion.file_id == f.id)
                        .order_by(desc(SharedDriveFileVersion.version_number))
                        .limit(1)
                    )
                    latest_version = result.scalar_one_or_none()
                    if latest_version:
                        # Ensure we access content_html, not content
                        if hasattr(latest_version, 'content_html') and latest_version.content_html:
                            file_data["content"] = latest_version.content_html[:5000]  # Limit to 5000 chars
                        else:
                            print(f"Warning: SharedDriveFileVersion {latest_version.id} has no content_html")
                except AttributeError as ae:
                    print(f"AttributeError accessing content for file {f.id}: {ae}")
                    # Continue without content
                except Exception as e:
                    print(f"Error fetching version content for file {f.id}: {e}")
                    # Continue without content
            files_data.append(file_data)
    
        # Get business context
        business_context = await get_business_context(db)
        
        # Generate screen activity using Ollama with timeout
        # Send comprehensive data for realistic AI-driven screen view
        import asyncio
        import time
        llm_client = OllamaClient()
        try:
            print(f"[SCREEN-VIEW] Generating comprehensive screen activity for employee {emp.name} (ID: {employee_id})")
            start_time = time.time()
            
            # Increase timeout to 60 seconds to allow for processing comprehensive data
            # This matches the httpx client timeout in OllamaClient
            screen_activity = await asyncio.wait_for(
                llm_client.generate_screen_activity(
                    employee_name=emp.name,
                    employee_title=emp.title,
                    employee_role=emp.role,
                    personality_traits=emp.personality_traits or [],
                    current_task=current_task,
                    project_name=project_name,
                    project_description=project_description,
                    recent_emails=emails_data,  # Full email data
                    recent_chats=chats_data,    # Full chat data
                    shared_drive_files=files_data,  # Full file data with content
                    business_context=business_context
                ),
                timeout=60.0  # 60 second timeout to allow comprehensive AI generation
            )
            
            elapsed = time.time() - start_time
            print(f"[SCREEN-VIEW] Screen activity generated in {elapsed:.2f}s")
            
        except asyncio.TimeoutError:
            print(f"[SCREEN-VIEW] LLM timeout after 60s for employee {emp.name}")
            # Return fallback activity on timeout
            screen_activity = {
                "application": "outlook",
                "action": "viewing",
                "content": {
                    "subject": "Work Update",
                    "recipient": "Team",
                    "body": f"{emp.name} is reviewing emails and working on {current_task or 'current tasks'}."
                },
                "mouse_position": {"x": 50, "y": 50},
                "window_state": "active"
            }
        except Exception as e:
            print(f"[SCREEN-VIEW] Error generating screen activity: {e}")
            import traceback
            traceback.print_exc()
            # Return fallback activity
            screen_activity = {
                "application": "outlook",
                "action": "viewing",
                "content": {
                    "subject": "Work Update",
                    "recipient": "Team",
                    "body": f"{emp.name} is reviewing emails related to their current work."
                },
                "mouse_position": {"x": 50, "y": 50},
                "window_state": "active"
            }
        finally:
            await llm_client.close()
        
        return {
            "employee_id": employee_id,
            "employee_name": emp.name,
            "employee_title": emp.title,
            "screen_activity": screen_activity,
            "actual_data": {
                "emails": emails_data,
                "chats": chats_data,
                "files": files_data
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, etc.)
        raise
    except Exception as e:
        # Catch any other errors and return a 500 with details
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_employee_screen_view: {e}")
        print(error_details)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/reviews/debug")
async def debug_reviews(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to see all reviews in the database."""
    result = await db.execute(
        select(EmployeeReview)
        .order_by(desc(EmployeeReview.created_at))
        .limit(50)
    )
    all_reviews = result.scalars().all()
    
    # Get employee names
    result = await db.execute(select(Employee))
    all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    
    return {
        "total_reviews": len(all_reviews),
        "reviews": [
            {
                "id": review.id,
                "employee_id": review.employee_id,
                "employee_name": all_employees.get(review.employee_id, "Unknown"),
                "manager_id": review.manager_id,
                "manager_name": all_employees.get(review.manager_id, "Unknown"),
                "review_date": review.review_date.isoformat() if review.review_date else None,
                "created_at": review.created_at.isoformat() if review.created_at else None,
                "overall_rating": review.overall_rating,
                "has_comments": bool(review.comments),
                "has_strengths": bool(review.strengths),
                "has_areas": bool(review.areas_for_improvement),
                "comments_length": len(review.comments or ""),
                "strengths_length": len(review.strengths or ""),
                "areas_length": len(review.areas_for_improvement or "")
            }
            for review in all_reviews
        ]
    }

@router.post("/employees/{employee_id}/reviews")
async def create_employee_review(employee_id: int, review_data: CreateReviewRequest, db: AsyncSession = Depends(get_db)):
    """Create a new review for an employee (for manual creation or system-generated)."""
    # Verify employee exists
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Terminated employees are not eligible for reviews
    if employee.status == "fired" or employee.fired_at:
        raise HTTPException(status_code=403, detail="Terminated employees are not eligible for performance reviews")
    
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
    
    # Update performance award after review is created
    from business.review_manager import ReviewManager
    review_manager = ReviewManager(db)
    await review_manager._update_performance_award()
    await db.commit()
    
    # Invalidate caches after data is committed
    await invalidate_cache("_fetch_employees_data")
    await invalidate_cache("_fetch_dashboard_data")
    
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

@router.get("/reviews/award-diagnostic")
async def get_award_diagnostic(db: AsyncSession = Depends(get_db)):
    """Diagnostic endpoint to check who should have the award vs who actually has it."""
    from business.review_manager import ReviewManager
    from sqlalchemy import select, desc, func
    from datetime import datetime
    
    # Get all active employees with their latest reviews
    result = await db.execute(
        select(Employee).where(Employee.status == "active")
    )
    all_employees = result.scalars().all()
    
    employee_reviews = []
    for employee in all_employees:
        # Get most recent review
        review_result = await db.execute(
            select(EmployeeReview)
            .where(EmployeeReview.employee_id == employee.id)
            .order_by(desc(EmployeeReview.review_date), desc(EmployeeReview.created_at))
            .limit(1)
        )
        latest_review = review_result.scalar_one_or_none()
        
        if latest_review:
            review_date = latest_review.review_date if latest_review.review_date else latest_review.created_at
            employee_reviews.append({
                "employee_id": employee.id,
                "employee_name": employee.name,
                "rating": latest_review.overall_rating,
                "review_date": review_date.isoformat() if review_date else None,
                "has_award": bool(employee.has_performance_award),
                "award_wins": int(employee.performance_award_wins) if employee.performance_award_wins else 0
            })
    
    if not employee_reviews:
        return {
            "error": "No reviews found",
            "current_holder": None,
            "should_be_holder": None
        }
    
    # Find who should have the award (highest rating, most recent review date)
    max_rating = max(er["rating"] for er in employee_reviews)
    top_employees = [er for er in employee_reviews if er["rating"] == max_rating]
    
    # Sort by review date (newest first), then by employee ID
    top_employees.sort(key=lambda x: (
        -(datetime.fromisoformat(x["review_date"]).timestamp() if x["review_date"] else 0),
        x["employee_id"]
    ))
    
    should_be_holder = top_employees[0] if top_employees else None
    
    # Find current holder
    result = await db.execute(
        select(Employee).where(
            Employee.has_performance_award == True,
            Employee.status == "active"
        )
    )
    current_holder_emp = result.scalar_one_or_none()
    current_holder = None
    if current_holder_emp:
        current_holder = {
            "employee_id": current_holder_emp.id,
            "employee_name": current_holder_emp.name,
            "award_wins": int(current_holder_emp.performance_award_wins) if current_holder_emp.performance_award_wins else 0
        }
    
    return {
        "current_holder": current_holder,
        "should_be_holder": should_be_holder,
        "all_top_employees": top_employees[:5],  # Top 5 for reference
        "max_rating": max_rating,
        "match": current_holder and should_be_holder and current_holder["employee_id"] == should_be_holder["employee_id"]
    }

@router.post("/reviews/initialize-award")
async def initialize_performance_award(db: AsyncSession = Depends(get_db), force: bool = False):
    """Initialize the performance award for existing reviews. Assigns award to employee with highest rating.
    
    Args:
        force: If True, will remove award from current holder and recalculate from scratch.
    """
    from business.review_manager import ReviewManager
    
    # If force is True, remove award from all employees first
    if force:
        result = await db.execute(
            select(Employee).where(Employee.has_performance_award == True)
        )
        current_holders = result.scalars().all()
        for holder in current_holders:
            holder.has_performance_award = False
        await db.commit()
        print(f"[AWARD] Force update: Removed award from {len(current_holders)} employee(s)")
    
    review_manager = ReviewManager(db)
    await review_manager._update_performance_award()
    await db.commit()
    
    # Get the current award holder
    result = await db.execute(
        select(Employee).where(
            Employee.has_performance_award == True,
            Employee.status == "active"
        )
    )
    award_holder = result.scalar_one_or_none()
    
    if award_holder:
        return {
            "success": True,
            "message": f"Performance award initialized. Current holder: {award_holder.name}",
            "award_holder": {
                "id": award_holder.id,
                "name": award_holder.name,
                "title": award_holder.title
            }
        }
    else:
        return {
            "success": True,
            "message": "Performance award initialized. No award holder assigned (no reviews found or no eligible employees).",
            "award_holder": None
        }

@router.post("/reviews/update-award-now")
async def update_performance_award_now(db: AsyncSession = Depends(get_db)):
    """FORCE update the performance award RIGHT NOW. Use this to immediately assign the award."""
    from business.review_manager import ReviewManager
    
    print("🏆 [AWARD] FORCING immediate performance award update via API...")
    review_manager = ReviewManager(db)
    await review_manager._update_performance_award()
    await db.commit()
    
    # Get the current award holder
    result = await db.execute(
        select(Employee).where(
            Employee.has_performance_award == True,
            Employee.status == "active"
        )
    )
    award_holder = result.scalar_one_or_none()
    
    if award_holder:
        return {
            "success": True,
            "message": f"Performance award updated! Current holder: {award_holder.name}",
            "award_holder": {
                "id": award_holder.id,
                "name": award_holder.name,
                "title": award_holder.title,
                "rating": None  # We'd need to query the review to get this
            }
        }
    else:
        return {
            "success": True,
            "message": "Performance award updated. No award holder assigned (no reviews found or no eligible employees).",
            "award_holder": None
        }

@router.get("/employees/{employee_id}/award-message")
async def get_award_congratulatory_message(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Generate an AI congratulatory message from the manager for the employee's performance award."""
    from business.review_manager import ReviewManager
    from llm.ollama_client import OllamaClient
    
    # Get employee
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if not employee.has_performance_award:
        raise HTTPException(status_code=400, detail="Employee does not currently hold the performance award")
    
    # Get the employee's most recent review to find their manager
    result = await db.execute(
        select(EmployeeReview)
        .where(EmployeeReview.employee_id == employee_id)
        .order_by(desc(EmployeeReview.review_date), desc(EmployeeReview.created_at))
        .limit(1)
    )
    latest_review = result.scalar_one_or_none()
    
    if not latest_review:
        raise HTTPException(status_code=404, detail="No reviews found for this employee")
    
    # Get the manager
    result = await db.execute(select(Employee).where(Employee.id == latest_review.manager_id))
    manager = result.scalar_one_or_none()
    
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    # Get employee's latest rating
    latest_rating = latest_review.overall_rating
    award_wins = employee.performance_award_wins if hasattr(employee, 'performance_award_wins') else 1
    
    # Generate congratulatory message using Ollama
    manager_personality = ", ".join(manager.personality_traits) if manager.personality_traits else "professional, supportive"
    employee_personality = ", ".join(employee.personality_traits) if employee.personality_traits else "dedicated"
    
    prompt = f"""You are {manager.name}, {manager.title} at TechFlow Solutions. You are writing a congratulatory message to {employee.name}, {employee.title}, who has just earned the Performance Award for having the highest review rating ({latest_rating:.1f}/5.0) among all employees.

This is {employee.name}'s {award_wins} time{'s' if award_wins > 1 else ''} winning this award.

Your personality traits: {manager_personality}
Your role: {manager.role}
Your backstory: {manager.backstory or "Experienced manager focused on team development"}

Employee being congratulated:
- Name: {employee.name}
- Title: {employee.title}
- Department: {employee.department}
- Personality: {employee_personality}
- Backstory: {employee.backstory or "Team member"}
- Latest Rating: {latest_rating:.1f}/5.0
- Award Wins: {award_wins}

Write a warm, professional, and personalized congratulatory message (2-3 sentences) from your perspective as {manager.name}. The message should:
1. Congratulate {employee.name} on earning the Performance Award
2. Acknowledge their excellent performance (rating: {latest_rating:.1f}/5.0)
3. If this is not their first win, acknowledge their consistent excellence
4. Express appreciation for their contributions
5. Encourage them to continue their great work

Write the message in a natural, conversational tone that matches your personality traits. Be genuine and specific."""

    try:
        llm_client = OllamaClient()
        message = await llm_client.generate_response(prompt)
        
        # Clean up the message (remove any JSON formatting if present)
        message = message.strip()
        # Remove quotes if the entire message is wrapped in them
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        if message.startswith("'") and message.endswith("'"):
            message = message[1:-1]
        
        return {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "manager_id": manager.id,
            "manager_name": manager.name,
            "manager_title": manager.title,
            "rating": latest_rating,
            "award_wins": award_wins,
            "message": message,
            "generated_at": local_now().isoformat()
        }
    except Exception as e:
        import traceback
        print(f"Error generating award message: {e}")
        traceback.print_exc()
        # Fallback message
        fallback_message = f"Congratulations, {employee.name}! You've earned the Performance Award with a rating of {latest_rating:.1f}/5.0. Your dedication and excellent work are truly appreciated. Keep up the outstanding performance!"
        return {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "manager_id": manager.id,
            "manager_name": manager.name,
            "manager_title": manager.title,
            "rating": latest_rating,
            "award_wins": award_wins,
            "message": fallback_message,
            "generated_at": local_now().isoformat()
        }

@cached_query(cache_duration=15)  # Cache for 15 seconds
async def _fetch_projects_data(db: AsyncSession):
    """Internal function to fetch projects data."""
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
            logger.error(f"Error calculating progress for project {proj.id}: {e}", exc_info=True)
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

@router.get("/projects")
async def get_projects(db: AsyncSession = Depends(get_db)):
    """Get all projects."""
    try:
        return await _fetch_projects_data(db)
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
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

async def sync_products_from_reviews(db: AsyncSession):
    """
    Automatically create/update products from reviews.
    Finds all projects with reviews and ensures they have corresponding products.
    """
    try:
        # Find all unique projects that have reviews
        result = await db.execute(
            select(Project)
            .join(CustomerReview, CustomerReview.project_id == Project.id)
            .where(CustomerReview.project_id.isnot(None))
            .distinct()
        )
        projects_with_reviews = result.scalars().all()
        
        if not projects_with_reviews:
            return 0
        
        products_created = 0
        products_updated = 0
        
        for project in projects_with_reviews:
            if not project:
                continue
            
            # Check if product already exists for this project
            existing_product = None
            if project.product_id:
                result = await db.execute(select(Product).where(Product.id == project.product_id))
                existing_product = result.scalar_one_or_none()
            
            # If no product linked, check if a product with the same name exists
            if not existing_product:
                result = await db.execute(select(Product).where(Product.name == project.name))
                existing_product = result.scalar_one_or_none()
            
            if existing_product:
                # Product exists, ensure project and reviews are linked
                if project.product_id != existing_product.id:
                    project.product_id = existing_product.id
                    products_updated += 1
                
                # Update reviews to link to this product
                result = await db.execute(
                    select(CustomerReview).where(
                        CustomerReview.project_id == project.id,
                        CustomerReview.product_id.is_(None)
                    )
                )
                unlinked_reviews = result.scalars().all()
                for review in unlinked_reviews:
                    review.product_id = existing_product.id
                    products_updated += 1
            else:
                # Create new product from project
                new_product = Product(
                    name=project.name,
                    description=project.description or f"Product based on {project.name} project",
                    category="Service",
                    status="active" if project.status == "completed" else "development",
                    price=0.0,
                    launch_date=project.completed_at if project.completed_at else project.created_at,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_product)
                await db.flush()  # Get the ID
                
                # Link project to product
                project.product_id = new_product.id
                
                # Link all reviews for this project to the product
                result = await db.execute(
                    select(CustomerReview).where(CustomerReview.project_id == project.id)
                )
                reviews = result.scalars().all()
                for review in reviews:
                    review.product_id = new_product.id
                
                products_created += 1
        
        if products_created > 0 or products_updated > 0:
            await db.commit()
            print(f"✅ Synced products from reviews: {products_created} created, {products_updated} updated")
        
        return products_created + products_updated
    except Exception as e:
        print(f"Error syncing products from reviews: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        return 0

@cached_query(cache_duration=20)  # Cache for 20 seconds
async def _fetch_products_data(db: AsyncSession):
    """Internal function to fetch products data."""
    # Sync products from reviews before fetching
    await sync_products_from_reviews(db)
    
    # Optimized query: Get all products with aggregated data in a single query
    # This eliminates N+1 queries by using LEFT JOINs and aggregations
    result = await db.execute(
        select(
            Product,
            func.count(CustomerReview.id).label('review_count'),
            func.coalesce(func.avg(CustomerReview.rating), 0.0).label('avg_rating'),
            func.coalesce(func.sum(Project.revenue), 0.0).label('total_sales'),
            func.count(func.distinct(ProductTeamMember.id)).label('team_count')
        )
        .outerjoin(CustomerReview, Product.id == CustomerReview.product_id)
        .outerjoin(Project, Product.id == Project.product_id)
        .outerjoin(ProductTeamMember, Product.id == ProductTeamMember.product_id)
        .group_by(Product.id)
        .order_by(desc(Product.created_at))
    )
    
    rows = result.all()
    
    product_list = []
    for product, review_count, avg_rating, total_sales, team_count in rows:
        product_list.append({
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "status": product.status,
            "price": product.price,
            "launch_date": product.launch_date.isoformat() if product.launch_date else None,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            "review_count": int(review_count) if review_count else 0,
            "average_rating": round(float(avg_rating), 1) if avg_rating else 0.0,
            "total_sales": float(total_sales) if total_sales else 0.0,
            "team_count": int(team_count) if team_count else 0
        })
    
    return product_list

@router.get("/products")
async def get_products(db: AsyncSession = Depends(get_db)):
    """Get all products. Automatically syncs products from reviews."""
    try:
        return await _fetch_products_data(db)
    except Exception as e:
        logger.error(f"Error fetching products: {e}", exc_info=True)
        return []

@router.post("/products/sync-from-reviews")
async def sync_products_from_reviews_endpoint(db: AsyncSession = Depends(get_db)):
    """Manually trigger sync of products from reviews."""
    try:
        count = await sync_products_from_reviews(db)
        await db.commit()
        # Invalidate products cache after sync
        await invalidate_cache("_fetch_products_data")
        return {
            "success": True,
            "message": f"Synced products from reviews: {count} products created/updated",
            "count": count
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in sync endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error syncing products: {str(e)}")

@router.get("/products/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get product details with team members, sales, and feedback."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get team members
    team_result = await db.execute(
        select(ProductTeamMember, Employee)
        .join(Employee, ProductTeamMember.employee_id == Employee.id)
        .where(ProductTeamMember.product_id == product_id)
        .order_by(ProductTeamMember.added_at)
    )
    team_members_data = team_result.all()
    
    team_members = []
    for team_member, employee in team_members_data:
        team_members.append({
            "id": team_member.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_title": employee.title,
            "employee_department": employee.department,
            "role": team_member.role,
            "responsibility": team_member.responsibility,
            "added_at": team_member.added_at.isoformat() if team_member.added_at else None,
            "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None
        })
    
    # Get customer reviews
    reviews_result = await db.execute(
        select(CustomerReview)
        .where(CustomerReview.product_id == product_id)
        .order_by(desc(CustomerReview.created_at))
    )
    reviews = reviews_result.scalars().all()
    
    customer_reviews = []
    total_rating = 0.0
    for review in reviews:
        total_rating += review.rating
        customer_reviews.append({
            "id": review.id,
            "customer_name": review.customer_name,
            "customer_title": review.customer_title,
            "company_name": review.company_name,
            "rating": review.rating,
            "review_text": review.review_text,
            "verified_purchase": review.verified_purchase,
            "helpful_count": review.helpful_count,
            "created_at": review.created_at.isoformat() if review.created_at else None
        })
    
    avg_rating = total_rating / len(reviews) if reviews else 0.0
    
    # Get sales data (from projects related to this product)
    projects_result = await db.execute(
        select(Project).where(Project.product_id == product_id)
    )
    projects = projects_result.scalars().all()
    
    sales_data = {
        "total_revenue": sum(p.revenue for p in projects),
        "total_budget": sum(p.budget for p in projects),
        "project_count": len(projects),
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "revenue": p.revenue,
                "budget": p.budget,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in projects
        ]
    }
    
    # Get financial transactions related to this product (through projects)
    financials_result = await db.execute(
        select(Financial)
        .join(Project, Financial.project_id == Project.id)
        .where(Project.product_id == product_id)
        .order_by(desc(Financial.timestamp))
        .limit(50)
    )
    financials = financials_result.scalars().all()
    
    recent_transactions = [
        {
            "id": f.id,
            "type": f.type,
            "amount": f.amount,
            "description": f.description,
            "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            "project_id": f.project_id
        }
        for f in financials
    ]
    
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "status": product.status,
        "price": product.price,
        "launch_date": product.launch_date.isoformat() if product.launch_date else None,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "team_members": team_members,
        "customer_reviews": customer_reviews,
        "average_rating": round(avg_rating, 1),
        "review_count": len(reviews),
        "sales": sales_data,
        "recent_transactions": recent_transactions
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
            "timestamp": (act.timestamp or local_now()).isoformat()
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
            "timestamp": (act.timestamp or local_now()).isoformat()
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
    """Get dashboard data with caching."""
    try:
        # Test database connection first
        try:
            await db.execute(select(Employee).limit(1))
        except Exception as db_error:
            logger.error(f"Database connection error in dashboard: {db_error}", exc_info=True)
            # Return default values if DB is not accessible
            return {
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
                    "location": "New York",
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
        
        return await _fetch_dashboard_data(db)
    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {e}", exc_info=True)
        # Return default values instead of crashing
        return {
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

@cached_query(cache_duration=10)  # Cache for 10 seconds (dashboard updates frequently)
async def _fetch_dashboard_data(db: AsyncSession):
    """Get dashboard data."""
    try:
        # Safely import and initialize managers
        try:
            financial_manager = FinancialManager(db)
        except Exception as e:
            print(f"Error creating FinancialManager: {e}")
            financial_manager = None
        
        try:
            project_manager = ProjectManager(db)
        except Exception as e:
            print(f"Error creating ProjectManager: {e}")
            project_manager = None
        
        try:
            goal_system = GoalSystem(db)
        except Exception as e:
            print(f"Error creating GoalSystem: {e}")
            goal_system = None
        
        try:
            revenue = await financial_manager.get_total_revenue() if financial_manager else 0.0
        except:
            revenue = 0.0
        
        try:
            profit = await financial_manager.get_profit() if financial_manager else 0.0
        except:
            profit = 0.0
        
        try:
            expenses = await financial_manager.get_total_expenses() if financial_manager else 0.0
        except:
            expenses = 0.0
        
        try:
            active_projects = await project_manager.get_active_projects() if project_manager else []
            # Ensure it's a list
            if not isinstance(active_projects, list):
                active_projects = []
        except Exception as e:
            logger.error(f"Error getting active projects: {e}", exc_info=True)
            active_projects = []
        
        # Get only active employees (not terminated)
        try:
            result = await db.execute(
                select(Employee).where(Employee.status == "active")
            )
            active_employees = result.scalars().all()
        except:
            active_employees = []
        
        # Get recent activities
        try:
            result = await db.execute(
                select(Activity)
                .order_by(desc(Activity.timestamp))
                .limit(20)
            )
            recent_activities = result.scalars().all()
        except:
            recent_activities = []
        
        try:
            if goal_system:
                goals = await goal_system.get_business_goals()
                goals_with_keys = await goal_system.get_business_goals_with_keys()
                goal_progress_raw = await goal_system.evaluate_goals()
            else:
                goals = []
                goals_with_keys = []
                goal_progress_raw = {}
        except Exception as e:
            logger.error(f"Error getting goals: {e}", exc_info=True)
            goals = []
            goals_with_keys = []
            goal_progress_raw = {}
        
        # Map goal_progress to match goals order (for frontend compatibility)
        goal_progress = {}
        for idx, goal_info in enumerate(goals_with_keys):
            goal_key = goal_info["key"]
            goal_progress[goal_key] = goal_progress_raw.get(goal_key, False)
        
        # Get business settings
        try:
            result = await db.execute(select(BusinessSettings))
            business_settings = result.scalars().all()
            settings_dict = {setting.setting_key: setting.setting_value for setting in business_settings}
        except:
            settings_dict = {}
        
        business_name = settings_dict.get("business_name", "TechFlow Solutions")
        business_mission = settings_dict.get("business_mission", "To deliver innovative technology solutions that empower businesses to achieve their goals through cutting-edge software development and consulting services.")
        business_industry = settings_dict.get("business_industry", "Technology & Software Development")
        business_founded = settings_dict.get("business_founded", "2024")
        business_location = settings_dict.get("business_location", "New York")
        
        # Get all projects for company overview
        try:
            result = await db.execute(select(Project).order_by(desc(Project.created_at)))
            all_projects = result.scalars().all()
        except:
            all_projects = []
        
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
        try:
            result = await db.execute(
                select(Employee).where(Employee.role == "CEO", Employee.status == "active")
            )
            ceo = result.scalar_one_or_none()
            ceo_name = ceo.name if ceo else "Not Assigned"
        except:
            ceo_name = "Not Assigned"
        
        # Calculate average project budget
        projects_with_budget = [p for p in all_projects if p.budget and p.budget > 0]
        avg_project_budget = sum(p.budget for p in projects_with_budget) / len(projects_with_budget) if projects_with_budget else 0.0
        
        # Get leadership team (CEO, C-level executives, and Managers)
        leadership_roles = ["CEO", "CTO", "COO", "CFO", "Manager"]
        leadership_employees = [emp for emp in active_employees if emp.role in leadership_roles or (hasattr(emp, 'hierarchy_level') and emp.hierarchy_level <= 2)]
        
        # Get recent leadership decisions
        leadership_employee_ids = [emp.id for emp in leadership_employees]
        leadership_decisions = []
        if leadership_employee_ids:
            try:
                # Get decisions from Decision table
                result = await db.execute(
                    select(Decision)
                    .where(Decision.employee_id.in_(leadership_employee_ids))
                    .order_by(desc(Decision.timestamp))
                    .limit(10)
                )
                decisions = result.scalars().all()
            except:
                decisions = []
            leadership_decisions = [
                {
                    "id": d.id,
                    "employee_id": d.employee_id,
                    "employee_name": next((emp.name for emp in leadership_employees if emp.id == d.employee_id), "Unknown"),
                    "employee_role": next((emp.role for emp in leadership_employees if emp.id == d.employee_id), "Unknown"),
                    "decision_type": d.decision_type,
                    "description": d.description,
                    "reasoning": d.reasoning,
                    "timestamp": (d.timestamp or local_now()).isoformat()
                }
                for d in decisions
            ]
            
            # Also get strategic decisions from Activities table
            try:
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
            except:
                strategic_activities = []
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
                    "timestamp": (act.timestamp or local_now()).isoformat()
                })
            
            # Sort by timestamp descending and limit to 10
            leadership_decisions.sort(key=lambda x: x["timestamp"], reverse=True)
            leadership_decisions = leadership_decisions[:10]
        
        # Get recent leadership activities
        leadership_activities = []
        if leadership_employee_ids:
            try:
                result = await db.execute(
                    select(Activity)
                    .where(Activity.employee_id.in_(leadership_employee_ids))
                    .order_by(desc(Activity.timestamp))
                    .limit(15)
                )
                activities = result.scalars().all()
            except:
                activities = []
            leadership_activities = [
                {
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "employee_name": next((emp.name for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "employee_role": next((emp.role for emp in leadership_employees if emp.id == act.employee_id), "Unknown"),
                    "activity_type": act.activity_type,
                    "description": act.description,
                    "timestamp": (act.timestamp or local_now()).isoformat()
                }
                for act in activities
            ]
        
        # Calculate leadership metrics
        # Get projects with leadership involvement
        leadership_employee_ids_set = set(leadership_employee_ids)
        try:
            result = await db.execute(
                select(Task).where(Task.employee_id.in_(leadership_employee_ids_set))
            )
            leadership_tasks = result.scalars().all()
            projects_with_leadership = set(task.project_id for task in leadership_tasks if task.project_id)
        except:
            projects_with_leadership = set()
        
        # Count strategic decisions (from both Decision table and Activity table)
        strategic_count = 0
        try:
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
        except:
            pass
        
        # Get employee review statistics
        completed_reviews_count = 0
        in_progress_reviews_count = 0
        try:
            # Completed reviews: reviews with all fields filled (comments, strengths, areas_for_improvement)
            # Check for both not None and not empty strings
            from sqlalchemy import and_, or_
            result = await db.execute(
                select(EmployeeReview)
                .where(
                    and_(
                        EmployeeReview.comments.isnot(None),
                        EmployeeReview.comments != '',
                        EmployeeReview.strengths.isnot(None),
                        EmployeeReview.strengths != '',
                        EmployeeReview.areas_for_improvement.isnot(None),
                        EmployeeReview.areas_for_improvement != ''
                    )
                )
            )
            completed_reviews = result.scalars().all()
            completed_reviews_count = len(completed_reviews)
            
            # In progress reviews: reviews that exist but are missing some optional fields
            # Or reviews that have empty strings
            result = await db.execute(
                select(EmployeeReview)
                .where(
                    or_(
                        EmployeeReview.comments.is_(None),
                        EmployeeReview.comments == '',
                        EmployeeReview.strengths.is_(None),
                        EmployeeReview.strengths == '',
                        EmployeeReview.areas_for_improvement.is_(None),
                        EmployeeReview.areas_for_improvement == ''
                    )
                )
            )
            in_progress_reviews = result.scalars().all()
            in_progress_reviews_count = len(in_progress_reviews)
        except:
            pass
        
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
        
        # Get break tracking data
        now = local_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Cache for employee lookups to avoid duplicate queries
        employee_cache = {emp.id: emp for emp in active_employees}
        
        # Helper function to get employee, querying database if needed
        async def get_employee(employee_id: int) -> Optional[Employee]:
            if not employee_id:
                return None
            if employee_id in employee_cache:
                return employee_cache[employee_id]
            # Query database if not in cache
            try:
                result = await db.execute(select(Employee).where(Employee.id == employee_id))
                emp = result.scalar_one_or_none()
                if emp:
                    employee_cache[employee_id] = emp
                    return emp
            except:
                pass
            return None
        
        # Helper function to get employee name
        async def get_employee_name(employee_id: int) -> str:
            emp = await get_employee(employee_id)
            if emp:
                return emp.name
            return f"Employee #{employee_id}" if employee_id else "System"
        
        # Helper function to get default breakroom based on floor
        def get_default_breakroom(floor: int) -> str:
            if floor == 2:
                return "breakroom_floor2"
            elif floor >= 3:
                return "breakroom_floor2"  # Default to floor 2 breakroom
            return "breakroom"
        
        # Get employees currently on break
        employees_on_break = []
        for emp in active_employees:
            if emp.activity_state == "break" or (emp.current_room and "breakroom" in emp.current_room.lower()):
                # Determine if they're actually on break or just passing through
                is_actually_on_break = emp.activity_state == "break"
                
                # Find when they entered the breakroom
                # First, try to find the most recent activity where they entered a breakroom
                breakroom_entry_time = None
                
                # Query for most recent activity that shows them entering breakroom
                # First, try to find activities with breakroom as target_room in metadata
                entry_result = await db.execute(
                    select(Activity)
                    .where(
                        Activity.employee_id == emp.id,
                        or_(
                            Activity.activity_type == "coffee_break",
                            Activity.activity_type == "break"
                        )
                    )
                    .order_by(desc(Activity.timestamp))
                    .limit(10)  # Get recent break activities to check metadata
                )
                entry_activities = entry_result.scalars().all()
                
                # Check each activity to see if it's for a breakroom entry
                for entry_activity in entry_activities:
                    metadata = entry_activity.activity_metadata or {}
                    target_room = metadata.get("target_room", "")
                    description = entry_activity.description or ""
                    
                    # Check if this activity is for entering a breakroom
                    if ("breakroom" in target_room.lower() or 
                        "breakroom" in description.lower() or
                        entry_activity.activity_type in ["coffee_break", "break"]):
                        breakroom_entry_time = entry_activity.timestamp
                        break
                
                # If no entry activity found, use last_coffee_break if available
                if not breakroom_entry_time and emp.last_coffee_break:
                    breakroom_entry_time = emp.last_coffee_break
                
                # If still no time found, query for most recent activity in general (as fallback)
                if not breakroom_entry_time:
                    recent_result = await db.execute(
                        select(Activity)
                        .where(Activity.employee_id == emp.id)
                        .order_by(desc(Activity.timestamp))
                        .limit(1)
                    )
                    recent_activity = recent_result.scalar_one_or_none()
                    if recent_activity:
                        breakroom_entry_time = recent_activity.timestamp
                
                employees_on_break.append({
                    "id": emp.id,
                    "name": emp.name,
                    "title": emp.title,
                    "department": emp.department,
                    "current_room": emp.current_room or emp.home_room or get_default_breakroom(emp.floor or 1),
                    "floor": emp.floor,
                    "activity_state": emp.activity_state,
                    "last_coffee_break": emp.last_coffee_break.isoformat() if emp.last_coffee_break else None,
                    "breakroom_entry_time": breakroom_entry_time.isoformat() if breakroom_entry_time else None,
                    "is_actually_on_break": is_actually_on_break
                })
        
        # Get break activities for today (including break returns)
        result = await db.execute(
            select(Activity)
            .where(
                Activity.activity_type.in_(["coffee_break", "break", "break_returned"]),
                Activity.timestamp >= today_start
            )
            .order_by(desc(Activity.timestamp))
        )
        today_breaks = result.scalars().all()
        
        # Get break returns and break denials (including manager abuse tracking)
        break_returns = []
        manager_abuse_incidents = []
        break_denials = []
        
        # Also query for break_denied activities
        denied_result = await db.execute(
            select(Activity)
            .where(
                Activity.activity_type == "break_denied",
                Activity.timestamp >= today_start
            )
            .order_by(desc(Activity.timestamp))
        )
        denied_breaks = denied_result.scalars().all()
        
        for act in today_breaks:
            if act.activity_type == "break_returned":
                metadata = act.activity_metadata if act.activity_metadata and isinstance(act.activity_metadata, dict) else {}
                is_manager_abuse = metadata.get("is_manager", False) or metadata.get("enforcement_type") == "manager_break_enforcement"
                
                employee_name = await get_employee_name(act.employee_id)
                
                return_data = {
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "employee_name": employee_name,
                    "manager_name": metadata.get("manager_name", "System") if not is_manager_abuse else "System (Manager Abuse)",
                    "manager_id": metadata.get("manager_id") if not is_manager_abuse else None,
                    "description": act.description,
                    "break_duration_minutes": metadata.get("break_duration_minutes", 0),
                    "timestamp": act.timestamp.isoformat() if act.timestamp else None,
                    "is_manager_abuse": is_manager_abuse,
                    "enforcement_type": metadata.get("enforcement_type", "manager_return")
                }
                break_returns.append(return_data)
                
                if is_manager_abuse:
                    manager_abuse_incidents.append(return_data)
        
        for act in denied_breaks:
            metadata = act.activity_metadata if act.activity_metadata and isinstance(act.activity_metadata, dict) else {}
            if metadata.get("is_manager", False):
                employee_name = await get_employee_name(act.employee_id)
                break_denials.append({
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "employee_name": employee_name,
                    "reason": metadata.get("reason", "Break abuse detected"),
                    "timestamp": act.timestamp.isoformat() if act.timestamp else None
                })
        
        # Group breaks by employee for daily time visibility
        employee_break_history = {}
        for break_activity in today_breaks:
            emp_id = break_activity.employee_id
            if not emp_id:
                continue
            
            if emp_id not in employee_break_history:
                employee_name = await get_employee_name(emp_id)
                employee_break_history[emp_id] = {
                    "employee_id": emp_id,
                    "employee_name": employee_name,
                    "breaks": [],
                    "total_break_count": 0,
                    "total_break_time_minutes": 0
                }
            
            # Get break room from metadata, or derive from employee data
            break_room = None
            if break_activity.activity_metadata and isinstance(break_activity.activity_metadata, dict):
                break_room = break_activity.activity_metadata.get("target_room")
            
            # If no room in metadata, try to get from employee's current room or use default
            if not break_room:
                emp = employee_cache.get(emp_id)
                if not emp:
                    emp = await get_employee(emp_id)
                if emp:
                    break_room = emp.current_room or emp.home_room or get_default_breakroom(emp.floor or 1)
                else:
                    break_room = get_default_breakroom(1)
            
            employee_break_history[emp_id]["breaks"].append({
                "id": break_activity.id,
                "timestamp": break_activity.timestamp.isoformat() if break_activity.timestamp else None,
                "description": break_activity.description,
                "room": break_room,
                "break_type": break_activity.activity_metadata.get("break_type", "coffee") if break_activity.activity_metadata and isinstance(break_activity.activity_metadata, dict) else "coffee"
            })
            employee_break_history[emp_id]["total_break_count"] += 1
        
        # Sort breaks by timestamp (most recent first) for each employee
        for emp_id in employee_break_history:
            employee_break_history[emp_id]["breaks"].sort(key=lambda x: x["timestamp"] or "", reverse=True)
        
        # Convert to list for frontend
        break_history_list = list(employee_break_history.values())
        
        return {
            "business_name": business_name,
            "revenue": revenue or 0.0,
            "profit": profit or 0.0,
            "expenses": expenses or 0.0,
            "active_projects": len(active_projects) if isinstance(active_projects, list) else (active_projects if isinstance(active_projects, int) else 0),
            "employee_count": len(active_employees),
            "recent_activities": [
                {
                    "id": act.id,
                    "employee_id": act.employee_id,
                    "activity_type": act.activity_type,
                    "description": act.description,
                    "timestamp": (act.timestamp or local_now()).isoformat()
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
                "active_projects_count": len(active_projects) if isinstance(active_projects, list) else (active_projects if isinstance(active_projects, int) else 0),
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
            },
            # Break tracking data
            "break_tracking": {
                "employees_on_break": employees_on_break,
                "break_history": break_history_list,
                "break_returns": break_returns,
                "manager_abuse_incidents": manager_abuse_incidents,
                "break_denials": break_denials,
                "total_on_break": len(employees_on_break),
                "total_breaks_today": len([b for b in today_breaks if b.activity_type in ["coffee_break", "break"]]),
                "total_returns_today": len(break_returns),
                "total_manager_abuse_today": len(manager_abuse_incidents),
                "total_break_denials_today": len(break_denials)
            }
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in _fetch_dashboard_data: {e}")
        print(error_details)
        # Return default values on any error
        return {
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
    cutoff = local_now() - timedelta(days=days)
    
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
    cutoff = local_now() - timedelta(days=days)
    
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
        date_key = fin.timestamp.date().isoformat() if fin.timestamp else local_now().date().isoformat()
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

@router.get("/employees/{employee_id}/meetings")
async def get_employee_meetings(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get all meetings for a specific employee (as organizer or attendee)."""
    try:
        from database.models import Meeting
        from sqlalchemy import or_
        
        # Get all meetings where employee is organizer or attendee
        # For JSONB arrays in PostgreSQL, we need to check if the array contains the employee_id
        # First get all meetings, then filter in Python since JSONB array contains is complex
        result = await db.execute(
            select(Meeting)
            .order_by(Meeting.start_time)
        )
        all_meetings = result.scalars().all()
        
        # Filter meetings where employee is organizer or in attendee_ids
        meetings = []
        for meeting in all_meetings:
            # Check if employee is organizer
            if meeting.organizer_id == employee_id:
                meetings.append(meeting)
            # Check if employee is in attendee_ids (handle both int and string IDs)
            elif meeting.attendee_ids:
                # Convert attendee_ids to a set of integers for comparison
                attendee_ids_set = set()
                for aid in meeting.attendee_ids:
                    if isinstance(aid, int):
                        attendee_ids_set.add(aid)
                    elif isinstance(aid, str) and aid.isdigit():
                        attendee_ids_set.add(int(aid))
                    elif isinstance(aid, (int, float)):
                        attendee_ids_set.add(int(aid))
                
                if employee_id in attendee_ids_set:
                    meetings.append(meeting)
        
        # Debug logging
        if len(meetings) > 0:
            print(f"Found {len(meetings)} meetings for employee {employee_id}")
        else:
            print(f"No meetings found for employee {employee_id} (checked {len(all_meetings)} total meetings)")
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        meeting_list = []
        for meeting in meetings:
            # Get attendee names
            attendee_names = [all_employees.get(aid, "Unknown") for aid in (meeting.attendee_ids or [])]
            
            meeting_list.append({
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "organizer_id": meeting.organizer_id,
                "organizer_name": all_employees.get(meeting.organizer_id, "Unknown"),
                "attendee_ids": meeting.attendee_ids or [],
                "attendee_names": attendee_names,
                "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                "status": meeting.status,
                "agenda": meeting.agenda,
                "outline": meeting.outline,
                "transcript": meeting.transcript,
                "live_transcript": meeting.live_transcript,
                "meeting_metadata": meeting.meeting_metadata or {},
                "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None
            })
        
        return meeting_list
    except Exception as e:
        print(f"Error fetching employee meetings for employee {employee_id}: {e}")
        import traceback
        traceback.print_exc()
        return []

@router.get("/employees/{employee_id}/training")
async def get_employee_training(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get training summary and history for a specific employee."""
    try:
        from business.training_manager import TrainingManager
        
        # Verify employee exists
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = result.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        training_manager = TrainingManager()
        summary = await training_manager.get_employee_training_summary(employee_id, db)
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching employee training: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching employee training: {str(e)}")

@router.get("/training/sessions")
async def get_all_training_sessions(
    limit: int = 50,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all training sessions with optional filtering."""
    try:
        query = select(TrainingSession).options(selectinload(TrainingSession.employee))
        
        if status:
            query = query.where(TrainingSession.status == status)
        
        query = query.order_by(desc(TrainingSession.start_time)).limit(limit)
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        return [
            {
                "id": s.id,
                "employee_id": s.employee_id,
                "employee_name": s.employee.name if s.employee else "Unknown",
                "training_room": s.training_room,
                "training_topic": s.training_topic,
                "training_material_id": s.training_material_id,
                "duration_minutes": s.duration_minutes,
                "status": s.status,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
            }
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Error fetching training sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching training sessions: {str(e)}")

@router.get("/training/overview")
async def get_training_overview(db: AsyncSession = Depends(get_db)):
    """Get overall training statistics and overview."""
    try:
        # Check if it's work hours (7am-7pm Monday-Friday)
        # Employees are only at the office during work hours
        is_work_time = is_work_hours()
        
        # Get total sessions
        total_sessions_result = await db.execute(
            select(func.count(TrainingSession.id))
            .where(TrainingSession.status == "completed")
        )
        total_sessions = total_sessions_result.scalar_one() or 0
        
        # Get total training time
        total_time_result = await db.execute(
            select(func.sum(TrainingSession.duration_minutes))
            .where(TrainingSession.status == "completed")
        )
        total_minutes = total_time_result.scalar_one() or 0
        
        # Get active sessions - only count during work hours
        # During non-work hours, employees are at home, so no active training sessions
        if is_work_time:
            active_sessions_result = await db.execute(
                select(func.count(TrainingSession.id))
                .where(TrainingSession.status == "in_progress")
            )
            active_sessions = active_sessions_result.scalar_one() or 0
        else:
            active_sessions = 0
        
        # Get unique employees trained
        unique_employees_result = await db.execute(
            select(func.count(func.distinct(TrainingSession.employee_id)))
            .where(TrainingSession.status == "completed")
        )
        unique_employees = unique_employees_result.scalar_one() or 0
        
        # Get top training topics
        top_topics_result = await db.execute(
            select(
                TrainingSession.training_topic,
                func.count(TrainingSession.id).label('count')
            )
            .where(TrainingSession.status == "completed")
            .group_by(TrainingSession.training_topic)
            .order_by(desc('count'))
            .limit(10)
        )
        top_topics = [
            {"topic": row.training_topic, "count": row.count}
            for row in top_topics_result.all()
        ]
        
        # Get employees currently in training - only during work hours
        # During non-work hours (7pm-7am or weekends), employees are at home
        if is_work_time:
            current_training_result = await db.execute(
                select(TrainingSession, Employee)
                .join(Employee, TrainingSession.employee_id == Employee.id)
                .where(TrainingSession.status == "in_progress")
            )
            current_training = [
                {
                    "employee_id": s.employee_id,
                    "employee_name": emp.name,
                    "topic": s.training_topic,
                    "room": s.training_room,
                    "training_material_id": s.training_material_id,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                }
                for s, emp in current_training_result.all()
            ]
        else:
            # Outside work hours - employees are at home, no training sessions
            current_training = []
        
        return {
            "total_sessions": total_sessions,
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 1),
            "active_sessions": active_sessions,
            "unique_employees_trained": unique_employees,
            "top_topics": top_topics,
            "current_training": current_training,
        }
    except Exception as e:
        logger.error(f"Error fetching training overview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching training overview: {str(e)}")

@router.get("/training/materials")
async def get_training_materials(
    topic: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get training materials with optional filtering."""
    try:
        query = select(TrainingMaterial)
        
        if topic:
            query = query.where(TrainingMaterial.topic.ilike(f"%{topic}%"))
        if department:
            query = query.where(TrainingMaterial.department == department)
        
        query = query.order_by(desc(TrainingMaterial.usage_count)).limit(limit)
        
        result = await db.execute(query)
        materials = result.scalars().all()
        
        return [
            {
                "id": m.id,
                "title": m.title,
                "topic": m.topic,
                "description": m.description,
                "difficulty_level": m.difficulty_level,
                "estimated_duration_minutes": m.estimated_duration_minutes,
                "department": m.department,
                "usage_count": m.usage_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in materials
        ]
    except Exception as e:
        logger.error(f"Error fetching training materials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching training materials: {str(e)}")

@router.get("/training/materials/{material_id}")
async def get_training_material(material_id: int, db: AsyncSession = Depends(get_db)):
    """Get full training material content by ID."""
    try:
        result = await db.execute(
            select(TrainingMaterial).where(TrainingMaterial.id == material_id)
        )
        material = result.scalar_one_or_none()
        
        if not material:
            raise HTTPException(status_code=404, detail="Training material not found")
        
        return {
            "id": material.id,
            "title": material.title,
            "topic": material.topic,
            "content": material.content,
            "description": material.description,
            "difficulty_level": material.difficulty_level,
            "estimated_duration_minutes": material.estimated_duration_minutes,
            "department": material.department,
            "usage_count": material.usage_count,
            "created_at": material.created_at.isoformat() if material.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching training material: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching training material: {str(e)}")

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
        try:
            result = await db.execute(select(Employee))
            all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        except Exception as e:
            print(f"Error fetching employees for chats: {e}")
            all_employees = {}
        
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
        
        # Always generate a reply when manager sends a message
        # The manager is sending TO the employee, so the employee should respond
        # This ensures proper back-and-forth: Manager -> Employee -> Manager -> Employee
        
        # Save the user's message
        user_chat = ChatMessage(
            sender_id=None,  # None represents messages from the user/manager
            recipient_id=request.employee_id,
            message=request.message,
            thread_id=thread_id
        )
        db.add(user_chat)
        await db.flush()  # Flush to get the timestamp
        
        # Always generate a reply - manager sends to employee, employee responds
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

@router.post("/chats/check-and-respond")
async def trigger_message_response_check(db: AsyncSession = Depends(get_db)):
    """Manually trigger message response check for all employees (for testing)."""
    try:
        from employees.roles import create_employee_agent
        from engine.office_simulator import get_business_context
        from sqlalchemy import select
        
        # Get all active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employees = result.scalars().all()
        
        if not employees:
            return {
                "success": True,
                "message": "No active employees to check messages for",
                "employees_processed": 0,
                "responses_sent": 0
            }
        
        # Get business context
        business_context = await get_business_context(db)
        
        # Import OllamaClient
        from llm.ollama_client import OllamaClient
        llm_client = OllamaClient()
        
        responses_count = 0
        errors = []
        
        for employee in employees:
            try:
                # Create employee agent
                agent = create_employee_agent(employee, db, llm_client)
                
                # Check and respond to messages
                await agent._check_and_respond_to_messages(business_context)
                
                responses_count += 1
            except Exception as e:
                error_msg = f"Error checking messages for {employee.name} (ID: {employee.id}): {str(e)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
                import traceback
                traceback.print_exc()
                continue
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Message response check completed for {responses_count} employee(s)",
            "employees_processed": responses_count,
            "total_employees": len(employees),
            "errors": errors if errors else None
        }
    except Exception as e:
        await db.rollback()
        print(f"❌ Error in message response check endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error checking messages: {str(e)}")

@router.post("/employees/fix-walking")
async def fix_walking_employees(db: AsyncSession = Depends(get_db)):
    """Fix all employees stuck in walking state without destinations."""
    try:
        from engine.movement_system import fix_walking_employees_without_destination
        fixed_count = await fix_walking_employees_without_destination(db)
        await db.commit()
        return {
            "success": True,
            "fixed_count": fixed_count,
            "message": f"Fixed {fixed_count} employees walking without destinations"
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error fixing walking employees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fixing walking employees: {str(e)}")

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
                        time_since_hire = local_now() - hired_at_naive
                        if time_since_hire > timedelta(hours=1):
                            employee.activity_state = "working"
                            if employee.home_room:
                                await update_employee_location(employee, employee.home_room, "working", db)
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
                        
                        time_since_hire = local_now() - hired_at_naive
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

@router.post("/employees/fix-idle")
async def fix_idle_employees(db: AsyncSession = Depends(get_db)):
    """IMMEDIATELY fix ALL employees stuck in idle state - they should be working!"""
    try:
        # Get ALL idle employees
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.activity_state == "idle"
            )
        )
        idle_employees = result.scalars().all()
        
        if not idle_employees:
            return {
                "message": "No idle employees found",
                "details": {
                    "total_fixed": 0,
                    "total_idle": 0
                }
            }
        
        fixed_count = 0
        
        # Fix ALL idle employees immediately
        for employee in idle_employees:
            try:
                # Set them to working - they should NEVER be idle
                employee.activity_state = "working"
                fixed_count += 1
            except Exception as e:
                print(f"Error fixing idle employee {getattr(employee, 'name', 'unknown')}: {e}")
                continue
        
        await db.commit()
        
        return {
            "message": f"Fixed {fixed_count} idle employees - they are now working!",
            "details": {
                "total_fixed": fixed_count,
                "total_idle": 0
            }
        }
    except Exception as e:
        await db.rollback()
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error in fix_idle_employees: {e}")
        print(error_msg)
        raise HTTPException(status_code=500, detail=f"Error fixing idle employees: {str(e)}")

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
                "capacity": 15,  # Updated to support birthday parties (15 people)
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
                "capacity": 15,  # Updated to support birthday parties (15 people)
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
        recent_cutoff = local_now() - timedelta(hours=2)
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
        
        # Check if it's work hours - employees should only be at office during work hours
        from config import is_work_hours
        is_work_time = is_work_hours()
        
        # Group active employees by floor and room (only include those with a room assigned)
        employees_by_room = {}
        active_with_rooms = []
        for employee in active_employees:
            # During non-work hours, employees should be at home, not in the office
            if not is_work_time:
                continue  # Skip this employee - they should be at home
            
            # Safely get room fields (they might not exist in old database)
            current_room = getattr(employee, 'current_room', None)
            home_room = getattr(employee, 'home_room', None)
            target_room = getattr(employee, 'target_room', None)
            activity_state = getattr(employee, 'activity_state', 'working')
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
                    "target_room": target_room,
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
                    target_room = getattr(employee, 'target_room', None)
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
                                    "target_room": target_room,
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
                    target_room = getattr(employee, 'target_room', None)
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
                                    "target_room": target_room,
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

class RoomConversationRequest(BaseModel):
    room_id: str
    employee_ids: List[int]

@router.post("/room/conversations")
async def generate_room_conversations(
    request: RoomConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate casual conversations between employees in a room."""
    try:
        # Get employees
        result = await db.execute(
            select(Employee).where(Employee.id.in_(request.employee_ids))
        )
        employees = result.scalars().all()
        
        if len(employees) < 2:
            return {"conversations": []}
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(db)
        
        # Select 1-2 pairs randomly (not everyone talking at once)
        import random
        num_pairs = min(2, len(employees) // 2)
        selected_pairs = []
        available_employees = employees.copy()
        
        for _ in range(num_pairs):
            if len(available_employees) < 2:
                break
            pair = random.sample(available_employees, 2)
            selected_pairs.append(pair)
            # Remove selected employees from available pool
            for emp in pair:
                available_employees.remove(emp)
        
        # Generate conversations for each pair
        from llm.ollama_client import OllamaClient
        llm_client = OllamaClient()
        conversations = []
        
        for pair in selected_pairs:
            emp1, emp2 = pair
            
            # Randomly choose conversation type
            conversation_type = random.choice(["work", "personal", "mixed"])
            
            # Generate conversation
            conversation_data = await llm_client.generate_casual_conversation(
                employee1_name=emp1.name,
                employee1_title=emp1.title,
                employee1_role=emp1.role,
                employee1_personality=emp1.personality_traits or [],
                employee2_name=emp2.name,
                employee2_title=emp2.title,
                employee2_role=emp2.role,
                employee2_personality=emp2.personality_traits or [],
                business_context=business_context,
                conversation_type=conversation_type
            )
            
            conversations.append({
                "employee1_id": emp1.id,
                "employee1_name": emp1.name,
                "employee2_id": emp2.id,
                "employee2_name": emp2.name,
                "messages": conversation_data.get("messages", [])
            })
        
        return {"conversations": conversations}
    except Exception as e:
        print(f"Error generating room conversations: {e}")
        import traceback
        traceback.print_exc()
        return {"conversations": []}

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
async def get_notifications(
    limit: int = 50, 
    offset: int = 0,
    unread_only: bool = False, 
    db: AsyncSession = Depends(get_db)
):
    """Get all notifications, optionally filtered to unread only. Supports pagination."""
    try:
        # Cap limit at 250 total (5 pages of 50)
        max_limit = 250
        if limit > max_limit:
            limit = max_limit
        
        query = select(Notification).order_by(desc(Notification.created_at))
        
        if unread_only:
            query = query.where(Notification.read == False)
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        # Get total count for pagination info
        count_query = select(func.count(Notification.id))
        if unread_only:
            count_query = count_query.where(Notification.read == False)
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
    except Exception as e:
        import traceback
        print(f"Error in get_notifications: {e}")
        print(traceback.format_exc())
        notifications = []
        total_count = 0
    
    # Get employee names
    try:
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    except Exception as e:
        print(f"Error fetching employees for notifications: {e}")
        all_employees = {}
    
    return {
        "notifications": [
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
        ],
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < min(total_count, max_limit)
    }

@router.get("/notifications/unread-count")
async def get_unread_notification_count(db: AsyncSession = Depends(get_db)):
    """Get count of unread notifications."""
    try:
        result = await db.execute(
            select(func.count(Notification.id)).where(Notification.read == False)
        )
        count = result.scalar() or 0
        return {"count": count}
    except Exception as e:
        import traceback
        print(f"Error in get_unread_notification_count: {e}")
        print(traceback.format_exc())
        return {"count": 0}

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

@router.get("/customer-reviews")
async def get_customer_reviews(limit: int = 1000, project_id: int = None, db: AsyncSession = Depends(get_db)):
    """Get customer reviews, optionally filtered by project."""
    from business.customer_review_manager import CustomerReviewManager
    
    review_manager = CustomerReviewManager(db)
    
    if project_id:
        reviews = await review_manager.get_reviews_for_project(project_id)
    else:
        reviews = await review_manager.get_all_reviews(limit=limit)
    
    # Get project names
    result = await db.execute(select(Project))
    projects = {p.id: p.name for p in result.scalars().all()}
    
    return [
        {
            "id": review.id,
            "project_id": review.project_id,
            "project_name": projects.get(review.project_id, "Unknown Project"),
            "customer_name": review.customer_name,
            "customer_title": review.customer_title,
            "company_name": review.company_name,
            "rating": review.rating,
            "review_text": review.review_text,
            "verified_purchase": review.verified_purchase,
            "helpful_count": review.helpful_count,
            "created_at": review.created_at.isoformat() if review.created_at else None
        }
        for review in reviews
    ]

@router.post("/customer-reviews/generate")
async def generate_customer_reviews(hours_since_completion: float = 24.0, db: AsyncSession = Depends(get_db)):
    """Generate customer reviews for completed projects."""
    from business.customer_review_manager import CustomerReviewManager
    
    try:
        review_manager = CustomerReviewManager(db)
        reviews_created = await review_manager.generate_reviews_for_completed_projects(
            hours_since_completion=hours_since_completion
        )
        
        return {
            "success": True,
            "message": f"Generated {len(reviews_created)} customer review(s)",
            "reviews_created": len(reviews_created)
        }
    except Exception as e:
        import traceback
        print(f"Error generating customer reviews: {e}")
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "reviews_created": 0
        }

@router.get("/customer-reviews/stats")
async def get_customer_review_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about customer reviews."""
    # Get all reviews
    result = await db.execute(select(CustomerReview))
    all_reviews = result.scalars().all()
    
    if not all_reviews:
        return {
            "total_reviews": 0,
            "average_rating": 0.0,
            "rating_distribution": {},
            "reviews_by_project": {}
        }
    
    # Calculate average rating
    total_rating = sum(r.rating for r in all_reviews)
    average_rating = round(total_rating / len(all_reviews), 1)
    
    # Rating distribution
    rating_distribution = {}
    for review in all_reviews:
        rating_key = f"{int(review.rating)} stars"
        rating_distribution[rating_key] = rating_distribution.get(rating_key, 0) + 1
    
    # Reviews by project (for backwards compatibility with frontend)
    result = await db.execute(select(Project))
    projects = {p.id: p.name for p in result.scalars().all()}
    
    reviews_by_project = {}
    verified_purchases = 0
    
    for review in all_reviews:
        # Count verified purchases
        if review.verified_purchase:
            verified_purchases += 1
        
        # Group by project (for backwards compatibility)
        if review.project_id and review.project_id in projects:
            project_name = projects[review.project_id]
            if project_name not in reviews_by_project:
                reviews_by_project[project_name] = {
                    "count": 0,
                    "average_rating": 0.0,
                    "total_rating": 0.0
                }
            reviews_by_project[project_name]["count"] += 1
            reviews_by_project[project_name]["total_rating"] += review.rating
    
    # Calculate averages for projects
    for project_name in reviews_by_project:
        data = reviews_by_project[project_name]
        data["average_rating"] = round(data["total_rating"] / data["count"], 1)
        del data["total_rating"]
    
    # Reviews by product (only real products)
    result = await db.execute(select(Product))
    products = {p.id: p.name for p in result.scalars().all()}
    
    reviews_by_product = {}
    
    for review in all_reviews:
        # Group by product (only if review is linked to a real product)
        if review.product_id and review.product_id in products:
            product_name = products[review.product_id]
            if product_name not in reviews_by_product:
                reviews_by_product[product_name] = {
                    "count": 0,
                    "average_rating": 0.0,
                    "total_rating": 0.0
                }
            reviews_by_product[product_name]["count"] += 1
            reviews_by_product[product_name]["total_rating"] += review.rating
    
    # Calculate averages for products
    for product_name in reviews_by_product:
        data = reviews_by_product[product_name]
        data["average_rating"] = round(data["total_rating"] / data["count"], 1)
        del data["total_rating"]
    
    return {
        "total_reviews": len(all_reviews),
        "average_rating": average_rating,
        "verified_purchases": verified_purchases,
        "products_reviewed": len(reviews_by_product),
        "reviews_by_product": reviews_by_product,
        "rating_distribution": rating_distribution,
        "reviews_by_project": reviews_by_project
    }

@router.get("/meetings")
async def get_meetings(db: AsyncSession = Depends(get_db)):
    """Get all meetings."""
    try:
        result = await db.execute(
            select(Meeting)
            .order_by(Meeting.start_time)
        )
        meetings = result.scalars().all()
        
        # Get employee names
        result = await db.execute(select(Employee))
        all_employees = {emp.id: emp.name for emp in result.scalars().all()}
        
        meeting_list = []
        for meeting in meetings:
            # Get attendee names
            attendee_names = [all_employees.get(aid, "Unknown") for aid in (meeting.attendee_ids or [])]
            
            meeting_list.append({
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "organizer_id": meeting.organizer_id,
                "organizer_name": all_employees.get(meeting.organizer_id, "Unknown"),
                "attendee_ids": meeting.attendee_ids or [],
                "attendee_names": attendee_names,
                "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                "status": meeting.status,
                "agenda": meeting.agenda,
                "outline": meeting.outline,
                "transcript": meeting.transcript,
                "live_transcript": meeting.live_transcript,
                "meeting_metadata": meeting.meeting_metadata or {},
                "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None
            })
        
        return meeting_list
    except Exception as e:
        print(f"Error fetching meetings: {e}")
        return []

@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific meeting by ID."""
    try:
        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = result.scalar_one_or_none()
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Optimized: Get all attendees in a single query instead of N+1 queries
        attendee_ids_list = meeting.attendee_ids or []
        
        # Get all employees in one query (organizer + attendees)
        all_employee_ids = [meeting.organizer_id] + attendee_ids_list
        all_employee_ids = list(set(all_employee_ids))  # Remove duplicates
        
        if all_employee_ids:
            result = await db.execute(
                select(Employee).where(Employee.id.in_(all_employee_ids))
            )
            employees_dict = {emp.id: emp for emp in result.scalars().all()}
        else:
            employees_dict = {}
        
        # Get organizer name
        organizer = employees_dict.get(meeting.organizer_id)
        organizer_name = organizer.name if organizer else "Unknown"
        
        # Get attendee details - ensure we get ALL attendees
        attendee_details = []
        for aid in attendee_ids_list:
            emp = employees_dict.get(aid)
            if emp:
                attendee_details.append({
                    "id": emp.id,
                    "name": emp.name,
                    "title": emp.title,
                    "role": emp.role,
                    "department": emp.department,
                    "avatar_path": emp.avatar_path
                })
        
        # Ensure we have all attendees - if any are missing, log it
        if len(attendee_details) < len(attendee_ids_list):
            missing_ids = set(attendee_ids_list) - set([a["id"] for a in attendee_details])
            print(f"⚠️ Warning: Missing {len(missing_ids)} attendees for meeting {meeting.id}: {missing_ids}")
        
        return {
            "id": meeting.id,
            "title": meeting.title,
            "description": meeting.description,
            "organizer_id": meeting.organizer_id,
            "organizer_name": organizer_name,
            "attendee_ids": meeting.attendee_ids or [],
            "attendees": attendee_details,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
            "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
            "status": meeting.status,
            "agenda": meeting.agenda,
            "outline": meeting.outline,
            "transcript": meeting.transcript,
            "live_transcript": meeting.live_transcript,
            "meeting_metadata": meeting.meeting_metadata or {},
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/meetings/generate")
async def generate_meetings(db: AsyncSession = Depends(get_db)):
    """Generate new meetings for the day."""
    try:
        from business.meeting_manager import MeetingManager
        manager = MeetingManager(db)
        meetings_created = await manager.generate_meetings()
        await db.commit()
        # Invalidate dashboard cache since meetings affect dashboard
        await invalidate_cache("_fetch_dashboard_data")
        return {
            "success": True,
            "message": f"Generated {meetings_created} meetings",
            "meetings_created": meetings_created
        }
    except Exception as e:
        print(f"Error generating meetings: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "meetings_created": 0
        }

@router.post("/meetings/generate-now")
async def generate_meetings_now(db: AsyncSession = Depends(get_db)):
    """Generate meetings for last week, today, and an in-progress meeting."""
    try:
        from business.meeting_manager import MeetingManager
        from database.models import Meeting
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        meeting_manager = MeetingManager(db)
        now = local_now()
        
        # Generate meetings for last week (7 days ago to today)
        last_week_start = now - timedelta(days=7)
        last_week_start = last_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Check existing meetings in this range
        result = await db.execute(
            select(Meeting).where(
                Meeting.start_time >= last_week_start,
                Meeting.start_time < tomorrow_start
            )
        )
        existing_meetings = result.scalars().all()
        
        # Generate meetings for last week
        past_meetings = await meeting_manager.generate_meetings_for_date_range(
            last_week_start, today_start
        )
        
        # Generate meetings for today
        today_meetings = await meeting_manager.generate_meetings()
        
        # Always generate an in-progress meeting if one doesn't exist
        result = await db.execute(
            select(Meeting).where(Meeting.status == "in_progress")
        )
        in_progress_meetings = result.scalars().all()
        
        in_progress_created = 0
        if len(in_progress_meetings) == 0:
            in_progress_meeting = await meeting_manager.generate_in_progress_meeting()
            if in_progress_meeting:
                in_progress_created = 1
        
        return {
            "success": True,
            "message": "Generated meetings successfully",
            "past_meetings": past_meetings,
            "today_meetings": today_meetings,
            "in_progress_created": in_progress_created,
            "total_existing": len(existing_meetings)
        }
    except Exception as e:
        print(f"Error generating meetings: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "past_meetings": 0,
            "today_meetings": 0,
            "in_progress_created": 0
        }

@router.post("/meetings/generate-yesterday")
async def generate_meetings_yesterday(db: AsyncSession = Depends(get_db)):
    """Generate meetings specifically for yesterday if they don't exist."""
    try:
        from business.meeting_manager import MeetingManager
        from database.models import Meeting
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        meeting_manager = MeetingManager(db)
        now = local_now()
        
        # Calculate yesterday's date range
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start + timedelta(days=1)
        
        # Check if meetings already exist for yesterday
        result = await db.execute(
            select(Meeting).where(
                Meeting.start_time >= yesterday_start,
                Meeting.start_time < yesterday_end
            )
        )
        existing_meetings = result.scalars().all()
        
        if len(existing_meetings) > 0:
            return {
                "success": True,
                "message": f"Yesterday already has {len(existing_meetings)} meetings",
                "meetings_created": 0,
                "existing_count": len(existing_meetings)
            }
        
        # Generate meetings for yesterday
        meetings_created = await meeting_manager.generate_meetings_for_date_range(
            yesterday_start, yesterday_end
        )
        
        return {
            "success": True,
            "message": f"Generated {meetings_created} meetings for yesterday",
            "meetings_created": meetings_created,
            "date": yesterday_start.strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Error generating meetings for yesterday: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "meetings_created": 0
        }

@router.post("/meetings/schedule-in-15min")
async def schedule_meeting_in_15min(db: AsyncSession = Depends(get_db)):
    """Schedule a meeting to start in 15 minutes."""
    try:
        from business.meeting_manager import MeetingManager
        from database.models import Meeting, Employee
        from sqlalchemy import select
        from datetime import datetime, timedelta
        import random
        import json
        
        meeting_manager = MeetingManager(db)
        now = local_now()
        
        # Meeting starts in 15 minutes
        start_time = now + timedelta(minutes=15)
        # Meeting lasts 30-60 minutes
        duration = random.randint(30, 60)
        end_time = start_time + timedelta(minutes=duration)
        
        # Get all active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) < 2:
            return {
                "success": False,
                "message": "Not enough employees to create a meeting",
                "meeting_id": None
            }
        
        # Randomly select an organizer and 1-3 attendees
        organizer = random.choice(all_employees)
        available = [e for e in all_employees if e.id != organizer.id]
        num_attendees = random.randint(1, min(3, len(available)))
        attendees = random.sample(available, num_attendees)
        attendees.append(organizer)  # Organizer is also an attendee
        
        # Determine meeting type and description
        meeting_types = ["Team Sync", "Project Review", "Strategy Discussion", "Status Update", "Planning Session"]
        meeting_type = random.choice(meeting_types)
        
        meeting_descriptions = {
            "Team Sync": "Weekly team synchronization and updates",
            "Project Review": "Review project progress and milestones",
            "Strategy Discussion": "Strategic planning and decision-making",
            "Status Update": "Team status updates and coordination",
            "Planning Session": "Planning upcoming tasks and priorities"
        }
        meeting_description = meeting_descriptions.get(meeting_type, "General discussion")
        
        attendee_ids = [e.id for e in attendees]
        
        # Generate meeting title
        title = f"{meeting_type}: {organizer.department or 'General'}"
        
        # Get business context for agenda generation
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(db)
        
        # Generate agenda and outline using LLM
        agenda, outline = await meeting_manager._generate_meeting_agenda(
            meeting_type, meeting_description, organizer, attendees, business_context
        )
        
        # Ensure agenda and outline are strings
        if isinstance(agenda, (list, dict)):
            agenda = json.dumps(agenda) if isinstance(agenda, dict) else "\n".join(str(item) for item in agenda)
        if isinstance(outline, (list, dict)):
            outline = json.dumps(outline) if isinstance(outline, dict) else "\n".join(str(item) for item in outline)
        
        # Create meeting
        meeting = Meeting(
            title=title,
            description=meeting_description,
            organizer_id=organizer.id,
            attendee_ids=attendee_ids,
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
            agenda=str(agenda) if agenda else None,
            outline=str(outline) if outline else None,
            meeting_metadata={}
        )
        
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)
        
        return {
            "success": True,
            "message": f"Meeting scheduled for {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "meeting_id": meeting.id,
            "title": meeting.title,
            "start_time": meeting.start_time.isoformat(),
            "end_time": meeting.end_time.isoformat()
        }
    except Exception as e:
        print(f"Error scheduling meeting: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "meeting_id": None
        }

@router.post("/meetings/schedule-in-1min")
async def schedule_meeting_in_1min(db: AsyncSession = Depends(get_db)):
    """Schedule a meeting to start in 1 minute and last 5 minutes."""
    try:
        from business.meeting_manager import MeetingManager
        from database.models import Meeting, Employee
        from sqlalchemy import select
        from datetime import datetime, timedelta
        import random
        import json
        
        meeting_manager = MeetingManager(db)
        now = local_now()
        
        # Meeting starts in 10 seconds (to ensure it starts before the 5-minute window)
        start_time = now + timedelta(seconds=10)
        # Meeting lasts 5 minutes
        end_time = start_time + timedelta(minutes=5)
        
        # Get all active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        if len(all_employees) < 2:
            return {
                "success": False,
                "message": "Not enough employees to create a meeting",
                "meeting_id": None
            }
        
        # Randomly select an organizer and 1-3 attendees
        organizer = random.choice(all_employees)
        available = [e for e in all_employees if e.id != organizer.id]
        num_attendees = random.randint(1, min(3, len(available)))
        attendees = random.sample(available, num_attendees)
        attendees.append(organizer)  # Organizer is also an attendee
        
        # Determine meeting type and description
        meeting_types = ["Team Sync", "Project Review", "Strategy Discussion", "Status Update", "Planning Session"]
        meeting_type = random.choice(meeting_types)
        
        meeting_descriptions = {
            "Team Sync": "Weekly team synchronization and updates",
            "Project Review": "Review project progress and milestones",
            "Strategy Discussion": "Strategic planning and decision-making",
            "Status Update": "Team status updates and coordination",
            "Planning Session": "Planning upcoming tasks and priorities"
        }
        meeting_description = meeting_descriptions.get(meeting_type, "General discussion")
        
        attendee_ids = [e.id for e in attendees]
        
        # Generate meeting title
        title = f"{meeting_type}: {organizer.department or 'General'}"
        
        # Get business context for agenda generation
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(db)
        
        # Generate agenda and outline using LLM
        agenda, outline = await meeting_manager._generate_meeting_agenda(
            meeting_type, meeting_description, organizer, attendees, business_context
        )
        
        # Ensure agenda and outline are strings
        if isinstance(agenda, (list, dict)):
            agenda = json.dumps(agenda) if isinstance(agenda, dict) else "\n".join(str(item) for item in agenda)
        if isinstance(outline, (list, dict)):
            outline = json.dumps(outline) if isinstance(outline, dict) else "\n".join(str(item) for item in outline)
        
        # Create meeting
        meeting = Meeting(
            title=title,
            description=meeting_description,
            organizer_id=organizer.id,
            attendee_ids=attendee_ids,
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
            agenda=str(agenda) if agenda else None,
            outline=str(outline) if outline else None,
            meeting_metadata={}
        )
        
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)
        
        return {
            "success": True,
            "message": f"Meeting scheduled for {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC (5 minutes duration)",
            "meeting_id": meeting.id,
            "title": meeting.title,
            "start_time": meeting.start_time.isoformat(),
            "end_time": meeting.end_time.isoformat()
        }
    except Exception as e:
        print(f"Error scheduling meeting: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "meeting_id": None
        }

@router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a meeting by ID."""
    try:
        from database.models import Meeting
        from sqlalchemy import select
        
        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = result.scalar_one_or_none()
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        await db.delete(meeting)
        await db.commit()
        
        # Invalidate dashboard cache since meetings affect dashboard
        await invalidate_cache("_fetch_dashboard_data")
        
        return {
            "success": True,
            "message": f"Meeting {meeting_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting meeting: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/meetings/update-status")
async def update_meeting_status_endpoint(db: AsyncSession = Depends(get_db)):
    """Manually trigger meeting status update (scheduled -> in_progress -> completed)."""
    try:
        from business.meeting_manager import MeetingManager
        
        meeting_manager = MeetingManager(db)
        await meeting_manager.update_meeting_status()
        
        return {
            "success": True,
            "message": "Meeting statuses updated successfully"
        }
    except Exception as e:
        print(f"Error updating meeting status: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

@router.post("/meetings/cleanup-missed")
async def cleanup_missed_meetings(db: AsyncSession = Depends(get_db)):
    """Delete meetings that are scheduled but have passed their end time."""
    try:
        from database.models import Meeting
        from sqlalchemy import select
        from datetime import datetime
        
        now = local_now()
        
        # Find meetings that are scheduled but have passed their end time
        result = await db.execute(
            select(Meeting).where(
                Meeting.status == "scheduled",
                Meeting.end_time < now
            )
        )
        missed_meetings = result.scalars().all()
        
        deleted_count = 0
        for meeting in missed_meetings:
            await db.delete(meeting)
            deleted_count += 1
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} missed meeting(s)",
            "deleted_count": deleted_count
        }
    except Exception as e:
        print(f"Error cleaning up missed meetings: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "deleted_count": 0
        }

@router.post("/meetings/force-update")
async def force_meeting_update(db: AsyncSession = Depends(get_db)):
    """Force immediate update of all in-progress meetings (bypasses background task)."""
    try:
        from business.meeting_manager import MeetingManager
        from database.models import Meeting
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        meeting_manager = MeetingManager(db)
        
        # CRITICAL: Update meeting status FIRST (this transitions scheduled->in_progress)
        # This must happen before we query for in_progress meetings
        await meeting_manager.update_meeting_status()
        await db.commit()  # Ensure status changes are committed
        
        # Get meetings after status update
        result = await db.execute(
            select(Meeting).where(Meeting.status == 'in_progress')
        )
        meetings_before = result.scalars().all()
        
        # If no in-progress meetings, create one
        if len(meetings_before) == 0:
            print("No in-progress meetings found, generating one...")
            in_progress_meeting = await meeting_manager.generate_in_progress_meeting()
            if in_progress_meeting:
                meetings_before = [in_progress_meeting]
                print(f"Generated in-progress meeting: {in_progress_meeting.id}")
        
        # FORCE generate content for each meeting regardless of last_update
        for meeting in meetings_before:
            try:
                await db.refresh(meeting)
                print(f"🔄 Force updating meeting {meeting.id}: {meeting.title}")
                print(f"  Attendees: {len(meeting.attendee_ids or [])}")
                
                # Check current metadata
                current_metadata = meeting.meeting_metadata or {}
                print(f"  Current metadata keys: {list(current_metadata.keys())}")
                print(f"  Current last_update: {current_metadata.get('last_content_update', 'NOT SET')}")
                
                # Force generate content by calling _generate_live_meeting_content directly
                await meeting_manager._generate_live_meeting_content(meeting)
                
                # Commit to ensure changes are saved
                await db.commit()
                
                # Refresh to get updated state
                await db.refresh(meeting)
                metadata = meeting.meeting_metadata or {}
                live_messages = metadata.get("live_messages", [])
                last_update = metadata.get("last_content_update", "NOT SET")
                print(f"  ✅ After generation: {len(live_messages) if isinstance(live_messages, list) else 0} messages")
                print(f"  ✅ Last update: {last_update}")
            except Exception as e:
                print(f"❌ ERROR generating content for meeting {meeting.id}: {e}")
                import traceback
                traceback.print_exc()
        
        meetings = meetings_before
        
        updates = []
        for meeting in meetings:
            metadata = meeting.meeting_metadata or {}
            live_messages = metadata.get("live_messages", [])
            updates.append({
                "meeting_id": meeting.id,
                "title": meeting.title,
                "live_messages_count": len(live_messages) if isinstance(live_messages, list) else 0,
                "last_update": metadata.get("last_content_update", "Never")
            })
        
        return {
            "success": True,
            "message": f"Force updated {len(meetings)} meeting(s)",
            "meetings_updated": len(meetings),
            "meetings": updates
        }
    except Exception as e:
        print(f"Error forcing meeting update: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "meetings_updated": 0
        }

# Quick Wins API Routes

@router.get("/birthdays/upcoming")
async def get_upcoming_birthdays(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Get upcoming birthdays."""
    from business.birthday_manager import BirthdayManager
    manager = BirthdayManager(db)
    upcoming = await manager.get_upcoming_birthdays(days)
    return [
        {
            "employee_id": item["employee"].id,
            "employee_name": item["employee"].name,
            "days_until": item["days_until"],
            "date": item["date"].isoformat()
        }
        for item in upcoming
    ]

@router.get("/birthdays/today")
async def get_birthdays_today(db: AsyncSession = Depends(get_db)):
    """Get employees with birthdays today."""
    from business.birthday_manager import BirthdayManager
    manager = BirthdayManager(db)
    birthdays = await manager.check_birthdays_today()
    return [
        {
            "id": emp.id,
            "name": emp.name,
            "title": emp.title,
            "birthday_month": emp.birthday_month,
            "birthday_day": emp.birthday_day
        }
        for emp in birthdays
    ]

@router.get("/birthdays/parties")
async def get_birthday_parties(db: AsyncSession = Depends(get_db)):
    """Get scheduled birthday parties with room information."""
    from business.birthday_manager import BirthdayManager
    manager = BirthdayManager(db)
    parties = await manager.get_scheduled_parties()
    # Ensure dates are properly formatted
    return [
        {
            **party,
            "celebration_date": party["celebration_date"],
            "party_time": party["party_time"]
        }
        for party in parties
    ]

@router.post("/birthdays/generate-meetings")
async def generate_birthday_meetings(days_ahead: int = 90, db: AsyncSession = Depends(get_db)):
    """Generate birthday party meetings for upcoming birthdays (appears on calendar).
    
    This creates Meeting records for birthday parties so they appear on the calendar.
    Only creates meetings for active employees (excludes terminated employees).
    Birthdays are static - once set, they never change.
    """
    from business.birthday_manager import BirthdayManager
    from database.models import Employee
    from sqlalchemy import select
    import random
    
    # First, ensure all active employees have birthdays assigned
    result = await db.execute(
        select(Employee)
        .where(Employee.status == "active")
        .where(Employee.status != "fired")
        .where(Employee.fired_at.is_(None))
        .where(
            (Employee.birthday_month.is_(None)) | 
            (Employee.birthday_day.is_(None))
        )
    )
    employees_without_birthdays = result.scalars().all()
    
    if employees_without_birthdays:
        print(f"🎂 Assigning birthdays to {len(employees_without_birthdays)} employees...")
        for emp in employees_without_birthdays:
            if not emp.birthday_month or not emp.birthday_day:
                birthday_month = random.randint(1, 12)
                if birthday_month in [1, 3, 5, 7, 8, 10, 12]:
                    max_day = 31
                elif birthday_month in [4, 6, 9, 11]:
                    max_day = 30
                else:  # February
                    max_day = 28
                birthday_day = random.randint(1, max_day)
                emp.birthday_month = birthday_month
                emp.birthday_day = birthday_day
        await db.commit()
        print(f"✅ Assigned birthdays to {len(employees_without_birthdays)} employees")
    
    # Delete existing birthday meetings with wrong attendee counts (less than 15)
    from database.models import Meeting
    existing_result = await db.execute(select(Meeting))
    all_meetings = existing_result.scalars().all()
    deleted = 0
    for m in all_meetings:
        meta = m.meeting_metadata or {}
        if isinstance(meta, dict) and meta.get('is_birthday_party'):
            attendee_count = len(m.attendee_ids or [])
            if attendee_count != 15:
                await db.delete(m)
                deleted += 1
    if deleted > 0:
        await db.commit()
        print(f"🗑️ Deleted {deleted} birthday meetings with incorrect attendee counts")
    
    # Now generate the meetings properly
    from database.models import Meeting
    from employees.room_assigner import ROOM_BREAKROOM
    from datetime import datetime, timedelta
    from config import now as local_now
    import random
    
    today = local_now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today_start + timedelta(days=min(days_ahead, 365))
    
    # Get employees with birthdays
    result = await db.execute(
        select(Employee)
        .where(Employee.status == "active")
        .where(Employee.fired_at.is_(None))
        .where(Employee.birthday_month.isnot(None))
        .where(Employee.birthday_day.isnot(None))
    )
    employees = result.scalars().all()
    
    force_created = 0
    for emp in employees:
        try:
            bday = datetime(today.year, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
            if bday < today_start:
                bday = datetime(today.year + 1, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
            
            if bday.date() > end_date.date():
                continue
            
            # Check if exists - simple check
            start = bday.replace(hour=14, minute=0, second=0, microsecond=0)
            check_start = start - timedelta(hours=12)
            check_end = start + timedelta(hours=12)
            existing_result = await db.execute(
                select(Meeting)
                .where(Meeting.start_time >= check_start)
                .where(Meeting.start_time <= check_end)
            )
            existing_meetings = existing_result.scalars().all()
            exists = False
            for m in existing_meetings:
                meta = m.meeting_metadata or {}
                if isinstance(meta, dict) and meta.get('is_birthday_party') and meta.get('birthday_employee_id') == emp.id:
                    exists = True
                    break
            if exists:
                continue
            
            # Create meeting  
            end = start + timedelta(hours=1)
            
            all_emps_result = await db.execute(
                select(Employee).where(Employee.status == "active").where(Employee.id != emp.id)
            )
            all_emps = all_emps_result.scalars().all()
            # Get exactly 14 other employees (or as many as available)
            num_attendees = min(14, len(all_emps))
            if num_attendees > 0:
                attendees = random.sample(all_emps, num_attendees)
            else:
                attendees = []
            # Create attendee_ids: 14 colleagues + birthday person = 15 total
            attendee_ids = [e.id for e in attendees] + [emp.id]
            
            # Ensure we have exactly 15 (or as many as possible)
            if len(attendee_ids) < 15 and len(all_emps) < 14:
                attendee_ids = [e.id for e in all_emps] + [emp.id]
            
            room, floor = random.choice([(f"{ROOM_BREAKROOM}_floor2", 2), (ROOM_BREAKROOM, 1)])
            room_name = room.replace("_floor2", "").replace("_", " ").title()
            
            meeting = Meeting(
                title=f"🎂 {emp.name}'s Birthday Party",
                description=f"Birthday party for {emp.name}",
                organizer_id=emp.id,
                attendee_ids=attendee_ids,
                start_time=start,
                end_time=end,
                status="scheduled",
                agenda=f"Birthday celebration for {emp.name}",
                outline="1. Welcome\n2. Cake\n3. Song\n4. Gifts",
                meeting_metadata={
                    "is_birthday_party": True,
                    "birthday_employee_id": emp.id,
                    "room_name": room_name,
                    "party_floor": floor
                }
            )
            db.add(meeting)
            force_created += 1
        except Exception as e:
            print(f"Error creating for {emp.name}: {e}")
            continue
    
    await db.commit()
    
    # Also run the manager function
    manager = BirthdayManager(db)
    manager_created = await manager.generate_birthday_party_meetings(days_ahead=days_ahead)
    
    meetings_created = force_created + manager_created
    
    # Verify meetings were created
    from database.models import Meeting
    verify_result = await db.execute(select(Meeting))
    all_meetings = verify_result.scalars().all()
    verified_count = 0
    for meeting in all_meetings:
        metadata = meeting.meeting_metadata or {}
        if isinstance(metadata, dict) and metadata.get('is_birthday_party'):
            verified_count += 1
    
    return {
        "message": f"Generated {meetings_created} birthday party meetings",
        "meetings_created": meetings_created,
        "birthdays_assigned": len(employees_without_birthdays) if employees_without_birthdays else 0,
        "verified_meetings_in_db": verified_count
    }

@router.post("/birthdays/force-create-test")
async def force_create_birthday_test(db: AsyncSession = Depends(get_db)):
    """Force create a birthday party meeting for testing."""
    from database.models import Employee, Meeting
    from sqlalchemy import select
    from config import now as local_now
    from datetime import datetime, timedelta
    from employees.room_assigner import ROOM_BREAKROOM
    import random
    
    # Find Lily Nguyen or first employee with birthday in next 7 days
    today = local_now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today_start + timedelta(days=7)
    
    result = await db.execute(
        select(Employee)
        .where(Employee.status == "active")
        .where(Employee.birthday_month.isnot(None))
        .where(Employee.birthday_day.isnot(None))
        .where(Employee.name.like("Lily%"))
    )
    emp = result.scalar_one_or_none()
    
    if not emp:
        # Get any employee with birthday in next 7 days
        result = await db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.birthday_month.isnot(None))
            .where(Employee.birthday_day.isnot(None))
        )
        all_emps = result.scalars().all()
        for e in all_emps:
            try:
                bday = datetime(today.year, e.birthday_month, e.birthday_day, tzinfo=today.tzinfo)
                if bday < today_start:
                    bday = datetime(today.year + 1, e.birthday_month, e.birthday_day, tzinfo=today.tzinfo)
                if bday.date() <= end_date.date():
                    emp = e
                    break
            except:
                continue
    
    if not emp:
        return {"error": "No suitable employee found"}
    
    # Calculate birthday
    birthday_this_year = datetime(today.year, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
    if birthday_this_year < today_start:
        birthday_this_year = datetime(today.year + 1, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
    
    birthday_start = birthday_this_year.replace(hour=14, minute=0, second=0, microsecond=0)
    birthday_end = birthday_start + timedelta(hours=1)
    
    # Get attendees
    all_emps_result = await db.execute(
        select(Employee)
        .where(Employee.status == "active")
        .where(Employee.id != emp.id)
    )
    all_emps = all_emps_result.scalars().all()
    attendees = random.sample(all_emps, min(14, len(all_emps))) if all_emps else []
    attendee_ids = [e.id for e in attendees] + [emp.id]
    
    # Create meeting
    meeting = Meeting(
        title=f"🎂 {emp.name}'s Birthday Party",
        description=f"Birthday party for {emp.name}",
        organizer_id=emp.id,
        attendee_ids=attendee_ids,
        start_time=birthday_start,
        end_time=birthday_end,
        status="scheduled",
        meeting_metadata={
            "is_birthday_party": True,
            "birthday_employee_id": emp.id,
            "room_name": "Breakroom",
            "party_floor": 1
        }
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    
    return {
        "success": True,
        "meeting_id": meeting.id,
        "employee_name": emp.name,
        "start_time": meeting.start_time.isoformat(),
        "attendees_count": len(attendee_ids)
    }

@router.post("/birthdays/debug-generation")
async def debug_birthday_generation(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to see why birthday parties aren't being generated."""
    from business.birthday_manager import BirthdayManager
    from database.models import Employee, Meeting
    from sqlalchemy import select
    from config import now as local_now
    from datetime import timedelta
    
    today = local_now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check employees
    result = await db.execute(
        select(Employee)
        .where(Employee.status == "active")
        .where(Employee.status != "fired")
        .where(Employee.fired_at.is_(None))
        .where(Employee.birthday_month.isnot(None))
        .where(Employee.birthday_day.isnot(None))
    )
    employees_with_birthdays = result.scalars().all()
    
    # Check first few employees
    sample_employees = []
    for emp in employees_with_birthdays[:5]:
        try:
            from datetime import datetime
            birthday_this_year = datetime(today.year, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
            if birthday_this_year < today_start:
                birthday_this_year = datetime(today.year + 1, emp.birthday_month, emp.birthday_day, tzinfo=today.tzinfo)
            days_until = (birthday_this_year.date() - today_start.date()).days
            sample_employees.append({
                "name": emp.name,
                "id": emp.id,
                "birthday_month": emp.birthday_month,
                "birthday_day": emp.birthday_day,
                "birthday_date": birthday_this_year.isoformat(),
                "days_until": days_until
            })
        except:
            pass
    
    # Check existing meetings
    result = await db.execute(select(Meeting))
    all_meetings = result.scalars().all()
    birthday_meetings = []
    for meeting in all_meetings:
        metadata = meeting.meeting_metadata or {}
        if isinstance(metadata, dict) and metadata.get('is_birthday_party'):
            birthday_meetings.append({
                "id": meeting.id,
                "title": meeting.title,
                "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                "employee_id": metadata.get('birthday_employee_id')
            })
    
    return {
        "total_employees_with_birthdays": len(employees_with_birthdays),
        "sample_employees": sample_employees,
        "existing_birthday_meetings": len(birthday_meetings),
        "birthday_meetings": birthday_meetings,
        "today": today_start.isoformat()
    }

# Holiday API Routes

@router.get("/holidays/today")
async def get_holiday_today(db: AsyncSession = Depends(get_db)):
    """Check if today is a US holiday."""
    from business.holiday_manager import HolidayManager
    manager = HolidayManager(db)
    holiday_name = manager.is_holiday_today()
    if holiday_name:
        # Check if we've already celebrated
        celebration = await manager.check_holiday_today()
        return {
            "is_holiday": True,
            "holiday_name": holiday_name,
            "celebrated": celebration is None  # If celebration is None, we already celebrated
        }
    return {
        "is_holiday": False,
        "holiday_name": None,
        "celebrated": False
    }

@router.get("/holidays/upcoming")
async def get_upcoming_holidays(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get upcoming US holidays."""
    try:
        from business.holiday_manager import HolidayManager
        manager = HolidayManager(db)
        upcoming = await manager.get_upcoming_holidays(days)
        return [
            {
                "holiday_name": item["holiday_name"],
                "date": item["date"].isoformat() if hasattr(item["date"], "isoformat") else str(item["date"]),
                "days_until": item["days_until"]
            }
            for item in upcoming
        ]
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Holidays library not available: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching holidays: {str(e)}")

@router.get("/holidays/parties")
async def get_holiday_parties(db: AsyncSession = Depends(get_db)):
    """Get scheduled holiday parties with room information."""
    from business.holiday_manager import HolidayManager
    manager = HolidayManager(db)
    parties = await manager.get_scheduled_holiday_parties()
    return [
        {
            **party,
            "celebration_date": party["celebration_date"],
            "party_time": party["party_time"]
        }
        for party in parties
    ]

@router.post("/holidays/celebrate")
async def celebrate_holiday_today(db: AsyncSession = Depends(get_db)):
    """Manually trigger holiday celebration for today if it's a holiday."""
    from business.holiday_manager import HolidayManager
    manager = HolidayManager(db)
    holiday_name = await manager.check_holiday_today()
    if holiday_name:
        celebration = await manager.celebrate_holiday(holiday_name)
        if celebration:
            return {
                "success": True,
                "message": f"Celebrated {holiday_name}!",
                "celebration_id": celebration.id,
                "attendees_count": len(celebration.attendees) if celebration.attendees else 0
            }
        else:
            return {
                "success": False,
                "message": f"Already celebrated {holiday_name} today"
            }
    return {
        "success": False,
        "message": "Today is not a US holiday"
    }

@router.post("/holidays/generate-meetings")
async def generate_holiday_meetings(days_ahead: int = 365, db: AsyncSession = Depends(get_db)):
    """Generate holiday party meetings for upcoming US holidays (appears on calendar).
    
    This creates Meeting records for holiday parties so they appear on the calendar.
    Only creates meetings for active employees (excludes terminated employees).
    """
    from business.holiday_manager import HolidayManager
    manager = HolidayManager(db)
    meetings_created = await manager.generate_holiday_meetings(days_ahead=days_ahead)
    
    return {
        "message": f"Generated {meetings_created} holiday party meetings",
        "meetings_created": meetings_created
    }

@router.get("/pets")
async def get_pets(db: AsyncSession = Depends(get_db)):
    """Get all office pets."""
    from business.pet_manager import PetManager
    from database.models import OfficePet
    manager = PetManager(db)
    pets = await manager.get_all_pets()
    if not pets:
        pets = await manager.initialize_pets()
    return [
        {
            "id": pet.id,
            "name": pet.name,
            "pet_type": pet.pet_type,
            "avatar_path": pet.avatar_path,
            "current_room": pet.current_room,
            "floor": pet.floor,
            "personality": pet.personality,
            "favorite_employee_id": pet.favorite_employee_id,
            "last_room_change": pet.last_room_change.isoformat() if pet.last_room_change else None
        }
        for pet in pets
    ]

@router.get("/pets/care-log")
async def get_pet_care_log(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get pet care log showing which employees have cared for pets."""
    from database.models import PetCareLog, OfficePet, Employee, Activity
    from sqlalchemy import desc
    
    # First, try to backfill PetCareLog entries from Activities that don't have them
    # This handles old activities that were created before PetCareLog entries were added
    try:
        result = await db.execute(
            select(Activity)
            .where(Activity.activity_type.in_(["pet_care", "pet_interaction"]))
            .order_by(desc(Activity.timestamp))
            .limit(100)
        )
        activities = result.scalars().all()
        
        for activity in activities:
            # Check if this activity already has a care log
            if activity.activity_metadata and isinstance(activity.activity_metadata, dict):
                care_log_id = activity.activity_metadata.get("care_log_id")
                if care_log_id:
                    # Check if care log exists
                    log_result = await db.execute(
                        select(PetCareLog).where(PetCareLog.id == care_log_id)
                    )
                    if log_result.scalar_one_or_none():
                        continue  # Care log exists, skip
            
            # Try to create a care log from this activity
            pet_id = activity.activity_metadata.get("pet_id") if activity.activity_metadata else None
            employee_id = activity.employee_id
            
            if pet_id and employee_id:
                # Check if care log already exists for this activity
                existing_result = await db.execute(
                    select(PetCareLog)
                    .where(PetCareLog.pet_id == pet_id)
                    .where(PetCareLog.employee_id == employee_id)
                    .where(PetCareLog.created_at >= activity.timestamp if activity.timestamp else True)
                    .limit(1)
                )
                if not existing_result.scalar_one_or_none():
                    # Determine action from description or metadata
                    desc_lower = activity.description.lower() if activity.description else ""
                    if "fed" in desc_lower or "🍖" in desc_lower:
                        action = "feed"
                    elif "played" in desc_lower or "🎾" in desc_lower:
                        action = "play"
                    else:
                        action = "pet"
                    
                    # Create care log with default stats
                    care_log = PetCareLog(
                        pet_id=pet_id,
                        employee_id=employee_id,
                        care_action=action,
                        pet_happiness_before=60.0,
                        pet_hunger_before=50.0,
                        pet_energy_before=50.0,
                        pet_happiness_after=75.0,
                        pet_hunger_after=40.0,
                        pet_energy_after=60.0,
                        ai_reasoning=f"Backfilled from activity: {activity.description}"
                    )
                    db.add(care_log)
                    await db.flush()  # Flush to get the ID
                    
                    # Update activity metadata
                    if activity.activity_metadata:
                        activity.activity_metadata["care_log_id"] = care_log.id
                    else:
                        activity.activity_metadata = {"care_log_id": care_log.id}
                    db.add(activity)
        
        await db.commit()
    except Exception as e:
        print(f"Error backfilling care logs: {e}")
        await db.rollback()
    
    # Now get all care logs with relationships loaded
    result = await db.execute(
        select(PetCareLog, OfficePet, Employee)
        .outerjoin(OfficePet, PetCareLog.pet_id == OfficePet.id)
        .outerjoin(Employee, PetCareLog.employee_id == Employee.id)
        .order_by(desc(PetCareLog.created_at))
        .limit(limit)
    )
    rows = result.all()
    
    return [
        {
            "id": log.id,
            "pet_id": log.pet_id,
            "pet_name": pet.name if pet else "Unknown",
            "pet_type": pet.pet_type if pet else "Unknown",
            "employee_id": log.employee_id,
            "employee_name": employee.name if employee else "Unknown",
            "employee_title": employee.title if employee else "Unknown",
            "care_action": log.care_action,
            "pet_happiness_before": log.pet_happiness_before,
            "pet_hunger_before": log.pet_hunger_before,
            "pet_energy_before": log.pet_energy_before,
            "pet_happiness_after": log.pet_happiness_after,
            "pet_hunger_after": log.pet_hunger_after,
            "pet_energy_after": log.pet_energy_after,
            "ai_reasoning": log.ai_reasoning,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log, pet, employee in rows
    ]

@router.get("/pets/{pet_id}/care-log")
async def get_pet_care_log_by_pet(pet_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get care log for a specific pet."""
    from database.models import PetCareLog, OfficePet, Employee
    from sqlalchemy import desc
    
    result = await db.execute(
        select(PetCareLog)
        .where(PetCareLog.pet_id == pet_id)
        .join(Employee, PetCareLog.employee_id == Employee.id)
        .order_by(desc(PetCareLog.created_at))
        .limit(limit)
    )
    care_logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "employee_id": log.employee_id,
            "employee_name": log.employee.name if log.employee else "Unknown",
            "employee_title": log.employee.title if log.employee else "Unknown",
            "care_action": log.care_action,
            "pet_happiness_before": log.pet_happiness_before,
            "pet_hunger_before": log.pet_hunger_before,
            "pet_energy_before": log.pet_energy_before,
            "pet_happiness_after": log.pet_happiness_after,
            "pet_hunger_after": log.pet_hunger_after,
            "pet_energy_after": log.pet_energy_after,
            "ai_reasoning": log.ai_reasoning,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in care_logs
    ]

@router.post("/pets/{pet_id}/care")
async def log_pet_care(
    pet_id: int,
    care_data: dict = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Log a pet care action (feed, play, or pet) from the frontend."""
    from database.models import PetCareLog, OfficePet, Employee
    from sqlalchemy import select
    
    # Get the pet
    result = await db.execute(select(OfficePet).where(OfficePet.id == pet_id))
    pet = result.scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    # Get employee (if provided, otherwise use a random active employee or pet's favorite)
    employee = None
    employee_id = care_data.get("employee_id")
    if employee_id:
        result = await db.execute(select(Employee).where(Employee.id == employee_id))
        employee = result.scalar_one_or_none()
    
    if not employee:
        # Use pet's favorite employee or a random active employee
        if pet.favorite_employee_id:
            result = await db.execute(select(Employee).where(Employee.id == pet.favorite_employee_id))
            employee = result.scalar_one_or_none()
        if not employee:
            result = await db.execute(
                select(Employee).where(Employee.status == "active").limit(1)
            )
            employee = result.scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="No employee available")
    
    # Get care action and stats
    action = care_data.get("action", "pet")  # feed, play, or pet
    if action not in ["feed", "play", "pet"]:
        action = "pet"
    
    stats_before = {
        "happiness": care_data.get("happiness_before", 75.0),
        "hunger": care_data.get("hunger_before", 50.0),
        "energy": care_data.get("energy_before", 70.0)
    }
    
    stats_after = {
        "happiness": care_data.get("happiness_after", stats_before["happiness"]),
        "hunger": care_data.get("hunger_after", stats_before["hunger"]),
        "energy": care_data.get("energy_after", stats_before["energy"])
    }
    
    # Create care log
    care_log = PetCareLog(
        pet_id=pet.id,
        employee_id=employee.id,
        care_action=action,
        pet_happiness_before=stats_before["happiness"],
        pet_hunger_before=stats_before["hunger"],
        pet_energy_before=stats_before["energy"],
        pet_happiness_after=stats_after["happiness"],
        pet_hunger_after=stats_after["hunger"],
        pet_energy_after=stats_after["energy"],
        ai_reasoning=care_data.get("reasoning", "User-initiated care action")
    )
    db.add(care_log)
    
    # Create activity
    from database.models import Activity
    action_descriptions = {
        "feed": f"🍖 {employee.name} fed {pet.name}",
        "play": f"🎾 {employee.name} played with {pet.name}",
        "pet": f"❤️ {employee.name} petted and comforted {pet.name}"
    }
    
    activity = Activity(
        employee_id=employee.id,
        activity_type="pet_care",
        description=action_descriptions.get(action, f"🐾 {employee.name} cared for {pet.name}"),
        activity_metadata={
            "pet_id": pet.id,
            "pet_name": pet.name,
            "care_action": action,
            "care_log_id": care_log.id,
            "happiness_change": stats_after["happiness"] - stats_before["happiness"],
            "hunger_change": stats_after["hunger"] - stats_before["hunger"],
            "energy_change": stats_after["energy"] - stats_before["energy"]
        }
    )
    db.add(activity)
    await db.flush()
    # Broadcast activity
    try:
        from business.activity_broadcaster import broadcast_activity
        await broadcast_activity(activity, db, employee)
    except:
        pass  # Don't fail if broadcasting fails
    
    await db.commit()
    await db.refresh(care_log)
    
    return {
        "id": care_log.id,
        "pet_id": care_log.pet_id,
        "pet_name": pet.name,
        "pet_type": pet.pet_type,
        "employee_id": care_log.employee_id,
        "employee_name": employee.name,
        "employee_title": employee.title,
        "care_action": care_log.care_action,
        "pet_happiness_before": care_log.pet_happiness_before,
        "pet_hunger_before": care_log.pet_hunger_before,
        "pet_energy_before": care_log.pet_energy_before,
        "pet_happiness_after": care_log.pet_happiness_after,
        "pet_hunger_after": care_log.pet_hunger_after,
        "pet_energy_after": care_log.pet_energy_after,
        "ai_reasoning": care_log.ai_reasoning,
        "created_at": care_log.created_at.isoformat() if care_log.created_at else None
    }

@router.post("/pets/generate-test-care")
async def generate_test_care_logs(db: AsyncSession = Depends(get_db)):
    """Generate some test pet care logs immediately for testing."""
    from database.models import PetCareLog, OfficePet, Employee, Activity
    from sqlalchemy import select
    import random
    
    # Get all pets
    result = await db.execute(select(OfficePet))
    pets = result.scalars().all()
    
    if not pets:
        raise HTTPException(status_code=404, detail="No pets found. Please initialize pets first.")
    
    # Get active employees
    result = await db.execute(select(Employee).where(Employee.status == "active"))
    employees = result.scalars().all()
    
    if not employees:
        raise HTTPException(status_code=404, detail="No active employees found.")
    
    care_logs = []
    actions = ["feed", "play", "pet"]
    
    # Generate 5-10 care logs
    num_logs = random.randint(5, 10)
    for _ in range(num_logs):
        pet = random.choice(pets)
        employee = random.choice(employees)
        action = random.choice(actions)
        
        # Generate realistic stats
        happiness_before = random.randint(40, 80)
        hunger_before = random.randint(30, 80)
        energy_before = random.randint(30, 80)
        
        # Calculate stats after based on action
        if action == "feed":
            happiness_after = min(100, happiness_before + random.randint(5, 20))
            hunger_after = max(0, hunger_before - random.randint(20, 40))
            energy_after = energy_before
        elif action == "play":
            happiness_after = min(100, happiness_before + random.randint(10, 25))
            hunger_after = hunger_before
            energy_after = max(0, energy_before - random.randint(10, 25))
        else:  # pet
            happiness_after = min(100, happiness_before + random.randint(5, 15))
            hunger_after = hunger_before
            energy_after = min(100, energy_before + random.randint(2, 8))
        
        care_log = PetCareLog(
            pet_id=pet.id,
            employee_id=employee.id,
            care_action=action,
            pet_happiness_before=happiness_before,
            pet_hunger_before=hunger_before,
            pet_energy_before=energy_before,
            pet_happiness_after=happiness_after,
            pet_hunger_after=hunger_after,
            pet_energy_after=energy_after,
            ai_reasoning=f"Test data: {employee.name} {action}ed {pet.name}"
        )
        db.add(care_log)
        care_logs.append(care_log)
        
        # Create activity
        action_descriptions = {
            "feed": f"🍖 {employee.name} fed {pet.name}",
            "play": f"🎾 {employee.name} played with {pet.name}",
            "pet": f"❤️ {employee.name} petted and comforted {pet.name}"
        }
        
        activity = Activity(
            employee_id=employee.id,
            activity_type="pet_care",
            description=action_descriptions.get(action, f"🐾 {employee.name} cared for {pet.name}"),
            activity_metadata={
                "pet_id": pet.id,
                "pet_name": pet.name,
                "care_action": action,
                "care_log_id": care_log.id
            }
        )
        db.add(activity)
    
    await db.commit()
    
    return {
        "message": f"Generated {len(care_logs)} test care logs",
        "count": len(care_logs)
    }

@router.get("/employees/{employee_id}/pet-care")
async def get_employee_pet_care(employee_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get pet care activities for a specific employee."""
    from database.models import PetCareLog, OfficePet
    from sqlalchemy import desc
    
    result = await db.execute(
        select(PetCareLog)
        .where(PetCareLog.employee_id == employee_id)
        .join(OfficePet, PetCareLog.pet_id == OfficePet.id)
        .order_by(desc(PetCareLog.created_at))
        .limit(limit)
    )
    care_logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "pet_id": log.pet_id,
            "pet_name": log.pet.name if log.pet else "Unknown",
            "pet_type": log.pet.pet_type if log.pet else "Unknown",
            "care_action": log.care_action,
            "pet_happiness_before": log.pet_happiness_before,
            "pet_hunger_before": log.pet_hunger_before,
            "pet_energy_before": log.pet_energy_before,
            "pet_happiness_after": log.pet_happiness_after,
            "pet_hunger_after": log.pet_hunger_after,
            "pet_energy_after": log.pet_energy_after,
            "ai_reasoning": log.ai_reasoning,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in care_logs
    ]

@router.get("/gossip")
async def get_gossip(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent gossip."""
    from business.gossip_manager import GossipManager
    from database.models import Gossip
    manager = GossipManager(db)
    gossip_list = await manager.get_recent_gossip(limit)
    return [
        {
            "id": g.id,
            "originator_id": g.originator_id,
            "spreader_id": g.spreader_id,
            "recipient_id": g.recipient_id,
            "topic": g.topic,
            "content": g.content,
            "credibility": g.credibility,
            "spread_count": g.spread_count,
            "created_at": g.created_at.isoformat()
        }
        for g in gossip_list
    ]

@router.get("/weather")
async def get_weather(db: AsyncSession = Depends(get_db)):
    """Get today's weather."""
    from business.weather_manager import WeatherManager
    manager = WeatherManager(db)
    weather = await manager.get_today_weather()
    if not weather:
        return None
    return {
        "id": weather.id,
        "condition": weather.condition,
        "temperature": weather.temperature,
        "productivity_modifier": weather.productivity_modifier,
        "description": weather.description,
        "date": weather.date.isoformat()
    }

@router.get("/random-events")
async def get_random_events(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    """Get random events."""
    from business.random_event_manager import RandomEventManager
    from database.models import RandomEvent
    from sqlalchemy import select, desc
    manager = RandomEventManager(db)
    
    if active_only:
        events = await manager.get_active_events()
    else:
        result = await db.execute(
            select(RandomEvent)
            .order_by(desc(RandomEvent.start_time))
            .limit(20)
        )
        events = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "impact": e.impact,
            "affected_employees": e.affected_employees,
            "productivity_modifier": e.productivity_modifier,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "resolved": e.resolved
        }
        for e in events
    ]

@router.get("/newsletters")
async def get_newsletters(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get latest newsletters."""
    from business.newsletter_manager import NewsletterManager
    from database.models import Newsletter
    from sqlalchemy import select, desc
    manager = NewsletterManager(db)
    newsletters = await manager.get_latest_newsletters(limit)
    return [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "author_id": n.author_id,
            "issue_number": n.issue_number,
            "published_date": n.published_date.isoformat(),
            "read_count": n.read_count
        }
        for n in newsletters
    ]

@router.post("/newsletters/{newsletter_id}/read")
async def mark_newsletter_read(newsletter_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a newsletter as read."""
    from business.newsletter_manager import NewsletterManager
    manager = NewsletterManager(db)
    await manager.mark_as_read(newsletter_id)
    return {"success": True, "message": "Newsletter marked as read"}

@router.get("/suggestions")
async def get_suggestions(status: str = None, db: AsyncSession = Depends(get_db)):
    """Get suggestions."""
    from business.suggestion_manager import SuggestionManager
    from database.models import Suggestion, Employee, SuggestionVote
    from sqlalchemy import select, desc
    manager = SuggestionManager(db)
    
    if status:
        result = await db.execute(
            select(Suggestion)
            .where(Suggestion.status == status)
            .order_by(desc(Suggestion.upvotes), desc(Suggestion.created_at))
        )
    else:
        result = await db.execute(
            select(Suggestion)
            .order_by(desc(Suggestion.upvotes), desc(Suggestion.created_at))
            .limit(50)
        )
    suggestions = result.scalars().all()
    
    # Get employee names
    result = await db.execute(select(Employee))
    all_employees = {emp.id: emp.name for emp in result.scalars().all()}
    
    # Get votes for all suggestions
    suggestion_ids = [s.id for s in suggestions]
    votes_result = await db.execute(
        select(SuggestionVote)
        .where(SuggestionVote.suggestion_id.in_(suggestion_ids))
    )
    all_votes = votes_result.scalars().all()
    
    # Group votes by suggestion_id
    votes_by_suggestion = {}
    for vote in all_votes:
        if vote.suggestion_id not in votes_by_suggestion:
            votes_by_suggestion[vote.suggestion_id] = []
        votes_by_suggestion[vote.suggestion_id].append({
            "id": vote.id,
            "employee_id": vote.employee_id,
            "employee_name": all_employees.get(vote.employee_id, "Unknown"),
            "created_at": vote.created_at.isoformat() if vote.created_at else None
        })
    
    return [
        {
            "id": s.id,
            "employee_id": s.employee_id,
            "employee_name": all_employees.get(s.employee_id, "Unknown"),
            "category": s.category,
            "title": s.title,
            "content": s.content,
            "status": s.status,
            "upvotes": s.upvotes,
            "reviewed_by_id": s.reviewed_by_id,
            "reviewer_name": all_employees.get(s.reviewed_by_id, None) if s.reviewed_by_id else None,
            "review_notes": s.review_notes,
            "manager_comments": s.manager_comments,
            "votes": votes_by_suggestion.get(s.id, []),
            "created_at": s.created_at.isoformat(),
            "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None
        }
        for s in suggestions
    ]

@router.post("/suggestions/{suggestion_id}/upvote")
async def upvote_suggestion(suggestion_id: int, db: AsyncSession = Depends(get_db)):
    """Upvote a suggestion."""
    from business.suggestion_manager import SuggestionManager
    manager = SuggestionManager(db)
    await manager.upvote_suggestion(suggestion_id)
    return {"success": True, "message": "Suggestion upvoted"}

# Database health check endpoint
@router.get("/db/health")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """Check if database is working and return basic stats."""
    try:
        from sqlalchemy import text
        
        # Test basic query
        result = await db.execute(text("SELECT COUNT(*) as count FROM employees"))
        employee_count = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) as count FROM projects"))
        project_count = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) as count FROM shared_drive_files"))
        file_count = result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "stats": {
                "employees": employee_count,
                "projects": project_count,
                "files": file_count
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }

# Shared Drive API Endpoints
@cached_query(cache_duration=30)  # Cache for 30 seconds (shared drive changes less frequently)
async def _fetch_shared_drive_structure(db: AsyncSession):
    """Internal function to fetch shared drive structure."""
    from business.shared_drive_manager import SharedDriveManager
    manager = SharedDriveManager(db)
    structure = await manager.get_file_structure()
    # Ensure we always return a dict, never None
    return structure if structure is not None else {}

@router.get("/shared-drive/structure")
async def get_shared_drive_structure(db: AsyncSession = Depends(get_db)):
    """Get hierarchical file structure."""
    try:
        return await _fetch_shared_drive_structure(db)
    except Exception as e:
        logger.error(f"Error in get_shared_drive_structure: {e}", exc_info=True)
        # Return empty structure - frontend will use cache if available
        return {}

@cached_query(cache_duration=30)  # Cache for 30 seconds
async def _fetch_shared_drive_files(
    db: AsyncSession,
    department: str = None,
    employee_id: int = None,
    project_id: int = None,
    file_type: str = None,
    limit: int = 100
):
    """Internal function to fetch shared drive files."""
    query = select(SharedDriveFile).options(
        selectinload(SharedDriveFile.employee),
        selectinload(SharedDriveFile.project),
        selectinload(SharedDriveFile.last_updated_by)
    )
    
    if department:
        query = query.where(SharedDriveFile.department == department)
    if employee_id:
        query = query.where(SharedDriveFile.employee_id == employee_id)
    if project_id:
        query = query.where(SharedDriveFile.project_id == project_id)
    if file_type:
        query = query.where(SharedDriveFile.file_type == file_type)
    
    query = query.order_by(desc(SharedDriveFile.updated_at)).limit(limit)
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    return [
        {
            "id": f.id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "department": f.department,
            "employee_id": f.employee_id,
            "employee_name": f.employee.name if f.employee else None,
            "project_id": f.project_id,
            "project_name": f.project.name if f.project else None,
            "file_size": f.file_size,
            "current_version": f.current_version,
            "last_updated_by_id": f.last_updated_by_id,
            "last_updated_by_name": f.last_updated_by.name if f.last_updated_by else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            "metadata": f.file_metadata
        }
        for f in files
    ]

@router.get("/shared-drive/files")
async def get_shared_drive_files(
    department: str = None,
    employee_id: int = None,
    project_id: int = None,
    file_type: str = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get all files with optional filters."""
    try:
        return await _fetch_shared_drive_files(db, department, employee_id, project_id, file_type, limit)
    except Exception as e:
        logger.error(f"Error in get_shared_drive_files: {e}", exc_info=True)
        # Return empty list - frontend will use cache if available
        return []

@router.get("/shared-drive/files/{file_id}")
async def get_shared_drive_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """Get file details and HTML content."""
    result = await db.execute(
        select(SharedDriveFile)
        .options(
            selectinload(SharedDriveFile.employee),
            selectinload(SharedDriveFile.project),
            selectinload(SharedDriveFile.last_updated_by)
        )
        .where(SharedDriveFile.id == file_id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "id": file.id,
        "file_name": file.file_name,
        "file_type": file.file_type,
        "department": file.department,
        "employee_id": file.employee_id,
        "employee_name": file.employee.name if file.employee else None,
        "project_id": file.project_id,
        "project_name": file.project.name if file.project else None,
        "file_path": file.file_path,
        "file_size": file.file_size,
        "content_html": file.content_html,
        "current_version": file.current_version,
        "last_updated_by_id": file.last_updated_by_id,
        "last_updated_by_name": file.last_updated_by.name if file.last_updated_by else None,
        "created_at": file.created_at.isoformat() if file.created_at else None,
        "updated_at": file.updated_at.isoformat() if file.updated_at else None,
        "metadata": file.file_metadata
    }

@router.get("/shared-drive/files/{file_id}/view")
async def view_shared_drive_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """Serve file HTML for viewing."""
    result = await db.execute(
        select(SharedDriveFile).where(SharedDriveFile.id == file_id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=file.content_html)

@router.get("/shared-drive/files/{file_id}/versions")
async def get_file_versions(file_id: int, db: AsyncSession = Depends(get_db)):
    """Get version history for a file."""
    result = await db.execute(
        select(SharedDriveFile).where(SharedDriveFile.id == file_id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    result = await db.execute(
        select(SharedDriveFileVersion)
        .options(selectinload(SharedDriveFileVersion.created_by))
        .where(SharedDriveFileVersion.file_id == file_id)
        .order_by(desc(SharedDriveFileVersion.version_number))
    )
    versions = result.scalars().all()
    
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "file_size": v.file_size,
            "created_by_id": v.created_by_id,
            "created_by_name": v.created_by.name if v.created_by else None,
            "change_summary": v.change_summary,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "metadata": v.file_metadata
        }
        for v in versions
    ]

@router.get("/shared-drive/files/{file_id}/versions/{version_number}")
async def get_file_version_content(
    file_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Get specific version content."""
    result = await db.execute(
        select(SharedDriveFileVersion)
        .options(selectinload(SharedDriveFileVersion.created_by))
        .where(
            SharedDriveFileVersion.file_id == file_id,
            SharedDriveFileVersion.version_number == version_number
        )
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return {
        "id": version.id,
        "file_id": version.file_id,
        "version_number": version.version_number,
        "content_html": version.content_html,
        "file_size": version.file_size,
        "created_by_id": version.created_by_id,
        "created_by_name": version.created_by.name if version.created_by else None,
        "change_summary": version.change_summary,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "metadata": version.file_metadata
    }

@router.get("/employees/{employee_id}/recent-files")
async def get_employee_recent_files(
    employee_id: int,
    limit: int = 15,
    db: AsyncSession = Depends(get_db)
):
    """Get recent files created/updated by employee."""
    from business.shared_drive_manager import SharedDriveManager
    manager = SharedDriveManager(db)
    files = await manager.get_employee_recent_files(employee_id, limit)
    
    return [
        {
            "id": f.id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "department": f.department,
            "project_id": f.project_id,
            "project_name": f.project.name if f.project else None,
            "current_version": f.current_version,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            "version_count": len(f.versions) if f.versions else 0
        }
        for f in files
    ]

@router.post("/shared-drive/generate")
async def generate_shared_drive_documents(
    employee_id: Optional[int] = None,
    count: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger document generation (for testing)."""
    from business.shared_drive_manager import SharedDriveManager
    from engine.office_simulator import get_business_context
    
    manager = SharedDriveManager(db)
    business_context = await get_business_context(db)
    
    if employee_id:
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employees = [result.scalar_one_or_none()] if result.scalar_one_or_none() else []
    else:
        result = await db.execute(
            select(Employee).where(Employee.status == "active").limit(count)
        )
        employees = result.scalars().all()
    
    if not employees:
        raise HTTPException(status_code=404, detail="No active employees found")
    
    total_created = 0
    total_updated = 0
    errors = []
    
    for employee in employees:
        try:
            created = await manager.generate_documents_for_employee(employee, business_context)
            total_created += len(created)
            
            updated = await manager.update_existing_documents(employee, business_context)
            total_updated += len(updated)
        except Exception as e:
            errors.append(f"Employee {employee.id} ({employee.name}): {str(e)}")
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Generated documents for {len(employees)} employees",
        "files_created": total_created,
        "files_updated": total_updated,
        "employees_processed": len(employees),
        "errors": errors if errors else None
    }

@router.get("/config/timezone")
async def get_timezone_config():
    """Get the configured timezone for the application."""
    try:
        return {
            "timezone": TIMEZONE_NAME
        }
    except Exception as e:
        print(f"Error in get_timezone_config: {e}")
        return {
            "timezone": "America/New_York"
        }

# ========================================
# HOME VIEW ENDPOINTS
# ========================================

@router.get("/home/employees")
async def get_home_employees():
    """Get all active employees with their home settings."""
    async with async_session_maker() as db:
        # Optimized query: Load employees with home settings in one query
        result = await db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .options(selectinload(Employee.home_settings))
            .order_by(Employee.name)
        )
        employees = result.scalars().all()

        # Get family counts for all employees in one query
        family_counts_result = await db.execute(
            select(FamilyMember.employee_id, func.count(FamilyMember.id))
            .group_by(FamilyMember.employee_id)
        )
        family_counts = dict(family_counts_result.all())

        # Get pet counts for all employees in one query
        pet_counts_result = await db.execute(
            select(HomePet.employee_id, func.count(HomePet.id))
            .group_by(HomePet.employee_id)
        )
        pet_counts = dict(pet_counts_result.all())

        # Build response with loaded data
        employee_data = []
        for employee in employees:
            home_settings = employee.home_settings
            
            employee_data.append({
                "id": employee.id,
                "name": employee.name,
                "title": employee.title,
                "department": employee.department,
                "avatar_path": employee.avatar_path,
                "activity_state": employee.activity_state,
                "home_settings": {
                    "home_type": home_settings.home_type if home_settings else None,
                    "home_layout_exterior": home_settings.home_layout_exterior if home_settings else None,
                    "home_layout_interior": home_settings.home_layout_interior if home_settings else None,
                    "living_situation": home_settings.living_situation if home_settings else None,
                    "home_address": home_settings.home_address if home_settings else None,
                } if home_settings else None,
                "family_count": family_counts.get(employee.id, 0),
                "pet_count": pet_counts.get(employee.id, 0)
            })

        return employee_data

@router.get("/home/employees/{employee_id}")
async def get_employee_home(employee_id: int):
    """Get detailed home information for a specific employee."""
    async with async_session_maker() as db:
        # Get employee
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get home settings
        home_result = await db.execute(
            select(HomeSettings).where(HomeSettings.employee_id == employee_id)
        )
        home_settings = home_result.scalar_one_or_none()

        # Get family members
        family_result = await db.execute(
            select(FamilyMember).where(FamilyMember.employee_id == employee_id)
        )
        family_members = family_result.scalars().all()

        # Get home pets
        pet_result = await db.execute(
            select(HomePet).where(HomePet.employee_id == employee_id)
        )
        home_pets = pet_result.scalars().all()

        return {
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "title": employee.title,
                "department": employee.department,
                "avatar_path": employee.avatar_path,
                "activity_state": employee.activity_state,
                "hobbies": employee.hobbies,
                "personality_traits": employee.personality_traits,
            },
            "home_settings": {
                "home_type": home_settings.home_type,
                "home_layout_exterior": home_settings.home_layout_exterior,
                "home_layout_interior": home_settings.home_layout_interior,
                "living_situation": home_settings.living_situation,
                "home_address": home_settings.home_address,
            } if home_settings else None,
            "family_members": [
                {
                    "id": fm.id,
                    "name": fm.name,
                    "relationship_type": fm.relationship_type,
                    "age": fm.age,
                    "gender": fm.gender,
                    "avatar_path": fm.avatar_path,
                    "occupation": fm.occupation,
                    "personality_traits": fm.personality_traits,
                    "interests": fm.interests,
                    "current_location": fm.current_location or "inside",
                } for fm in family_members
            ],
            "home_pets": [
                {
                    "id": pet.id,
                    "name": pet.name,
                    "pet_type": pet.pet_type,
                    "avatar_path": pet.avatar_path,
                    "breed": pet.breed,
                    "age": pet.age,
                    "personality": pet.personality,
                    "current_location": pet.current_location or "inside",
                } for pet in home_pets
            ]
        }

@router.get("/home/employees/{employee_id}/family")
async def get_employee_family(employee_id: int):
    """Get all family members for a specific employee."""
    async with async_session_maker() as db:
        # Verify employee exists
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get family members
        family_result = await db.execute(
            select(FamilyMember).where(FamilyMember.employee_id == employee_id)
        )
        family_members = family_result.scalars().all()

        return [
            {
                "id": fm.id,
                "name": fm.name,
                "relationship_type": fm.relationship_type,
                "age": fm.age,
                "gender": fm.gender,
                "avatar_path": fm.avatar_path,
                "occupation": fm.occupation,
                "personality_traits": fm.personality_traits,
                "interests": fm.interests,
            } for fm in family_members
        ]

@router.get("/home/employees/{employee_id}/pets")
async def get_employee_home_pets(employee_id: int):
    """Get all home pets for a specific employee."""
    async with async_session_maker() as db:
        # Verify employee exists
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get home pets
        pet_result = await db.execute(
            select(HomePet).where(HomePet.employee_id == employee_id)
        )
        home_pets = pet_result.scalars().all()

        return [
            {
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "avatar_path": pet.avatar_path,
                "breed": pet.breed,
                "age": pet.age,
                "personality": pet.personality,
            } for pet in home_pets
        ]

@router.get("/home/layouts")
async def get_home_layouts():
    """Get available home layout images."""
    import os

    home_layout_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "home_layout")

    if not os.path.exists(home_layout_dir):
        return {
            "city_exteriors": [],
            "country_exteriors": [],
            "city_interiors": [],
            "country_interiors": []
        }

    files = os.listdir(home_layout_dir)

    return {
        "city_exteriors": [f for f in files if f.startswith("city_home") and not "interior" in f],
        "country_exteriors": [f for f in files if f.startswith("home") and not f.startswith("home_layout") and not "interior" in f],
        "city_interiors": [f for f in files if "city_home_interior" in f],
        "country_interiors": [f for f in files if "country_home_interior" in f]
    }

@router.get("/home/layout/{employee_id}")
async def get_home_layout(employee_id: int, view: str = "interior"):
    """Get home layout data for a specific employee including all occupants and their positions."""
    async with async_session_maker() as db:
        # Get employee
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get home settings
        home_result = await db.execute(
            select(HomeSettings).where(HomeSettings.employee_id == employee_id)
        )
        home_settings = home_result.scalar_one_or_none()

        if not home_settings:
            raise HTTPException(status_code=404, detail="Home settings not found for this employee")

        # Get family members
        family_result = await db.execute(
            select(FamilyMember).where(FamilyMember.employee_id == employee_id)
        )
        family_members = family_result.scalars().all()

        # Get home pets
        pet_result = await db.execute(
            select(HomePet).where(HomePet.employee_id == employee_id)
        )
        home_pets = pet_result.scalars().all()

        # Check if it's work hours - employees should not be at home during work hours
        from config import is_work_hours
        is_work_time = is_work_hours()

        # Select layout image based on view type
        if view == "exterior":
            layout_image = home_settings.home_layout_exterior
            view_location = "outside"
        else:
            layout_image = home_settings.home_layout_interior
            view_location = "inside"

        # Generate positions for occupants with sleep-aware positioning
        import random
        occupants = []

        # Bedroom positioning for sleeping people:
        # Master bedroom (top-right area): Employees and spouses
        # Children's room (top-left area): Children and pets
        # Living areas (center/bottom): Awake people

        master_bedroom_x = (65, 85)  # Right side
        master_bedroom_y = (15, 35)  # Top

        children_room_x = (15, 35)   # Left side
        children_room_y = (15, 35)   # Top

        living_area_x = (20, 80)     # Center
        living_area_y = (40, 80)     # Bottom/middle

        # Track sleeping spouses for positioning together
        sleeping_spouse_position = None

        # Add employee ONLY if it's not work hours (employees are at office during work hours)
        if not is_work_time and view_location == "inside":  # Only show in interior view
            employee_sleep_state = getattr(employee, 'sleep_state', 'awake')

            # Position employee based on sleep state
            if employee_sleep_state == "sleeping":
                # Employee sleeps in master bedroom
                position = {
                    "x": random.uniform(*master_bedroom_x),
                    "y": random.uniform(*master_bedroom_y)
                }
                sleeping_spouse_position = position  # Save for spouse
            else:
                # Employee awake - in living area
                position = {
                    "x": random.uniform(*living_area_x),
                    "y": random.uniform(*living_area_y)
                }

            occupants.append({
                "id": employee.id,
                "name": employee.name,
                "type": "employee",
                "avatar_path": employee.avatar_path,
                "title": employee.title,
                "role": employee.role,
                "department": employee.department,
                "sleep_state": employee_sleep_state,
                "position": position
            })

        # Add family members with sleep-aware positioning
        children = []  # Track children for room sharing

        for fm in family_members:
            fm_location = fm.current_location or "inside"
            fm_sleep_state = getattr(fm, 'sleep_state', 'awake')

            # Only show in matching view location
            if fm_location == view_location:
                # Position based on relationship and sleep state
                if fm_sleep_state == "sleeping":
                    if fm.relationship_type == "spouse":
                        # Spouse sleeps next to employee in master bedroom
                        if sleeping_spouse_position:
                            # Position near employee
                            position = {
                                "x": sleeping_spouse_position["x"] + random.uniform(-5, 5),
                                "y": sleeping_spouse_position["y"] + random.uniform(-3, 3)
                            }
                        else:
                            # Employee not sleeping, spouse sleeps alone
                            position = {
                                "x": random.uniform(*master_bedroom_x),
                                "y": random.uniform(*master_bedroom_y)
                            }
                    elif fm.relationship_type == "child":
                        # Children sleep in children's room (will group together)
                        children.append(fm)
                        position = {
                            "x": random.uniform(*children_room_x),
                            "y": random.uniform(*children_room_y)
                        }
                    else:
                        # Other family (parents, siblings) sleep in guest area
                        position = {
                            "x": random.uniform(40, 60),
                            "y": random.uniform(20, 40)
                        }
                else:
                    # Awake - in living area
                    position = {
                        "x": random.uniform(*living_area_x),
                        "y": random.uniform(*living_area_y)
                    }

                occupants.append({
                    "id": fm.id,
                    "name": fm.name,
                    "type": "family",
                    "relationship_type": fm.relationship_type,
                    "avatar_path": fm.avatar_path,
                    "sleep_state": fm_sleep_state,
                    "position": position
                })

        # Add pets with sleep-aware positioning (pets sleep with children)
        for pet in home_pets:
            pet_location = pet.current_location or "inside"
            pet_sleep_state = getattr(pet, 'sleep_state', 'awake')

            if pet_location == view_location:
                if pet_sleep_state == "sleeping":
                    # Pets sleep in children's room
                    position = {
                        "x": random.uniform(*children_room_x),
                        "y": random.uniform(*children_room_y)
                    }
                else:
                    # Awake pets roam living area
                    position = {
                        "x": random.uniform(*living_area_x),
                        "y": random.uniform(*living_area_y)
                    }

                occupants.append({
                    "id": pet.id,
                    "name": pet.name,
                    "type": "pet",
                    "pet_type": pet.pet_type,
                    "avatar_path": pet.avatar_path,
                    "sleep_state": pet_sleep_state,
                    "position": position
                })
        
        # Determine what locations are present (for display purposes)
        locations_present = set()
        if not is_work_time:
            locations_present.add(view_location)  # Employee is in the current view if not work hours
        for fm in family_members:
            locations_present.add(fm.current_location or "inside")
        for pet in home_pets:
            locations_present.add(pet.current_location or "inside")

        return {
            "employee_id": employee_id,
            "view": view,
            "view_location": view_location,
            "is_work_hours": is_work_time,
            "layout_image": layout_image,
            "home_type": home_settings.home_type,
            "home_address": home_settings.home_address,
            "occupants": occupants,
            "locations_present": list(locations_present)
        }

class HomeLocationUpdateRequest(BaseModel):
    employee_id: int
    location: str  # "inside" or "outside"

@router.post("/home/locations")
async def update_home_locations(request: HomeLocationUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update locations for all family members and pets in an employee's home."""
    # Verify location is valid
    if request.location not in ["inside", "outside"]:
        raise HTTPException(status_code=400, detail="Location must be 'inside' or 'outside'")
    
    # Get employee
    result = await db.execute(
        select(Employee).where(Employee.id == request.employee_id, Employee.status == "active")
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Get all family members and pets
    family_result = await db.execute(
        select(FamilyMember).where(FamilyMember.employee_id == request.employee_id)
    )
    family_members = family_result.scalars().all()

    pet_result = await db.execute(
        select(HomePet).where(HomePet.employee_id == request.employee_id)
    )
    home_pets = pet_result.scalars().all()

    # Update all family members to the same location
    for fm in family_members:
        fm.current_location = request.location

    # Update all pets to the same location
    for pet in home_pets:
        pet.current_location = request.location

    await db.commit()

    return {
        "success": True,
        "employee_id": request.employee_id,
        "location": request.location,
        "family_members_updated": len(family_members),
        "pets_updated": len(home_pets)
    }

class HomeConversationRequest(BaseModel):
    employee_id: int

@router.post("/home/conversations")
async def generate_home_conversations(
    request: HomeConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate home conversations between employee and family members, or between family members if employee is at work."""
    try:
        # Get employee
        result = await db.execute(
            select(Employee).where(Employee.id == request.employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get family members
        family_result = await db.execute(
            select(FamilyMember).where(FamilyMember.employee_id == request.employee_id)
        )
        family_members = family_result.scalars().all()

        if len(family_members) == 0:
            return {"conversations": []}

        # Get home pets for context
        pet_result = await db.execute(
            select(HomePet).where(HomePet.employee_id == request.employee_id)
        )
        home_pets = pet_result.scalars().all()

        # Get home settings for context
        home_result = await db.execute(
            select(HomeSettings).where(HomeSettings.employee_id == request.employee_id)
        )
        home_settings = home_result.scalar_one_or_none()

        # Check if it's work hours
        from config import is_work_hours
        is_work_time = is_work_hours()

        # Generate conversations
        from llm.ollama_client import OllamaClient
        llm_client = OllamaClient()
        conversations = []

        # Get current time for context
        from config import now
        current_time = now()
        time_of_day = "evening" if 18 <= current_time.hour < 22 else "night" if 22 <= current_time.hour or current_time.hour < 6 else "morning" if 6 <= current_time.hour < 12 else "afternoon"

        import random

        if is_work_time:
            # Employee is at work - generate conversations between family members
            if len(family_members) >= 2:
                # Generate 1-2 conversations between family members
                num_conversations = min(2, len(family_members) // 2)
                available_family = family_members.copy()
                
                for _ in range(num_conversations):
                    if len(available_family) < 2:
                        break
                    
                    # Pick two different family members
                    pair = random.sample(available_family, 2)
                    fm1, fm2 = pair
                    
                    # Remove them from available pool
                    available_family.remove(fm1)
                    available_family.remove(fm2)
                    
                    # Generate conversation between family members
                    conversation_data = await llm_client.generate_family_conversation(
                        family_member1_name=fm1.name,
                        family_member1_relationship=fm1.relationship_type,
                        family_member1_age=fm1.age,
                        family_member1_personality=fm1.personality_traits or [],
                        family_member1_interests=fm1.interests or [],
                        family_member1_occupation=fm1.occupation,
                        family_member2_name=fm2.name,
                        family_member2_relationship=fm2.relationship_type,
                        family_member2_age=fm2.age,
                        family_member2_personality=fm2.personality_traits or [],
                        family_member2_interests=fm2.interests or [],
                        family_member2_occupation=fm2.occupation,
                        employee_name=employee.name,
                        time_of_day=time_of_day,
                        has_pets=len(home_pets) > 0,
                        home_type=home_settings.home_type if home_settings else "city"
                    )
                    
                    conversations.append({
                        "family_member1_id": fm1.id,
                        "family_member1_name": fm1.name,
                        "family_member2_id": fm2.id,
                        "family_member2_name": fm2.name,
                        "employee_id": None,  # Employee not involved
                        "employee_name": None,
                        "messages": conversation_data.get("messages", [])
                    })
        else:
            # Employee is home - generate conversations between employee and family members
            # Select 1-2 family members to have conversations with
            num_conversations = min(2, len(family_members))
            selected_family = random.sample(family_members, num_conversations)

            for family_member in selected_family:
                # Generate conversation between employee and family member
                conversation_data = await llm_client.generate_home_conversation(
                    employee_name=employee.name,
                    employee_title=employee.title,
                    employee_personality=employee.personality_traits or [],
                    employee_hobbies=employee.hobbies or [],
                    family_member_name=family_member.name,
                    family_member_relationship=family_member.relationship_type,
                    family_member_age=family_member.age,
                    family_member_personality=family_member.personality_traits or [],
                    family_member_interests=family_member.interests or [],
                    family_member_occupation=family_member.occupation,
                    time_of_day=time_of_day,
                    has_pets=len(home_pets) > 0,
                    home_type=home_settings.home_type if home_settings else "city"
                )

                conversations.append({
                    "employee_id": employee.id,
                    "employee_name": employee.name,
                    "family_member_id": family_member.id,
                    "family_member_name": family_member.name,
                    "family_member1_id": None,
                    "family_member1_name": None,
                    "family_member2_id": None,
                    "family_member2_name": None,
                    "messages": conversation_data.get("messages", [])
                })
            
            # Also generate conversations between family members if there are 2+ family members
            if len(family_members) >= 2:
                # Generate 1 conversation between family members
                available_family = [fm for fm in family_members if fm.id not in [f.id for f in selected_family]]
                if len(available_family) >= 2:
                    pair = random.sample(available_family, 2)
                    fm1, fm2 = pair
                    
                    conversation_data = await llm_client.generate_family_conversation(
                        family_member1_name=fm1.name,
                        family_member1_relationship=fm1.relationship_type,
                        family_member1_age=fm1.age,
                        family_member1_personality=fm1.personality_traits or [],
                        family_member1_interests=fm1.interests or [],
                        family_member1_occupation=fm1.occupation,
                        family_member2_name=fm2.name,
                        family_member2_relationship=fm2.relationship_type,
                        family_member2_age=fm2.age,
                        family_member2_personality=fm2.personality_traits or [],
                        family_member2_interests=fm2.interests or [],
                        family_member2_occupation=fm2.occupation,
                        employee_name=employee.name,
                        time_of_day=time_of_day,
                        has_pets=len(home_pets) > 0,
                        home_type=home_settings.home_type if home_settings else "city"
                    )
                    
                    conversations.append({
                        "family_member1_id": fm1.id,
                        "family_member1_name": fm1.name,
                        "family_member2_id": fm2.id,
                        "family_member2_name": fm2.name,
                        "employee_id": None,
                        "employee_name": None,
                        "messages": conversation_data.get("messages", [])
                    })

        return {"conversations": conversations}
    except Exception as e:
        print(f"Error generating home conversations: {e}")
        import traceback
        traceback.print_exc()
        return {"conversations": []}

# ========================================
# CLOCK IN/OUT ENDPOINTS
# ========================================

@router.get("/clock-events/today")
async def get_clock_events_today():
    """Get all clock in/out events for today."""
    async with async_session_maker() as db:
        from business.clock_manager import ClockManager
        clock_manager = ClockManager(db)

        events = await clock_manager.get_all_clock_events_today()

        # Get employee details for each event
        result_data = []
        for event in events:
            emp_result = await db.execute(
                select(Employee).where(Employee.id == event.employee_id)
            )
            employee = emp_result.scalar_one_or_none()

            if employee:
                result_data.append({
                    "id": event.id,
                    "employee": {
                        "id": employee.id,
                        "name": employee.name,
                        "title": employee.title,
                        "department": employee.department,
                        "avatar_path": employee.avatar_path,
                    },
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "location": event.location,
                    "notes": event.notes,
                })

        return result_data

@router.get("/employees/{employee_id}/clock-history")
async def get_employee_clock_history(employee_id: int, days: int = 7):
    """Get clock in/out history for a specific employee."""
    async with async_session_maker() as db:
        # Verify employee exists
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.status == "active")
        )
        employee = result.scalar_one_or_none()

        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        from business.clock_manager import ClockManager
        clock_manager = ClockManager(db)

        events = await clock_manager.get_employee_clock_history(employee_id, days=days)

        return [
            {
                "id": event.id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "location": event.location,
                "notes": event.notes,
            } for event in events
        ]

@router.get("/clock-events/stats")
async def get_clock_stats():
    """Get clock in/out statistics for today."""
    async with async_session_maker() as db:
        from config import now
        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get all active employees
        emp_result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        total_employees = len(emp_result.scalars().all())

        # Count clock ins today
        clock_in_result = await db.execute(
            select(ClockInOut).where(
                and_(
                    ClockInOut.event_type == "clock_in",
                    ClockInOut.timestamp >= today_start
                )
            )
        )
        clocked_in_count = len(clock_in_result.scalars().all())

        # Count clock outs today
        clock_out_result = await db.execute(
            select(ClockInOut).where(
                and_(
                    ClockInOut.event_type == "clock_out",
                    ClockInOut.timestamp >= today_start
                )
            )
        )
        clocked_out_count = len(clock_out_result.scalars().all())

        # Get employees currently at work (clocked in but not clocked out)
        currently_at_work_result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.activity_state.notin_(["at_home", "sleeping", "leaving_work", "commuting_home"])
                )
            )
        )
        currently_at_work = len(currently_at_work_result.scalars().all())

        return {
            "total_employees": total_employees,
            "clocked_in_today": clocked_in_count,
            "clocked_out_today": clocked_out_count,
            "currently_at_work": currently_at_work,
            "currently_at_home": total_employees - currently_at_work
        }


@router.post("/clock-events/backfill")
async def backfill_missing_clock_outs():
    """Backfill missing clock-out events for employees who already left but don't have clock-out records."""
    async with async_session_maker() as db:
        from business.clock_manager import ClockManager
        clock_manager = ClockManager(db)
        
        result = await clock_manager.backfill_missing_clock_outs()
        return result

@router.post("/sleep/enforce")
async def enforce_sleep_rules():
    """Manually enforce sleep rules based on current time."""
    async with async_session_maker() as db:
        from business.sleep_manager import SleepManager
        
        sleep_manager = SleepManager(db)
        result = await sleep_manager.enforce_sleep_rules()
        return result

@router.get("/sleep/status")
async def get_sleep_status():
    """Get current sleep status of all employees, family members, and pets."""
    async with async_session_maker() as db:
        from business.sleep_manager import SleepManager
        from sqlalchemy import and_
        from config import now
        
        sleep_manager = SleepManager(db)
        stats = await sleep_manager.get_sleeping_stats()
        
        # Get detailed list of sleeping employees
        employees_result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.sleep_state == "sleeping"
                )
            ).order_by(Employee.name)
        )
        sleeping_employees = employees_result.scalars().all()
        
        # Get sleeping family members with employee info
        family_result = await db.execute(
            select(FamilyMember, Employee.name.label('employee_name'), Employee.id.label('employee_id')).join(
                Employee, FamilyMember.employee_id == Employee.id
            ).where(
                FamilyMember.sleep_state == "sleeping"
            ).order_by(Employee.name, FamilyMember.name)
        )
        sleeping_family = family_result.all()
        
        # Get sleeping pets with employee info
        pets_result = await db.execute(
            select(HomePet, Employee.name.label('employee_name'), Employee.id.label('employee_id')).join(
                Employee, HomePet.employee_id == Employee.id
            ).where(
                HomePet.sleep_state == "sleeping"
            ).order_by(Employee.name, HomePet.name)
        )
        sleeping_pets = pets_result.all()
        
        current_time = now()
        
        return {
            "current_time": current_time.isoformat(),
            "statistics": stats,
            "sleeping_employees": [
                {
                    "id": emp.id,
                    "name": emp.name,
                    "title": emp.title,
                    "department": emp.department,
                    "activity_state": emp.activity_state,
                    "sleep_state": emp.sleep_state
                }
                for emp in sleeping_employees
            ],
            "sleeping_family": [
                {
                    "id": fm.FamilyMember.id,
                    "name": fm.FamilyMember.name,
                    "relationship_type": fm.FamilyMember.relationship_type,
                    "age": fm.FamilyMember.age,
                    "employee_id": fm.employee_id,
                    "employee_name": fm.employee_name,
                    "sleep_state": fm.FamilyMember.sleep_state
                }
                for fm in sleeping_family
            ],
            "sleeping_pets": [
                {
                    "id": pet.HomePet.id,
                    "name": pet.HomePet.name,
                    "pet_type": pet.HomePet.pet_type,
                    "employee_id": pet.employee_id,
                    "employee_name": pet.employee_name,
                    "sleep_state": pet.HomePet.sleep_state
                }
                for pet in sleeping_pets
            ]
        }

@router.get("/company-hierarchy")
async def get_company_hierarchy(db: AsyncSession = Depends(get_db)):
    """Get complete organizational hierarchy starting from CEO."""

    # Find the CEO
    ceo_result = await db.execute(
        select(Employee).where(
            Employee.status == "active",
            Employee.role == "CEO"
        )
    )
    ceo = ceo_result.scalar_one_or_none()

    if not ceo:
        return {"error": "CEO not found", "hierarchy": []}

    async def build_hierarchy_node(employee: Employee) -> dict:
        """Recursively build hierarchy tree."""
        # Get direct reports
        reports_result = await db.execute(
            select(Employee).where(
                Employee.manager_id == employee.id,
                Employee.status == "active"
            ).order_by(Employee.name)
        )
        reports = reports_result.scalars().all()

        # Recursively build children nodes
        children = []
        for report in reports:
            children.append(await build_hierarchy_node(report))

        return {
            "id": employee.id,
            "name": employee.name,
            "title": employee.title,
            "role": employee.role,
            "department": employee.department,
            "avatar_path": employee.avatar_path if hasattr(employee, 'avatar_path') else None,
            "direct_reports_count": len(reports),
            "children": children
        }

    # Build complete hierarchy starting from CEO
    hierarchy = await build_hierarchy_node(ceo)

    # Get stats
    all_employees_result = await db.execute(
        select(Employee).where(Employee.status == "active")
    )
    all_employees = all_employees_result.scalars().all()

    executives_count = len([e for e in all_employees if e.role in ["CEO", "CTO", "COO", "CFO"]])
    managers_count = len([e for e in all_employees if e.role == "Manager"])
    employees_count = len([e for e in all_employees if e.role == "Employee"])

    return {
        "hierarchy": hierarchy,
        "stats": {
            "total": len(all_employees),
            "executives": executives_count,
            "managers": managers_count,
            "employees": employees_count,
            "ratio": f"1:{employees_count // managers_count if managers_count > 0 else 0}"
        }
    }

