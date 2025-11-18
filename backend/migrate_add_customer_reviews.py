"""Migration script to add customer_reviews table."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add customer_reviews table if it doesn't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if customer_reviews table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='customer_reviews'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating customer_reviews table...")
                await db.execute("""
                    CREATE TABLE customer_reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        customer_name TEXT NOT NULL,
                        customer_title TEXT,
                        company_name TEXT,
                        rating REAL NOT NULL,
                        review_text TEXT NOT NULL,
                        verified_purchase BOOLEAN DEFAULT 1,
                        helpful_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects(id)
                    )
                """)
                # Create index for better query performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_customer_reviews_project_id ON customer_reviews(project_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_customer_reviews_created_at ON customer_reviews(created_at)")
                await db.commit()
                print("[OK] Created customer_reviews table")
            else:
                print("[OK] customer_reviews table already exists")
        except Exception as e:
            print(f"Error creating customer_reviews table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())



