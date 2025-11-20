"""
Script to backfill thread_id for emails and chat messages that don't have it set.
This ensures all messages have proper thread tracking for conversation management.
"""
import asyncio
from sqlalchemy import select, update
from database.database import async_session_maker
from database.models import Email, ChatMessage
from employees.base import generate_thread_id


async def backfill_email_thread_ids():
    """Backfill thread_id for emails that don't have it."""
    async with async_session_maker() as db:
        # Get all emails without thread_id
        result = await db.execute(
            select(Email).where(
                (Email.thread_id.is_(None)) | (Email.thread_id == "")
            )
        )
        emails = result.scalars().all()

        if not emails:
            print("[OK] All emails already have thread_id set")
            return 0

        print(f"[INFO] Found {len(emails)} emails without thread_id. Backfilling...")

        updated = 0
        for email in emails:
            # Generate thread_id based on sender and recipient
            thread_id = generate_thread_id(email.sender_id, email.recipient_id)
            email.thread_id = thread_id
            updated += 1

            if updated % 100 == 0:
                print(f"  Processed {updated}/{len(emails)} emails...")

        await db.commit()
        print(f"[OK] Updated {updated} emails with thread_id")
        return updated


async def backfill_chat_thread_ids():
    """Backfill thread_id for chat messages that don't have it."""
    async with async_session_maker() as db:
        # Get all chat messages without thread_id
        result = await db.execute(
            select(ChatMessage).where(
                (ChatMessage.thread_id.is_(None)) | (ChatMessage.thread_id == "")
            )
        )
        chats = result.scalars().all()

        if not chats:
            print("[OK] All chat messages already have thread_id set")
            return 0

        print(f"[INFO] Found {len(chats)} chat messages without thread_id. Backfilling...")

        updated = 0
        for chat in chats:
            # Skip messages without sender_id (system messages)
            if chat.sender_id is None or chat.recipient_id is None:
                continue

            # Generate thread_id based on sender and recipient
            thread_id = generate_thread_id(chat.sender_id, chat.recipient_id)
            chat.thread_id = thread_id
            updated += 1

            if updated % 100 == 0:
                print(f"  Processed {updated}/{len(chats)} chat messages...")

        await db.commit()
        print(f"[OK] Updated {updated} chat messages with thread_id")
        return updated


async def main():
    """Main function to backfill thread_ids."""
    print("=" * 60)
    print("Starting thread_id backfill for emails and chat messages...")
    print("=" * 60)

    email_count = await backfill_email_thread_ids()
    chat_count = await backfill_chat_thread_ids()

    print("=" * 60)
    print(f"[SUCCESS] Backfill complete!")
    print(f"   - {email_count} emails updated")
    print(f"   - {chat_count} chat messages updated")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
