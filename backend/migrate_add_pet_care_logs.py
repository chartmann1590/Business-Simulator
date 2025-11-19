"""Migration script to add pet_care_logs table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add pet_care_logs table if it doesn't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if pet_care_logs table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='pet_care_logs'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating pet_care_logs table...")
                await db.execute("""
                    CREATE TABLE pet_care_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pet_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        care_action TEXT NOT NULL,
                        pet_happiness_before REAL,
                        pet_hunger_before REAL,
                        pet_energy_before REAL,
                        pet_happiness_after REAL,
                        pet_hunger_after REAL,
                        pet_energy_after REAL,
                        ai_reasoning TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (pet_id) REFERENCES office_pets(id),
                        FOREIGN KEY (employee_id) REFERENCES employees(id)
                    )
                """)
                # Create indexes for better query performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_pet_care_logs_pet_id ON pet_care_logs(pet_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_pet_care_logs_employee_id ON pet_care_logs(employee_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_pet_care_logs_created_at ON pet_care_logs(created_at)")
                await db.commit()
                print("[OK] Created pet_care_logs table")
            else:
                print("[OK] pet_care_logs table already exists")
        except Exception as e:
            print(f"Error creating pet_care_logs table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())


