"""
Helper utility for creating notifications with duplicate prevention.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import timedelta
from database.models import Notification
from config import now as local_now


async def create_notification_if_not_duplicate(
    db: AsyncSession,
    notification_type: str,
    title: str,
    message: str,
    employee_id: int = None,
    review_id: int = None,
    duplicate_window_minutes: int = 5
) -> Notification:
    """
    Create a notification only if a similar one doesn't already exist within the duplicate window.
    
    Args:
        db: Database session
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        employee_id: Related employee ID (optional)
        review_id: Related review ID (optional)
        duplicate_window_minutes: Time window in minutes to check for duplicates (default: 5)
    
    Returns:
        The created Notification object, or None if a duplicate was found
    """
    # Calculate the time threshold for duplicate checking
    # Use timezone-aware datetime from config
    threshold_time = local_now() - timedelta(minutes=duplicate_window_minutes)
    
    # Build query to check for duplicates
    query = select(Notification).where(
        and_(
            Notification.notification_type == notification_type,
            Notification.title == title,
            Notification.message == message,
            Notification.created_at >= threshold_time
        )
    )
    
    # If employee_id is specified, also match on that
    if employee_id is not None:
        query = query.where(Notification.employee_id == employee_id)
    else:
        # If employee_id is None, only match notifications with None employee_id
        query = query.where(Notification.employee_id.is_(None))
    
    # If review_id is specified, also match on that
    if review_id is not None:
        query = query.where(Notification.review_id == review_id)
    else:
        query = query.where(Notification.review_id.is_(None))
    
    # Check for existing duplicate
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Duplicate found, return None
        return None
    
    # No duplicate found, create the notification
    notification = Notification(
        notification_type=notification_type,
        title=title,
        message=message,
        employee_id=employee_id,
        review_id=review_id,
        read=False
    )
    db.add(notification)
    await db.flush()  # Flush to get the ID without committing
    
    return notification

