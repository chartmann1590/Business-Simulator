"""
INSTANT REPLY SCRIPT - Bypasses LLM, uses fallback responses for SPEED
Replies to ALL unreplied messages IMMEDIATELY with simple responses
"""
import asyncio
from sqlalchemy import select
from database.database import async_session_maker
from database.models import Email, ChatMessage, Employee
from employees.base import generate_thread_id
from datetime import datetime, timedelta, timezone


async def instant_reply_emails():
    """Reply to ALL unreplied emails with instant fallback responses."""
    print("=" * 80)
    print("INSTANT EMAIL REPLIES - NO LLM, PURE SPEED")
    print("=" * 80)

    async with async_session_maker() as db:
        # Get all emails from last 7 days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(Email)
            .where(Email.timestamp >= cutoff_time)
            .order_by(Email.timestamp.asc())
        )
        all_emails = result.scalars().all()

        print(f"[INFO] Found {len(all_emails)} emails to process")

        # Group by thread to find unreplied emails
        total_replied = 0

        for email in all_emails:
            # Get recipient
            result = await db.execute(
                select(Employee).where(
                    Employee.id == email.recipient_id,
                    Employee.status == "active"
                )
            )
            recipient = result.scalar_one_or_none()

            if not recipient:
                continue

            thread_id = email.thread_id or generate_thread_id(recipient.id, email.sender_id)

            # Check if already responded (10-minute window)
            time_buffer_start = email.timestamp + timedelta(seconds=2)
            time_buffer_end = email.timestamp + timedelta(minutes=10)

            result = await db.execute(
                select(Email)
                .where(
                    Email.sender_id == recipient.id,
                    Email.recipient_id == email.sender_id,
                    Email.thread_id == thread_id,
                    Email.timestamp >= time_buffer_start,
                    Email.timestamp <= time_buffer_end
                )
                .limit(1)
            )
            already_responded = result.scalar_one_or_none() is not None

            if not already_responded:
                # Get sender
                sender_result = await db.execute(
                    select(Employee).where(Employee.id == email.sender_id)
                )
                sender = sender_result.scalar_one_or_none()

                if not sender:
                    continue

                sender_name = sender.name

                # INSTANT FALLBACK RESPONSE - NO LLM
                response = f"Hi {sender_name},\n\nThanks for your email. I've reviewed it and will follow up as needed.\n\nBest regards,\n{recipient.name}"

                # Create reply
                reply_subject = f"Re: {email.subject}" if not email.subject.startswith("Re:") else email.subject

                reply_email = Email(
                    sender_id=recipient.id,
                    recipient_id=email.sender_id,
                    subject=reply_subject,
                    body=response,
                    read=False,
                    thread_id=thread_id
                )
                db.add(reply_email)

                # Mark original as read
                email.read = True

                total_replied += 1

                if total_replied % 10 == 0:
                    print(f"  Progress: {total_replied} emails replied...")

        # Commit all replies
        await db.commit()

        print("=" * 80)
        print(f"EMAIL COMPLETE - Replied to {total_replied} emails INSTANTLY")
        print("=" * 80)
        return total_replied


async def instant_reply_chats():
    """Reply to ALL unreplied chats with instant fallback responses."""
    print("\n" + "=" * 80)
    print("INSTANT CHAT REPLIES - NO LLM, PURE SPEED")
    print("=" * 80)

    async with async_session_maker() as db:
        # Get all chats from last 7 days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.timestamp >= cutoff_time,
                ChatMessage.sender_id.isnot(None)
            )
            .order_by(ChatMessage.timestamp.asc())
        )
        all_chats = result.scalars().all()

        print(f"[INFO] Found {len(all_chats)} chat messages to process")

        total_replied = 0

        for chat in all_chats:
            if chat.sender_id is None or chat.recipient_id is None:
                continue

            # Get recipient
            result = await db.execute(
                select(Employee).where(
                    Employee.id == chat.recipient_id,
                    Employee.status == "active"
                )
            )
            recipient = result.scalar_one_or_none()

            if not recipient:
                continue

            thread_id = chat.thread_id or generate_thread_id(recipient.id, chat.sender_id)

            # Check if already responded (10-minute window)
            time_buffer_start = chat.timestamp + timedelta(seconds=2)
            time_buffer_end = chat.timestamp + timedelta(minutes=10)

            result = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.sender_id == recipient.id,
                    ChatMessage.recipient_id == chat.sender_id,
                    ChatMessage.thread_id == thread_id,
                    ChatMessage.timestamp >= time_buffer_start,
                    ChatMessage.timestamp <= time_buffer_end
                )
                .limit(1)
            )
            already_responded = result.scalar_one_or_none() is not None

            if not already_responded:
                # Get sender
                sender_result = await db.execute(
                    select(Employee).where(Employee.id == chat.sender_id)
                )
                sender = sender_result.scalar_one_or_none()

                if not sender:
                    continue

                sender_name = sender.name

                # INSTANT FALLBACK RESPONSE - NO LLM
                response = f"Thanks for reaching out, {sender_name}! Got your message and will follow up as needed."

                # Create reply
                reply_chat = ChatMessage(
                    sender_id=recipient.id,
                    recipient_id=chat.sender_id,
                    message=response,
                    thread_id=thread_id
                )
                db.add(reply_chat)

                total_replied += 1

                if total_replied % 10 == 0:
                    print(f"  Progress: {total_replied} chats replied...")

        # Commit all replies
        await db.commit()

        print("=" * 80)
        print(f"CHAT COMPLETE - Replied to {total_replied} chats INSTANTLY")
        print("=" * 80)
        return total_replied


async def main():
    """Main function - instant replies to everything."""
    print("\n" + "=" * 80)
    print("INSTANT MESSAGE REPLY PROCESSOR")
    print("Bypassing LLM for maximum speed - using fallback responses")
    print("=" * 80)

    start_time = datetime.now()

    # Process emails
    email_replies = await instant_reply_emails()

    # Process chats
    chat_replies = await instant_reply_chats()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("INSTANT REPLY COMPLETE")
    print("=" * 80)
    print(f"Email replies sent: {email_replies}")
    print(f"Chat replies sent: {chat_replies}")
    print(f"Total replies: {email_replies + chat_replies}")
    print(f"Processing time: {duration:.1f} seconds")
    print("=" * 80)
    print("\nSUCCESS! All messages replied to!")
    print("Check Teams and Outlook NOW - you should see replies!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
