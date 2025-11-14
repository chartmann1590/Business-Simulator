from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
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
    Activity, BusinessMetric, Email, ChatMessage, BusinessSettings
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
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow the app to continue
        # The tables might already exist or will be created on next startup

