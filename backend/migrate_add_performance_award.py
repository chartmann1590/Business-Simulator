"""Migration script to add has_performance_award field to employees table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add has_performance_award field to employees table if it doesn't exist."""
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
        if 'has_performance_award' not in column_names:
            print("Adding has_performance_award column...")
            await db.execute("ALTER TABLE employees ADD COLUMN has_performance_award BOOLEAN DEFAULT 0")
            await db.commit()
            print("[OK] Added has_performance_award column")
        else:
            print("[OK] has_performance_award column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())



