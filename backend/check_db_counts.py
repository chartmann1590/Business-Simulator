import asyncio
from sqlalchemy import select, func
from database.database import async_session_maker
from database.models import Email, ChatMessage

async def check_counts():
    async with async_session_maker() as db:
        email_count = await db.scalar(select(func.count(Email.id)))
        chat_count = await db.scalar(select(func.count(ChatMessage.id)))
        print(f"Emails: {email_count}")
        print(f"Chats: {chat_count}")

if __name__ == "__main__":
    asyncio.run(check_counts())
