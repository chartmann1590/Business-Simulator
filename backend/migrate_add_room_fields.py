"""Migration script to add room fields to employees table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add room fields to employees table if they don't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if columns exist
        cursor = await db.execute("PRAGMA table_info(employees)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Existing columns: {column_names}")
        
        # Add columns if they don't exist
        if 'current_room' not in column_names:
            print("Adding current_room column...")
            await db.execute("ALTER TABLE employees ADD COLUMN current_room TEXT")
            await db.commit()
            print("[OK] Added current_room column")
        else:
            print("[OK] current_room column already exists")
        
        if 'home_room' not in column_names:
            print("Adding home_room column...")
            await db.execute("ALTER TABLE employees ADD COLUMN home_room TEXT")
            await db.commit()
            print("[OK] Added home_room column")
        else:
            print("[OK] home_room column already exists")
        
        if 'activity_state' not in column_names:
            print("Adding activity_state column...")
            await db.execute("ALTER TABLE employees ADD COLUMN activity_state TEXT DEFAULT 'idle'")
            await db.commit()
            print("[OK] Added activity_state column")
        else:
            print("[OK] activity_state column already exists")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

