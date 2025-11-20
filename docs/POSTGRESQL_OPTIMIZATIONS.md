# PostgreSQL Optimization Guide

This document outlines all the optimizations implemented for PostgreSQL to ensure fast loading and better performance.

## Overview

The project has been optimized for PostgreSQL with the following improvements:

1. **Database Indexes** - Comprehensive indexing strategy
2. **Query Optimization** - Eliminated N+1 queries
3. **Connection Pooling** - Optimized pool settings
4. **PostgreSQL-Specific Features** - Using native PostgreSQL optimizations
5. **Bulk Operations** - Efficient batch processing

## 1. Database Indexes

### Automatic Index Creation

All indexes are automatically created when the database initializes. The index optimization script (`backend/database/optimize_indexes.py`) creates:

- **Foreign Key Indexes**: All foreign keys are indexed for faster joins
- **Query Column Indexes**: Frequently queried columns (status, dates, etc.)
- **Composite Indexes**: Multi-column indexes for common query patterns
- **Unique Constraints**: Properly indexed unique columns

### Key Indexes Created

- Employee: `status`, `role`, `department`, `hierarchy_level`, `current_room`, `floor`, `activity_state`
- Project: `status`, `priority`, `product_id`, `deadline`, `created_at`
- Task: `employee_id`, `project_id`, `status`, `priority`
- Meeting: `organizer_id`, `status`, `start_time`, `end_time`
- And many more...

### Running Index Optimization Manually

```bash
cd backend
python -m database.optimize_indexes
```

## 2. Query Optimizations

### Eliminated N+1 Queries

#### Products Endpoint (`/api/products`)
**Before**: Looped through products, querying reviews/sales/team for each product separately
**After**: Single query with LEFT JOINs and aggregations

```python
# Optimized query uses:
# - LEFT JOINs for related data
# - GROUP BY with aggregations
# - Single database round-trip
```

#### Meetings Endpoint (`/api/meetings/{meeting_id}`)
**Before**: Queried employees one by one in a loop
**After**: Single query with `IN` clause to fetch all attendees at once

#### Employees Endpoint (`/api/employees`)
**Before**: Loaded all reviews and processed in Python
**After**: Uses PostgreSQL `DISTINCT ON` for efficient latest review lookup

### Query Patterns Used

1. **JOINs instead of loops**: Related data fetched in single queries
2. **Aggregations in SQL**: COUNT, SUM, AVG computed in database
3. **Window functions**: PostgreSQL-specific features for complex queries
4. **Batch fetching**: Multiple records fetched with `IN` clauses

## 3. Connection Pooling

### Optimized Settings

```python
pool_size=25          # Increased from 20 for better concurrency
max_overflow=15       # Increased from 10 for peak loads
pool_timeout=30       # Wait time for connection
pool_pre_ping=True    # Verify connections before use
pool_recycle=3600     # Recycle connections after 1 hour
```

### PostgreSQL-Specific Connection Settings

```python
connect_args={
    "server_settings": {
        "application_name": "office_simulator",
        "jit": "on",                    # Enable JIT compilation
        "work_mem": "16MB",            # Memory for sorts/joins
        "maintenance_work_mem": "64MB" # Memory for index operations
    }
}
```

## 4. PostgreSQL-Specific Features

### DISTINCT ON

Used for getting latest records per group:

```sql
SELECT DISTINCT ON (employee_id)
    employee_id, review_date, overall_rating
FROM employee_reviews
ORDER BY employee_id, review_date DESC
```

### ANALYZE

Tables are automatically analyzed after index creation to update statistics for the query planner.

### JIT Compilation

Just-In-Time compilation is enabled for complex queries, improving performance for analytical queries.

## 5. Bulk Operations

### Available Functions

Located in `backend/database/bulk_operations.py`:

- `bulk_insert_optimized()`: Efficient batch inserts
- `bulk_update_optimized()`: Batch updates with CASE statements
- `bulk_upsert_optimized()`: INSERT ... ON CONFLICT DO UPDATE

### Usage Example

```python
from database.bulk_operations import bulk_insert_optimized
from database.models import Activity

records = [
    {"employee_id": 1, "activity_type": "task_completed", ...},
    {"employee_id": 2, "activity_type": "task_completed", ...},
    # ... more records
]

await bulk_insert_optimized(session, Activity, records, batch_size=1000)
```

## 6. Performance Monitoring

### Query Performance

To analyze query performance, you can:

1. Enable query logging (set `echo=True` in engine creation for debugging)
2. Use PostgreSQL's `EXPLAIN ANALYZE`:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM employees WHERE status = 'active';
   ```

### Index Usage

Check which indexes are being used:

```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## 7. Maintenance

### Regular Maintenance Tasks

1. **ANALYZE**: Run periodically to update statistics
   ```python
   from database.bulk_operations import analyze_table
   await analyze_table(session, "employees")
   ```

2. **VACUUM**: For tables with high UPDATE/DELETE activity
   ```python
   from database.bulk_operations import vacuum_table
   await vacuum_table(session, "activities", analyze=True)
   ```

### Automatic Maintenance

- Indexes are created automatically on database initialization
- Tables are analyzed after index creation
- Connection pool automatically recycles stale connections

## 8. Best Practices

### Query Writing

1. **Use JOINs**: Always prefer JOINs over loops
2. **Filter Early**: Use WHERE clauses to reduce data early
3. **Limit Results**: Use LIMIT when you don't need all records
4. **Use Indexes**: Query on indexed columns when possible

### Connection Management

1. **Reuse Sessions**: Don't create new sessions unnecessarily
2. **Close Properly**: Always use context managers (`async with`)
3. **Batch Operations**: Group multiple operations in transactions

### Index Strategy

1. **Index Foreign Keys**: Always index foreign keys
2. **Index Query Columns**: Index columns used in WHERE clauses
3. **Composite Indexes**: Create for multi-column queries
4. **Monitor Usage**: Remove unused indexes

## 9. Performance Improvements

### Expected Improvements

- **Query Speed**: 5-10x faster for complex queries with indexes
- **N+1 Elimination**: 10-100x faster for endpoints with related data
- **Connection Efficiency**: Better handling of concurrent requests
- **Bulk Operations**: 50-100x faster than individual inserts

### Monitoring

Watch for:
- Slow queries (check PostgreSQL logs)
- Missing indexes (use `EXPLAIN ANALYZE`)
- Connection pool exhaustion (monitor pool metrics)
- Table bloat (run VACUUM regularly)

## 10. Troubleshooting

### Slow Queries

1. Check if indexes exist: `\d table_name` in psql
2. Analyze query plan: `EXPLAIN ANALYZE`
3. Check table statistics: `SELECT * FROM pg_stat_user_tables`

### Connection Issues

1. Check pool size: May need to increase for high concurrency
2. Monitor connections: `SELECT * FROM pg_stat_activity`
3. Check for leaks: Ensure sessions are properly closed

### Index Issues

1. Verify indexes exist: Run optimization script
2. Check index usage: Query `pg_stat_user_indexes`
3. Rebuild if needed: `REINDEX TABLE table_name`

## Summary

The project is now fully optimized for PostgreSQL with:

✅ Comprehensive indexing strategy
✅ Eliminated N+1 query patterns
✅ Optimized connection pooling
✅ PostgreSQL-specific optimizations
✅ Efficient bulk operations
✅ Automatic maintenance

These optimizations ensure fast loading times and better performance as the database grows.


