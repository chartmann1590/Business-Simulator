"""Migration script to add target_room field to employees table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

async def migrate_database():
    """Add target_room field to employees table if it doesn't exist."""
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Please set it in your .env file or environment variables. "
            "Format: postgresql+asyncpg://user:password@host:port/database"
        )
    
    # Create async engine with timeout settings for migration
    engine = create_async_engine(
        database_url, 
        echo=False,
        pool_size=1,  # Minimal pool for migration
        max_overflow=0,  # No overflow for migration
        pool_timeout=60,  # Timeout for acquiring connection
        connect_args={
            "command_timeout": 60,  # 60 second timeout for commands
        }
    )
    
    try:
        print("Connecting to database...")
        async with engine.begin() as conn:
            print("Checking if target_room column exists...")
            # Check if column exists using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'employees'
                AND column_name = 'target_room'
            """))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Adding target_room column...")
                print("Note: This requires an exclusive lock on the employees table.")
                print("If the backend server is running, you may need to stop it first.")
                try:
                    # Use IF NOT EXISTS syntax (PostgreSQL 9.5+)
                    await conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS target_room VARCHAR"))
                    print("[OK] Added target_room column")
                except Exception as alter_error:
                    # If IF NOT EXISTS doesn't work, try without it
                    if "IF NOT EXISTS" in str(alter_error):
                        await conn.execute(text("ALTER TABLE employees ADD COLUMN target_room VARCHAR"))
                        print("[OK] Added target_room column")
                    else:
                        raise
            else:
                print("[OK] target_room column already exists")
        
        print("\nMigration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())

