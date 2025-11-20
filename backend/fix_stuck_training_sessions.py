"""
Script to fix stuck training sessions - end all sessions over 30 minutes old.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import get_db
from database.models import TrainingSession, Employee
from sqlalchemy import select, and_
from business.training_manager import TrainingManager
from engine.movement_system import update_employee_location
from employees.room_assigner import ROOM_TRAINING_ROOM, ROOM_CUBICLES
from config import now as local_now, now_naive as get_now_naive, utc_to_local


async def fix_stuck_sessions():
    """End all training sessions that have exceeded 30 minutes."""
    async for db in get_db():
        try:
            now = local_now()
            thirty_minutes_ago = now - timedelta(minutes=30)
            
            # Get all in-progress sessions
            result = await db.execute(
                select(TrainingSession)
                .where(TrainingSession.status == "in_progress")
            )
            all_sessions = result.scalars().all()
            
            print(f"Found {len(all_sessions)} in-progress training sessions")
            
            expired_count = 0
            moved_count = 0
            
            for session in all_sessions:
                if not session.start_time:
                    print(f"  [SKIP] Session {session.id} has no start_time")
                    continue
                
                # Normalize start_time for comparison - handle timezone properly
                start_time = session.start_time
                
                # If start_time is timezone-aware, convert both to the same timezone for comparison
                if start_time.tzinfo:
                    # Convert timezone-aware start_time to local timezone, then make naive
                    start_time_local = utc_to_local(start_time) if start_time.tzinfo.utcoffset(start_time).total_seconds() == 0 else start_time.astimezone(local_now().tzinfo)
                    start_time = start_time_local.replace(tzinfo=None)
                else:
                    # Assume naive datetime is in local timezone
                    start_time = start_time
                
                # Use naive datetime for comparison (local time)
                now_local_naive = get_now_naive()
                thirty_min_ago_naive = now_local_naive - timedelta(minutes=30)
                
                # Calculate actual time difference (in minutes)
                time_diff = (now_local_naive - start_time).total_seconds() / 60
                
                # Check if expired (more than 30 minutes have passed)
                if time_diff >= 30:
                    # Get employee
                    emp_result = await db.execute(
                        select(Employee).where(Employee.id == session.employee_id)
                    )
                    employee = emp_result.scalar_one_or_none()
                    
                    if not employee:
                        print(f"  [SKIP] Session {session.id} - employee not found")
                        continue
                    
                    # Calculate duration using naive datetimes
                    now_local_naive = get_now_naive()
                    duration = now_local_naive - start_time
                    duration_minutes = int(duration.total_seconds() / 60)
                    
                    # End the session (use naive datetime)
                    session.end_time = now_local_naive
                    session.status = "completed"
                    session.duration_minutes = duration_minutes
                    
                    expired_count += 1
                    
                    # Check if employee is still in training room
                    is_in_training_room = (
                        employee.current_room == ROOM_TRAINING_ROOM or
                        (employee.current_room and employee.current_room.startswith(f"{ROOM_TRAINING_ROOM}_floor"))
                    )
                    
                    if is_in_training_room:
                        # Move employee out
                        target_room = employee.home_room
                        if not target_room:
                            employee_floor = getattr(employee, 'floor', 1)
                            target_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                        
                        try:
                            await update_employee_location(employee, target_room, "working", db)
                            moved_count += 1
                            print(f"  [FIXED] {employee.name} - Ended session ({duration_minutes} min) and moved to {target_room}")
                        except Exception as e:
                            print(f"  [ERROR] Failed to move {employee.name}: {e}")
                    else:
                        print(f"  [ENDED] {employee.name} - Ended session ({duration_minutes} min), already out of training room")
                else:
                    # Not expired yet
                    remaining = 30 - time_diff
                    print(f"  [OK] Session {session.id} - Still in training ({remaining:.1f} minutes remaining, started {time_diff:.1f} min ago)")
            
            await db.commit()
            
            print(f"\n[COMPLETE] Fixed {expired_count} expired sessions, moved {moved_count} employees")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(fix_stuck_sessions())

