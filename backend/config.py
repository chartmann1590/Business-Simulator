"""
Timezone configuration module for the application.
Provides centralized timezone handling with configurable timezone support.
"""
import os
from datetime import datetime, timezone
from typing import Optional
import pytz


# Get timezone from environment variable, default to America/New_York
TIMEZONE_NAME = os.getenv("TIMEZONE", "America/New_York")

# Cache the timezone object
_timezone_cache: Optional[pytz.BaseTzInfo] = None


def get_timezone() -> pytz.BaseTzInfo:
    """
    Get the configured timezone object.
    
    Returns:
        pytz.timezone object for the configured timezone
    """
    global _timezone_cache
    if _timezone_cache is None:
        try:
            _timezone_cache = pytz.timezone(TIMEZONE_NAME)
        except pytz.exceptions.UnknownTimeZoneError:
            print(f"Warning: Unknown timezone '{TIMEZONE_NAME}', falling back to 'America/New_York'")
            _timezone_cache = pytz.timezone("America/New_York")
    return _timezone_cache


def now() -> datetime:
    """
    Get the current time in the configured timezone.
    
    Returns:
        datetime object with timezone info set to the configured timezone
    """
    tz = get_timezone()
    # Get UTC time first, then convert to local timezone
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(tz)


def utc_to_local(utc_dt: datetime) -> datetime:
    """
    Convert a UTC datetime to the configured local timezone.
    
    Args:
        utc_dt: datetime object (assumed to be UTC if timezone-naive)
        
    Returns:
        datetime object in the configured timezone
    """
    tz = get_timezone()
    # If datetime is naive, assume it's UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(tz)


def local_to_utc(local_dt: datetime) -> datetime:
    """
    Convert a local datetime (in configured timezone) to UTC.
    
    Args:
        local_dt: datetime object (assumed to be in configured timezone if timezone-naive)
        
    Returns:
        datetime object in UTC
    """
    tz = get_timezone()
    # If datetime is naive, assume it's in the configured timezone
    if local_dt.tzinfo is None:
        local_dt = tz.localize(local_dt)
    return local_dt.astimezone(timezone.utc)


def now_naive() -> datetime:
    """
    Get the current time in the configured timezone as a naive datetime.
    This is useful for database operations that expect naive datetimes.
    
    Returns:
        datetime object without timezone info, but representing local time
    """
    return now().replace(tzinfo=None)


def get_midnight_today() -> datetime:
    """
    Get today's midnight (00:00:00) in the configured timezone.
    
    Returns:
        datetime object representing today at midnight in configured timezone
    """
    tz = get_timezone()
    local_now = now()
    midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight


def get_midnight_tomorrow() -> datetime:
    """
    Get tomorrow's midnight (00:00:00) in the configured timezone.
    
    Returns:
        datetime object representing tomorrow at midnight in configured timezone
    """
    from datetime import timedelta
    midnight_today = get_midnight_today()
    return midnight_today + timedelta(days=1)



