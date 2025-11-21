"""
Simple script to add manager_id column to employees table
"""
import asyncio
from database.database import engine
from sqlalchemy import text


async def add_manager_column():
    print("Adding manager_id column to employees table...")

    async with engine.begin() as conn:
        # Add the column
        try:
            await conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS manager_id INTEGER"))
            print("Column added successfully")
        except Exception as e:
            print(f"Column may already exist or error: {e}")

        # Add index
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_employees_manager_id ON employees(manager_id)"))
            print("Index added successfully")
        except Exception as e:
            print(f"Index may already exist or error: {e}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(add_manager_column())
