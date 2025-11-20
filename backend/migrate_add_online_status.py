"""Migration script to add online_status field to employees table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

async def migrate_database():
    """Add online_status field to employees table if it doesn't exist."""
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
                AND column_name = 'online_status'
            """))
            column_exists = result.fetchone() is not None
            
            # Add column if it doesn't exist
            if not column_exists:
                print("Adding online_status column...")
                await conn.execute(text("""
                    ALTER TABLE employees 
                    ADD COLUMN online_status VARCHAR DEFAULT 'online'
                """))
                print("[OK] Added online_status column")
                
                # Update existing rows to have 'online' status
                await conn.execute(text("""
                    UPDATE employees 
                    SET online_status = 'online' 
                    WHERE online_status IS NULL
                """))
                print("[OK] Updated existing employees with default online_status")
            else:
                print("[OK] online_status column already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())

