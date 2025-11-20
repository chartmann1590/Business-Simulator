from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.dialects.postgresql import asyncpg
import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
# Look for .env file in the backend directory (parent of database directory)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

# PostgreSQL connection configuration
# Default connection string for local development
# Format: postgresql+asyncpg://user:password@host:port/database
# DATABASE_URL must be set in environment variables or .env file
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file or environment variables. "
        "Format: postgresql+asyncpg://user:password@host:port/database"
    )

# PostgreSQL connection pooling configuration optimized for performance
# pool_size: number of connections to maintain persistently (optimized for async)
# max_overflow: additional connections that can be created on demand
# pool_timeout: seconds to wait before giving up on getting a connection
# pool_pre_ping: verify connections before using them (prevents stale connections)
# pool_recycle: recycle connections after this many seconds (prevents connection timeout)
# connect_args: PostgreSQL-specific connection optimizations
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=50,  # INCREASED: More persistent connections for high concurrency
    max_overflow=30,  # INCREASED: More overflow capacity for peak loads (80 total)
    pool_timeout=60,  # INCREASED: Give more time to acquire connections during high load
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=1800,  # REDUCED: Recycle connections every 30 min to prevent staleness
    # PostgreSQL-specific optimizations
    connect_args={
        "server_settings": {
            "application_name": "office_simulator",
            "jit": "on",  # Enable JIT compilation for complex queries
            "work_mem": "16MB",  # Increase work memory for sorts/joins
            "maintenance_work_mem": "64MB",  # For index creation/maintenance
        },
        "timeout": 60,  # Connection timeout in seconds
        "command_timeout": 60,  # Command execution timeout
    },
    # Use connection pooling with statement caching
    execution_options={
        "isolation_level": "READ COMMITTED",  # PostgreSQL default, good for most cases
    }
)

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
    Activity, BusinessMetric, Email, ChatMessage, BusinessSettings, BusinessGoal,
    EmployeeReview, Notification, CustomerReview, Product, ProductTeamMember,
    Meeting, OfficePet, Gossip, Weather, RandomEvent, Newsletter, Suggestion, SuggestionVote, BirthdayCelebration,
    TrainingSession, TrainingMaterial, HomeSettings, FamilyMember, HomePet, ClockInOut, HolidayCelebration, SharedDriveFile, SharedDriveFileVersion, PetCareLog
)

async def get_db():
    async with async_session_maker() as session:
        yield session

