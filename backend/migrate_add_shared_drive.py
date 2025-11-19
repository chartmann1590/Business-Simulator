"""Migration script to add shared_drive_files and shared_drive_file_versions tables."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add shared_drive_files and shared_drive_file_versions tables if they don't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if shared_drive_files table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='shared_drive_files'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating shared_drive_files table...")
                await db.execute("""
                    CREATE TABLE shared_drive_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT NOT NULL,
                        file_type TEXT NOT NULL,
                        department TEXT,
                        employee_id INTEGER,
                        project_id INTEGER,
                        file_path TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        content_html TEXT NOT NULL,
                        file_metadata TEXT DEFAULT '{}',
                        last_updated_by_id INTEGER,
                        current_version INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES employees(id),
                        FOREIGN KEY (project_id) REFERENCES projects(id),
                        FOREIGN KEY (last_updated_by_id) REFERENCES employees(id)
                    )
                """)
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_employee_id ON shared_drive_files(employee_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_project_id ON shared_drive_files(project_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_department ON shared_drive_files(department)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_file_type ON shared_drive_files(file_type)")
                await db.commit()
                print("[OK] Created shared_drive_files table")
            else:
                print("[OK] shared_drive_files table already exists")
        except Exception as e:
            print(f"Error creating shared_drive_files table: {e}")
            import traceback
            traceback.print_exc()
        
        # Check if shared_drive_file_versions table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='shared_drive_file_versions'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating shared_drive_file_versions table...")
                await db.execute("""
                    CREATE TABLE shared_drive_file_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER NOT NULL,
                        version_number INTEGER NOT NULL,
                        content_html TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        created_by_id INTEGER,
                        change_summary TEXT,
                        file_metadata TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES shared_drive_files(id),
                        FOREIGN KEY (created_by_id) REFERENCES employees(id)
                    )
                """)
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_file_id ON shared_drive_file_versions(file_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_version_number ON shared_drive_file_versions(file_id, version_number)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_created_by_id ON shared_drive_file_versions(created_by_id)")
                await db.commit()
                print("[OK] Created shared_drive_file_versions table")
            else:
                print("[OK] shared_drive_file_versions table already exists")
        except Exception as e:
            print(f"Error creating shared_drive_file_versions table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

