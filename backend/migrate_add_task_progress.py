"""Migration script to add progress column to tasks table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add progress column to tasks table if it doesn't exist."""
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if column exists
        cursor = await db.execute("PRAGMA table_info(tasks)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Existing columns: {column_names}")
        
        # Add column if it doesn't exist
        if 'progress' not in column_names:
            print("Adding progress column to tasks table...")
            await db.execute("ALTER TABLE tasks ADD COLUMN progress REAL DEFAULT 0.0")
            await db.commit()
            print("[OK] Added progress column")
            
            # Update existing tasks: set progress based on status
            print("Updating existing tasks...")
            await db.execute("UPDATE tasks SET progress = 100.0 WHERE status = 'completed'")
            await db.execute("UPDATE tasks SET progress = 50.0 WHERE status = 'in_progress' AND (progress IS NULL OR progress = 0.0)")
            await db.execute("UPDATE tasks SET progress = 0.0 WHERE progress IS NULL")
            await db.commit()
            print("[OK] Updated existing tasks")
        else:
            print("[OK] progress column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())





