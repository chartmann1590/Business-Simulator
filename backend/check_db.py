"""Quick script to check database status and recreate if needed."""
import asyncio
import os
from database.database import init_db, engine
from sqlalchemy import inspect, text

async def check_database():
    """Check if all required tables exist."""
    print("Checking database...")
    
    # Check database connection
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:843e2c46eea146588dbac98162a3835f@localhost:5432/office_db"
    )
    print(f"Database URL: {database_url.split('@')[0]}@***")
    
    # Try to initialize
    try:
        await init_db()
        print("✓ Database initialization successful")
        
        # Check tables using PostgreSQL information_schema
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"\nTables in database: {len(tables)}")
            for table in tables:
                print(f"  - {table}")
            
            required_tables = [
                'employees', 'projects', 'tasks', 'decisions', 
                'financials', 'activities', 'business_metrics',
                'emails', 'chat_messages'
            ]
            
            print(f"\nRequired tables: {len(required_tables)}")
            missing = [t for t in required_tables if t not in tables]
            if missing:
                print(f"⚠ Missing tables: {missing}")
                print("\nRecommendation: Run 'python setup_postgresql.py' to setup the database")
            else:
                print("✓ All required tables exist")
                
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nMake sure PostgreSQL is running and the database exists.")
        print("Run 'python setup_postgresql.py' to setup the database.")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())
