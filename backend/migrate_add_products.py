"""Migration script to add products and product_team_members tables."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add products and product_team_members tables if they don't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if products table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='products'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating products table...")
                await db.execute("""
                    CREATE TABLE products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        status TEXT DEFAULT 'active',
                        price REAL DEFAULT 0.0,
                        launch_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at)")
                await db.commit()
                print("[OK] Created products table")
            else:
                print("[OK] products table already exists")
        except Exception as e:
            print(f"Error creating products table: {e}")
            import traceback
            traceback.print_exc()
        
        # Check if product_team_members table exists
        try:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='product_team_members'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("Creating product_team_members table...")
                await db.execute("""
                    CREATE TABLE product_team_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        role TEXT,
                        responsibility TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id),
                        FOREIGN KEY (employee_id) REFERENCES employees(id)
                    )
                """)
                await db.execute("CREATE INDEX IF NOT EXISTS idx_product_team_members_product_id ON product_team_members(product_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_product_team_members_employee_id ON product_team_members(employee_id)")
                await db.commit()
                print("[OK] Created product_team_members table")
            else:
                print("[OK] product_team_members table already exists")
        except Exception as e:
            print(f"Error creating product_team_members table: {e}")
            import traceback
            traceback.print_exc()
        
        # Add product_id column to projects table if it doesn't exist
        try:
            cursor = await db.execute("PRAGMA table_info(projects)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'product_id' not in column_names:
                print("Adding product_id column to projects table...")
                await db.execute("ALTER TABLE projects ADD COLUMN product_id INTEGER")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_product_id ON projects(product_id)")
                await db.commit()
                print("[OK] Added product_id column to projects table")
            else:
                print("[OK] product_id column already exists in projects table")
        except Exception as e:
            print(f"Error adding product_id to projects table: {e}")
            import traceback
            traceback.print_exc()
        
        # Add product_id column to customer_reviews table if it doesn't exist
        try:
            cursor = await db.execute("PRAGMA table_info(customer_reviews)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'product_id' not in column_names:
                print("Adding product_id column to customer_reviews table...")
                await db.execute("ALTER TABLE customer_reviews ADD COLUMN product_id INTEGER")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_customer_reviews_product_id ON customer_reviews(product_id)")
                await db.commit()
                print("[OK] Added product_id column to customer_reviews table")
            else:
                print("[OK] product_id column already exists in customer_reviews table")
        except Exception as e:
            print(f"Error adding product_id to customer_reviews table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())




