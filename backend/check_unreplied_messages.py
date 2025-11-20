"""
Diagnostic script to check for unreplied emails and chat messages.
This helps identify communication issues where messages don't get responses.
"""
import asyncio
from sqlalchemy import select, and_, or_, func
from database.database import async_session_maker
from database.models import Email, ChatMessage, Employee
from employees.base import generate_thread_id
from datetime import datetime, timedelta, timezone


async def check_unreplied_emails():
    """Check for emails that haven't received replies."""
    async with async_session_maker() as db:
        # Get all emails from the last 7 days
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        result = await db.execute(
            select(Email)
            .where(Email.timestamp >= cutoff_time)
            .order_by(Email.timestamp.asc())
        )
        all_emails = result.scalars().all()

        if not all_emails:
            print("[INFO] No emails found in the last 7 days")
            return

        print(f"[INFO] Analyzing {len(all_emails)} emails from the last 7 days...")

        # Group emails by thread
        threads = {}
        for email in all_emails:
            thread_id = email.thread_id or generate_thread_id(email.sender_id, email.recipient_id)
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(email)

        print(f"[INFO] Found {len(threads)} email conversation threads")

        # Check each thread for unreplied messages
        unreplied_count = 0
        unreplied_details = []

        for thread_id, emails in threads.items():
            # Sort emails by timestamp
            emails = sorted(emails, key=lambda e: e.timestamp)

            # Check each email for a reply
            for i, email in enumerate(emails):
                # Look for a reply from the recipient within 10 minutes
                reply_window_start = email.timestamp + timedelta(seconds=2)
                reply_window_end = email.timestamp + timedelta(minutes=10)

                # Check if recipient responded
                has_reply = False
                for other_email in emails[i+1:]:
                    if (other_email.sender_id == email.recipient_id and
                        other_email.recipient_id == email.sender_id and
                        reply_window_start <= other_email.timestamp <= reply_window_end):
                        has_reply = True
                        break

                if not has_reply:
                    unreplied_count += 1
                    # Get sender and recipient names
                    sender_result = await db.execute(
                        select(Employee).where(Employee.id == email.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    recipient_result = await db.execute(
                        select(Employee).where(Employee.id == email.recipient_id)
                    )
                    recipient = recipient_result.scalar_one_or_none()

                    sender_name = sender.name if sender else f"Employee {email.sender_id}"
                    recipient_name = recipient.name if recipient else f"Employee {email.recipient_id}"

                    # Calculate age, handling timezone-aware timestamps
                    now = datetime.now(timezone.utc)
                    email_time = email.timestamp if email.timestamp.tzinfo else email.timestamp.replace(tzinfo=timezone.utc)
                    age_hours = (now - email_time).total_seconds() / 3600

                    unreplied_details.append({
                        'sender': sender_name,
                        'recipient': recipient_name,
                        'subject': email.subject,
                        'timestamp': email.timestamp,
                        'age_hours': age_hours
                    })

        print(f"\n[RESULT] Email Analysis:")
        print(f"  - Total emails: {len(all_emails)}")
        print(f"  - Unreplied emails: {unreplied_count}")
        print(f"  - Reply rate: {((len(all_emails) - unreplied_count) / len(all_emails) * 100):.1f}%")

        if unreplied_details:
            print(f"\n[WARNING] Recent unreplied emails (showing up to 10):")
            # Sort by age and show most recent
            unreplied_details.sort(key=lambda x: x['age_hours'])
            for detail in unreplied_details[:10]:
                print(f"  - From {detail['sender']} to {detail['recipient']}")
                print(f"    Subject: {detail['subject'][:60]}...")
                print(f"    Sent: {detail['timestamp']} ({detail['age_hours']:.1f}h ago)")


async def check_unreplied_chats():
    """Check for chat messages that haven't received replies."""
    async with async_session_maker() as db:
        # Get all chat messages from the last 7 days
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        result = await db.execute(
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.timestamp >= cutoff_time,
                    ChatMessage.sender_id.isnot(None)  # Exclude system messages
                )
            )
            .order_by(ChatMessage.timestamp.asc())
        )
        all_chats = result.scalars().all()

        if not all_chats:
            print("[INFO] No chat messages found in the last 7 days")
            return

        print(f"[INFO] Analyzing {len(all_chats)} chat messages from the last 7 days...")

        # Group chats by thread
        threads = {}
        for chat in all_chats:
            if chat.sender_id is None or chat.recipient_id is None:
                continue
            thread_id = chat.thread_id or generate_thread_id(chat.sender_id, chat.recipient_id)
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(chat)

        print(f"[INFO] Found {len(threads)} chat conversation threads")

        # Check each thread for unreplied messages
        unreplied_count = 0
        unreplied_details = []

        for thread_id, chats in threads.items():
            # Sort chats by timestamp
            chats = sorted(chats, key=lambda c: c.timestamp)

            # Check each chat for a reply
            for i, chat in enumerate(chats):
                # Look for a reply from the recipient within 10 minutes
                reply_window_start = chat.timestamp + timedelta(seconds=2)
                reply_window_end = chat.timestamp + timedelta(minutes=10)

                # Check if recipient responded
                has_reply = False
                for other_chat in chats[i+1:]:
                    if (other_chat.sender_id == chat.recipient_id and
                        other_chat.recipient_id == chat.sender_id and
                        reply_window_start <= other_chat.timestamp <= reply_window_end):
                        has_reply = True
                        break

                if not has_reply:
                    unreplied_count += 1
                    # Get sender and recipient names
                    sender_result = await db.execute(
                        select(Employee).where(Employee.id == chat.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    recipient_result = await db.execute(
                        select(Employee).where(Employee.id == chat.recipient_id)
                    )
                    recipient = recipient_result.scalar_one_or_none()

                    sender_name = sender.name if sender else f"Employee {chat.sender_id}"
                    recipient_name = recipient.name if recipient else f"Employee {chat.recipient_id}"

                    # Calculate age, handling timezone-aware timestamps
                    now = datetime.now(timezone.utc)
                    chat_time = chat.timestamp if chat.timestamp.tzinfo else chat.timestamp.replace(tzinfo=timezone.utc)
                    age_hours = (now - chat_time).total_seconds() / 3600

                    unreplied_details.append({
                        'sender': sender_name,
                        'recipient': recipient_name,
                        'message': chat.message,
                        'timestamp': chat.timestamp,
                        'age_hours': age_hours
                    })

        print(f"\n[RESULT] Chat Analysis:")
        print(f"  - Total chat messages: {len(all_chats)}")
        print(f"  - Unreplied messages: {unreplied_count}")
        print(f"  - Reply rate: {((len(all_chats) - unreplied_count) / len(all_chats) * 100):.1f}%")

        if unreplied_details:
            print(f"\n[WARNING] Recent unreplied chats (showing up to 10):")
            # Sort by age and show most recent
            unreplied_details.sort(key=lambda x: x['age_hours'])
            for detail in unreplied_details[:10]:
                print(f"  - From {detail['sender']} to {detail['recipient']}")
                print(f"    Message: {detail['message'][:60]}...")
                print(f"    Sent: {detail['timestamp']} ({detail['age_hours']:.1f}h ago)")


async def main():
    """Main function to check unreplied messages."""
    print("=" * 60)
    print("Communication Analysis - Checking for unreplied messages...")
    print("=" * 60)
    print()

    await check_unreplied_emails()
    print()
    print("-" * 60)
    print()
    await check_unreplied_chats()

    print()
    print("=" * 60)
    print("[INFO] Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
