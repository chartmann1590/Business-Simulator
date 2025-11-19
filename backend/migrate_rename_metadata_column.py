"""Migration script to rename metadata column to file_metadata in shared drive tables."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Rename metadata column to file_metadata in shared_drive_files and shared_drive_file_versions tables."""
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if metadata column exists in shared_drive_files
        try:
            cursor = await db.execute("PRAGMA table_info(shared_drive_files)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'metadata' in column_names and 'file_metadata' not in column_names:
                print("Renaming metadata to file_metadata in shared_drive_files table...")
                # SQLite doesn't support ALTER TABLE RENAME COLUMN directly, so we need to recreate
                await db.execute("""
                    CREATE TABLE shared_drive_files_new (
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
                await db.execute("""
                    INSERT INTO shared_drive_files_new 
                    SELECT id, file_name, file_type, department, employee_id, project_id, 
                           file_path, file_size, content_html, metadata, last_updated_by_id,
                           current_version, created_at, updated_at
                    FROM shared_drive_files
                """)
                await db.execute("DROP TABLE shared_drive_files")
                await db.execute("ALTER TABLE shared_drive_files_new RENAME TO shared_drive_files")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_employee_id ON shared_drive_files(employee_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_project_id ON shared_drive_files(project_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_department ON shared_drive_files(department)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_file_type ON shared_drive_files(file_type)")
                await db.commit()
                print("[OK] Renamed metadata to file_metadata in shared_drive_files")
            else:
                print("[OK] Column already renamed or doesn't exist in shared_drive_files")
        except Exception as e:
            print(f"Error renaming column in shared_drive_files: {e}")
            import traceback
            traceback.print_exc()
        
        # Check if metadata column exists in shared_drive_file_versions
        try:
            cursor = await db.execute("PRAGMA table_info(shared_drive_file_versions)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'metadata' in column_names and 'file_metadata' not in column_names:
                print("Renaming metadata to file_metadata in shared_drive_file_versions table...")
                await db.execute("""
                    CREATE TABLE shared_drive_file_versions_new (
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
                await db.execute("""
                    INSERT INTO shared_drive_file_versions_new 
                    SELECT id, file_id, version_number, content_html, file_size, 
                           created_by_id, change_summary, metadata, created_at
                    FROM shared_drive_file_versions
                """)
                await db.execute("DROP TABLE shared_drive_file_versions")
                await db.execute("ALTER TABLE shared_drive_file_versions_new RENAME TO shared_drive_file_versions")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_file_id ON shared_drive_file_versions(file_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_version_number ON shared_drive_file_versions(file_id, version_number)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_created_by_id ON shared_drive_file_versions(created_by_id)")
                await db.commit()
                print("[OK] Renamed metadata to file_metadata in shared_drive_file_versions")
            else:
                print("[OK] Column already renamed or doesn't exist in shared_drive_file_versions")
        except Exception as e:
            print(f"Error renaming column in shared_drive_file_versions: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

