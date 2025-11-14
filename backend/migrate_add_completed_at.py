"""Migration script to add completed_at column to projects table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add completed_at column to projects table if it doesn't exist."""
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if column exists
        cursor = await db.execute("PRAGMA table_info(projects)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Existing columns: {column_names}")
        
        # Add column if it doesn't exist
        if 'completed_at' not in column_names:
            print("Adding completed_at column...")
            await db.execute("ALTER TABLE projects ADD COLUMN completed_at DATETIME")
            await db.commit()
            print("[OK] Added completed_at column")
        else:
            print("[OK] completed_at column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())
