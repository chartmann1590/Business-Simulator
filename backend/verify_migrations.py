"""
Verify all required database columns exist
"""
import asyncio
from database.database import engine
from sqlalchemy import text

async def verify_migrations():
    """Verify all required migrations have been applied."""
    print("=" * 60)
    print("Verifying Database Migrations")
    print("=" * 60)
    print()

    async with engine.begin() as conn:
        # Check employees table columns
        print("Checking employees table...")
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'employees'
            ORDER BY column_name
        """))
        employee_columns = [row[0] for row in result.fetchall()]

        required_columns = ['manager_id', 'online_status', 'sleep_state', 'last_coffee_break']
        for col in required_columns:
            if col in employee_columns:
                print(f"  [OK] {col}")
            else:
                print(f"  [MISSING] {col}")

        # Check office_pets table columns
        print()
        print("Checking office_pets table...")
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'office_pets'
            ORDER BY column_name
        """))
        pet_columns = [row[0] for row in result.fetchall()]

        pet_required = ['last_room_change', 'current_room', 'floor']
        for col in pet_required:
            if col in pet_columns:
                print(f"  [OK] {col}")
            else:
                print(f"  [MISSING] {col}")

        # Check family_members table columns
        print()
        print("Checking family_members table...")
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'family_members'
            ORDER BY column_name
        """))
        family_columns = [row[0] for row in result.fetchall()]

        family_required = ['sleep_state', 'current_location']
        for col in family_required:
            if col in family_columns:
                print(f"  [OK] {col}")
            else:
                print(f"  [MISSING] {col}")

        # Check home_pets table columns
        print()
        print("Checking home_pets table...")
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'home_pets'
            ORDER BY column_name
        """))
        home_pet_columns = [row[0] for row in result.fetchall()]

        home_pet_required = ['sleep_state', 'current_location']
        for col in home_pet_required:
            if col in home_pet_columns:
                print(f"  [OK] {col}")
            else:
                print(f"  [MISSING] {col}")

    print()
    print("=" * 60)
    print("Verification Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_migrations())
