import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from database.models import Employee, Activity, BusinessMetric, Financial, EmployeeReview, Project
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
from config import now as local_now, get_midnight_tomorrow
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

async def get_business_context(db: AsyncSession) -> dict:
    """Get current business context for decision making (standalone function)."""
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

class OfficeSimulator:
    def __init__(self):
        self.llm_client = OllamaClient()
        from business.communication_manager import CommunicationManager
        self.communication_manager = CommunicationManager()
        self.running = False
        self.websocket_connections: Set = set()
        self.review_tick_counter = 0  # Counter for periodic reviews
        self.boardroom_discussion_counter = 0  # Counter for boardroom discussions (every 15 ticks = 2 minutes)
        self.meeting_generation_counter = 0  # Counter for meeting generation (every 450 ticks = 1 hour)
        self.last_meeting_check_date = None  # Track the last date we checked for meetings
        self.award_update_counter = 0  # Counter for award updates (every 30 ticks = 4 minutes)
        self.quick_wins_counter = 0  # Counter for quick wins features
        self.last_weather_date = None  # Track last weather update date
        self.last_birthday_meeting_generation = None  # Track last birthday meeting generation date
        self.last_birthday_check_date = None  # Track last birthday check date
        self.last_holiday_check_date = None  # Track last holiday check date
        self.shared_drive_update_counter = 0  # Counter for shared drive updates
        self.last_shared_drive_update = None  # Track last shared drive update time
    
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
        return await get_business_context(db)
    
    async def fix_waiting_in_training_rooms(self):
        """Background task to fix employees stuck in training rooms with waiting status."""
        try:
            async with async_session_maker() as db:
                from employees.room_assigner import ROOM_TRAINING_ROOM
                
                # Get all employees in training rooms with waiting status
                training_rooms = [
                    ROOM_TRAINING_ROOM,
                    f"{ROOM_TRAINING_ROOM}_floor2",
                    f"{ROOM_TRAINING_ROOM}_floor4",
                    f"{ROOM_TRAINING_ROOM}_floor4_2",
                    f"{ROOM_TRAINING_ROOM}_floor4_3",
                    f"{ROOM_TRAINING_ROOM}_floor4_4",
                    f"{ROOM_TRAINING_ROOM}_floor4_5"
                ]
                
                result = await db.execute(
                    select(Employee).where(
                        Employee.status == "active",
                        Employee.activity_state == "waiting",
                        Employee.current_room.in_(training_rooms)
                    )
                )
                waiting_in_training = result.scalars().all()
                
                if waiting_in_training:
                    fixed_count = 0
                    for emp in waiting_in_training:
                        emp.activity_state = "training"
                        fixed_count += 1
                    
                    await db.commit()
                    if fixed_count > 0:
                        print(f"Fixed {fixed_count} employees stuck in training rooms with waiting status")
        except Exception as e:
            print(f"Error fixing waiting employees in training rooms: {e}")
    
    async def fix_idle_employees(self):
        """IMMEDIATELY fix ALL employees stuck in idle state - they should be working!"""
        from config import is_work_hours

        # Only fix idle employees during work hours
        # During non-work hours (7pm-7am), employees should be at home, not working
        if not is_work_hours():
            return  # Skip fixing idle employees when they should be at home

        try:
            async with async_session_maker() as db:
                # Get ALL idle employees
                result = await db.execute(
                    select(Employee).where(
                        Employee.status == "active",
                        Employee.activity_state == "idle"
                    )
                )
                idle_employees = result.scalars().all()

                if not idle_employees:
                    return

                fixed_count = 0

                # Fix ALL idle employees immediately (only during work hours)
                for employee in idle_employees:
                    try:
                        await db.refresh(employee, ["current_room", "home_room", "activity_state"])

                        # Set them to working - they should NEVER be idle during work hours
                        employee.activity_state = "working"
                        fixed_count += 1
                        await db.flush()
                    except Exception as e:
                        print(f"Error fixing idle employee {getattr(employee, 'name', 'unknown')}: {e}")
                        continue
                
                if fixed_count > 0:
                    await db.commit()
                    print(f"[!] FIXED {fixed_count} IDLE EMPLOYEES - They are now WORKING!")
                    
        except Exception as e:
            print(f"Error fixing idle employees: {e}")
            import traceback
            traceback.print_exc()
    
    async def process_waiting_employees(self):
        """Process ALL employees stuck in waiting state to retry their movement."""
        try:
            async with async_session_maker() as db:
                from engine.movement_system import (
                    process_employee_movement, 
                    find_available_training_room,
                    update_employee_location,
                    check_room_has_space,
                    determine_target_room
                )
                from employees.room_assigner import ROOM_TRAINING_ROOM, ROOM_CUBICLES, ROOM_OPEN_OFFICE
                from datetime import datetime, timedelta
                
                # Get ALL waiting employees - process them all immediately
                result = await db.execute(
                    select(Employee).where(
                        Employee.status == "active",
                        Employee.activity_state == "waiting"
                    )
                )
                waiting_employees = result.scalars().all()
                
                if not waiting_employees:
                    return
                
                processed_count = 0
                fixed_count = 0
                
                # Process ALL waiting employees - no limit
                for employee in waiting_employees:
                    try:
                        # Refresh employee to get latest state
                        await db.refresh(employee, ["current_room", "home_room", "activity_state", "hired_at"])
                        
                        # Check if they're in a training room but marked as waiting
                        training_rooms = [
                            ROOM_TRAINING_ROOM,
                            f"{ROOM_TRAINING_ROOM}_floor2",
                            f"{ROOM_TRAINING_ROOM}_floor4",
                            f"{ROOM_TRAINING_ROOM}_floor4_2",
                            f"{ROOM_TRAINING_ROOM}_floor4_3",
                            f"{ROOM_TRAINING_ROOM}_floor4_4",
                            f"{ROOM_TRAINING_ROOM}_floor4_5"
                        ]
                        
                        is_in_training_room = employee.current_room in training_rooms
                        
                        if is_in_training_room:
                            # They're already in a training room - just fix the status
                            employee.activity_state = "training"
                            fixed_count += 1
                            await db.flush()
                            continue
                        
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
                            # New hire waiting for training - find any available training room
                            available_training_room = await find_available_training_room(db, exclude_employee_id=employee.id)
                            if available_training_room:
                                await update_employee_location(employee, available_training_room, "training", db)
                                fixed_count += 1
                            else:
                                # All training rooms full - check if training should be complete
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
                                            # Training complete - move to home room and start working
                                            employee.activity_state = "working"
                                            if employee.home_room:
                                                await update_employee_location(employee, employee.home_room, "working", db)
                                            fixed_count += 1
                                    except Exception:
                                        pass
                        else:
                            # Not a new hire - AGGRESSIVELY find them a room
                            # Try multiple fallback options in order
                            moved = False
                            
                            # Strategy 1: Try home room
                            if employee.home_room:
                                has_space = await check_room_has_space(employee.home_room, db, exclude_employee_id=employee.id)
                                if has_space:
                                    await update_employee_location(employee, employee.home_room, "working", db)
                                    fixed_count += 1
                                    moved = True
                            
                            # Strategy 2: If home room full, try cubicles on their floor
                            if not moved:
                                employee_floor = getattr(employee, 'floor', 1)
                                cubicles_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                                has_space = await check_room_has_space(cubicles_room, db, exclude_employee_id=employee.id)
                                if has_space:
                                    await update_employee_location(employee, cubicles_room, "working", db)
                                    fixed_count += 1
                                    moved = True
                            
                            # Strategy 3: Try open office on their floor
                            if not moved:
                                open_office_room = f"{ROOM_OPEN_OFFICE}_floor{employee_floor}" if employee_floor > 1 else ROOM_OPEN_OFFICE
                                has_space = await check_room_has_space(open_office_room, db, exclude_employee_id=employee.id)
                                if has_space:
                                    await update_employee_location(employee, open_office_room, "working", db)
                                    fixed_count += 1
                                    moved = True
                            
                            # Strategy 4: Try any available room using determine_target_room
                            if not moved:
                                target_room = await determine_target_room("working", "", employee, db)
                                if target_room and target_room != employee.current_room:
                                    has_space = await check_room_has_space(target_room, db, exclude_employee_id=employee.id)
                                    if has_space:
                                        await update_employee_location(employee, target_room, "working", db)
                                        fixed_count += 1
                                        moved = True
                            
                            # Strategy 5: If still nothing, try ANY cubicles or open office on ANY floor
                            if not moved:
                                # Try all floors' cubicles and open offices
                                for floor in [1, 2, 3, 4]:
                                    if floor == 1:
                                        test_rooms = [ROOM_CUBICLES, ROOM_OPEN_OFFICE]
                                    else:
                                        test_rooms = [
                                            f"{ROOM_CUBICLES}_floor{floor}",
                                            f"{ROOM_OPEN_OFFICE}_floor{floor}"
                                        ]
                                    
                                    for test_room in test_rooms:
                                        has_space = await check_room_has_space(test_room, db, exclude_employee_id=employee.id)
                                        if has_space:
                                            await update_employee_location(employee, test_room, "working", db)
                                            fixed_count += 1
                                            moved = True
                                            break
                                    if moved:
                                        break
                            
                            # Strategy 6: Last resort - if they have a current_room, set to working
                            # Better than staying in waiting forever
                            if not moved and employee.current_room:
                                employee.activity_state = "working"
                                fixed_count += 1
                                moved = True
                        
                        processed_count += 1
                        await db.flush()
                        
                    except Exception as e:
                        print(f"Error processing waiting employee {getattr(employee, 'name', 'unknown')} (ID: {getattr(employee, 'id', 'unknown')}): {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Always commit to ensure changes are saved
                if fixed_count > 0:
                    await db.commit()
                    print(f"[+] Processed {processed_count} waiting employees, fixed {fixed_count}")
                else:
                    # Even if no fixes, commit to ensure any state changes are saved
                    await db.commit()
                    if processed_count > 0:
                        print(f"[i] Processed {processed_count} waiting employees (none needed fixing)")
                    
        except Exception as e:
            print(f"Error processing waiting employees: {e}")
            import traceback
            traceback.print_exc()
    
    async def ensure_training_sessions(self, db):
        """Ensure all employees in training rooms have active training sessions, and move out those who've been there too long."""
        try:
            from business.training_manager import TrainingManager
            from employees.room_assigner import ROOM_TRAINING_ROOM
            from sqlalchemy import select, and_
            from database.models import Employee, TrainingSession
            from datetime import datetime, timedelta
            from engine.movement_system import update_employee_location
            
            training_manager = TrainingManager()
            
            # Find all employees currently in training rooms
            # Check for all possible training room variations
            from sqlalchemy import or_
            training_room_conditions = [
                Employee.current_room == ROOM_TRAINING_ROOM,
                Employee.current_room.like(f"{ROOM_TRAINING_ROOM}_floor%"),
                Employee.current_room.like(f"{ROOM_TRAINING_ROOM}_floor4%"),
            ]
            result = await db.execute(
                select(Employee).where(
                    and_(
                        Employee.status == "active",
                        or_(*training_room_conditions)
                    )
                )
            )
            employees_in_training = result.scalars().all()
            
            for employee in employees_in_training:
                # Check if they have an active training session
                session_result = await db.execute(
                    select(TrainingSession).where(
                        and_(
                            TrainingSession.employee_id == employee.id,
                            TrainingSession.status == "in_progress"
                        )
                    )
                    .order_by(TrainingSession.start_time.desc())
                )
                existing_session = session_result.scalar_one_or_none()
                
                # Check if employee has been in training room for more than 30 minutes
                should_move_out = False
                if existing_session and existing_session.start_time:
                    time_in_training = datetime.now() - existing_session.start_time
                    if time_in_training > timedelta(minutes=30):
                        # Training session exceeded 30 minutes - end it and move employee out
                        existing_session.end_time = datetime.now()
                        existing_session.status = "completed"
                        duration = existing_session.end_time - existing_session.start_time
                        existing_session.duration_minutes = int(duration.total_seconds() / 60)
                        should_move_out = True
                elif not existing_session:
                    # No session but in training room - check if they've been there too long
                    # Use hired_at as a fallback, but prefer to create a session first
                    # For now, create a session and let the 30-minute check handle it next tick
                    if employee.current_room:
                        try:
                            await training_manager.start_training_session(
                                employee,
                                employee.current_room,
                                db
                            )
                            await db.flush()
                        except Exception as e:
                            print(f"Error creating training session for {employee.name}: {e}")
                            # If we can't create a session, check hired_at as fallback
                            if hasattr(employee, 'hired_at') and employee.hired_at:
                                time_since_hire = datetime.now() - employee.hired_at.replace(tzinfo=None) if employee.hired_at.tzinfo else datetime.now() - employee.hired_at
                                if time_since_hire > timedelta(minutes=30):
                                    should_move_out = True
                
                # Move employee out if training exceeded 30 minutes
                if should_move_out:
                    target_room = employee.home_room
                    if not target_room:
                        # Fallback to cubicles or open office
                        from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                        employee_floor = getattr(employee, 'floor', 1)
                        target_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                    
                    try:
                        await update_employee_location(employee, target_room, "working", db)
                        await db.flush()
                        print(f"Moved {employee.name} out of training room after exceeding 30 minutes")
                    except Exception as e:
                        print(f"Error moving {employee.name} out of training room: {e}")
                        import traceback
                        traceback.print_exc()
        except Exception as e:
            print(f"Error in ensure_training_sessions: {e}")
            import traceback
            traceback.print_exc()
    
    async def update_employee_locations_based_on_time(self):
        """Update employee locations based on current time (7pm-7am home, 7am-7pm office)."""
        from config import is_work_hours, should_be_at_home
        from database.models import Employee
        from sqlalchemy import select

        try:
            async with async_session_maker() as db:
                # Get all active employees
                result = await db.execute(
                    select(Employee).where(Employee.status == "active")
                )
                employees = result.scalars().all()

                if should_be_at_home():
                    # It's 7pm-7am: employees should be at home
                    # Update employees who are currently not marked as being at home
                    for employee in employees:
                        # Only update if employee is currently not marked as being at home
                        if employee.activity_state not in ["at_home", "sleeping"]:
                            employee.activity_state = "at_home"
                            employee.current_room = None  # Clear office room
                            employee.target_room = None  # Clear office target
                            employee.floor = None  # Clear office floor
                else:
                    # It's 7am-7pm: employees should be at office
                    # Update employees who are currently at home to be at office
                    for employee in employees:
                        if employee.activity_state in ["at_home", "sleeping"]:
                            # Transition employee to office
                            if employee.home_room:
                                # Send them to their home room (office desk/workspace)
                                employee.current_room = employee.home_room
                                employee.floor = 1  # Default to floor 1
                            else:
                                # No home room assigned, put them in a common area
                                employee.current_room = "Open Workspace"
                                employee.floor = 1

                            employee.activity_state = "working"
                            employee.target_room = None

                await db.commit()
        except Exception as e:
            logger.error(f"Error updating employee locations based on time: {e}", exc_info=True)

    async def simulation_tick(self):
        """Execute one simulation tick."""
        # FIRST: Update employee locations based on time (7pm-7am home, 7am-7pm office)
        await self.update_employee_locations_based_on_time()

        # SECOND: Fix ALL idle employees immediately - they should be working!
        await self.fix_idle_employees()
        
        # Second: Fix employees walking without a destination - CRITICAL FIX
        try:
            async with async_session_maker() as db:
                # Ensure all employees in training rooms have active training sessions
                await self.ensure_training_sessions(db)
                
                # Check for and end expired training sessions (over 30 minutes)
                from business.training_manager import TrainingManager
                training_manager = TrainingManager()
                ended_count = await training_manager.check_and_end_expired_sessions(db)
                if ended_count > 0:
                    await db.commit()
                    logger.info(f"✅ Ended {ended_count} expired training sessions (over 30 minutes)")
                from engine.movement_system import fix_walking_employees_without_destination
                fixed = await fix_walking_employees_without_destination(db)
                if fixed > 0:
                    await db.commit()
                    logger.info(f"✅ Fixed {fixed} employees walking without destination")
                # Also check and fix any remaining walking employees without target_room
                from sqlalchemy import select, and_, or_
                from database.models import Employee
                result = await db.execute(
                    select(Employee).where(
                        and_(
                            Employee.status == "active",
                            Employee.activity_state == "walking",
                            or_(
                                Employee.target_room.is_(None),
                                Employee.target_room == ""
                            )
                        )
                    )
                )
                remaining = result.scalars().all()
                if remaining:
                    logger.warning(f"⚠️ Found {len(remaining)} employees still walking without destination after fix! Running additional fix...")
                    fixed2 = await fix_walking_employees_without_destination(db)
                    if fixed2 > 0:
                        await db.commit()
                        logger.info(f"✅ Additional fix: {fixed2} more employees fixed")
        except Exception as e:
            logger.error(f"Error fixing walking employees: {e}", exc_info=True)
        
        # Third: Enforce room capacity - detect and fix over-capacity rooms
        try:
            async with async_session_maker() as capacity_db:
                from engine.movement_system import enforce_room_capacity
                capacity_stats = await enforce_room_capacity(capacity_db)
                if capacity_stats["employees_redistributed"] > 0:
                    await capacity_db.commit()
                    logger.warning(f"🔧 Capacity enforcement: Fixed {capacity_stats['over_capacity_rooms']} over-capacity rooms, redistributed {capacity_stats['employees_redistributed']} employees")
        except Exception as e:
            logger.error(f"Error enforcing room capacity: {e}", exc_info=True)
        
        # Fourth: Fix any employees stuck in training rooms with waiting status
        await self.fix_waiting_in_training_rooms()
        
        # Fifth: Process waiting employees to retry their movement
        await self.process_waiting_employees()
        
        # System-level break enforcement (runs every tick to catch abuse immediately)
        try:
            async with async_session_maker() as break_db:
                from business.coffee_break_manager import CoffeeBreakManager
                break_manager = CoffeeBreakManager(break_db)
                enforcement_stats = await break_manager.enforce_break_limits_system_level()
                if enforcement_stats["total_returned"] > 0:
                    logger.info(f"[*] System-level break enforcement: returned {enforcement_stats['total_returned']} employee(s) to work ({enforcement_stats['managers_returned']} managers, {enforcement_stats['regular_employees_returned']} regular employees)")
        except Exception as e:
            logger.error(f"[-] Error in system-level break enforcement: {e}", exc_info=True)
        
        # Conduct periodic reviews every tick to ensure reviews happen promptly
        # This ensures we catch reviews as soon as they're due
        try:
            async with async_session_maker() as review_db:
                from business.review_manager import ReviewManager
                review_manager = ReviewManager(review_db)
                reviews_created = await review_manager.conduct_periodic_reviews(hours_since_last_review=6.0)
                # Commit is handled inside conduct_periodic_reviews, but ensure session stays open
                if reviews_created:
                    print(f"[+] Conducted {len(reviews_created)} employee performance reviews")
                    # Verify reviews are in the database by querying them
                    for review in reviews_created:
                        # Query back to verify persistence
                        verify_result = await review_db.execute(
                            select(EmployeeReview).where(EmployeeReview.id == review.id)
                        )
                        verified = verify_result.scalar_one_or_none()
                        if verified:
                            # Get employee and manager names for logging
                            emp_result = await review_db.execute(
                                select(Employee).where(Employee.id == review.employee_id)
                            )
                            emp = emp_result.scalar_one_or_none()
                            mgr_result = await review_db.execute(
                                select(Employee).where(Employee.id == review.manager_id)
                            )
                            mgr = mgr_result.scalar_one_or_none()
                            if emp and mgr:
                                print(f"   [*] {mgr.name} reviewed {emp.name} - Rating: {review.overall_rating}/5.0 (Review ID: {review.id})")
                        else:
                            print(f"   [!] WARNING: Review {review.id} not found after commit!")
        except Exception as e:
            import traceback
            print(f"[-] Error conducting periodic reviews: {e}")
            print(f"Traceback: {traceback.format_exc()}")
        
        # Update performance award periodically (every 4 minutes = 30 ticks)
        self.award_update_counter += 1
        if self.award_update_counter >= 30:  # 30 * 8 seconds = 240 seconds = 4 minutes
            self.award_update_counter = 0
            try:
                async with async_session_maker() as award_db:
                    from business.review_manager import ReviewManager
                    review_manager = ReviewManager(award_db)
                    print("[AWARD] Running performance award update from simulation tick...")
                    await review_manager._update_performance_award()
                    await award_db.commit()
                    print("[AWARD] Award update from simulation tick completed!")
            except Exception as e:
                import traceback
                print(f"[-] [AWARD] Error updating award in simulation tick: {e}")
                print(f"Traceback: {traceback.format_exc()}")
        
        # Generate boardroom discussions every 2 minutes (120 seconds)
        # Check every tick (8 seconds), so every 15 ticks = 2 minutes
        self.boardroom_discussion_counter += 1
        if self.boardroom_discussion_counter >= 15:  # 15 * 8 seconds = 120 seconds = 2 minutes
            self.boardroom_discussion_counter = 0
            try:
                async with async_session_maker() as boardroom_db:
                    from business.boardroom_manager import BoardroomManager
                    boardroom_manager = BoardroomManager(boardroom_db)
                    chats_created = await boardroom_manager.generate_boardroom_discussions()
                    if chats_created > 0:
                        print(f"💼 Generated {chats_created} boardroom discussions")
            except Exception as e:
                import traceback
                print(f"[-] Error generating boardroom discussions: {e}")
                print(f"Traceback: {traceback.format_exc()}")
        
        # Customer reviews are now handled by a dedicated background task (runs immediately, then every 30 minutes)
        # See generate_customer_reviews_periodically() method
        
        # Quick Wins Features Integration
        self.quick_wins_counter += 1
        now = local_now()
        current_date = now.date()
        
        # Check birthdays daily
        if self.last_birthday_check_date != current_date:
            self.last_birthday_check_date = current_date
            try:
                async with async_session_maker() as birthday_db:
                    from business.birthday_manager import BirthdayManager
                    birthday_manager = BirthdayManager(birthday_db)
                    birthdays = await birthday_manager.check_birthdays_today()
                    for emp in birthdays:
                        celebration = await birthday_manager.celebrate_birthday(emp)
                        if celebration:
                            print(f"🎂 Birthday celebration for {emp.name}!")
            except Exception as e:
                print(f"[-] Error checking birthdays: {e}")
        
        # Check holidays daily
        if self.last_holiday_check_date != current_date:
            self.last_holiday_check_date = current_date
            try:
                async with async_session_maker() as holiday_db:
                    from business.holiday_manager import HolidayManager
                    holiday_manager = HolidayManager(holiday_db)
                    holiday_name = await holiday_manager.check_holiday_today()
                    if holiday_name:
                        celebration = await holiday_manager.celebrate_holiday(holiday_name)
                        if celebration:
                            print(f"🎉 Holiday celebration: {holiday_name}!")
            except Exception as e:
                print(f"[-] Error checking holidays: {e}")
        
        # Update weather daily
        if self.last_weather_date != current_date:
            self.last_weather_date = current_date
            try:
                async with async_session_maker() as weather_db:
                    from business.weather_manager import WeatherManager
                    weather_manager = WeatherManager(weather_db)
                    await weather_manager.get_today_weather()
            except Exception as e:
                print(f"[-] Error updating weather: {e}")
        
        # Check for random events (every 20 ticks = ~2.5 minutes)
        if self.quick_wins_counter % 20 == 0:
            try:
                async with async_session_maker() as event_db:
                    from business.random_event_manager import RandomEventManager
                    event_manager = RandomEventManager(event_db)
                    await event_manager.resolve_expired_events()
                    event = await event_manager.check_for_random_event()
                    if event:
                        print(f"[!] Random event: {event.title}")
            except Exception as e:
                print(f"❌ Error checking random events: {e}")
        
        # Publish newsletter weekly (on Fridays)
        if now.weekday() == 4:  # Friday
            try:
                async with async_session_maker() as newsletter_db:
                    from business.newsletter_manager import NewsletterManager
                    newsletter_manager = NewsletterManager(newsletter_db)
                    if await newsletter_manager.should_publish_newsletter():
                        newsletter = await newsletter_manager.publish_newsletter()
                        if newsletter:
                            print(f"📰 Published newsletter issue #{newsletter.issue_number}")
            except Exception as e:
                print(f"❌ Error publishing newsletter: {e}")
        
        # Move pets occasionally (every 50 ticks = ~6.5 minutes)
        # Only move pets during work hours
        from config import is_work_hours
        if self.quick_wins_counter % 50 == 0 and is_work_hours():
            try:
                async with async_session_maker() as pet_db:
                    from business.pet_manager import PetManager
                    pet_manager = PetManager(pet_db)
                    pets = await pet_manager.get_all_pets()
                    if not pets:
                        pets = await pet_manager.initialize_pets()
                    for pet in pets:
                        await pet_manager.move_pet_randomly(pet)
            except Exception as e:
                print(f"❌ Error moving pets: {e}")
        
        # Check for pet interactions (every 5 ticks = ~40 seconds) - MUCH MORE FREQUENT
        # Only check for interactions during work hours
        if self.quick_wins_counter % 5 == 0 and is_work_hours():
            try:
                async with async_session_maker() as pet_interaction_db:
                    from business.pet_manager import PetManager
                    pet_manager = PetManager(pet_interaction_db, self.llm_client)
                    interactions = await pet_manager.check_pet_interactions()
                    if interactions:
                        print(f"🐾 {len(interactions)} pet interaction(s) occurred")
            except Exception as e:
                print(f"❌ Error checking pet interactions: {e}")
                import traceback
                traceback.print_exc()
        
        # Check for pets needing care and provide AI-powered care (every 10 ticks = ~1.3 minutes) - MUCH MORE FREQUENT
        # Only provide care during work hours
        if self.quick_wins_counter % 10 == 0 and is_work_hours():
            try:
                async with async_session_maker() as pet_care_db:
                    from business.pet_manager import PetManager
                    pet_manager = PetManager(pet_care_db, self.llm_client)
                    business_context = await get_business_context(pet_care_db)
                    care_logs = await pet_manager.check_and_provide_pet_care(business_context)
                    if care_logs:
                        print(f"🐾 AI provided care for {len(care_logs)} pet(s)")
            except Exception as e:
                print(f"❌ Error providing AI pet care: {e}")
                import traceback
                traceback.print_exc()
        
        # Run Communication Manager (every 10 ticks = ~1.3 minutes)
        if self.quick_wins_counter % 10 == 0:
            try:
                async with async_session_maker() as comm_db:
                    # Re-initialize with DB session
                    self.communication_manager.db = comm_db
                    business_context = await get_business_context(comm_db)
                    await self.communication_manager.run_cycle(comm_db, business_context)
            except Exception as e:
                print(f"❌ Error in communication manager: {e}")
                import traceback
                traceback.print_exc()
        
        # Check for meeting generation every hour (3600 seconds)
        # Check every tick (8 seconds), so every 450 ticks = 1 hour
        # Also check if it's a new day to ensure meetings are scheduled
        self.meeting_generation_counter += 1
        # now and current_date already defined above for quick wins
        
        # Check if it's a new day or if we should check (every hour)
        is_new_day = self.last_meeting_check_date is None or self.last_meeting_check_date != current_date
        should_check = is_new_day or self.meeting_generation_counter >= 450  # Every hour or new day
        
        if should_check:
            self.meeting_generation_counter = 0
            self.last_meeting_check_date = current_date
            
            try:
                async with async_session_maker() as meeting_db:
                    from business.meeting_manager import MeetingManager
                    from database.models import Meeting
                    
                    meeting_manager = MeetingManager(meeting_db)
                    
                    # Check if there are meetings scheduled for today
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    tomorrow_start = today_start + timedelta(days=1)
                    
                    result = await meeting_db.execute(
                        select(Meeting).where(
                            Meeting.start_time >= today_start,
                            Meeting.start_time < tomorrow_start
                        )
                    )
                    existing_meetings = result.scalars().all()
                    
                    # If it's a new day and there are no meetings, or if there are fewer than 3 meetings, generate them
                    if is_new_day and len(existing_meetings) == 0:
                        print(f"[*] New day detected ({current_date}), generating meetings for today...")
                        meetings_created = await meeting_manager.generate_meetings()
                        if meetings_created > 0:
                            print(f"[+] Generated {meetings_created} meetings for the new day")
                    elif len(existing_meetings) < 3:
                        print(f"[*] Only {len(existing_meetings)} meetings found for today, generating more...")
                        meetings_created = await meeting_manager.generate_meetings()
                        if meetings_created > 0:
                            print(f"[+] Generated {meetings_created} additional meetings for today")
                    else:
                        # Meetings already exist for today, no need to generate
                        pass
            except Exception as e:
                import traceback
                print(f"❌ Error generating meetings: {e}")
                print(f"Traceback: {traceback.format_exc()}")
        
        # Update meeting statuses every tick (check for in_progress and completed)
        # This MUST run every tick to keep meetings active
        try:
            async with async_session_maker() as meeting_status_db:
                from business.meeting_manager import MeetingManager
                meeting_manager = MeetingManager(meeting_status_db)
                await meeting_manager.update_meeting_status()
        except Exception as e:
            # Log errors but don't crash - but make them visible
            print(f"❌ CRITICAL: Error updating meeting status: {e}")
            import traceback
            traceback.print_exc()
        
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
                
                # Process up to 5 employees per tick (increased from 3 for more activity and communications)
                for employee in employee_list[:5]:
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
                            
                            # Quick Wins: Coffee break check
                            try:
                                from business.coffee_break_manager import CoffeeBreakManager
                                coffee_manager = CoffeeBreakManager(db)
                                if await coffee_manager.should_take_coffee_break(employee_instance):
                                    coffee_activity = await coffee_manager.take_coffee_break(employee_instance)
                                    # Broadcast coffee break
                                    await self.broadcast_activity({
                                        "type": "activity",
                                        "data": {
                                            "activity_type": coffee_activity.activity_type,
                                            "employee_id": employee_instance.id,
                                            "description": coffee_activity.description,
                                            "timestamp": coffee_activity.timestamp.isoformat()
                                        }
                                    })
                            except Exception as e:
                                pass  # Don't fail on coffee break errors
                            
                            # Quick Wins: Generate suggestion occasionally
                            try:
                                from business.suggestion_manager import SuggestionManager
                                suggestion_manager = SuggestionManager(db)
                                suggestion = await suggestion_manager.generate_suggestion(employee_instance)
                                if suggestion:
                                    await self.broadcast_activity({
                                        "type": "activity",
                                        "data": {
                                            "activity_type": "suggestion_submitted",
                                            "employee_id": employee_instance.id,
                                            "description": f"[*] {employee_instance.name} submitted a suggestion: {suggestion.title}",
                                            "timestamp": suggestion.created_at.isoformat()
                                        }
                                    })
                            except Exception as e:
                                pass  # Don't fail on suggestion errors
                            
                            # Quick Wins: Generate gossip occasionally when employees interact
                            if activity and activity.activity_type in ["communication", "meeting", "collaboration"]:
                                try:
                                    from business.gossip_manager import GossipManager
                                    gossip_manager = GossipManager(db)
                                    # Get a random other employee
                                    other_employees_result = await db.execute(
                                        select(Employee)
                                        .where(Employee.status == "active")
                                        .where(Employee.id != employee_instance.id)
                                    )
                                    other_employees = other_employees_result.scalars().all()
                                    if other_employees:
                                        recipient = random.choice(other_employees)
                                        gossip = await gossip_manager.generate_gossip(employee_instance, recipient)
                                        if gossip:
                                            await self.broadcast_activity({
                                                "type": "activity",
                                                "data": {
                                                    "activity_type": "gossip",
                                                    "employee_id": employee_instance.id,
                                                    "description": f"💬 {employee_instance.name} shared some gossip",
                                                    "timestamp": gossip.created_at.isoformat()
                                                }
                                            })
                                except Exception as e:
                                    pass  # Don't fail on gossip errors
                            
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
                                "timestamp": (activity.timestamp or local_now()).isoformat(),
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
                                "timestamp": local_now().isoformat()
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
                        
                        # Check for completed projects and trigger new project creation (30% chance per tick)
                        if random.random() < 0.3:  # 30% chance per tick
                            async with async_session_maker() as completion_db:
                                try:
                                    await self._handle_completed_projects(completion_db)
                                    await completion_db.commit()
                                except Exception as e:
                                    print(f"Error handling completed projects: {e}")
                                    await completion_db.rollback()
                        
                        # Check for projects at 100% and mark them as completed (EVERY TICK - critical for completion!)
                        async with async_session_maker() as completion_check_db:
                            try:
                                await self._check_and_complete_projects(completion_check_db)
                                await completion_check_db.commit()
                            except Exception as e:
                                print(f"Error checking project completion: {e}")
                                await completion_check_db.rollback()
                        
                        # Ensure projects and tasks are actively being worked on (50% chance per tick)
                        if random.random() < 0.5:  # 50% chance per tick
                            async with async_session_maker() as activity_db:
                                try:
                                    await self._ensure_active_work(activity_db)
                                    await activity_db.commit()
                                except Exception as e:
                                    print(f"Error ensuring active work: {e}")
                                    await activity_db.rollback()
                
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
                elif employee.role in ["CTO", "COO", "CFO"]:
                    salary = random.uniform(10000, 18000)  # C-level executives get higher salary
                elif employee.role == "Manager":
                    salary = random.uniform(8000, 15000)
                else:
                    salary = random.uniform(4000, 8000)
                total_salary += salary
            
            # Record salary expenses (only if we haven't recorded them recently)
            # Check if we've recorded salaries in the last 30 days
            cutoff = local_now() - timedelta(days=30)
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
        # Maximum staffing cap: Don't hire beyond 500 employees
        MAX_EMPLOYEES = 500
        
        print(f"📊 Employee Management: {active_count} active, profit: ${profit:,.2f}, revenue: ${revenue:,.2f}, max: {MAX_EMPLOYEES}")
        
        # Firing logic: Can fire employees with cause (performance issues, budget cuts, restructuring, etc.)
        # But we must maintain minimum staffing
        fired_this_tick = False
        if active_count > MIN_EMPLOYEES:
            # Priority 1: Check for employees with consistently bad performance reviews
            # These should be terminated regardless of budget
            employees_with_bad_reviews = await self._check_employees_with_bad_reviews(db, active_employees)
            if employees_with_bad_reviews:
                print(f"[!] Found {len(employees_with_bad_reviews)} employee(s) with consistently bad performance reviews - terminating")
                for employee in employees_with_bad_reviews:
                    if active_count > MIN_EMPLOYEES:
                        await self._fire_employee_for_performance(db, employee)
                        fired_this_tick = True
                        active_count -= 1
                        # Re-fetch active employees after firing
                        result = await db.execute(select(Employee).where(Employee.status == "active"))
                        active_employees = result.scalars().all()
            
            # Priority 2: Check for restructuring needs (overstaffing, department changes, etc.)
            if active_count > MIN_EMPLOYEES:
                restructuring_needed, restructuring_reason = await self._check_restructuring_needs(db, active_employees, business_context)
                if restructuring_needed:
                    logger.warning(f"[!] Restructuring needed: {restructuring_reason}")
                    if random.random() < 0.3:  # 30% chance to fire for restructuring
                        await self._fire_employee_for_restructuring(db, active_employees, restructuring_reason)
                        fired_this_tick = True
                        # Re-fetch active count after firing
                        result = await db.execute(select(Employee).where(Employee.status == "active"))
                        active_employees_after = result.scalars().all()
                        active_count = len(active_employees_after)
            
            # Priority 3: Budget-based termination (if losing money)
            if active_count > MIN_EMPLOYEES:
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
                    Employee.role.in_(["Manager", "CTO", "COO", "CFO"]),
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
                try:
                    await self._hire_employee(db, business_context)
                    print(f"Strategic hiring: Preparing for project growth ({active_count} employees, {project_count} projects, max: {MAX_EMPLOYEES})")
                except Exception as e:
                    print(f"❌ Error in strategic hiring: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Priority 6: Fallback growth hiring - if we're below max and have work, occasionally hire
        # This ensures we continue growing even when other conditions aren't met
        if active_count < MAX_EMPLOYEES and (project_count > 0 or unassigned_count > 0):
            # If we have work but are below max, occasionally hire to grow
            # Lower chance to avoid over-hiring, but ensures growth continues
            growth_chance = 0.15 if profit > 0 else 0.05  # 15% if profitable, 5% if not
            if random.random() < growth_chance:
                try:
                    hires = min(MAX_EMPLOYEES - active_count, random.randint(1, 2))
                    if hires > 0:
                        for _ in range(hires):
                            await self._hire_employee(db, business_context)
                        print(f"Growth hiring (fallback): Hired {hires} employee(s) (current: {active_count}, projects: {project_count}, tasks: {unassigned_count}, max: {MAX_EMPLOYEES})")
                except Exception as e:
                    print(f"❌ Error in fallback growth hiring: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Final summary - get updated count
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        final_active_employees = result.scalars().all()
        final_count = len(final_active_employees)
        
        if final_count != active_count:
            logger.info(f"📈 Employee count changed: {active_count} → {final_count} (delta: {final_count - active_count})")
        else:
            logger.info(f"📊 No employee count change this tick (still {final_count}/{MAX_EMPLOYEES})")
    
    async def _hire_employee(self, db: AsyncSession, business_context: dict):
        """Hire a new employee."""
        try:
            from database.models import Employee, Activity
            from datetime import datetime
            import random
            
            departments = ["Engineering", "Product", "Marketing", "Sales", "Operations", "IT", "Administration", "HR", "Design"]
            roles = ["Employee", "Manager"]
            
            # Get existing employee names to avoid duplicates
            result = await db.execute(select(Employee.name))
            existing_names = [row[0] for row in result.all()]
            
            # Generate unique employee name using AI
            role = random.choice(roles)
            department = random.choice(departments)
            hierarchy_level = 2 if role in ["Manager", "CTO", "COO", "CFO"] else 3
            
            name = await self.llm_client.generate_unique_employee_name(
                existing_names=existing_names,
                department=department,
                role=role
            )
            
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
            
            # Special handling for IT and Reception to ensure they get appropriate titles
            if department == "IT":
                if role in ["Manager", "CTO", "COO", "CFO"]:
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
            
            # Assign random birthday
            birthday_month = random.randint(1, 12)
            if birthday_month in [1, 3, 5, 7, 8, 10, 12]:
                max_day = 31
            elif birthday_month in [4, 6, 9, 11]:
                max_day = 30
            else:  # February
                max_day = 28
            birthday_day = random.randint(1, max_day)
            
            # Assign random hobbies
            hobbies_list = [
                ["photography", "hiking", "cooking"],
                ["reading", "yoga", "gardening"],
                ["gaming", "music", "traveling"],
                ["sports", "writing", "painting"],
                ["reading", "chess", "puzzles"]
            ]
            hobbies = random.choice(hobbies_list)
            
            new_employee = Employee(
                name=name,
                title=title,
                role=role,
                hierarchy_level=hierarchy_level,
                department=department,
                status="active",
                personality_traits=personality_traits,
                backstory=f"{name} joined the team to help drive growth and innovation.",
                hired_at=local_now(),
                birthday_month=birthday_month,
                birthday_day=birthday_day,
                hobbies=hobbies
            )
            db.add(new_employee)
            await db.flush()  # Flush to get the employee ID
            
            # Assign home room and floor based on role/department
            home_room, floor = await assign_home_room(new_employee, db)
            new_employee.home_room = home_room
            new_employee.floor = floor
            
            # New hires start in training room - find any available training room
            from employees.room_assigner import ROOM_TRAINING_ROOM
            from engine.movement_system import find_available_training_room
            
            # Find an available training room (checks all floors including floor 4 overflow)
            training_room = await find_available_training_room(db, exclude_employee_id=None)
            
            if not training_room:
                # All training rooms are full - use floor 4 as fallback (it has the most capacity)
                training_room = f"{ROOM_TRAINING_ROOM}_floor4"
                new_employee.floor = 4
            else:
                # Update floor based on training room location
                if training_room.endswith('_floor2'):
                    new_employee.floor = 2
                elif training_room.endswith('_floor4') or '_floor4_' in training_room:
                    new_employee.floor = 4
                else:
                    new_employee.floor = 1
            
            new_employee.current_room = training_room
            new_employee.activity_state = "training"  # Mark as in training
            
            # Create training session immediately for new hire
            try:
                from business.training_manager import TrainingManager
                training_manager = TrainingManager()
                await training_manager.start_training_session(new_employee, training_room, db)
                await db.flush()
            except Exception as e:
                print(f"Error creating training session for new hire {new_employee.name}: {e}")
                import traceback
                traceback.print_exc()
            
            # Create activity
            activity = Activity(
                employee_id=None,
                activity_type="hiring",
                description=f"Hired {name} as {title} in {department} - Starting training",
                activity_metadata={"employee_id": None, "action": "hire"}
            )
            db.add(activity)
            
            await db.flush()
            activity.activity_metadata["employee_id"] = new_employee.id
            # Broadcast activity
            try:
                from business.activity_broadcaster import broadcast_activity
                await broadcast_activity(activity, db, new_employee)
            except:
                pass  # Don't fail if broadcasting fails
            
            # Create notification for employee hire
            from database.models import Notification
            notification = Notification(
                notification_type="employee_hired",
                title=f"New Employee Hired: {name}",
                message=f"{name} has been hired as {title} in the {department} department.",
                employee_id=new_employee.id,
                review_id=None,
                read=False
            )
            db.add(notification)
            
            await db.commit()
            
            # Generate birthday party meeting for new employee if birthday is within 90 days
            try:
                from business.birthday_manager import BirthdayManager
                birthday_manager = BirthdayManager(db)
                result = await birthday_manager.generate_birthday_party_for_employee(new_employee)
                if result and result.get("created"):
                    print(f"🎂 Generated birthday party meeting for {name}")
            except Exception as e:
                print(f"Warning: Could not generate birthday party for {name}: {e}")
            
            print(f"Hired new employee: {name} ({title})")
        except Exception as e:
            print(f"❌ Error hiring employee: {e}")
            import traceback
            traceback.print_exc()
            # Re-raise to let caller know hiring failed
            raise
    
    async def _hire_employee_specific(self, db: AsyncSession, business_context: dict, 
                                     department: str = None, title: str = None, role: str = "Employee"):
        """Hire a specific type of employee (e.g., IT, Reception)."""
        from database.models import Employee, Activity
        from datetime import datetime
        import random
        
        # Get existing employee names to avoid duplicates
        result = await db.execute(select(Employee.name))
        existing_names = [row[0] for row in result.all()]
        
        hierarchy_level = 2 if role in ["Manager", "CTO", "COO", "CFO"] else 3
        
        # Generate unique employee name using AI
        name = await self.llm_client.generate_unique_employee_name(
            existing_names=existing_names,
            department=department,
            role=role
        )
        
        # Determine title and department based on parameters
        if title:
            employee_title = title
        elif department == "IT":
            if role in ["Manager", "CTO", "COO", "CFO"]:
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
        
        # Assign random birthday
        birthday_month = random.randint(1, 12)
        if birthday_month in [1, 3, 5, 7, 8, 10, 12]:
            max_day = 31
        elif birthday_month in [4, 6, 9, 11]:
            max_day = 30
        else:  # February
            max_day = 28
        birthday_day = random.randint(1, max_day)
        
        # Assign random hobbies
        hobbies_list = [
            ["photography", "hiking", "cooking"],
            ["reading", "yoga", "gardening"],
            ["gaming", "music", "traveling"],
            ["sports", "writing", "painting"],
            ["reading", "chess", "puzzles"]
        ]
        hobbies = random.choice(hobbies_list)
        
        new_employee = Employee(
            name=name,
            title=employee_title,
            role=role,
            hierarchy_level=hierarchy_level,
            department=department,
            status="active",
            personality_traits=personality_traits,
            backstory=f"{name} joined the team to help drive growth and innovation.",
            hired_at=local_now(),
            birthday_month=birthday_month,
            birthday_day=birthday_day,
            hobbies=hobbies
        )
        db.add(new_employee)
        await db.flush()  # Flush to get the employee ID
        
        # Assign home room and floor based on role/department
        home_room, floor = await assign_home_room(new_employee, db)
        new_employee.home_room = home_room
        new_employee.floor = floor
        
        # New hires start in training room - find any available training room
        from employees.room_assigner import ROOM_TRAINING_ROOM
        from engine.movement_system import find_available_training_room
        
        # Find an available training room (checks all floors including floor 4 overflow)
        training_room = await find_available_training_room(db, exclude_employee_id=None)
        
        if not training_room:
            # All training rooms are full - use floor 4 as fallback (it has the most capacity)
            training_room = f"{ROOM_TRAINING_ROOM}_floor4"
            new_employee.floor = 4
        else:
            # Update floor based on training room location
            if training_room.endswith('_floor2'):
                new_employee.floor = 2
            elif training_room.endswith('_floor4') or '_floor4_' in training_room:
                new_employee.floor = 4
            else:
                new_employee.floor = 1
        
        new_employee.current_room = training_room
        new_employee.activity_state = "training"  # Mark as in training
        
        # Create training session immediately for new hire
        try:
            from business.training_manager import TrainingManager
            training_manager = TrainingManager()
            await training_manager.start_training_session(new_employee, training_room, db)
            await db.flush()
        except Exception as e:
            print(f"Error creating training session for new hire {new_employee.name}: {e}")
            import traceback
            traceback.print_exc()
        
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
        
        # Create notification for employee hire
        from database.models import Notification
        notification = Notification(
            notification_type="employee_hired",
            title=f"New Employee Hired: {name}",
            message=f"{name} has been hired as {employee_title} in the {department} department.",
            employee_id=new_employee.id,
            review_id=None,
            read=False
        )
        db.add(notification)
        
        await db.commit()
        
        # Generate birthday party meeting for new employee if birthday is within 90 days
        try:
            from business.birthday_manager import BirthdayManager
            birthday_manager = BirthdayManager(db)
            result = await birthday_manager.generate_birthday_party_for_employee(new_employee)
            if result and result.get("created"):
                print(f"🎂 Generated birthday party meeting for {name}")
        except Exception as e:
            print(f"Warning: Could not generate birthday party for {name}: {e}")
        
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
        
        # Prefer firing employees over managers and C-level executives (70% chance)
        if random.random() < 0.7:
            candidates = [e for e in candidates if e.role == "Employee"]
        
        if not candidates:
            # Don't fire CEO or C-level executives
            candidates = [e for e in active_employees if e.role not in ["CEO", "CTO", "COO", "CFO"]]
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
        
        # Prioritize employees with poor reviews
        from business.review_manager import ReviewManager
        review_manager = ReviewManager(db)
        
        # Get average ratings for candidates
        candidate_ratings = {}
        for candidate in candidates:
            avg_rating = await review_manager.get_average_rating(candidate.id)
            if avg_rating:
                candidate_ratings[candidate.id] = avg_rating
            else:
                # If no reviews, give neutral rating
                candidate_ratings[candidate.id] = 3.0
        
        # Sort candidates by rating (lowest first - more likely to fire)
        candidates_with_ratings = [(c, candidate_ratings.get(c.id, 3.0)) for c in candidates]
        candidates_with_ratings.sort(key=lambda x: x[1])
        
        # Weight selection: 60% chance to pick from bottom 30% (worst performers)
        if random.random() < 0.6 and len(candidates_with_ratings) > 3:
            bottom_count = max(1, len(candidates_with_ratings) // 3)
            worst_candidates = [c for c, _ in candidates_with_ratings[:bottom_count]]
            employee_to_fire = random.choice(worst_candidates)
        else:
            # Random selection from all candidates
            employee_to_fire = random.choice(candidates)
        
        # Generate AI termination reason based on business context and reviews
        business_context = await self.get_business_context(db)
        avg_rating = candidate_ratings.get(employee_to_fire.id, 3.0)
        termination_reason = await self._generate_termination_reason(
            employee_to_fire, 
            business_context
        )
        
        employee_to_fire.status = "fired"
        employee_to_fire.fired_at = local_now()
        
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
        
        # Create notification for employee termination
        from database.models import Notification
        notification = Notification(
            notification_type="employee_fired",
            title=f"Employee Terminated: {employee_to_fire.name}",
            message=f"{employee_to_fire.name} ({employee_to_fire.title}) has been terminated. Reason: {termination_reason}",
            employee_id=employee_to_fire.id,
            review_id=None,
            read=False
        )
        db.add(notification)
        
        await db.commit()
        print(f"Fired employee: {employee_to_fire.name} ({employee_to_fire.title}) - Reason: {termination_reason}")
    
    async def _check_employees_with_bad_reviews(self, db: AsyncSession, active_employees: list) -> list:
        """
        Check for employees with consistently bad performance reviews.
        Returns list of employees who have 3+ consecutive reviews below 2.0.
        """
        from business.review_manager import ReviewManager
        from sqlalchemy import desc
        
        review_manager = ReviewManager(db)
        employees_to_terminate = []
        
        for employee in active_employees:
            # Skip CEO and C-level executives
            if employee.role in ["CEO", "CTO", "COO", "CFO"]:
                continue
            
            # Get recent reviews (last 5)
            recent_reviews = await review_manager.get_recent_reviews(employee.id, limit=5)
            
            if len(recent_reviews) >= 3:
                # Check if last 3 reviews are all below 2.0
                last_3_reviews = recent_reviews[:3]
                all_bad = all(review.overall_rating < 2.0 for review in last_3_reviews)
                
                if all_bad:
                    avg_rating = sum(review.overall_rating for review in last_3_reviews) / 3
                    print(f"  ⚠️  {employee.name} has 3+ consecutive bad reviews (avg: {avg_rating:.1f}/5.0) - marked for termination")
                    employees_to_terminate.append(employee)
        
        return employees_to_terminate
    
    async def _check_restructuring_needs(self, db: AsyncSession, active_employees: list, business_context: dict) -> tuple:
        """
        Check if restructuring is needed (overstaffing, department changes, etc.)
        Returns (needs_restructuring: bool, reason: str)
        """
        from sqlalchemy import func
        
        # Check for overstaffing in departments
        department_counts = {}
        for emp in active_employees:
            dept = emp.department or "Unassigned"
            department_counts[dept] = department_counts.get(dept, 0) + 1
        
        # If any department has more than 30 employees, consider restructuring
        for dept, count in department_counts.items():
            if count > 30:
                return True, f"Overstaffing in {dept} department ({count} employees)"
        
        # Check if we're significantly over the optimal employee count
        # Optimal is roughly 3 employees per active project
        active_projects = business_context.get('active_projects', 0)
        optimal_employee_count = active_projects * 3 + 20  # Base + project support
        current_count = len(active_employees)
        
        if current_count > optimal_employee_count * 1.5:  # 50% over optimal
            return True, f"Organizational restructuring needed - {current_count} employees vs optimal {optimal_employee_count}"
        
        # Check if profit is negative and we have too many employees
        profit = business_context.get('profit', 0)
        if profit < -10000 and current_count > 50:
            return True, f"Cost-cutting restructuring due to financial losses (${profit:,.2f})"
        
        return False, ""
    
    async def _fire_employee_for_performance(self, db: AsyncSession, employee):
        """
        Fire an employee specifically for consistently bad performance reviews.
        """
        from database.models import Activity, Notification
        from datetime import datetime
        from business.review_manager import ReviewManager
        
        review_manager = ReviewManager(db)
        recent_reviews = await review_manager.get_recent_reviews(employee.id, limit=3)
        avg_rating = sum(review.overall_rating for review in recent_reviews) / len(recent_reviews) if recent_reviews else 2.0
        
        business_context = await self.get_business_context(db)
        termination_reason = f"Terminated due to consistently poor performance reviews. Average rating over last {len(recent_reviews)} reviews: {avg_rating:.1f}/5.0. Performance did not meet company standards despite feedback and opportunities for improvement."
        
        employee.status = "fired"
        employee.fired_at = local_now()
        employee.current_task_id = None
        
        # Create activity with termination reason
        activity = Activity(
            employee_id=None,
            activity_type="firing",
            description=f"Terminated {employee.name} ({employee.title}) for consistently poor performance. Average rating: {avg_rating:.1f}/5.0",
            activity_metadata={
                "employee_id": employee.id,
                "action": "fire",
                "termination_reason": termination_reason,
                "termination_type": "performance",
                "average_rating": avg_rating,
                "review_count": len(recent_reviews)
            }
        )
        db.add(activity)
        
        # Create notification
        notification = Notification(
            notification_type="employee_fired",
            title=f"Employee Terminated: {employee.name}",
            message=f"{employee.name} ({employee.title}) has been terminated due to consistently poor performance reviews (avg: {avg_rating:.1f}/5.0).",
            employee_id=employee.id,
            read=False
        )
        db.add(notification)
        
        await db.commit()
        print(f"🔥 Fired {employee.name} ({employee.title}) for consistently poor performance (avg rating: {avg_rating:.1f}/5.0)")
    
    async def _fire_employee_for_restructuring(self, db: AsyncSession, active_employees: list, restructuring_reason: str):
        """
        Fire an employee specifically for restructuring reasons.
        """
        from database.models import Activity, Notification
        from datetime import datetime
        from sqlalchemy import select
        
        # Don't fire CEO or C-level executives
        candidates = [e for e in active_employees if e.role not in ["CEO", "CTO", "COO", "CFO"]]
        
        if not candidates:
            return
        
        # Prefer firing regular employees over managers (70% chance)
        if random.random() < 0.7:
            candidates = [e for e in candidates if e.role == "Employee"]
        
        if not candidates:
            candidates = [e for e in active_employees if e.role not in ["CEO", "CTO", "COO", "CFO"]]
        
        # Select employee to fire (prefer those in overstaffed departments or with lower performance)
        employee_to_fire = random.choice(candidates)
        
        business_context = await self.get_business_context(db)
        termination_reason = f"Terminated as part of organizational restructuring. {restructuring_reason}"
        
        employee_to_fire.status = "fired"
        employee_to_fire.fired_at = local_now()
        employee_to_fire.current_task_id = None
        
        # Create activity with termination reason
        activity = Activity(
            employee_id=None,
            activity_type="firing",
            description=f"Terminated {employee_to_fire.name} ({employee_to_fire.title}) as part of restructuring. {restructuring_reason}",
            activity_metadata={
                "employee_id": employee_to_fire.id,
                "action": "fire",
                "termination_reason": termination_reason,
                "termination_type": "restructuring",
                "restructuring_reason": restructuring_reason
            }
        )
        db.add(activity)
        
        # Create notification
        notification = Notification(
            notification_type="employee_fired",
            title=f"Employee Terminated: {employee_to_fire.name}",
            message=f"{employee_to_fire.name} ({employee_to_fire.title}) has been terminated as part of organizational restructuring. {restructuring_reason}",
            employee_id=employee_to_fire.id,
            read=False
        )
        db.add(notification)
        
        await db.commit()
        print(f"🔥 Fired {employee_to_fire.name} ({employee_to_fire.title}) for restructuring: {restructuring_reason}")
    
    async def _manage_project_capacity(self, db: AsyncSession):
        """Periodically review project capacity and hire employees if needed instead of canceling."""
        from business.project_manager import ProjectManager
        from database.models import Activity
        
        # Maximum staffing cap: Don't hire beyond 500 employees
        MAX_EMPLOYEES = 500
        
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
            # Respect max cap of 500 employees
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
                    try:
                        for _ in range(hires_needed):
                            await self._hire_employee(db, business_context)
                    except Exception as e:
                        print(f"❌ Error in capacity management hiring: {e}")
                        import traceback
                        traceback.print_exc()
                
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
    
    async def _handle_completed_projects(self, db: AsyncSession):
        """Monitor for completed projects and ensure new ones are created to maintain growth."""
        from business.project_manager import ProjectManager
        from database.models import Project, Activity, Employee
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        project_manager = ProjectManager(db)
        
        # Check for projects completed in the last 2 hours (recently completed)
        cutoff_time = local_now() - timedelta(hours=2)
        result = await db.execute(
            select(Project).where(
                Project.status == "completed",
                Project.completed_at >= cutoff_time
            )
        )
        recently_completed = result.scalars().all()
        
        if not recently_completed:
            return
        
        # Get active projects count
        active_projects = await project_manager.get_active_projects()
        active_count = len(active_projects)
        
        # Get employee count
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        active_employees = result.scalars().all()
        employee_count = len(active_employees)
        max_projects = max(1, int(employee_count / 3))
        
        # For each recently completed project, check if we need to create a replacement
        for completed_project in recently_completed:
            # Check if we already created a replacement project for this completion
            # (to avoid creating multiple projects for the same completion)
            result = await db.execute(
                select(Project).where(
                    Project.status.in_(["planning", "active"]),
                    Project.created_at >= completed_project.completed_at
                )
            )
            replacement_projects = result.scalars().all()
            
            # Only create if we haven't already created a replacement
            if len(replacement_projects) == 0:
                # Check capacity
                can_create, reason = await project_manager.check_capacity_for_new_project()
                
                # Create new project to replace completed one (even if at capacity, we'll hire)
                project_names = [
                    "Growth Initiative",
                    "Next Phase Expansion",
                    "Market Development Project",
                    "Innovation Drive",
                    "Strategic Growth Program",
                    "Business Expansion Initiative",
                    "Revenue Growth Project",
                    "Market Penetration Strategy",
                    "Company Growth Initiative"
                ]
                
                project_name = random.choice(project_names)
                project = await project_manager.create_project(
                    name=project_name,
                    description=f"New project launched following completion of '{completed_project.name}' to maintain company growth and momentum",
                    priority="high",
                    budget=random.uniform(50000, 200000)
                )
                
                # Log project creation
                activity = Activity(
                    employee_id=None,
                    activity_type="project_created",
                    description=f"New project '{project_name}' launched following completion of '{completed_project.name}' to drive company growth",
                    activity_metadata={
                        "project_id": project.id,
                        "project_name": project_name,
                        "triggered_by": "project_completion",
                        "completed_project_id": completed_project.id,
                        "completed_project_name": completed_project.name,
                        "system_generated": True
                    }
                )
                db.add(activity)
                await db.flush()
                # Broadcast activity
                try:
                    from business.activity_broadcaster import broadcast_activity
                    await broadcast_activity(activity, db, None)
                except:
                    pass  # Don't fail if broadcasting fails
                print(f"System: Created new project '{project_name}' following completion of '{completed_project.name}' to maintain growth (active: {active_count}/{max_projects})")
                
                # If at capacity, note that hiring will be needed
                if not can_create:
                    activity = Activity(
                        employee_id=None,
                        activity_type="decision",
                        description=f"New project '{project_name}' created following project completion. Additional hiring will be needed to support growth.",
                        activity_metadata={
                            "decision_type": "growth_focus",
                            "action": "project_created_at_capacity",
                            "project_id": project.id,
                            "reason": reason
                        }
                    )
                    db.add(activity)
                    await db.flush()
                    # Broadcast activity
                    try:
                        from business.activity_broadcaster import broadcast_activity
                        await broadcast_activity(activity, db, None)
                    except:
                        pass  # Don't fail if broadcasting fails
    
    async def _check_and_complete_projects(self, db: AsyncSession):
        """Check all active projects and mark those at 100% as completed."""
        from business.project_manager import ProjectManager
        from database.models import Project
        
        project_manager = ProjectManager(db)
        
        # Get all active projects (planning and active status)
        active_projects = await project_manager.get_active_projects()
        
        if not active_projects:
            return
        
        completed_count = 0
        for project in active_projects:
            if project.status not in ["completed", "cancelled"]:
                # Calculate progress - this will automatically call ensure_project_completion if at 100%
                progress = await project_manager.calculate_project_progress(project.id)
                
                # Explicitly ensure completion - this handles both progress-based and task-based completion
                await project_manager.ensure_project_completion(project.id, progress)
                
                # Refresh project to check if status changed
                await db.refresh(project, ["status", "completed_at"])
                if project.status == "completed":
                    completed_count += 1
                    print(f"✅ Project '{project.name}' (ID: {project.id}) marked as completed - Progress: {progress:.1f}%")
        
        if completed_count > 0:
            print(f"✅ Completed {completed_count} project(s) that reached completion criteria")
    
    async def _ensure_active_work(self, db: AsyncSession):
        """Ensure projects and tasks are actively being worked on."""
        from business.project_manager import ProjectManager
        from database.models import Project, Task, Employee, Activity
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        project_manager = ProjectManager(db)
        
        # Get active projects
        active_projects = await project_manager.get_active_projects()
        
        if not active_projects:
            return
        
        # Check for stalled projects (no activity in last 24 hours)
        now = local_now()
        cutoff_time = now - timedelta(hours=24)
        
        stalled_projects = []
        for project in active_projects:
            # Check if project has recent activity
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
                
                if (now - last_activity) > timedelta(hours=24):
                    stalled_projects.append(project)
            else:
                # No activity timestamp - check if project has tasks
                result = await db.execute(
                    select(Task).where(Task.project_id == project.id)
                )
                tasks = result.scalars().all()
                if tasks:
                    # Has tasks but no activity - might be stalled
                    stalled_projects.append(project)
        
        # For stalled projects, ensure tasks are assigned and being worked on
        for project in stalled_projects:
            # Get tasks for this project
            result = await db.execute(
                select(Task).where(
                    Task.project_id == project.id,
                    Task.status.in_(["pending", "in_progress"])
                )
            )
            project_tasks = result.scalars().all()
            
            if not project_tasks:
                # No tasks - create some
                task_descriptions = [
                    f"Work on {project.name}",
                    f"Continue development for {project.name}",
                    f"Progress on {project.name}",
                    f"Implementation for {project.name}",
                    f"Testing for {project.name}"
                ]
                num_tasks = random.randint(2, 4)
                for i in range(num_tasks):
                    task = Task(
                        employee_id=None,
                        project_id=project.id,
                        description=random.choice(task_descriptions),
                        status="pending",
                        priority=project.priority,
                        progress=0.0
                    )
                    db.add(task)
                await db.flush()
                print(f"Created tasks for stalled project: {project.name}")
            else:
                # Check for unassigned tasks
                unassigned_tasks = [t for t in project_tasks if t.employee_id is None]
                
                if unassigned_tasks:
                    # Get available employees (not in training, not busy)
                    result = await db.execute(
                        select(Employee).where(
                            Employee.status == "active",
                            Employee.current_task_id.is_(None)
                        )
                    )
                    available_employees = result.scalars().all()
                    
                    # Filter out employees in training
                    from employees.room_assigner import ROOM_TRAINING_ROOM
                    
                    assignable_employees = []
                    for emp in available_employees:
                        is_in_training = False
                        
                        if hasattr(emp, 'activity_state') and emp.activity_state == "training":
                            is_in_training = True
                        
                        current_room = getattr(emp, 'current_room', None)
                        if (current_room == ROOM_TRAINING_ROOM or 
                            current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_2" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_3" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_4" or
                            current_room == f"{ROOM_TRAINING_ROOM}_floor4_5"):
                            is_in_training = True
                        
                        hired_at = getattr(emp, 'hired_at', None)
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
                            assignable_employees.append(emp)
                    
                    # PRIORITY: Sort tasks by: 1) Project priority (high > medium > low), 2) Revenue, 3) Progress
                    # This ensures we focus on high-priority, high-revenue projects first
                    task_priorities = []
                    priority_weights = {"high": 3, "medium": 2, "low": 1}
                    
                    for task in unassigned_tasks:
                        if task.project_id:
                            # Fetch project to get priority and revenue
                            result = await db.execute(
                                select(Project).where(Project.id == task.project_id)
                            )
                            task_project = result.scalar_one_or_none()
                            
                            if task_project:
                                project_progress = await project_manager.calculate_project_progress(task.project_id)
                                priority_weight = priority_weights.get(task_project.priority, 1)
                                revenue = task_project.revenue or 0.0
                                
                                # Calculate priority score: priority (0-3) * 1000 + revenue + progress
                                # This ensures high-priority projects always come first, then by revenue, then by progress
                                priority_score = (priority_weight * 1000) + (revenue / 1000) + project_progress
                                task_priorities.append((task, priority_score, task_project.priority, revenue, project_progress))
                            else:
                                task_priorities.append((task, 0.0, "low", 0.0, 0.0))
                        else:
                            task_priorities.append((task, 0.0, "low", 0.0, 0.0))
                    
                    # Sort by priority score (descending) - high-priority, high-revenue projects get priority
                    task_priorities.sort(key=lambda x: x[1], reverse=True)
                    prioritized_tasks = [task for task, _, _, _, _ in task_priorities]
                    
                    # Assign tasks to available employees (prioritizing high-priority, high-revenue projects)
                    assigned_count = 0
                    for task in prioritized_tasks[:len(assignable_employees)]:
                        if assignable_employees:
                            employee = random.choice(assignable_employees)
                            task.employee_id = employee.id
                            task.status = "in_progress"
                            employee.current_task_id = task.id
                            assignable_employees.remove(employee)
                            assigned_count += 1
                            
                            # Update project activity
                            await project_manager.update_project_activity(project.id)
                            
                            # Activate project if in planning
                            if project.status == "planning":
                                project.status = "active"
                    
                    if assigned_count > 0:
                        print(f"Assigned {assigned_count} task(s) to restart work on stalled project: {project.name}")
                
                # Update project activity even if tasks are assigned (to show it's being monitored)
                await project_manager.update_project_activity(project.id)
        
        # Also check for tasks that haven't made progress in a while
        result = await db.execute(
            select(Task).where(
                Task.status == "in_progress",
                Task.employee_id.isnot(None)
            )
        )
        in_progress_tasks = result.scalars().all()
        
        # Check for tasks with employees that might be stuck
        stuck_tasks = []
        for task in in_progress_tasks:
            # If task has been in progress for more than 2 hours with no progress update
            # (we can't easily track last progress update, so we'll check if progress is very low)
            if task.progress is not None and task.progress < 10:
                # Check if employee is actually working
                result = await db.execute(
                    select(Employee).where(Employee.id == task.employee_id)
                )
                employee = result.scalar_one_or_none()
                
                if employee and employee.current_task_id == task.id:
                    # Employee has the task assigned - ensure they're working
                    # Update project activity to show monitoring
                    if task.project_id:
                        await project_manager.update_project_activity(task.project_id)
                else:
                    # Task assigned but employee doesn't have it as current task - reassign
                    stuck_tasks.append(task)
        
        # Reassign stuck tasks
        if stuck_tasks:
            result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.current_task_id.is_(None)
                )
            )
            available_employees = result.scalars().all()
            
            # Filter out training employees
            from employees.room_assigner import ROOM_TRAINING_ROOM
            assignable_employees = []
            for emp in available_employees:
                is_in_training = False
                if hasattr(emp, 'activity_state') and emp.activity_state == "training":
                    is_in_training = True
                current_room = getattr(emp, 'current_room', None)
                if (current_room == ROOM_TRAINING_ROOM or 
                    current_room == f"{ROOM_TRAINING_ROOM}_floor2" or
                    current_room == f"{ROOM_TRAINING_ROOM}_floor4"):
                    is_in_training = True
                if not is_in_training:
                    assignable_employees.append(emp)
            
            reassigned_count = 0
            for task in stuck_tasks[:len(assignable_employees)]:
                if assignable_employees:
                    employee = random.choice(assignable_employees)
                    task.employee_id = employee.id
                    employee.current_task_id = task.id
                    assignable_employees.remove(employee)
                    reassigned_count += 1
                    
                    if task.project_id:
                        await project_manager.update_project_activity(task.project_id)
            
            if reassigned_count > 0:
                print(f"Reassigned {reassigned_count} stuck task(s) to ensure work continues")
    
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
    
    async def update_meetings_frequently(self):
        """Background task to update meeting status and generate live content very frequently (every 2-3 seconds)."""
        print("[*] Starting frequent meeting update background task...")
        from database.database import retry_on_lock
        from sqlalchemy.exc import OperationalError
        
        while self.running:
            try:
                async def update_meetings():
                    async with async_session_maker() as meeting_db:
                        from business.meeting_manager import MeetingManager
                        meeting_manager = MeetingManager(meeting_db)
                        await meeting_manager.update_meeting_status()
                
                # Use retry logic for database operations
                await retry_on_lock(update_meetings, max_retries=3, initial_delay=1.0)
                await asyncio.sleep(10)  # Update meetings every 10 seconds (slower pace, one message at a time)
            except OperationalError as e:
                if "database is locked" in str(e):
                    print(f"❌ Meeting update failed after retries (database locked)")
                    await asyncio.sleep(5)  # Wait longer before retrying
                else:
                    print(f"❌ Error in frequent meeting update: {e}")
                    import traceback
                    traceback.print_exc()
                    await asyncio.sleep(2)  # Wait a bit before retrying
            except Exception as e:
                print(f"❌ Error in frequent meeting update: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(2)  # Wait a bit before retrying
    
    async def update_performance_award_periodically(self):
        """Background task to periodically update the performance award (every 5 minutes)."""
        print("[*] Starting performance award update background task...")
        # Run immediately on startup
        try:
            async with async_session_maker() as award_db:
                from business.review_manager import ReviewManager
                review_manager = ReviewManager(award_db)
                print("[AWARD] Running initial performance award update on startup...")
                await review_manager._update_performance_award()
                await award_db.commit()
                print("[AWARD] Initial award update completed!")
        except Exception as e:
            print(f"[-] [AWARD] Error in initial award update: {e}")
            import traceback
            traceback.print_exc()
        
        # Then run periodically every 5 minutes
        while self.running:
            try:
                await asyncio.sleep(300)  # Wait 5 minutes (300 seconds)
                if not self.running:
                    break
                    
                async with async_session_maker() as award_db:
                    from business.review_manager import ReviewManager
                    review_manager = ReviewManager(award_db)
                    print("[AWARD] Running periodic performance award update...")
                    await review_manager._update_performance_award()
                    await award_db.commit()
                    print("[AWARD] Periodic award update completed!")
            except Exception as e:
                print(f"[-] [AWARD] Error in periodic award update: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)  # Wait 1 minute before retrying on error
    
    async def update_goals_daily(self):
        """Background task to update business goals daily at midnight (00:00)."""
        from datetime import datetime, time, timezone, timedelta
        
        print("[*] Starting daily goal update background task...")
        
        # Check immediately on startup
        try:
            async with async_session_maker() as goal_db:
                from business.goal_system import GoalSystem
                goal_system = GoalSystem(goal_db)
                
                # Check if goals need to be updated today
                if await goal_system.should_update_goals_today():
                    print("[*] Updating business goals on startup...")
                    await goal_system.generate_daily_goals()
                else:
                    print("[i] Business goals are up to date")
        except Exception as e:
            print(f"❌ Error in initial goal update: {e}")
            import traceback
            traceback.print_exc()
        
        # Main loop: check daily at midnight
        while self.running:
            try:
                # Calculate time until next midnight (tomorrow at 00:00:00) in configured timezone
                now = local_now()
                # Get tomorrow's midnight in local timezone
                tomorrow_midnight = get_midnight_tomorrow()
                seconds_until_midnight = (tomorrow_midnight - now).total_seconds()
                
                from config import get_timezone
                tz_name = get_timezone().zone
                print(f"[*] Next goal update scheduled for {tomorrow_midnight.strftime('%Y-%m-%d %H:%M:%S')} {tz_name} (in {seconds_until_midnight/3600:.1f} hours)")
                
                # Wait until midnight
                await asyncio.sleep(seconds_until_midnight)
                
                # Update goals at midnight
                if self.running:
                    async with async_session_maker() as goal_db:
                        from business.goal_system import GoalSystem
                        goal_system = GoalSystem(goal_db)
                        
                        # Check if goals need to be updated (should be true at midnight)
                        if await goal_system.should_update_goals_today():
                            print("[*] Updating business goals for new day...")
                            await goal_system.generate_daily_goals()
                        else:
                            print("[i] Goals already updated today")
                            
            except Exception as e:
                print(f"❌ Error in daily goal update: {e}")
                import traceback
                traceback.print_exc()
                # If error occurs, wait 1 hour before retrying
                await asyncio.sleep(3600)
    
    async def generate_customer_reviews_periodically(self):
        """Background task to generate customer reviews every 30 minutes."""
        print("[*] Starting customer review generation background task (runs immediately, then every 30 minutes)...")
        
        # Run immediately on startup
        first_run = True
        
        while self.running:
            try:
                async with async_session_maker() as customer_review_db:
                    from business.customer_review_manager import CustomerReviewManager
                    customer_review_manager = CustomerReviewManager(customer_review_db)
                    
                    # On first run, generate for all completed projects (hours_since_completion=0)
                    # On subsequent runs, generate for projects completed at least 1 hour ago
                    hours_threshold = 0.0 if first_run else 1.0
                    reviews_created = await customer_review_manager.generate_reviews_for_completed_projects(
                        hours_since_completion=hours_threshold
                    )
                    if reviews_created:
                        print(f"[+] Generated {len(reviews_created)} customer review(s) for completed projects")
                    else:
                        if first_run:
                            print("[i] No new customer reviews to generate at this time (no completed projects or reviews already exist)")
                        # Don't print on every periodic run to avoid spam
            except Exception as e:
                print(f"❌ Error generating customer reviews: {e}")
                import traceback
                traceback.print_exc()
            
            first_run = False
            # Wait 30 minutes (1800 seconds) before next generation
            await asyncio.sleep(1800)
    
    async def process_suggestions_periodically(self):
        """Background task to process suggestion votes and manager comments every 60 minutes."""
        print("[*] Starting suggestion processing background task (every 60 minutes)...")
        while self.running:
            try:
                async with async_session_maker() as suggestion_db:
                    from business.suggestion_manager import SuggestionManager
                    suggestion_manager = SuggestionManager(suggestion_db)
                    
                    # Process votes
                    await suggestion_manager.process_suggestion_votes()
                    
                    # Process manager comments
                    await suggestion_manager.process_manager_comments()
                    
                    print("[+] Suggestion processing completed")
            except Exception as e:
                print(f"❌ Error processing suggestions: {e}")
                import traceback
                traceback.print_exc()
            
            # Wait 60 minutes (3600 seconds) before next processing
            await asyncio.sleep(3600)
    
    async def update_shared_drive_periodically(self):
        """Background task to update shared drive every 5-10 minutes (optimized to prevent freezing)."""
        import random
        from business.shared_drive_manager import SharedDriveManager
        from database.database import retry_on_lock
        from sqlalchemy.exc import OperationalError
        
        # Wait longer on startup to let system stabilize
        await asyncio.sleep(30)
        first_run = True
        
        while self.running:
            try:
                async def update_shared_drive():
                    async with async_session_maker() as db:
                        shared_drive_manager = SharedDriveManager(db)
                        business_context = await get_business_context(db)
                        
                        # Get active employees
                        result = await db.execute(
                            select(Employee).where(Employee.status == "active")
                        )
                        employees = result.scalars().all()
                        
                        if employees:
                            # Process 2-3 employees per cycle for more frequent updates
                            if first_run:
                                num_to_process = min(3, len(employees))  # 3 on startup
                            else:
                                num_to_process = min(2, len(employees))  # 2 per cycle for better coverage
                            
                            employees_to_process = random.sample(list(employees), num_to_process)
                            
                            files_created = 0
                            files_updated = 0
                            
                            print(f"📁 Processing {num_to_process} employee(s) for shared drive update...")
                            
                            for employee in employees_to_process:
                                # Store employee info before try block
                                employee_name = employee.name
                                employee_id = employee.id
                                
                                try:
                                    # Generate new documents (AI decides what to create, limited to 1 per cycle)
                                    created = await shared_drive_manager.generate_documents_for_employee(
                                        employee, business_context, max_documents=1
                                    )
                                    files_created += len(created)
                                    
                                    # Small delay to prevent overwhelming the system
                                    await asyncio.sleep(1)
                                    
                                    # Update existing documents (only if not too many files)
                                    updated = await shared_drive_manager.update_existing_documents(
                                        employee, business_context, max_updates=1
                                    )
                                    files_updated += len(updated)
                                    
                                    await db.commit()
                                    
                                    if created or updated:
                                        print(f"  ✓ Employee {employee_name}: {len(created)} created, {len(updated)} updated")
                                    
                                    # Delay between employees to prevent blocking
                                    await asyncio.sleep(2)
                                    
                                except Exception as e:
                                    print(f"  ✗ Error processing shared drive for employee {employee_id} ({employee_name}): {e}")
                                    import traceback
                                    traceback.print_exc()
                                    await db.rollback()
                                    # Continue with next employee even if one fails
                                    await asyncio.sleep(1)
                            
                            if files_created > 0 or files_updated > 0:
                                print(f"📁 Shared drive updated: {files_created} created, {files_updated} updated")
                            elif first_run:
                                print(f"📁 Shared drive background task started (processed {num_to_process} employees)")
                        else:
                            print("⚠️  No active employees found for shared drive update")
                
                # Use retry logic for database operations
                await retry_on_lock(update_shared_drive, max_retries=3, initial_delay=1.0)
                        
            except OperationalError as e:
                if "database is locked" in str(e):
                    print(f"❌ Shared drive update failed after retries (database locked)")
                else:
                    print(f"❌ Error updating shared drive: {e}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"❌ Error updating shared drive: {e}")
                import traceback
                traceback.print_exc()
            
            # Mark first run as complete
            first_run = False
            
            # Wait 5-10 minutes (300-600 seconds) before next update - more frequent updates
            wait_time = random.randint(300, 600)
            print(f"📁 Next shared drive update in {wait_time // 60} minutes")
            await asyncio.sleep(wait_time)
    
    async def check_and_respond_to_messages_periodically(self):
        """Background task to check and respond to messages for all employees every 20 seconds."""
        print("💬 Starting message response background task (every 20 seconds - BALANCED)...")

        # Wait a bit on startup to let system stabilize
        await asyncio.sleep(5)

        while self.running:
            try:
                async with async_session_maker() as message_db:
                    from employees.roles import create_employee_agent
                    from sqlalchemy import select

                    # Get all active employees
                    result = await message_db.execute(
                        select(Employee).where(Employee.status == "active")
                    )
                    employees = result.scalars().all()

                    if not employees:
                        print("ℹ️  No active employees to check messages for")
                    else:
                        # Get business context
                        business_context = await self.get_business_context(message_db)

                        responses_count = 0
                        for employee in employees:
                            try:
                                # Create employee agent
                                agent = create_employee_agent(employee, message_db, self.llm_client)

                                # Check and respond to messages
                                await agent._check_and_respond_to_messages(business_context)

                                responses_count += 1
                            except Exception as e:
                                print(f"❌ Error checking messages for {employee.name}: {e}")
                                import traceback
                                traceback.print_exc()
                                continue

                        await message_db.commit()
                        logger.info(f"💬 Message response check completed for {responses_count} employee(s)")
                        print(f"💬 Message response check completed for {responses_count} employee(s)")

            except Exception as e:
                logger.error(f"[-] Error in message response background task: {e}", exc_info=True)
                import traceback
                traceback.print_exc()

            # Wait 20 seconds before next check (balanced for performance and DB load)
            if self.running:
                await asyncio.sleep(20)
    
    async def generate_communications_periodically(self):
        """Background task to generate spontaneous communications between employees every 5 minutes."""
        print("💬 Starting periodic communication generation task (every 5 minutes)...")
        
        # Wait a bit on startup to let system stabilize
        await asyncio.sleep(60)
        
        while self.running:
            try:
                async with async_session_maker() as comm_db:
                    from employees.roles import create_employee_agent
                    from sqlalchemy import select
                    import random
                    
                    # Get all active employees
                    result = await comm_db.execute(
                        select(Employee).where(Employee.status == "active")
                    )
                    employees = result.scalars().all()
                    
                    if not employees or len(employees) < 2:
                        print("ℹ️  Not enough employees for communication generation")
                    else:
                        # Get business context
                        business_context = await self.get_business_context(comm_db)
                        
                        # Select 3-5 random employees to generate communications
                        num_to_process = min(random.randint(3, 5), len(employees))
                        selected_employees = random.sample(employees, num_to_process)
                        
                        communications_generated = 0
                        for employee in selected_employees:
                            try:
                                # Create employee agent
                                agent = create_employee_agent(employee, comm_db, self.llm_client)
                                
                                # Create a simple decision context for spontaneous communication
                                decision = {
                                    "action_type": "communication",
                                    "decision": "Reach out to a teammate",
                                    "reasoning": "Spontaneous team communication to stay connected",
                                    "confidence": 0.7
                                }
                                
                                # Generate communication (this will use the improved probabilities)
                                await agent._generate_communication(decision, business_context)
                                communications_generated += 1
                            except Exception as e:
                                print(f"❌ Error generating communication for {employee.name}: {e}")
                                import traceback
                                traceback.print_exc()
                                continue
                        
                        await comm_db.commit()
                        if communications_generated > 0:
                            logger.info(f"[+] Generated {communications_generated} spontaneous communication(s)")
                        
            except Exception as e:
                logger.error(f"[-] Error in periodic communication generation task: {e}", exc_info=True)
                import traceback
                traceback.print_exc()
            
            # Wait 5 minutes (300 seconds) before next generation
            if self.running:
                await asyncio.sleep(300)
    
    async def manage_employees_periodically(self):
        """Background task to manage employee hiring and firing every 30-60 seconds."""
        logger.info("👥 Starting employee management background task (every 30-60 seconds)...")
        import random
        from database.database import retry_on_lock
        from sqlalchemy.exc import OperationalError
        
        # Wait a bit on startup to let system stabilize
        await asyncio.sleep(10)
        
        while self.running:
            try:
                async def manage_employees():
                    async with async_session_maker() as manage_db:
                        try:
                            business_context = await self.get_business_context(manage_db)
                            
                            logger.info(f"[*] Running employee management background task...")
                            await self._manage_employees(manage_db, business_context)
                            await manage_db.commit()
                            logger.info(f"[+] Employee management background task completed")
                        except Exception as e:
                            await manage_db.rollback()
                            raise
                
                # Use retry logic for database operations
                await retry_on_lock(manage_employees, max_retries=3, initial_delay=1.0)
                    
            except OperationalError as e:
                if "database is locked" in str(e):
                    logger.error(f"[-] Employee management failed after retries (database locked)")
                else:
                    logger.error(f"[-] Error in employee management background task: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[-] Error in employee management background task: {e}", exc_info=True)
            
            # Also manage project capacity in the same task
            try:
                async def manage_projects():
                    async with async_session_maker() as project_db:
                        try:
                            logger.info(f"[*] Running project capacity management...")
                            await self._manage_project_capacity(project_db)
                            await project_db.commit()
                            logger.info(f"[+] Project capacity management completed")
                        except Exception as e:
                            await project_db.rollback()
                            raise
                
                # Use retry logic for database operations
                await retry_on_lock(manage_projects, max_retries=3, initial_delay=1.0)
            except OperationalError as e:
                if "database is locked" in str(e):
                    logger.error(f"[-] Project management failed after retries (database locked)")
                else:
                    logger.error(f"[-] Error in project capacity management: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[-] Error in project capacity management: {e}", exc_info=True)
            
            # Wait 30-60 seconds before next check
            wait_time = random.randint(30, 60)
            await asyncio.sleep(wait_time)
    
    async def process_clock_events_periodically(self):
        """Background task to process employee clock in/out events every 2 minutes."""
        while self.running:
            try:
                async with async_session_maker() as db:
                    from business.clock_manager import ClockManager
                    clock_manager = ClockManager(db)

                    # Process end-of-day departures (6:45pm-7:15pm)
                    departure_stats = await clock_manager.process_end_of_day_departures()
                    if departure_stats["departed"] > 0:
                        logger.info(f"[CLOCK OUT] {departure_stats['message']}")

                    # Process commuting employees (transition leaving_work -> at_home)
                    commute_stats = await clock_manager.process_commuting_employees()
                    if commute_stats["arrived_home"] > 0:
                        logger.info(f"[ARRIVED HOME] {commute_stats['message']}")

                    # Process morning arrivals (6:45am-7:45am)
                    arrival_stats = await clock_manager.process_morning_arrivals()
                    if arrival_stats["arrived"] > 0:
                        logger.info(f"[CLOCK IN] {arrival_stats['message']}")

            except Exception as e:
                logger.error(f"Error in clock event processing: {e}", exc_info=True)

            # Run every 2 minutes (120 seconds)
            await asyncio.sleep(120)

    async def process_sleep_schedules_periodically(self):
        """Background task to process sleep schedules (bedtime 10pm-12am, wake 5:30am-9am)."""
        while self.running:
            try:
                async with async_session_maker() as db:
                    from business.sleep_manager import SleepManager
                    sleep_manager = SleepManager(db)

                    # Process bedtime (10pm-12am)
                    bedtime_stats = await sleep_manager.process_bedtime()
                    if bedtime_stats["went_to_sleep"] > 0:
                        logger.info(f"[BEDTIME] {bedtime_stats['message']}")

                    # Process wake-ups (employees 5:30am-6:45am, family 7:30am-9am)
                    wakeup_stats = await sleep_manager.process_wake_up()
                    if wakeup_stats["woke_employees"] > 0 or wakeup_stats["woke_family"] > 0:
                        logger.info(f"[WAKE UP] {wakeup_stats['message']}")

            except Exception as e:
                logger.error(f"Error in sleep schedule processing: {e}", exc_info=True)

            # Run every 2 minutes (120 seconds)
            await asyncio.sleep(120)

    async def run(self):
        """Run the simulation loop."""
        self.running = True
        logger.info("Office simulation started...")
        
        # Start the frequent meeting update task in the background
        meeting_task = asyncio.create_task(self.update_meetings_frequently())
        logger.info(f"[+] Created meeting update background task: {meeting_task}")
        
        # Start the daily goal update task in the background
        goal_task = asyncio.create_task(self.update_goals_daily())
        logger.info(f"[+] Created daily goal update background task: {goal_task}")
        
        # Start the customer review generation task in the background (runs immediately, then every 30 minutes)
        customer_review_task = asyncio.create_task(self.generate_customer_reviews_periodically())
        logger.info(f"[+] Created customer review generation background task (runs immediately, then every 30 minutes): {customer_review_task}")
        
        # Start the performance award update task in the background (every 5 minutes)
        award_task = asyncio.create_task(self.update_performance_award_periodically())
        logger.info(f"[+] Created performance award update background task (every 5 minutes, runs immediately): {award_task}")
        
        # Start the suggestion processing task in the background (every 60 minutes)
        suggestion_task = asyncio.create_task(self.process_suggestions_periodically())
        logger.info(f"[+] Created suggestion processing background task (every 60 minutes): {suggestion_task}")
        
        # Start the shared drive update task in the background (every 20-30 minutes, optimized)
        shared_drive_task = asyncio.create_task(self.update_shared_drive_periodically())
        logger.info(f"[+] Created shared drive update background task (every 20-30 minutes, optimized): {shared_drive_task}")
        
        # Start the employee management task in the background (every 30-60 seconds)
        employee_management_task = asyncio.create_task(self.manage_employees_periodically())
        logger.info(f"[+] Created employee management background task (every 30-60 seconds): {employee_management_task}")
        
        # Start the message response task in the background (every 20 seconds - BALANCED)
        message_response_task = asyncio.create_task(self.check_and_respond_to_messages_periodically())
        logger.info(f"[+] Created message response background task (every 20 seconds - BALANCED): {message_response_task}")
        
        # Start the periodic communication generation task (every 5 minutes for spontaneous communications)
        communication_task = asyncio.create_task(self.generate_communications_periodically())
        logger.info(f"[+] Created periodic communication generation background task (every 5 minutes): {communication_task}")

        # Start the clock in/out processing task (every 2 minutes for arrivals/departures)
        clock_task = asyncio.create_task(self.process_clock_events_periodically())
        logger.info(f"[+] Created clock in/out processing background task (every 2 minutes): {clock_task}")

        # Start the sleep schedule processing task (every 2 minutes for bedtime/wake-up)
        sleep_task = asyncio.create_task(self.process_sleep_schedules_periodically())
        logger.info(f"[+] Created sleep schedule processing background task (every 2 minutes): {sleep_task}")

        while self.running:
            try:
                await self.simulation_tick()
                await asyncio.sleep(8)  # Wait 8 seconds between ticks
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the simulation."""
        self.running = False
        print("Office simulation stopped.")

