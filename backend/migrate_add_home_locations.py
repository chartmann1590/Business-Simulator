"""
Migration script to add current_location columns to family_members and home_pets tables.
Run this to add location tracking for family members and pets (inside/outside).
"""
import asyncio
from sqlalchemy import text
from database.database import engine, DATABASE_URL

async def migrate_database():
    """Add current_location columns to family_members and home_pets tables."""
    print("=" * 80)
    print("HOME LOCATIONS MIGRATION")
    print("Adding current_location columns to family_members and home_pets tables")
    print("=" * 80)
    
    try:
        async with engine.begin() as conn:
            # Check if family_members table exists
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'family_members'
            """))
            family_table_exists = result.fetchone()
            
            if family_table_exists:
                # Check if current_location column exists in family_members
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'family_members'
                    AND column_name = 'current_location'
                """))
                family_location_exists = result.fetchone()
                
                if not family_location_exists:
                    print("[MIGRATION] Adding current_location column to family_members table...")
                    await conn.execute(text("""
                        ALTER TABLE family_members 
                        ADD COLUMN current_location TEXT DEFAULT 'inside'
                    """))
                    print("[OK] Added current_location column to family_members table")
                else:
                    print("[OK] current_location column already exists in family_members table")
            else:
                print("[SKIP] family_members table does not exist yet (will be created with column)")
            
            # Check if home_pets table exists
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'home_pets'
            """))
            pets_table_exists = result.fetchone()
            
            if pets_table_exists:
                # Check if current_location column exists in home_pets
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'home_pets'
                    AND column_name = 'current_location'
                """))
                pets_location_exists = result.fetchone()
                
                if not pets_location_exists:
                    print("[MIGRATION] Adding current_location column to home_pets table...")
                    await conn.execute(text("""
                        ALTER TABLE home_pets 
                        ADD COLUMN current_location TEXT DEFAULT 'inside'
                    """))
                    print("[OK] Added current_location column to home_pets table")
                else:
                    print("[OK] current_location column already exists in home_pets table")
            else:
                print("[SKIP] home_pets table does not exist yet (will be created with column)")
        
        print("=" * 80)
        print("[SUCCESS] Migration completed!")
        print("=" * 80)
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(migrate_database())

