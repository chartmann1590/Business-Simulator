"""Migration script to add thread_id field to emails and chat_messages tables."""
import asyncio
import aiosqlite
import os

async def migrate_database():
    """Add thread_id field to emails and chat_messages tables if they don't exist."""
    # Database is in the backend directory
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        # Check if emails table exists and add thread_id column
        try:
            cursor = await db.execute("PRAGMA table_info(emails)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"Existing emails columns: {column_names}")
            
            # Add column if it doesn't exist
            if 'thread_id' not in column_names:
                print("Adding thread_id column to emails table...")
                await db.execute("ALTER TABLE emails ADD COLUMN thread_id TEXT")
                # Create index for better query performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id)")
                await db.commit()
                print("[OK] Added thread_id column to emails table")
            else:
                print("[OK] thread_id column already exists in emails table")
        except Exception as e:
            print(f"Error checking emails table: {e}")
        
        # Check if chat_messages table exists and add thread_id column
        try:
            cursor = await db.execute("PRAGMA table_info(chat_messages)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"Existing chat_messages columns: {column_names}")
            
            # Add column if it doesn't exist
            if 'thread_id' not in column_names:
                print("Adding thread_id column to chat_messages table...")
                await db.execute("ALTER TABLE chat_messages ADD COLUMN thread_id TEXT")
                # Create index for better query performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id)")
                await db.commit()
                print("[OK] Added thread_id column to chat_messages table")
            else:
                print("[OK] thread_id column already exists in chat_messages table")
        except Exception as e:
            print(f"Error checking chat_messages table: {e}")
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())




