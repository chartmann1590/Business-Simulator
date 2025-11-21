"""
Migration script for sleep metrics and sick day tracking
Adds comprehensive sleep tracking and sick day management fields
"""
import asyncio
from database.database import engine
from sqlalchemy import text

async def migrate_sleep_and_sick_metrics():
    """Add sleep metrics and sick day tracking columns to employees table."""
    print("=" * 70)
    print("Migrating Sleep Metrics and Sick Day Tracking")
    print("=" * 70)
    print()

    async with engine.begin() as conn:
        # Check if employees table exists
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'employees'
        """))
        table_exists = result.fetchone() is not None

        if not table_exists:
            print("employees table does not exist yet. Skipping migration.")
            return

        # Get existing columns
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'employees'
        """))
        existing_columns = [row[0] for row in result.fetchall()]

        migrations_applied = []

        # Sleep metrics columns
        sleep_columns = {
            'last_sleep_time': 'TIMESTAMP WITH TIME ZONE',
            'last_wake_time': 'TIMESTAMP WITH TIME ZONE',
            'sleep_quality_score': 'DOUBLE PRECISION DEFAULT 100.0',
            'sleep_debt_hours': 'DOUBLE PRECISION DEFAULT 0.0',
            'total_sleep_hours_week': 'DOUBLE PRECISION DEFAULT 0.0',
            'average_bedtime_hour': 'DOUBLE PRECISION',
            'average_wake_hour': 'DOUBLE PRECISION',
        }

        for column_name, column_type in sleep_columns.items():
            if column_name not in existing_columns:
                print(f"Adding {column_name} column...")
                await conn.execute(text(f"""
                    ALTER TABLE employees
                    ADD COLUMN {column_name} {column_type}
                """))
                migrations_applied.append(column_name)
                print(f"  [OK] {column_name} added")

        # Sick day tracking columns
        sick_columns = {
            'is_sick': 'BOOLEAN DEFAULT FALSE',
            'sick_since': 'TIMESTAMP WITH TIME ZONE',
            'sick_reason': 'TEXT',
            'sick_days_this_month': 'INTEGER DEFAULT 0',
            'sick_days_this_year': 'INTEGER DEFAULT 0',
        }

        for column_name, column_type in sick_columns.items():
            if column_name not in existing_columns:
                print(f"Adding {column_name} column...")
                await conn.execute(text(f"""
                    ALTER TABLE employees
                    ADD COLUMN {column_name} {column_type}
                """))
                migrations_applied.append(column_name)
                print(f"  [OK] {column_name} added")

        # Create indexes for performance
        print()
        print("Creating indexes for performance...")

        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_employees_is_sick
                ON employees(is_sick)
                WHERE is_sick = TRUE
            """))
            print("  [OK] Index on is_sick created")
        except Exception as e:
            print(f"  [NOTE] Index on is_sick may already exist: {e}")

        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_employees_sleep_quality
                ON employees(sleep_quality_score)
            """))
            print("  [OK] Index on sleep_quality_score created")
        except Exception as e:
            print(f"  [NOTE] Index on sleep_quality_score may already exist: {e}")

    print()
    print("=" * 70)
    print("Migration Complete!")
    print("=" * 70)
    print()

    if migrations_applied:
        print(f"Applied {len(migrations_applied)} new columns:")
        for col in migrations_applied:
            print(f"  - {col}")
    else:
        print("All columns already exist - no changes needed")

    print()
    print("Sleep metrics and sick day tracking are now available!")
    print("Features enabled:")
    print("  - Sleep quality scoring")
    print("  - Sleep debt tracking")
    print("  - Weekly sleep hour totals")
    print("  - Average bedtime/wake time tracking")
    print("  - Sick day call-in system")
    print("  - Sick day history (monthly/yearly)")

if __name__ == "__main__":
    asyncio.run(migrate_sleep_and_sick_metrics())
