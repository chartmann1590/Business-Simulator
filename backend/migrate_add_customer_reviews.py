"""Migration script to add customer_reviews table."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate_database():
    """Add customer_reviews table if it doesn't exist."""
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:843e2c46eea146588dbac98162a3835f@localhost:5432/office_db"
    )
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check if customer_reviews table exists using PostgreSQL information_schema
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'customer_reviews'
            """))
            table_exists = result.fetchone()
            
            if not table_exists:
                print("Creating customer_reviews table...")
                await conn.execute(text("""
                    CREATE TABLE customer_reviews (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER,
                        product_id INTEGER,
                        customer_name TEXT NOT NULL,
                        customer_title TEXT,
                        company_name TEXT,
                        rating DOUBLE PRECISION NOT NULL,
                        review_text TEXT NOT NULL,
                        verified_purchase BOOLEAN DEFAULT TRUE,
                        helpful_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects(id),
                        FOREIGN KEY (product_id) REFERENCES products(id)
                    )
                """))
                # Create index for better query performance
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_reviews_project_id ON customer_reviews(project_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_reviews_product_id ON customer_reviews(product_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_reviews_created_at ON customer_reviews(created_at)"))
                print("[OK] Created customer_reviews table")
            else:
                print("[OK] customer_reviews table already exists")
        
        print("\nMigration completed!")
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_database())