async def retry_on_lock(func, max_retries=3, initial_delay=0.5):
    """
    Retry a database operation if it fails due to database lock or deadlock.
    
    PostgreSQL-specific error codes:
    - 40P01: deadlock_detected
    - 55P03: lock_not_available
    - 40001: serialization_failure
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles with each retry)
    
    Returns:
        Result of func() if successful
    
    Raises:
        The last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except OperationalError as e:
            last_exception = e
            error_str = str(e).lower()
            error_code = getattr(e.orig, 'pgcode', None) if hasattr(e, 'orig') else None
            
            # Check for PostgreSQL-specific lock errors
            is_lock_error = (
                error_code in ['40P01', '55P03', '40001'] or  # Deadlock, lock not available, serialization failure
                "deadlock" in error_str or
                "lock" in error_str or
                "serialization" in error_str
            )
            
            if is_lock_error and attempt < max_retries - 1:
                print(f"⚠️  Database lock/deadlock detected, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise
        except Exception as e:
            # For non-lock exceptions, don't retry
            raise
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception


async def safe_commit(session, max_retries=5, initial_delay=0.1):
    """
    Safely commit a database session with automatic retry and rollback on lock errors.
    
    Args:
        session: SQLAlchemy AsyncSession
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before retry (default: 0.1)
    """
    async def commit_op():
        return await session.commit()
    return await safe_db_operation(session, commit_op, max_retries, initial_delay)


async def safe_flush(session, max_retries=5, initial_delay=0.1):
    """
    Safely flush a database session with automatic retry and rollback on lock errors.
    
    Args:
        session: SQLAlchemy AsyncSession
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before retry (default: 0.1)
    """
    async def flush_op():
        return await session.flush()
    return await safe_db_operation(session, flush_op, max_retries, initial_delay)


async def safe_db_operation(session, operation, max_retries=5, initial_delay=0.1):
    """
    Safely execute a database operation with automatic retry and rollback on lock errors.
    
    This function handles:
    - PostgreSQL deadlock errors (40P01)
    - Lock timeout errors (55P03)
    - Serialization failures (40001)
    - Automatic session rollback on errors
    - Proper session state management
    
    Args:
        session: SQLAlchemy AsyncSession
        operation: Async function that performs the database operation (e.g., commit, flush)
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before retry (default: 0.1)
    
    Returns:
        Result of operation() if successful
    
    Raises:
        The last exception if all retries fail
    """
    from sqlalchemy.exc import PendingRollbackError
    
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # Check if session needs rollback first
            if session.in_transaction() and session.is_active:
                try:
                    # Try to access session state to check if it's in a bad state
                    pass
                except PendingRollbackError:
                    # Session needs rollback before we can proceed
                    try:
                        await session.rollback()
                    except Exception as rollback_error:
                        # If rollback fails, we're in a bad state - try to continue anyway
                        print(f"⚠️  Warning: Rollback failed: {rollback_error}")
            
            # Execute the operation
            return await operation()
            
        except OperationalError as e:
            last_exception = e
            error_str = str(e).lower()
            error_code = getattr(e.orig, 'pgcode', None) if hasattr(e, 'orig') else None
            
            # Check for PostgreSQL-specific lock/deadlock errors
            is_lock_error = (
                error_code in ['40P01', '55P03', '40001'] or  # Deadlock, lock not available, serialization failure
                "deadlock" in error_str or
                "lock" in error_str or
                "serialization" in error_str
            )
            
            if is_lock_error and attempt < max_retries - 1:
                # Rollback the session on lock error
                try:
                    await session.rollback()
                except Exception as rollback_error:
                    # Rollback might fail if session is already rolled back
                    pass
                
                print(f"⚠️  Database lock/deadlock detected, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 2.0)  # Exponential backoff, capped at 2 seconds
            else:
                # Final attempt failed or non-retryable error
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise
                
        except PendingRollbackError as e:
            last_exception = e
            # Session is in a bad state - rollback and retry
            try:
                await session.rollback()
            except Exception as rollback_error:
                print(f"⚠️  Warning: Rollback failed during retry: {rollback_error}")
            
            if attempt < max_retries - 1:
                print(f"⚠️  Session rollback required, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 2.0)
            else:
                raise
                
        except Exception as e:
            # For other exceptions, rollback and re-raise immediately (don't retry)
            try:
                await session.rollback()
            except Exception:
                pass
            raise
    
    # If we get here, all retries failed
    if last_exception:
        try:
            await session.rollback()
        except Exception:
            pass
        raise last_exception

async def init_db():
    """Initialize database and create all tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully.")
        
        # Run migrations for existing databases
        await _run_migrations()
        
        # Create optimization indexes (non-blocking, can run in background)
        try:
            from database.optimize_indexes import create_optimization_indexes
            await create_optimization_indexes()
            print("Database indexes optimized.")
        except Exception as index_error:
            print(f"Warning: Could not create optimization indexes: {index_error}")
            # Don't fail startup if indexes can't be created
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue
        # The tables might already exist or will be created on next startup

