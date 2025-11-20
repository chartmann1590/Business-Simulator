"""
Data migration script to migrate all data from SQLite to PostgreSQL.

This script:
1. Connects to the existing SQLite database
2. Reads all data from each table
3. Connects to PostgreSQL database
4. Inserts all data into PostgreSQL tables

Usage:
    python migrate_data_sqlite_to_postgresql.py

Environment variables:
    SQLITE_DB_PATH: Path to SQLite database (default: backend/office.db)
    DATABASE_URL: PostgreSQL connection string (required)
"""
import asyncio
import aiosqlite
import asyncpg
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import sys

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "office.db"))
POSTGRESQL_URL = os.getenv("DATABASE_URL")
if not POSTGRESQL_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file or environment variables. "
        "Format: postgresql+asyncpg://user:password@host:port/database"
    )

# Parse PostgreSQL URL to get connection parameters
def parse_postgresql_url(url: str) -> Dict[str, Any]:
    """Parse PostgreSQL connection URL into components."""
    # Format: postgresql+asyncpg://user:password@host:port/database
    url = url.replace("postgresql+asyncpg://", "")
    if "@" in url:
        auth, rest = url.split("@", 1)
        user, password = auth.split(":", 1)
    else:
        raise ValueError("Invalid DATABASE_URL format: missing authentication")
    
    if "/" in rest:
        host_port, database = rest.rsplit("/", 1)
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            port = int(port)
        else:
            host = host_port
            port = 5432
    else:
        host = "localhost"
        port = 5432
        database = rest
    
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database
    }

# List of all tables to migrate (in dependency order to respect foreign keys)
TABLES_ORDER = [
    "employees",  # No dependencies
    "projects",  # Depends on employees (via product_id, but product_id can be null)
    "tasks",  # Depends on employees, projects
    "decisions",  # Depends on employees
    "financials",  # Depends on projects
    "activities",  # Depends on employees
    "business_metrics",  # No dependencies
    "emails",  # Depends on employees
    "chat_messages",  # Depends on employees
    "business_settings",  # No dependencies
    "products",  # No dependencies (but projects depend on it)
    "product_team_members",  # Depends on products, employees
    "employee_reviews",  # Depends on employees
    "notifications",  # Depends on employees
    "customer_reviews",  # Depends on projects, products
    "meetings",  # Depends on employees
    "office_pets",  # Depends on employees
    "gossip",  # Depends on employees
    "weather",  # No dependencies
    "random_events",  # No dependencies
    "newsletters",  # Depends on employees
    "suggestions",  # Depends on employees
    "suggestion_votes",  # Depends on suggestions, employees
    "birthday_celebrations",  # Depends on employees
    "holiday_celebrations",  # No dependencies
    "shared_drive_files",  # Depends on employees
    "shared_drive_file_versions",  # Depends on shared_drive_files
]

