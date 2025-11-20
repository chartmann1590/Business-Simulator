"""Migration script to add shared_drive_files and shared_drive_file_versions tables."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate_database():
    """Add shared_drive_files and shared_drive_file_versions tables if they don't exist."""
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Please set it in your .env file or environment variables. "
            "Format: postgresql+asyncpg://user:password@host:port/database"
        )
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check if shared_drive_files table exists using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'shared_drive_files'
            """))
            table_exists = result.fetchone()
            
            if not table_exists:
                print("Creating shared_drive_files table...")
                await conn.execute(text("""
                    CREATE TABLE shared_drive_files (
                        id SERIAL PRIMARY KEY,
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
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_employee_id ON shared_drive_files(employee_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_project_id ON shared_drive_files(project_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_department ON shared_drive_files(department)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_files_file_type ON shared_drive_files(file_type)"))
                print("[OK] Created shared_drive_files table")
            else:
                print("[OK] shared_drive_files table already exists")
            
            # Check if shared_drive_file_versions table exists
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'shared_drive_file_versions'
            """))
            table_exists = result.fetchone()
            
            if not table_exists:
                print("Creating shared_drive_file_versions table...")
                await conn.execute(text("""
                    CREATE TABLE shared_drive_file_versions (
                        id SERIAL PRIMARY KEY,
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
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_file_id ON shared_drive_file_versions(file_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_version_number ON shared_drive_file_versions(file_id, version_number)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_shared_drive_file_versions_created_by_id ON shared_drive_file_versions(created_by_id)"))
                print("[OK] Created shared_drive_file_versions table")
            else:
                print("[OK] shared_drive_file_versions table already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())