async def _run_migrations():
    """Run database migrations for existing PostgreSQL databases."""
    try:
        # Check if employees table exists using PostgreSQL information_schema
        async with engine.begin() as conn:
            # Get list of tables using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            table_rows = result.fetchall()
            tables = [row[0] for row in table_rows]
        
        if 'employees' not in tables:
            # Table doesn't exist yet, skip migration (it will be created with the column)
            return
        
        # Check columns and add missing ones
        async with engine.begin() as conn:
            # Get column names from PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'employees'
            """))
            column_rows = result.fetchall()
            column_names = [row[0] for row in column_rows]
            
            # Migration: Add has_performance_award column if it doesn't exist
            if 'has_performance_award' not in column_names:
                print("Running migration: Adding has_performance_award column...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN has_performance_award BOOLEAN DEFAULT FALSE"))
                print("Migration completed: has_performance_award column added.")
            
            # Migration: Add products table if it doesn't exist
            if 'products' not in tables:
                print("Running migration: Creating products table...")
                await conn.execute(text("""
                    CREATE TABLE products (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        status TEXT DEFAULT 'active',
                        price DOUBLE PRECISION DEFAULT 0.0,
                        launch_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at)"))
                print("Migration completed: products table created.")
            
            # Migration: Add product_team_members table if it doesn't exist
            if 'product_team_members' not in tables:
                print("Running migration: Creating product_team_members table...")
                await conn.execute(text("""
                    CREATE TABLE product_team_members (
                        id SERIAL PRIMARY KEY,
                        product_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        role TEXT,
                        responsibility TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id),
                        FOREIGN KEY (employee_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_team_members_product_id ON product_team_members(product_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_team_members_employee_id ON product_team_members(employee_id)"))
                print("Migration completed: product_team_members table created.")
            
            # Migration: Add product_id to projects table if it doesn't exist
            if 'projects' in tables:
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'projects'
                """))
                project_column_rows = result.fetchall()
                project_column_names = [row[0] for row in project_column_rows]
                if 'product_id' not in project_column_names:
                    print("Running migration: Adding product_id column to projects table...")
                    await conn.execute(text("ALTER TABLE projects ADD COLUMN product_id INTEGER"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_product_id ON projects(product_id)"))
                    print("Migration completed: product_id column added to projects table.")
            
            # Migration: Add product_id to customer_reviews table if it doesn't exist
            if 'customer_reviews' in tables:
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'customer_reviews'
                """))
                review_column_rows = result.fetchall()
                review_column_names = [row[0] for row in review_column_rows]
                if 'product_id' not in review_column_names:
                    print("Running migration: Adding product_id column to customer_reviews table...")
                    await conn.execute(text("ALTER TABLE customer_reviews ADD COLUMN product_id INTEGER"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_reviews_product_id ON customer_reviews(product_id)"))
                    print("Migration completed: product_id column added to customer_reviews table.")
            
            # Migration: Add quick wins fields to employees table
            if 'birthday_month' not in column_names:
                print("Running migration: Adding quick wins fields to employees table...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN birthday_month INTEGER"))
                await conn.execute(text("ALTER TABLE employees ADD COLUMN birthday_day INTEGER"))
                await conn.execute(text("ALTER TABLE employees ADD COLUMN hobbies TEXT DEFAULT '[]'"))
                await conn.execute(text("ALTER TABLE employees ADD COLUMN last_coffee_break TIMESTAMP"))
                print("Migration completed: Quick wins fields added to employees table.")
            
            # Migration: Create office_pets table if it doesn't exist
            if 'office_pets' not in tables:
                print("Running migration: Creating office_pets table...")
                await conn.execute(text("""
                    CREATE TABLE office_pets (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        pet_type TEXT NOT NULL,
                        avatar_path TEXT NOT NULL,
                        current_room TEXT,
                        floor INTEGER DEFAULT 1,
                        personality TEXT,
                        favorite_employee_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (favorite_employee_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_office_pets_floor ON office_pets(floor)"))
                print("Migration completed: office_pets table created.")
            
            # Migration: Create gossip table if it doesn't exist
            if 'gossip' not in tables:
                print("Running migration: Creating gossip table...")
                await conn.execute(text("""
                    CREATE TABLE gossip (
                        id SERIAL PRIMARY KEY,
                        originator_id INTEGER,
                        spreader_id INTEGER,
                        recipient_id INTEGER,
                        topic TEXT NOT NULL,
                        content TEXT NOT NULL,
                        credibility DOUBLE PRECISION DEFAULT 0.5,
                        spread_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (originator_id) REFERENCES employees(id),
                        FOREIGN KEY (spreader_id) REFERENCES employees(id),
                        FOREIGN KEY (recipient_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gossip_created_at ON gossip(created_at)"))
                print("Migration completed: gossip table created.")
            
            # Migration: Create weather table if it doesn't exist
            if 'weather' not in tables:
                print("Running migration: Creating weather table...")
                await conn.execute(text("""
                    CREATE TABLE weather (
                        id SERIAL PRIMARY KEY,
                        condition TEXT NOT NULL,
                        temperature DOUBLE PRECISION NOT NULL,
                        productivity_modifier DOUBLE PRECISION DEFAULT 1.0,
                        description TEXT,
                        date TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_weather_date ON weather(date)"))
                print("Migration completed: weather table created.")
            
            # Migration: Create random_events table if it doesn't exist
            if 'random_events' not in tables:
                print("Running migration: Creating random_events table...")
                await conn.execute(text("""
                    CREATE TABLE random_events (
                        id SERIAL PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        impact TEXT DEFAULT 'low',
                        affected_employees TEXT DEFAULT '[]',
                        productivity_modifier DOUBLE PRECISION DEFAULT 1.0,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        resolved BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_random_events_resolved ON random_events(resolved)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_random_events_start_time ON random_events(start_time)"))
                print("Migration completed: random_events table created.")
            
            # Migration: Create newsletters table if it doesn't exist
            if 'newsletters' not in tables:
                print("Running migration: Creating newsletters table...")
                await conn.execute(text("""
                    CREATE TABLE newsletters (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        author_id INTEGER,
                        issue_number INTEGER NOT NULL,
                        published_date TIMESTAMP NOT NULL,
                        read_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (author_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_newsletters_issue_number ON newsletters(issue_number)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_newsletters_published_date ON newsletters(published_date)"))
                print("Migration completed: newsletters table created.")
            
            # Migration: Create suggestions table if it doesn't exist
            if 'suggestions' not in tables:
                print("Running migration: Creating suggestions table...")
                await conn.execute(text("""
                    CREATE TABLE suggestions (
                        id SERIAL PRIMARY KEY,
                        employee_id INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        upvotes INTEGER DEFAULT 0,
                        reviewed_by_id INTEGER,
                        review_notes TEXT,
                        manager_comments TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES employees(id),
                        FOREIGN KEY (reviewed_by_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_suggestions_employee_id ON suggestions(employee_id)"))
                print("Migration completed: suggestions table created.")
            else:
                # Migration: Add manager_comments column if it doesn't exist
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'suggestions'
                """))
                suggestion_column_rows = result.fetchall()
                suggestion_column_names = [row[0] for row in suggestion_column_rows]
                if 'manager_comments' not in suggestion_column_names:
                    try:
                        await conn.execute(text("ALTER TABLE suggestions ADD COLUMN manager_comments TEXT"))
                        print("Migration completed: Added manager_comments column to suggestions table.")
                    except Exception as e:
                        if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                            print(f"Note: manager_comments column may already exist: {e}")
            
            # Migration: Create suggestion_votes table if it doesn't exist
            if 'suggestion_votes' not in tables:
                print("Running migration: Creating suggestion_votes table...")
                await conn.execute(text("""
                    CREATE TABLE suggestion_votes (
                        id SERIAL PRIMARY KEY,
                        suggestion_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (suggestion_id) REFERENCES suggestions(id) ON DELETE CASCADE,
                        FOREIGN KEY (employee_id) REFERENCES employees(id),
                        UNIQUE(suggestion_id, employee_id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_suggestion_votes_suggestion_id ON suggestion_votes(suggestion_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_suggestion_votes_employee_id ON suggestion_votes(employee_id)"))
                print("Migration completed: suggestion_votes table created.")
            
            # Migration: Create birthday_celebrations table if it doesn't exist
            if 'birthday_celebrations' not in tables:
                print("Running migration: Creating birthday_celebrations table...")
                await conn.execute(text("""
                    CREATE TABLE birthday_celebrations (
                        id SERIAL PRIMARY KEY,
                        employee_id INTEGER NOT NULL,
                        celebration_date TIMESTAMP NOT NULL,
                        year INTEGER NOT NULL,
                        attendees TEXT DEFAULT '[]',
                        celebration_message TEXT,
                        party_room TEXT,
                        party_floor INTEGER,
                        party_time TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_birthday_celebrations_date ON birthday_celebrations(celebration_date)"))
                print("Migration completed: birthday_celebrations table created.")
            else:
                # Migration: Add party fields to existing birthday_celebrations table
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'birthday_celebrations'
                """))
                celebration_column_rows = result.fetchall()
                celebration_column_names = [row[0] for row in celebration_column_rows]
                
                if 'party_room' not in celebration_column_names:
                    print("Running migration: Adding party fields to birthday_celebrations table...")
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_room TEXT"))
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_floor INTEGER"))
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_time TIMESTAMP"))
                    print("Migration completed: Party fields added to birthday_celebrations table.")
            
            # Migration: Create holiday_celebrations table if it doesn't exist
            if 'holiday_celebrations' not in tables:
                print("Running migration: Creating holiday_celebrations table...")
                await conn.execute(text("""
                    CREATE TABLE holiday_celebrations (
                        id SERIAL PRIMARY KEY,
                        holiday_name TEXT NOT NULL,
                        celebration_date TIMESTAMP NOT NULL,
                        attendees TEXT DEFAULT '[]',
                        celebration_message TEXT,
                        party_room TEXT,
                        party_floor INTEGER,
                        party_time TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_date ON holiday_celebrations(celebration_date)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_holiday_name ON holiday_celebrations(holiday_name)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_created_at ON holiday_celebrations(created_at)"))
                print("Migration completed: holiday_celebrations table created.")
            
            # Migration: Add current_location columns to family_members and home_pets tables
            if 'family_members' in tables:
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'family_members'
                """))
                family_column_rows = result.fetchall()
                family_column_names = [row[0] for row in family_column_rows]
                
                if 'current_location' not in family_column_names:
                    print("Running migration: Adding current_location column to family_members table...")
                    await conn.execute(text("ALTER TABLE family_members ADD COLUMN current_location TEXT DEFAULT 'inside'"))
                    print("Migration completed: current_location column added to family_members table.")
            
            if 'home_pets' in tables:
                result = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'home_pets'
                """))
                pets_column_rows = result.fetchall()
                pets_column_names = [row[0] for row in pets_column_rows]

                if 'current_location' not in pets_column_names:
                    print("Running migration: Adding current_location column to home_pets table...")
                    await conn.execute(text("ALTER TABLE home_pets ADD COLUMN current_location TEXT DEFAULT 'inside'"))
                    print("Migration completed: current_location column added to home_pets table.")

            # Migration: Add online_status column to employees table (for Teams presence)
            if 'online_status' not in column_names:
                print("Running migration: Adding online_status column to employees table...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN online_status TEXT DEFAULT 'online'"))
                print("Migration completed: online_status column added to employees table.")

            # Migration: Add sleep_state column to employees table (for sleep schedules)
            if 'sleep_state' not in column_names:
                print("Running migration: Adding sleep_state column to employees table...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN sleep_state TEXT DEFAULT 'awake'"))
                print("Migration completed: sleep_state column added to employees table.")

            # Migration: Add sleep_state column to family_members table
            if 'family_members' in tables:
                result = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'family_members'
                """))
                family_sleep_column_rows = result.fetchall()
                family_sleep_column_names = [row[0] for row in family_sleep_column_rows]

                if 'sleep_state' not in family_sleep_column_names:
                    print("Running migration: Adding sleep_state column to family_members table...")
                    await conn.execute(text("ALTER TABLE family_members ADD COLUMN sleep_state TEXT DEFAULT 'awake'"))
                    print("Migration completed: sleep_state column added to family_members table.")

            # Migration: Add sleep_state column to home_pets table
            if 'home_pets' in tables:
                result = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'home_pets'
                """))
                pets_sleep_column_rows = result.fetchall()
                pets_sleep_column_names = [row[0] for row in pets_sleep_column_rows]

                if 'sleep_state' not in pets_sleep_column_names:
                    print("Running migration: Adding sleep_state column to home_pets table...")
                    await conn.execute(text("ALTER TABLE home_pets ADD COLUMN sleep_state TEXT DEFAULT 'awake'"))
                    print("Migration completed: sleep_state column added to home_pets table.")

            # Migration: Create clock_in_out table if it doesn't exist
            if 'clock_in_out' not in tables:
                print("Running migration: Creating clock_in_out table...")
                await conn.execute(text("""
                    CREATE TABLE clock_in_out (
                        id SERIAL PRIMARY KEY,
                        employee_id INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        location TEXT,
                        notes TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clock_in_out_employee_id ON clock_in_out(employee_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clock_in_out_timestamp ON clock_in_out(timestamp)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clock_in_out_event_type ON clock_in_out(event_type)"))
                print("Migration completed: clock_in_out table created.")
    except Exception as e:
        print(f"Warning: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue
