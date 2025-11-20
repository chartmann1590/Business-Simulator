"""
Database query result caching to improve performance and ensure data loads quickly.
This caches query results in memory to avoid repeated database hits.
"""
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
import hashlib
import json
import asyncio
from functools import wraps

# In-memory cache for query results
_query_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = asyncio.Lock()

# Default cache duration: 10 seconds
DEFAULT_CACHE_DURATION = 10

def _generate_cache_key(query_str: str, params: Any = None) -> str:
    """Generate a cache key from query string and parameters."""
    key_data = {
        'query': query_str,
        'params': str(params) if params else None
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

async def _get_cached_result(cache_key: str) -> Optional[Any]:
    """Get cached result if available and not expired."""
    async with _cache_lock:
        if cache_key in _query_cache:
            cached = _query_cache[cache_key]
            if datetime.now() - cached['timestamp'] < timedelta(seconds=cached['duration']):
                return cached['data']
            else:
                # Remove expired cache entry
                del _query_cache[cache_key]
    return None

async def _set_cached_result(cache_key: str, data: Any, duration: int = DEFAULT_CACHE_DURATION):
    """Cache query result."""
    async with _cache_lock:
        _query_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now(),
            'duration': duration
        }

def cached_query(cache_duration: int = DEFAULT_CACHE_DURATION):
    """
    Decorator to cache database query results.
    
    Usage:
        @cached_query(cache_duration=10)
        async def get_employees(db):
            result = await db.execute(select(Employee))
            return result.scalars().all()
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Generate cache key from function name and arguments
                cache_key = _generate_cache_key(
                    f"{func.__name__}",
                    {'args': str(args), 'kwargs': str(kwargs)}
                )
                
                # Check cache first
                cached_result = await _get_cached_result(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute query
                result = await func(*args, **kwargs)
                
                # Cache the result
                await _set_cached_result(cache_key, result, cache_duration)
                
                return result
            except Exception as e:
                # If caching fails, just execute the function normally
                print(f"Cache error in {func.__name__}: {e}")
                return await func(*args, **kwargs)
        return wrapper
    return decorator

async def clear_cache(pattern: Optional[str] = None):
    """Clear cache entries, optionally filtered by pattern."""
    async with _cache_lock:
        if pattern:
            keys_to_remove = [k for k in _query_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del _query_cache[key]
        else:
            _query_cache.clear()

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    async with _cache_lock:
        total_entries = len(_query_cache)
        expired_entries = sum(
            1 for cached in _query_cache.values()
            if datetime.now() - cached['timestamp'] >= timedelta(seconds=cached['duration'])
        )
        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries
        }

