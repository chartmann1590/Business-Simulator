"""Migration script to add performance_award_wins field to employees table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add performance_award_wins field to employees table if it doesn't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if column exists
        cursor = await db.execute("PRAGMA table_info(employees)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Existing columns: {column_names}")
        
        # Add column if it doesn't exist
        if 'performance_award_wins' not in column_names:
            print("Adding performance_award_wins column...")
            await db.execute("ALTER TABLE employees ADD COLUMN performance_award_wins INTEGER DEFAULT 0")
            await db.commit()
            print("[OK] Added performance_award_wins column")
        else:
            print("[OK] performance_award_wins column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