async def migrate_table_data(
    sqlite_conn: aiosqlite.Connection,
    pg_conn: asyncpg.Connection,
    table_name: str
) -> int:
    """
    Migrate data from SQLite table to PostgreSQL table.
    
    Returns:
        Number of rows migrated
    """
    print(f"  Migrating {table_name}...")
    
    # Get all data from SQLite
    cursor = await sqlite_conn.execute(f"SELECT * FROM {table_name}")
    rows = await cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    
    if not rows:
        print(f"    No data in {table_name}")
        return 0
    
    # Check if table exists in PostgreSQL
    table_exists = await pg_conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = $1
        )
    """, table_name)
    
    if not table_exists:
        print(f"    Warning: Table {table_name} does not exist in PostgreSQL, skipping...")
        return 0
    
    # Prepare data for insertion
    migrated_count = 0
    
    for row in rows:
        try:
            # Convert row to dict
            row_dict = dict(zip(column_names, row))
            
            # Handle JSON columns (SQLite stores as TEXT, PostgreSQL as JSONB)
            for key, value in row_dict.items():
                if value is not None and isinstance(value, str):
                    # Try to parse as JSON if it looks like JSON
                    if value.startswith('[') or value.startswith('{'):
                        try:
                            row_dict[key] = json.loads(value)
                        except (json.JSONDecodeError, ValueError):
                            pass  # Keep as string if not valid JSON
            
            # Handle boolean values (SQLite uses 0/1, PostgreSQL uses TRUE/FALSE)
            for key, value in row_dict.items():
                if isinstance(value, int) and key.lower().endswith(('_award', 'resolved', 'read')):
                    # Check if this is likely a boolean column
                    if value in (0, 1):
                        row_dict[key] = bool(value)
            
            # Build INSERT statement
            columns = list(row_dict.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(row_dict.values())
            
            # Convert None to NULL for optional columns
            for i, val in enumerate(values):
                if val is None:
                    values[i] = None
                elif isinstance(val, datetime):
                    # Ensure datetime is timezone-aware
                    if val.tzinfo is None:
                        # Assume UTC if timezone-naive
                        values[i] = val.replace(tzinfo=None)
            
            # Check if id column exists and try to use ON CONFLICT if it does
            has_id = 'id' in columns
            if has_id:
                # Try with ON CONFLICT first (for tables with primary key on id)
                insert_sql = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (id) DO NOTHING
                """
            else:
                # No id column, use regular INSERT
                insert_sql = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
            
            try:
                await pg_conn.execute(insert_sql, *values)
                migrated_count += 1
            except Exception as e:
                # If ON CONFLICT doesn't work (no unique constraint on id), try without it
                if has_id and ("ON CONFLICT" in str(e) or "conflict" in str(e).lower() or "unique" in str(e).lower()):
                    insert_sql = f"""
                        INSERT INTO {table_name} ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    try:
                        await pg_conn.execute(insert_sql, *values)
                        migrated_count += 1
                    except Exception as insert_error:
                        # Check if it's a duplicate key error (row already exists)
                        if "duplicate" in str(insert_error).lower() or "unique" in str(insert_error).lower():
                            pass  # Skip duplicate rows
                        else:
                            print(f"    Warning: Failed to insert row into {table_name}: {insert_error}")
                            print(f"    Row data (first 100 chars): {str(row_dict)[:100]}")
                else:
                    # Check if it's a duplicate key error (row already exists)
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        pass  # Skip duplicate rows
                    else:
                        print(f"    Warning: Failed to insert row into {table_name}: {e}")
                        print(f"    Row data (first 100 chars): {str(row_dict)[:100]}")
        
        except Exception as e:
            print(f"    Error processing row in {table_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"    Migrated {migrated_count} rows from {table_name}")
    return migrated_count

async def reset_sequences(pg_conn: asyncpg.Connection):
    """Reset PostgreSQL sequences to match the max ID in each table."""
    print("\n  Resetting sequences...")
    
    for table_name in TABLES_ORDER:
        try:
            # Check if table exists and has id column
            table_exists = await pg_conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
            """, table_name)
            
            if not table_exists:
                continue
            
            # Check if id column exists
            id_exists = await pg_conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = $1 
                    AND column_name = 'id'
                )
            """, table_name)
            
            if not id_exists:
                continue
            
            # Get max ID from table
            max_id = await pg_conn.fetchval(f"SELECT MAX(id) FROM {table_name}")
            if max_id is not None and max_id > 0:
                # Check if sequence exists
                seq_exists = await pg_conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM pg_sequences 
                        WHERE schemaname = 'public' 
                        AND sequencename = $1
                    )
                """, f"{table_name}_id_seq")
                
                if seq_exists:
                    # Reset sequence to max_id + 1 (so next insert gets max_id + 1)
                    await pg_conn.execute(f"SELECT setval('{table_name}_id_seq', {max_id}, true)")
                    print(f"    Reset {table_name}_id_seq to {max_id}")
        except Exception as e:
            # Sequence might not exist or table might be empty
            pass

async def main():
    """Main migration function."""
    print("=" * 60)
    print("SQLite to PostgreSQL Data Migration")
    print("=" * 60)
    
    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        return
    
    print(f"\nSQLite database: {SQLITE_DB_PATH}")
    print(f"PostgreSQL URL: {POSTGRESQL_URL.replace(POSTGRESQL_URL.split('@')[0].split(':')[-1] if '@' in POSTGRESQL_URL else '', '***')}")
    
    # Parse PostgreSQL connection parameters
    pg_params = parse_postgresql_url(POSTGRESQL_URL)
    
    # Connect to databases
    print("\nConnecting to databases...")
    try:
        sqlite_conn = await aiosqlite.connect(SQLITE_DB_PATH)
        print("  Connected to SQLite")
    except Exception as e:
        print(f"  Error connecting to SQLite: {e}")
        return
    
    try:
        pg_conn = await asyncpg.connect(**pg_params)
        print("  Connected to PostgreSQL")
    except Exception as e:
        print(f"  Error connecting to PostgreSQL: {e}")
        print("\nMake sure PostgreSQL is running and the database exists.")
        print("You can create the database with:")
        print(f"  createdb -U {pg_params['user']} {pg_params['database']}")
        await sqlite_conn.close()
        return
    
    try:
        # Migrate each table
        print("\nMigrating data...")
        total_migrated = 0
        
        for table_name in TABLES_ORDER:
            try:
                count = await migrate_table_data(sqlite_conn, pg_conn, table_name)
                total_migrated += count
            except Exception as e:
                print(f"  Error migrating {table_name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Reset sequences
        await reset_sequences(pg_conn)
        
        print("\n" + "=" * 60)
        print(f"Migration completed! Total rows migrated: {total_migrated}")
        print("=" * 60)
        
    finally:
        await sqlite_conn.close()
        await pg_conn.close()
        print("\nDatabase connections closed.")

if __name__ == "__main__":
    asyncio.run(main())

