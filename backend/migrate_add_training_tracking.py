"""
Migration script to add training tracking tables.
Run this to add training_sessions and training_materials tables.
"""
import asyncio
from sqlalchemy import text
from database.database import engine, DATABASE_URL
from database.models import Base
import asyncpg

async def migrate_database():
    """Add training tracking tables to the database."""
    db_url = DATABASE_URL
    
    # Check if we're using PostgreSQL
    if "postgresql" in db_url or "postgres" in db_url:
        print("Detected PostgreSQL database. Running migration...")
        
        # Parse PostgreSQL URL (handle both postgresql:// and postgresql+asyncpg://)
        # Remove the +asyncpg part if present for parsing
        clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if clean_url.startswith("postgresql://") or clean_url.startswith("postgres://"):
            # Extract connection details
            url_without_prefix = clean_url.replace("postgresql://", "").replace("postgres://", "")
            url_parts = url_without_prefix.split("@")
            if len(url_parts) == 2:
                auth, host_db = url_parts
                user_pass = auth.split(":")
                username = user_pass[0] if user_pass else "postgres"
                password = user_pass[1] if len(user_pass) > 1 else ""
                host_port_db = host_db.split("/")
                host_port = host_port_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 5432
                database = host_port_db[1] if len(host_port_db) > 1 else "office"
                
                # Connect using asyncpg for raw SQL
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user=username,
                    password=password,
                    database=database
                )
                
                try:
                    # Check if training_materials table exists
                    table_check = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'training_materials'
                        )
                    """)
                    
                    if not table_check:
                        print("Creating training_materials table...")
                        await conn.execute("""
                            CREATE TABLE training_materials (
                                id SERIAL PRIMARY KEY,
                                title TEXT NOT NULL,
                                topic TEXT NOT NULL,
                                content TEXT NOT NULL,
                                description TEXT,
                                difficulty_level TEXT DEFAULT 'intermediate',
                                estimated_duration_minutes INTEGER DEFAULT 30,
                                department TEXT,
                                created_by_ai BOOLEAN DEFAULT TRUE,
                                usage_count INTEGER DEFAULT 0,
                                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        await conn.execute("""
                            CREATE INDEX IF NOT EXISTS idx_training_materials_topic 
                            ON training_materials(topic)
                        """)
                        await conn.execute("""
                            CREATE INDEX IF NOT EXISTS idx_training_materials_department 
                            ON training_materials(department)
                        """)
                        print("[OK] training_materials table created")
                    else:
                        print("[OK] training_materials table already exists")
                    
                    # Check if training_sessions table exists
                    table_check = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'training_sessions'
                        )
                    """)
                    
                    if not table_check:
                        print("Creating training_sessions table...")
                        await conn.execute("""
                            CREATE TABLE training_sessions (
                                id SERIAL PRIMARY KEY,
                                employee_id INTEGER NOT NULL REFERENCES employees(id),
                                training_room TEXT NOT NULL,
                                training_topic TEXT NOT NULL,
                                training_material_id INTEGER REFERENCES training_materials(id),
                                start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                                end_time TIMESTAMP WITH TIME ZONE,
                                duration_minutes INTEGER,
                                status TEXT DEFAULT 'in_progress',
                                training_metadata JSONB DEFAULT '{}',
                                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        await conn.execute("""
                            CREATE INDEX IF NOT EXISTS idx_training_sessions_employee_id 
                            ON training_sessions(employee_id)
                        """)
                        await conn.execute("""
                            CREATE INDEX IF NOT EXISTS idx_training_sessions_start_time 
                            ON training_sessions(start_time)
                        """)
                        await conn.execute("""
                            CREATE INDEX IF NOT EXISTS idx_training_sessions_status 
                            ON training_sessions(status)
                        """)
                        print("[OK] training_sessions table created")
                    else:
                        print("[OK] training_sessions table already exists")
                    
                    print("\n[SUCCESS] Migration completed successfully!")
                    
                finally:
                    await conn.close()
        else:
            print("Could not parse PostgreSQL URL")
    else:
        # SQLite - use SQLAlchemy
        print("Detected SQLite database. Running migration...")
        async with engine.begin() as conn:
            # Check if tables exist
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('training_materials', 'training_sessions')
            """))
            existing_tables = [row[0] for row in result.fetchall()]
            
            if 'training_materials' not in existing_tables:
                print("Creating training_materials table...")
                await conn.execute(text("""
                    CREATE TABLE training_materials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        content TEXT NOT NULL,
                        description TEXT,
                        difficulty_level TEXT DEFAULT 'intermediate',
                        estimated_duration_minutes INTEGER DEFAULT 30,
                        department TEXT,
                        created_by_ai INTEGER DEFAULT 1,
                        usage_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_training_materials_topic 
                    ON training_materials(topic)
                """))
                print("[OK] training_materials table created")
            else:
                print("[OK] training_materials table already exists")
            
            if 'training_sessions' not in existing_tables:
                print("Creating training_sessions table...")
                await conn.execute(text("""
                    CREATE TABLE training_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id INTEGER NOT NULL REFERENCES employees(id),
                        training_room TEXT NOT NULL,
                        training_topic TEXT NOT NULL,
                        training_material_id INTEGER REFERENCES training_materials(id),
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        duration_minutes INTEGER,
                        status TEXT DEFAULT 'in_progress',
                        training_metadata TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_training_sessions_employee_id 
                    ON training_sessions(employee_id)
                """))
                print("[OK] training_sessions table created")
            else:
                print("[OK] training_sessions table already exists")
            
            print("\n[SUCCESS] Migration completed successfully!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())

