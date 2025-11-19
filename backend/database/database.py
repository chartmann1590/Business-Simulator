from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, func
from sqlalchemy.types import TypeDecorator, DateTime
import os
from datetime import datetime, timezone

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

# Custom function for timezone-aware now() in SQLite
def local_now():
    """Returns current time in configured timezone as ISO string for SQLite."""
    from config import now
    return now().isoformat()

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
        
        # Register custom timezone-aware now() function for SQLite
        # This function returns current time in configured timezone
        def sqlite_local_now():
            from config import now
            dt = now()
            # Return as ISO format string that SQLite can store
            return dt.isoformat()
        
        dbapi_conn.create_function("local_now", 0, sqlite_local_now)
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
    EmployeeReview, Notification, CustomerReview, Product, ProductTeamMember,
    Meeting, OfficePet, Gossip, Weather, RandomEvent, Newsletter, Suggestion, SuggestionVote, BirthdayCelebration
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
        from sqlalchemy import text
        
        # Check if employees table exists using async connection
        async with engine.begin() as conn:
            # Get list of tables using SQL query (works for SQLite)
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """))
            table_rows = result.fetchall()
            tables = [row[0] for row in table_rows]
        
        if 'employees' not in tables:
            # Table doesn't exist yet, skip migration (it will be created with the column)
            return
        
        # Check columns and add missing ones
        async with engine.begin() as conn:
            # Check if employees table exists and get its columns
            result = await conn.execute(text("PRAGMA table_info(employees)"))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]
            
            # Migration: Add has_performance_award column if it doesn't exist
            if 'has_performance_award' not in column_names:
                print("Running migration: Adding has_performance_award column...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN has_performance_award BOOLEAN DEFAULT 0"))
                print("Migration completed: has_performance_award column added.")
            
            # Migration: Add products table if it doesn't exist
            if 'products' not in tables:
                print("Running migration: Creating products table...")
                await conn.execute(text("""
                    CREATE TABLE products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        status TEXT DEFAULT 'active',
                        price REAL DEFAULT 0.0,
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
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                result = await conn.execute(text("PRAGMA table_info(projects)"))
                project_columns = result.fetchall()
                project_column_names = [col[1] for col in project_columns]
                if 'product_id' not in project_column_names:
                    print("Running migration: Adding product_id column to projects table...")
                    await conn.execute(text("ALTER TABLE projects ADD COLUMN product_id INTEGER"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_product_id ON projects(product_id)"))
                    print("Migration completed: product_id column added to projects table.")
            
            # Migration: Add product_id to customer_reviews table if it doesn't exist
            if 'customer_reviews' in tables:
                result = await conn.execute(text("PRAGMA table_info(customer_reviews)"))
                review_columns = result.fetchall()
                review_column_names = [col[1] for col in review_columns]
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
            
            # Migration: Create office_pets table
            if 'office_pets' not in tables:
                print("Running migration: Creating office_pets table...")
                await conn.execute(text("""
                    CREATE TABLE office_pets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            
            # Migration: Create gossip table
            if 'gossip' not in tables:
                print("Running migration: Creating gossip table...")
                await conn.execute(text("""
                    CREATE TABLE gossip (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        originator_id INTEGER,
                        spreader_id INTEGER,
                        recipient_id INTEGER,
                        topic TEXT NOT NULL,
                        content TEXT NOT NULL,
                        credibility REAL DEFAULT 0.5,
                        spread_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (originator_id) REFERENCES employees(id),
                        FOREIGN KEY (spreader_id) REFERENCES employees(id),
                        FOREIGN KEY (recipient_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gossip_created_at ON gossip(created_at)"))
                print("Migration completed: gossip table created.")
            
            # Migration: Create weather table
            if 'weather' not in tables:
                print("Running migration: Creating weather table...")
                await conn.execute(text("""
                    CREATE TABLE weather (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        condition TEXT NOT NULL,
                        temperature REAL NOT NULL,
                        productivity_modifier REAL DEFAULT 1.0,
                        description TEXT,
                        date TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_weather_date ON weather(date)"))
                print("Migration completed: weather table created.")
            
            # Migration: Create random_events table
            if 'random_events' not in tables:
                print("Running migration: Creating random_events table...")
                await conn.execute(text("""
                    CREATE TABLE random_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        impact TEXT DEFAULT 'low',
                        affected_employees TEXT DEFAULT '[]',
                        productivity_modifier REAL DEFAULT 1.0,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_random_events_resolved ON random_events(resolved)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_random_events_start_time ON random_events(start_time)"))
                print("Migration completed: random_events table created.")
            
            # Migration: Create newsletters table
            if 'newsletters' not in tables:
                print("Running migration: Creating newsletters table...")
                await conn.execute(text("""
                    CREATE TABLE newsletters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            
            # Migration: Create suggestions table
            if 'suggestions' not in tables:
                print("Running migration: Creating suggestions table...")
                await conn.execute(text("""
                    CREATE TABLE suggestions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                try:
                    await conn.execute(text("ALTER TABLE suggestions ADD COLUMN manager_comments TEXT"))
                    print("Migration completed: Added manager_comments column to suggestions table.")
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        print(f"Note: manager_comments column may already exist: {e}")
            
            # Migration: Create suggestion_votes table
            if 'suggestion_votes' not in tables:
                print("Running migration: Creating suggestion_votes table...")
                await conn.execute(text("""
                    CREATE TABLE suggestion_votes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            
            # Migration: Create birthday_celebrations table
            if 'birthday_celebrations' not in tables:
                print("Running migration: Creating birthday_celebrations table...")
                await conn.execute(text("""
                    CREATE TABLE birthday_celebrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                result = await conn.execute(text("PRAGMA table_info(birthday_celebrations)"))
                celebration_columns = result.fetchall()
                celebration_column_names = [col[1] for col in celebration_columns]
                
                if 'party_room' not in celebration_column_names:
                    print("Running migration: Adding party fields to birthday_celebrations table...")
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_room TEXT"))
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_floor INTEGER"))
                    await conn.execute(text("ALTER TABLE birthday_celebrations ADD COLUMN party_time TIMESTAMP"))
                    print("Migration completed: Party fields added to birthday_celebrations table.")
            
            # Migration: Create holiday_celebrations table
            if 'holiday_celebrations' not in tables:
                print("Running migration: Creating holiday_celebrations table...")
                await conn.execute(text("""
                    CREATE TABLE holiday_celebrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    except Exception as e:
        print(f"Warning: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue

