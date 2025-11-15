from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
import os

# Use absolute path to ensure we're using the right database file
_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "office.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{_db_path}")

# SQLite-specific configuration to handle locks better
# timeout=20 means wait up to 20 seconds for locks to be released
# check_same_thread=False allows multiple threads to access the database
engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    future=True,
    connect_args={
        "timeout": 20,  # Wait up to 20 seconds for locks
        "check_same_thread": False
    },
    pool_pre_ping=True  # Verify connections before using them
)

# Enable WAL (Write-Ahead Logging) mode for better concurrency
# This allows multiple readers and one writer simultaneously
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and optimize SQLite for concurrent access."""
    cursor = dbapi_conn.cursor()
    try:
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout (in milliseconds)
        cursor.execute("PRAGMA busy_timeout=20000")
        # Optimize for concurrent access
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()
    except Exception as e:
        print(f"Warning: Could not set SQLite pragmas: {e}")
        cursor.close()
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

# Import all models to ensure they're registered with Base
from database.models import (
    Employee, Project, Task, Decision, Financial, 
    Activity, BusinessMetric, Email, ChatMessage, BusinessSettings,
    EmployeeReview, Notification, CustomerReview
)

async def get_db():
    async with async_session_maker() as session:
        yield session

async def init_db():
    """Initialize database and create all tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully.")
        
        # Run migrations for existing databases
        await _run_migrations()
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue
        # The tables might already exist or will be created on next startup

async def _run_migrations():
    """Run database migrations for existing databases."""
    try:
        from sqlalchemy import text, inspect
        
        # Check if employees table exists
        inspector = inspect(engine.sync_engine)
        tables = inspector.get_table_names()
        
        if 'employees' not in tables:
            # Table doesn't exist yet, skip migration (it will be created with the column)
            return
        
        # Check columns and add missing ones
        async with engine.begin() as conn:
            # Check if employees table exists and get its columns
            result = await conn.execute(text("PRAGMA table_info(employees)"))
            columns = await result.fetchall()
            column_names = [col[1] for col in columns]
            
            # Migration: Add has_performance_award column if it doesn't exist
            if 'has_performance_award' not in column_names:
                print("Running migration: Adding has_performance_award column...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN has_performance_award BOOLEAN DEFAULT 0"))
                print("Migration completed: has_performance_award column added.")
    except Exception as e:
        print(f"Warning: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue

