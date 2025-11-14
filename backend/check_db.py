"""Quick script to check database status and recreate if needed."""
import asyncio
import os
from database.database import init_db, engine
from sqlalchemy import inspect

async def check_database():
    """Check if all required tables exist."""
    print("Checking database...")
    
    # Check if database file exists
    db_path = "./office.db"
    if os.path.exists(db_path):
        print(f"Database file exists: {db_path}")
        file_size = os.path.getsize(db_path)
        print(f"Database size: {file_size} bytes")
    else:
        print("Database file does not exist - will be created")
    
    # Try to initialize
    try:
        await init_db()
        print("✓ Database initialization successful")
        
        # Check tables
        async with engine.connect() as conn:
            inspector = inspect(engine.sync_engine)
            tables = inspector.get_table_names()
            print(f"\nTables in database: {len(tables)}")
            for table in sorted(tables):
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
                print("\nRecommendation: Delete office.db and restart the server")
            else:
                print("✓ All required tables exist")
                
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())


