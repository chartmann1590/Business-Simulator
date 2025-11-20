"""Migration script to add products and product_team_members tables."""
import asyncio
import asyncpg
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

async def migrate_database():
    """Add products and product_team_members tables if they don't exist."""
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
            # Check if products table exists using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'products'
            """))
            table_exists = result.fetchone()
            
            if not table_exists:
                print("Creating products table...")
                await conn.execute(text("""
                    CREATE TABLE products (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        status TEXT DEFAULT 'active',
                        price DOUBLE PRECISION DEFAULT 0.0,
                        launch_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at)"))
                print("[OK] Created products table")
            else:
                print("[OK] products table already exists")
            
            # Check if product_team_members table exists
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'product_team_members'
            """))
            table_exists = result.fetchone()
            
            if not table_exists:
                print("Creating product_team_members table...")
                await conn.execute(text("""
                    CREATE TABLE product_team_members (
                        id SERIAL PRIMARY KEY,
                        product_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        role TEXT,
                        responsibility TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id),
                        FOREIGN KEY (employee_id) REFERENCES employees(id)
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_team_members_product_id ON product_team_members(product_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_team_members_employee_id ON product_team_members(employee_id)"))
                print("[OK] Created product_team_members table")
            else:
                print("[OK] product_team_members table already exists")
            
            # Add product_id column to projects table if it doesn't exist
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'projects'
            """))
            column_rows = result.fetchall()
            column_names = [row[0] for row in column_rows]
            
            if 'product_id' not in column_names:
                print("Adding product_id column to projects table...")
                await conn.execute(text("ALTER TABLE projects ADD COLUMN product_id INTEGER"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_product_id ON projects(product_id)"))
                print("[OK] Added product_id column to projects table")
            else:
                print("[OK] product_id column already exists in projects table")
            
            # Add product_id column to customer_reviews table if it doesn't exist
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'customer_reviews'
            """))
            column_rows = result.fetchall()
            column_names = [row[0] for row in column_rows]
            
            if 'product_id' not in column_names:
                print("Adding product_id column to customer_reviews table...")
                await conn.execute(text("ALTER TABLE customer_reviews ADD COLUMN product_id INTEGER"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_reviews_product_id ON customer_reviews(product_id)"))
                print("[OK] Added product_id column to customer_reviews table")
            else:
                print("[OK] product_id column already exists in customer_reviews table")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())
