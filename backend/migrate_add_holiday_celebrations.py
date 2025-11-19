"""Migration script to add holiday_celebrations table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add holiday_celebrations table if it doesn't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if holiday_celebrations table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='holiday_celebrations'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating holiday_celebrations table...")
                await db.execute("""
                    CREATE TABLE holiday_celebrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        holiday_name TEXT NOT NULL,
                        celebration_date TIMESTAMP NOT NULL,
                        attendees TEXT,
                        celebration_message TEXT,
                        party_room TEXT,
                        party_floor INTEGER,
                        party_time TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create indexes for better query performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_date ON holiday_celebrations(celebration_date)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_holiday_name ON holiday_celebrations(holiday_name)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_holiday_celebrations_created_at ON holiday_celebrations(created_at)")
                await db.commit()
                print("[OK] Created holiday_celebrations table")
            else:
                print("[OK] holiday_celebrations table already exists")
        except Exception as e:
            print(f"Error creating holiday_celebrations table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

