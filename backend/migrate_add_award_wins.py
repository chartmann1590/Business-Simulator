"""Migration script to add performance_award_wins field to employees table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate_database():
    """Add performance_award_wins field to employees table if it doesn't exist."""
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:843e2c46eea146588dbac98162a3835f@localhost:5432/office_db"
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
            if 'performance_award_wins' not in column_names:
                print("Adding performance_award_wins column...")
                await conn.execute(text("ALTER TABLE employees ADD COLUMN performance_award_wins INTEGER DEFAULT 0"))
                print("[OK] Added performance_award_wins column")
            else:
                print("[OK] performance_award_wins column already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())
