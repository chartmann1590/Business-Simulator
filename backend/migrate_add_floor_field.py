"""Migration script to add floor field to employees table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add floor field to employees table if it doesn't exist."""
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
        if 'floor' not in column_names:
            print("Adding floor column...")
            await db.execute("ALTER TABLE employees ADD COLUMN floor INTEGER DEFAULT 1")
            await db.commit()
            print("[OK] Added floor column")
        else:
            print("[OK] floor column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())




