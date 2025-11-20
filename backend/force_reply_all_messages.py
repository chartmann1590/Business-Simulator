"""
EMERGENCY SCRIPT: Force reply to ALL unreplied messages IMMEDIATELY
This bypasses the background task and processes everything NOW.
"""
import asyncio
from sqlalchemy import select, and_, desc
from database.database import async_session_maker
from database.models import Email, ChatMessage, Employee
from employees.base import generate_thread_id
from employees.roles import create_employee_agent
from datetime import datetime, timedelta, timezone


async def force_reply_all_emails():
    """Force reply to ALL unreplied emails RIGHT NOW."""
    print("=" * 80)
    print("FORCING EMAIL REPLIES - PROCESSING ALL UNREPLIED EMAILS")
    print("=" * 80)

    async with async_session_maker() as db:
        # Get business context
        from engine.office_simulator import OfficeSimulator
        simulator = OfficeSimulator()
        business_context = await simulator.get_business_context(db)

        # Get all emails from last 7 days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(Email)
            .where(Email.timestamp >= cutoff_time)
            .order_by(Email.timestamp.asc())
        )
        all_emails = result.scalars().all()

        print(f"\n[INFO] Found {len(all_emails)} total emails in last 7 days")

        # Group by recipient
        emails_by_recipient = {}
        for email in all_emails:
            if email.recipient_id not in emails_by_recipient:
                emails_by_recipient[email.recipient_id] = []
            emails_by_recipient[email.recipient_id].append(email)

        total_replied = 0

        # Process each recipient's emails
        for recipient_id, emails in emails_by_recipient.items():
            # Get recipient employee
            result = await db.execute(
                select(Employee).where(
                    Employee.id == recipient_id,
                    Employee.status == "active"
                )
            )
            recipient = result.scalar_one_or_none()

            if not recipient:
                continue

            print(f"\n[PROCESSING] {recipient.name} - {len(emails)} emails to check")

            # Create agent for this employee
            from llm.ollama_client import OllamaClient
            llm_client = OllamaClient()
            agent = create_employee_agent(recipient, db, llm_client)

            # Sort emails by timestamp
            emails_sorted = sorted(emails, key=lambda e: e.timestamp)

            # Check each email for a response
            for email in emails_sorted:
                thread_id = email.thread_id or generate_thread_id(recipient_id, email.sender_id)

                # Check if already responded (10-minute window)
                time_buffer_start = email.timestamp + timedelta(seconds=2)
                time_buffer_end = email.timestamp + timedelta(minutes=10)

                result = await db.execute(
                    select(Email)
                    .where(
                        Email.sender_id == recipient_id,
                        Email.recipient_id == email.sender_id,
                        Email.thread_id == thread_id,
                        Email.timestamp >= time_buffer_start,
                        Email.timestamp <= time_buffer_end
                    )
                    .limit(1)
                )
                already_responded = result.scalar_one_or_none() is not None

                if not already_responded:
                    # Get sender name
                    sender_result = await db.execute(
                        select(Employee).where(Employee.id == email.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    sender_name = sender.name if sender else f"Employee {email.sender_id}"

                    print(f"  [REPLYING] To {sender_name}: {email.subject[:50]}...")

                    try:
                        await agent._respond_to_email(email, business_context)
                        email.read = True
                        total_replied += 1
                        print(f"  [SUCCESS] Sent reply to {sender_name}")
                    except Exception as e:
                        print(f"  [ERROR] Failed to reply: {e}")
                        continue

            # Commit after each employee
            await db.commit()
            print(f"[DONE] {recipient.name} - Committed replies to database")

        print("\n" + "=" * 80)
        print(f"EMAIL PROCESSING COMPLETE - Replied to {total_replied} emails")
        print("=" * 80)
        return total_replied


async def force_reply_all_chats():
    """Force reply to ALL unreplied chat messages RIGHT NOW."""
    print("\n" + "=" * 80)
    print("FORCING CHAT REPLIES - PROCESSING ALL UNREPLIED MESSAGES")
    print("=" * 80)

    async with async_session_maker() as db:
        # Get business context
        from engine.office_simulator import OfficeSimulator
        simulator = OfficeSimulator()
        business_context = await simulator.get_business_context(db)

        # Get all chats from last 7 days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.timestamp >= cutoff_time,
                    ChatMessage.sender_id.isnot(None)
                )
            )
            .order_by(ChatMessage.timestamp.asc())
        )
        all_chats = result.scalars().all()

        print(f"\n[INFO] Found {len(all_chats)} total chat messages in last 7 days")

        # Group by recipient
        chats_by_recipient = {}
        for chat in all_chats:
            if chat.recipient_id is None:
                continue
            if chat.recipient_id not in chats_by_recipient:
                chats_by_recipient[chat.recipient_id] = []
            chats_by_recipient[chat.recipient_id].append(chat)

        total_replied = 0

        # Process each recipient's chats
        for recipient_id, chats in chats_by_recipient.items():
            # Get recipient employee
            result = await db.execute(
                select(Employee).where(
                    Employee.id == recipient_id,
                    Employee.status == "active"
                )
            )
            recipient = result.scalar_one_or_none()

            if not recipient:
                continue

            print(f"\n[PROCESSING] {recipient.name} - {len(chats)} chat messages to check")

            # Create agent for this employee
            from llm.ollama_client import OllamaClient
            llm_client = OllamaClient()
            agent = create_employee_agent(recipient, db, llm_client)

            # Sort chats by timestamp
            chats_sorted = sorted(chats, key=lambda c: c.timestamp)

            # Check each chat for a response
            for chat in chats_sorted:
                if chat.sender_id is None:
                    continue

                thread_id = chat.thread_id or generate_thread_id(recipient_id, chat.sender_id)

                # Check if already responded (10-minute window)
                time_buffer_start = chat.timestamp + timedelta(seconds=2)
                time_buffer_end = chat.timestamp + timedelta(minutes=10)

                result = await db.execute(
                    select(ChatMessage)
                    .where(
                        ChatMessage.sender_id == recipient_id,
                        ChatMessage.recipient_id == chat.sender_id,
                        ChatMessage.thread_id == thread_id,
                        ChatMessage.timestamp >= time_buffer_start,
                        ChatMessage.timestamp <= time_buffer_end
                    )
                    .limit(1)
                )
                already_responded = result.scalar_one_or_none() is not None

                if not already_responded:
                    # Get sender name
                    sender_result = await db.execute(
                        select(Employee).where(Employee.id == chat.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    sender_name = sender.name if sender else f"Employee {chat.sender_id}"

                    print(f"  [REPLYING] To {sender_name}: {chat.message[:50]}...")

                    try:
                        await agent._respond_to_chat(chat, business_context)
                        total_replied += 1
                        print(f"  [SUCCESS] Sent reply to {sender_name}")
                    except Exception as e:
                        print(f"  [ERROR] Failed to reply: {e}")
                        continue

            # Commit after each employee
            await db.commit()
            print(f"[DONE] {recipient.name} - Committed replies to database")

        print("\n" + "=" * 80)
        print(f"CHAT PROCESSING COMPLETE - Replied to {total_replied} chats")
        print("=" * 80)
        return total_replied


async def main():
    """Main function - process ALL unreplied messages."""
    print("\n" + "=" * 80)
    print("EMERGENCY MESSAGE REPLY PROCESSOR")
    print("This will reply to ALL unreplied messages from the last 7 days")
    print("=" * 80)

    start_time = datetime.now()

    # Process emails
    email_replies = await force_reply_all_emails()

    # Process chats
    chat_replies = await force_reply_all_chats()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Email replies sent: {email_replies}")
    print(f"Chat replies sent: {chat_replies}")
    print(f"Total replies: {email_replies + chat_replies}")
    print(f"Processing time: {duration:.1f} seconds")
    print("=" * 80)
    print("\n[SUCCESS] All unreplied messages have been processed!")
    print("Check Teams and Outlook - you should see replies now!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
