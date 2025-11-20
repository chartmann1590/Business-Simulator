"""Migration script to add sleep_state field to employees table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

async def migrate_database():
    """Add sleep_state field to employees table if it doesn't exist."""
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Please set it in your .env file or environment variables. "
            "Format: postgresql+asyncpg://user:password@host:port/database"
        )
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check if column exists using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'employees'
                AND column_name = 'sleep_state'
            """))
            column_exists = result.fetchone() is not None
            
            # Add column if it doesn't exist
            if not column_exists:
                print("Adding sleep_state column...")
                await conn.execute(text("""
                    ALTER TABLE employees 
                    ADD COLUMN sleep_state VARCHAR DEFAULT 'awake'
                """))
                print("[OK] Added sleep_state column")
                
                # Update existing rows to have 'awake' status
                await conn.execute(text("""
                    UPDATE employees 
                    SET sleep_state = 'awake' 
                    WHERE sleep_state IS NULL
                """))
                print("[OK] Updated existing employees with default sleep_state")
            else:
                print("[OK] sleep_state column already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())

