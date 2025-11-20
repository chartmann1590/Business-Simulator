# Database Connection Pool Exhaustion Fix

## Problem

The application was experiencing widespread connection timeouts across all operations:

```
asyncio.exceptions.TimeoutError
  at asyncpg/connection.py line 2328: async with compat.timeout(timeout)
```

### Symptoms
- API endpoints returning 500 errors (activities, notifications, dashboard)
- Background tasks failing (meetings, training, reviews, awards, communications)
- Simulation tick errors
- Multiple `CancelledError` exceptions during connection attempts

### Root Cause

**Connection Pool Exhaustion**: The system has many concurrent operations all competing for database connections:

1. **API Requests** (from frontend polling)
   - Dashboard updates
   - Activity feeds
   - Notifications
   - Employee data
   - And more...

2. **Background Tasks** (running simultaneously)
   - Simulation tick (every 8 seconds)
   - Message response task (every 15-20 seconds)
   - Meeting updates
   - Training session checks
   - Performance award updates
   - Review management
   - Employee management (every 30-60 seconds)
   - Communication generation (every 5 minutes)
   - Shared drive updates (every 20-30 minutes)
   - And more...

**Original Configuration**:
- Pool size: 25 persistent connections
- Max overflow: 15 additional connections
- **Total: 40 max concurrent connections**
- Pool timeout: 30 seconds

With 10+ background tasks plus API requests, the system easily exceeded 40 concurrent connections.

## Solution Applied

### Fix #1: Increased Connection Pool Size

```python
# OLD CONFIGURATION
pool_size=25
max_overflow=15
# Total: 40 connections

# NEW CONFIGURATION
pool_size=50  # DOUBLED
max_overflow=30  # DOUBLED
# Total: 80 connections (2x capacity)
```

### Fix #2: Increased Timeouts

```python
# OLD
pool_timeout=30  # 30 seconds to acquire connection

# NEW
pool_timeout=60  # 60 seconds to acquire connection
```

Added connection-level timeouts:
```python
connect_args={
    "timeout": 60,  # Connection timeout
    "command_timeout": 60,  # Command execution timeout
}
```

### Fix #3: Faster Connection Recycling

```python
# OLD
pool_recycle=3600  # Recycle after 1 hour

# NEW
pool_recycle=1800  # Recycle after 30 minutes
```

This prevents connection staleness and ensures fresh connections more frequently.

### Fix #4: Optimized Background Task Frequency

Adjusted message response task to balance speed and database load:

```python
# INITIAL: 30 seconds (too slow)
# ATTEMPTED: 15 seconds (too frequent, contributed to pool exhaustion)
# FINAL: 20 seconds (balanced)
```

## Files Modified

1. **`backend/database/database.py`**
   - Increased `pool_size` from 25 to 50
   - Increased `max_overflow` from 15 to 30
   - Increased `pool_timeout` from 30 to 60
   - Reduced `pool_recycle` from 3600 to 1800
   - Added `timeout` and `command_timeout` to `connect_args`

2. **`backend/engine/office_simulator.py`**
   - Adjusted message response interval from 15s to 20s

3. **`CLAUDE.md`**
   - Updated documentation to reflect new connection pool configuration

4. **`COMMUNICATION_FIXES.md`**
   - Updated to document balanced timing and connection pool changes

## PostgreSQL Configuration (Optional)

If you continue to see connection issues, you may need to increase PostgreSQL's `max_connections`:

1. Edit your PostgreSQL configuration file (`postgresql.conf`):
   ```
   max_connections = 200  # Default is usually 100
   ```

2. Restart PostgreSQL:
   ```bash
   # Windows
   pg_ctl restart -D "C:\Program Files\PostgreSQL\12\data"

   # Linux
   sudo systemctl restart postgresql
   ```

3. Verify the setting:
   ```sql
   SHOW max_connections;
   ```

## How to Apply

**IMPORTANT**: The backend server must be restarted for these changes to take effect.

```bash
# Stop the current backend server (Ctrl+C)

# Restart it
cd backend
python main.py
```

## Monitoring Connection Usage

### Check Current Connections

Run this SQL query to see how many connections are active:

```sql
SELECT
    count(*) as connection_count,
    state,
    application_name
FROM pg_stat_activity
WHERE datname = 'office_db'
GROUP BY state, application_name
ORDER BY connection_count DESC;
```

### Expected Results After Fix

With the new configuration (80 max connections), you should see:
- Most operations completing successfully
- No more `TimeoutError` exceptions
- API requests returning 200 (not 500)
- Background tasks completing without errors

If you still see issues with >60 concurrent connections, it means:
1. There's a connection leak (connections not being closed)
2. More background tasks were added
3. Need to further increase pool size

## Connection Best Practices

### Always Close Sessions

```python
# GOOD - using context manager (automatically closes)
async with async_session_maker() as db:
    result = await db.execute(query)
    await db.commit()
# Session automatically closed here

# BAD - manual session management (can leak)
db = async_session_maker()
result = await db.execute(query)
# If exception occurs, session may not close!
```

### Use Transactions Properly

```python
# GOOD - commit or rollback in all paths
try:
    async with async_session_maker() as db:
        await db.execute(query)
        await db.commit()
except Exception:
    # Session auto-rollback on context exit
    raise

# GOOD - using safe_commit helper
async with async_session_maker() as db:
    await db.execute(query)
    await safe_commit(db)  # Auto-retry on lock errors
```

### Avoid Long-Running Queries

```python
# BAD - holding connection for long LLM call
async with async_session_maker() as db:
    data = await db.execute(query)
    llm_result = await llm_client.generate(...)  # Long operation!
    await db.execute(update_query)
    await db.commit()

# GOOD - release connection during LLM call
async with async_session_maker() as db:
    data = await db.execute(query)
    data_dict = data_to_dict(data)

llm_result = await llm_client.generate(...)  # No DB connection held

async with async_session_maker() as db:
    await db.execute(update_query)
    await db.commit()
```

## Verification

After restarting the backend, verify the fix by:

1. **Check backend logs** - should see:
   ```
   [+] Created message response background task (every 20 seconds - BALANCED)
   ```

2. **Monitor for errors** - should NOT see:
   ```
   asyncio.exceptions.TimeoutError
   ```

3. **Test API endpoints**:
   ```bash
   curl http://localhost:8000/api/dashboard
   curl http://localhost:8000/api/activities?limit=50
   curl http://localhost:8000/api/notifications
   ```
   All should return 200 status codes.

4. **Check PostgreSQL connections**:
   ```sql
   SELECT count(*) FROM pg_stat_activity
   WHERE application_name = 'office_simulator';
   ```
   Should be well under 80.

## Performance Impact

### Expected Improvements
- ✅ All API endpoints respond successfully
- ✅ Background tasks complete without timeouts
- ✅ Simulation runs smoothly
- ✅ No connection pool exhaustion errors

### Trade-offs
- Slightly higher memory usage (80 connections vs 40)
- Slightly higher PostgreSQL load
- But: System actually works correctly now!

## Future Considerations

If the application grows further, consider:

1. **Connection pooling proxy** (PgBouncer)
   - Manages connections more efficiently
   - Allows more app connections than DB connections

2. **Read replicas**
   - Separate read-only queries to replica
   - Reduces load on primary database

3. **Query optimization**
   - Use query caching more extensively
   - Add indexes for slow queries
   - Batch operations where possible

4. **Background task consolidation**
   - Combine similar tasks to reduce concurrent sessions
   - Use task queues (Celery, RQ) for better control
