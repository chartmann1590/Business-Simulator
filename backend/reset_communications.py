import asyncio
from sqlalchemy import delete
from database.database import async_session_maker
from database.models import Email, ChatMessage

async def reset_communications():
    """
    Deletes all existing emails and chat messages from the database.
    """
    print("WARNING: This will delete ALL emails and chat messages.")
    print("Starting cleanup...")
    
    async with async_session_maker() as db:
        try:
            # Delete all emails
            print("Deleting emails...")
            await db.execute(delete(Email))
            
            # Delete all chat messages
            print("Deleting chat messages...")
            await db.execute(delete(ChatMessage))
            
            await db.commit()
            print("SUCCESS: All communications have been deleted.")
            
        except Exception as e:
            print(f"ERROR: An error occurred during cleanup: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(reset_communications())
