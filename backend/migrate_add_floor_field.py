"""Migration script to add floor field to employees table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate_database():
    """Add floor field to employees table if it doesn't exist."""
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
            """))
            column_rows = result.fetchall()
            column_names = [row[0] for row in column_rows]
            
            print(f"Existing columns: {column_names}")
            
            # Add column if it doesn't exist
            if 'floor' not in column_names:
                print("Adding floor column...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN floor INTEGER DEFAULT 1"))
                print("[OK] Added floor column")
            else:
                print("[OK] floor column already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())
