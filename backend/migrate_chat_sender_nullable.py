"""Migration script to make sender_id nullable in chat_messages table to support user/system messages."""
import asyncio
import aiosqlite
import os


async def migrate_database():
    """Make sender_id nullable in chat_messages table."""
    db_path = os.path.join(os.path.dirname(__file__), "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        try:
            # SQLite doesn't support ALTER COLUMN directly, so we need to:
            # 1. Create a new table with nullable sender_id
            # 2. Copy data from old table
            # 3. Drop old table
            # 4. Rename new table
            
            print("Checking chat_messages table structure...")
            cursor = await db.execute("PRAGMA table_info(chat_messages)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Check if sender_id is already nullable
            sender_id_info = next((col for col in columns if col[1] == 'sender_id'), None)
            if sender_id_info and sender_id_info[3] == 0:  # 0 means nullable in SQLite
                print("[OK] sender_id is already nullable in chat_messages table")
                return
            
            print("Making sender_id nullable in chat_messages table...")
            
            # Create new table with nullable sender_id
            await db.execute("""
                CREATE TABLE chat_messages_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER REFERENCES employees(id),
                    recipient_id INTEGER NOT NULL REFERENCES employees(id),
                    message TEXT NOT NULL,
                    thread_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Copy data from old table
            await db.execute("""
                INSERT INTO chat_messages_new (id, sender_id, recipient_id, message, thread_id, timestamp)
                SELECT id, sender_id, recipient_id, message, thread_id, timestamp
                FROM chat_messages
            """)
            
            # Drop old table
            await db.execute("DROP TABLE chat_messages")
            
            # Rename new table
            await db.execute("ALTER TABLE chat_messages_new RENAME TO chat_messages")
            
            # Recreate indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_id ON chat_messages(sender_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_recipient_id ON chat_messages(recipient_id)")
            
            await db.commit()
            print("[OK] Made sender_id nullable in chat_messages table")
            
        except Exception as e:
            await db.rollback()
            print(f"Error migrating chat_messages table: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nMigration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_database())

