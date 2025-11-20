"""Helper module to broadcast activities via WebSocket."""
from typing import Optional
from database.models import Activity, Employee
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import now as local_now

# Global reference to simulator instance (set by main.py)
_simulator_instance: Optional[object] = None

def set_simulator_instance(simulator):
    """Set the global simulator instance."""
    global _simulator_instance
    _simulator_instance = simulator

async def broadcast_activity(activity: Activity, db: AsyncSession, employee: Optional[Employee] = None):
    """
    Broadcast an activity via WebSocket if simulator is available.
    
    Args:
        activity: The Activity object to broadcast
        db: Database session (used to fetch employee info if needed)
        employee: Optional Employee object (if already loaded)
    """
    global _simulator_instance
    
    if not _simulator_instance:
        return  # No simulator instance available
    
    try:
        # Get employee info if not provided
        if not employee and activity.employee_id:
            try:
                result = await db.execute(
                    select(Employee).where(Employee.id == activity.employee_id)
                )
                employee = result.scalar_one_or_none()
            except:
                employee = None
        
        # Build activity data
        activity_data = {
            "type": "activity",
            "id": activity.id,
            "employee_id": activity.employee_id,
            "employee_name": employee.name if employee else None,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "timestamp": (activity.timestamp or local_now()).isoformat(),
        }
        
        # Add location info if employee is available
        if employee:
            activity_data["current_room"] = getattr(employee, 'current_room', None)
            activity_data["activity_state"] = getattr(employee, 'activity_state', None)
        
        # Broadcast via simulator
        if hasattr(_simulator_instance, 'broadcast_activity'):
            await _simulator_instance.broadcast_activity(activity_data)
    except Exception as e:
        # Don't fail if broadcasting fails - it's not critical
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not broadcast activity {activity.id}: {e}")

