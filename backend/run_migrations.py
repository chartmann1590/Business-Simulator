"""
Manual migration script to test database migrations before backend restart.
Run this to ensure all migrations complete successfully.
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import init_db


async def main():
    """Run database initialization and migrations."""
    print("=" * 60)
    print("Running Database Migrations")
    print("=" * 60)
    print()

    try:
        await init_db()
        print()
        print("=" * 60)
        print("[SUCCESS] Migrations completed successfully!")
        print("=" * 60)
        print()
        print("The following changes have been applied:")
        print("  • online_status column added to employees table")
        print("  • sleep_state column added to employees table")
        print("  • sleep_state column added to family_members table")
        print("  • sleep_state column added to home_pets table")
        print("  • clock_in_out table created with indexes")
        print("  • manager_id column added to employees table (for organizational hierarchy)")
        print("  • Foreign key constraint added for manager_id")
        print()
        print("You can now restart the backend server.")

    except Exception as e:
        print()
        print("=" * 60)
        print("[ERROR] Migration failed!")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
