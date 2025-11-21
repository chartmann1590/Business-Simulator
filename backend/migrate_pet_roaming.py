"""
Migration script for office pet roaming feature
Adds last_room_change column to office_pets table
"""
import asyncio
from database.database import engine
from sqlalchemy import text

async def migrate_pet_roaming():
    """Add last_room_change column to office_pets table."""
    print("=" * 60)
    print("Migrating Office Pet Roaming Feature")
    print("=" * 60)
    print()

    async with engine.begin() as conn:
        # Check if office_pets table exists
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'office_pets'
        """))
        table_exists = result.fetchone() is not None

        if not table_exists:
            print("office_pets table does not exist yet. Skipping migration.")
            print("The column will be created when the table is first created.")
            return

        # Check if last_room_change column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'office_pets'
            AND column_name = 'last_room_change'
        """))
        column_exists = result.fetchone() is not None

        if column_exists:
            print("[OK] last_room_change column already exists in office_pets table")
        else:
            print("Adding last_room_change column to office_pets table...")
            await conn.execute(text("""
                ALTER TABLE office_pets
                ADD COLUMN last_room_change TIMESTAMP WITH TIME ZONE
            """))
            print("[OK] last_room_change column added successfully")

        # Update existing pets to set last_room_change to current time
        result = await conn.execute(text("""
            UPDATE office_pets
            SET last_room_change = CURRENT_TIMESTAMP
            WHERE last_room_change IS NULL
        """))
        rows_updated = result.rowcount
        if rows_updated > 0:
            print(f"[OK] Updated {rows_updated} existing pet(s) with current timestamp")

    print()
    print("=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print()
    print("Office pets will now roam the office and move rooms")
    print("automatically after staying in one room for 1+ hour.")

if __name__ == "__main__":
    asyncio.run(migrate_pet_roaming())
