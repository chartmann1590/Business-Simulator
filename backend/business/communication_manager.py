import asyncio
import random
from datetime import datetime, time
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Email, ChatMessage
from database.database import async_session_maker
from llm.ollama_client import OllamaClient
from config import now as local_now
import logging

logger = logging.getLogger(__name__)

class CommunicationManager:
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.llm_client = OllamaClient()
        self.last_check_time = None
        self.check_interval = 60  # Check every 60 seconds (simulation time)

    def check_schedule(self) -> bool:
        """
        Check if current time is within working hours (7am-7pm NY time, Mon-Fri).
        """
        current_time = local_now()
        
        # Check day of week (0=Monday, 6=Sunday)
        if current_time.weekday() >= 5:  # Saturday or Sunday
            return False
            
        # Check time of day (7am - 7pm)
        current_hour = current_time.hour
        if 7 <= current_hour < 19:
            return True
            
        return False

    async def get_random_employees(self, db: AsyncSession, count: int = 2):
        """Get random active employees for conversation."""
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        if len(employees) < count:
            return None
        return random.sample(employees, count)

    async def generate_new_conversation(self, db: AsyncSession, business_context: dict):
        """Start a new conversation (Email or Chat) between two employees."""
        employees = await self.get_random_employees(db)
        if not employees:
            return

        sender, recipient = employees
        
        # 50/50 chance of Email vs Chat
        comm_type = "email" if random.random() < 0.5 else "chat"
        
        try:
            message_data = await self.llm_client.generate_initial_business_message(
                sender_name=sender.name,
                sender_title=sender.title,
                sender_role=sender.role,
                recipient_name=recipient.name,
                recipient_title=recipient.title,
                recipient_role=recipient.role,
                communication_type=comm_type,
                business_context=business_context
            )
            
            if comm_type == "email":
                new_email = Email(
                    sender_id=sender.id,
                    recipient_id=recipient.id,
                    subject=message_data.get("subject", "No Subject"),
                    body=message_data.get("body", ""),
                    read=False,
                    thread_id=f"email_{sender.id}_{recipient.id}_{int(datetime.now().timestamp())}"
                )
                db.add(new_email)
                logger.info(f"Generated new Email from {sender.name} to {recipient.name}")
                
            else:  # chat
                new_chat = ChatMessage(
                    sender_id=sender.id,
                    recipient_id=recipient.id,
                    message=message_data.get("body", ""),
                    thread_id=f"chat_{sender.id}_{recipient.id}_{int(datetime.now().timestamp())}"
                )
                db.add(new_chat)
                logger.info(f"Generated new Chat from {sender.name} to {recipient.name}")
                
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error generating new conversation: {e}")

    async def process_replies(self, db: AsyncSession, business_context: dict):
        """Check for unreplied messages and generate replies."""
        
        # Process Emails
        # Find emails sent to active employees that are unread or recent and have no reply
        # For simplicity, we'll just pick a few recent unreplied emails to reply to
        # In a real system, we'd need more complex tracking of "replied to" state
        
        # Get recent emails (last 24 hours)
        # This is a simplified logic: find the last email in a thread, if it's not from the current user, reply to it
        # To avoid infinite loops, we'll add a probability check or depth check in a real system
        # Here we'll just check if the last message in a thread needs a reply
        
        # Fetch recent emails
        # We will just reply to 1 random unreplied email per tick to avoid flooding
        pass # Logic to be implemented in next step for detailed query

    async def reply_to_email(self, db: AsyncSession, email: Email, business_context: dict):
        """Generate a reply to a specific email."""
        try:
            sender = await db.get(Employee, email.sender_id)
            recipient = await db.get(Employee, email.recipient_id)
            
            if not sender or not recipient:
                return

            reply_body = await self.llm_client.generate_business_reply(
                sender_name=recipient.name, # Recipient becomes sender of reply
                sender_title=recipient.title,
                sender_role=recipient.role,
                recipient_name=sender.name, # Original sender becomes recipient
                recipient_title=sender.title,
                recipient_role=sender.role,
                original_message=email.body,
                original_subject=email.subject,
                communication_type="email",
                business_context=business_context
            )
            
            reply_subject = f"Re: {email.subject}" if not email.subject.startswith("Re:") else email.subject
            
            new_email = Email(
                sender_id=recipient.id,
                recipient_id=sender.id,
                subject=reply_subject,
                body=reply_body,
                read=False,
                thread_id=email.thread_id
            )
            db.add(new_email)
            email.read = True # Mark original as read
            await db.commit()
            logger.info(f"Generated Email reply from {recipient.name} to {sender.name}")
            
        except Exception as e:
            logger.error(f"Error replying to email: {e}")

    async def reply_to_chat(self, db: AsyncSession, chat: ChatMessage, business_context: dict):
        """Generate a reply to a specific chat."""
        try:
            sender = await db.get(Employee, chat.sender_id)
            recipient = await db.get(Employee, chat.recipient_id)
            
            if not sender or not recipient:
                return

            reply_body = await self.llm_client.generate_business_reply(
                sender_name=recipient.name,
                sender_title=recipient.title,
                sender_role=recipient.role,
                recipient_name=sender.name,
                recipient_title=sender.title,
                recipient_role=sender.role,
                original_message=chat.message,
                original_subject="",
                communication_type="chat",
                business_context=business_context
            )
            
            new_chat = ChatMessage(
                sender_id=recipient.id,
                recipient_id=sender.id,
                message=reply_body,
                thread_id=chat.thread_id
            )
            db.add(new_chat)
            await db.commit()
            logger.info(f"Generated Chat reply from {recipient.name} to {sender.name}")
            
        except Exception as e:
            logger.error(f"Error replying to chat: {e}")

    async def run_cycle(self, db: AsyncSession, business_context: dict):
        """Main execution cycle called by simulator."""
        if not self.check_schedule():
            return

        # 1. Chance to start new conversation
        if random.random() < 0.1: # 10% chance per tick
            await self.generate_new_conversation(db, business_context)

        # 2. Check for replies needed
        # Simplified: Find one unreplied email and one unreplied chat to process
        
        # Find an unread email
        result = await db.execute(select(Email).where(Email.read == False).limit(1))
        unread_email = result.scalar_one_or_none()
        if unread_email:
            # 30% chance to reply immediately
            if random.random() < 0.3:
                await self.reply_to_email(db, unread_email, business_context)

        # Find a recent chat (last 5 mins) that is the last in its thread and not from same person
        # This is complex to query efficiently in one go, so we'll simplify:
        # Get a random recent chat, check if it needs a reply
        # For now, let's just pick a random chat from last minute
        # In a real robust system we'd track "needs_reply" state
        
        # Placeholder for chat reply logic - will implement simple version:
        # If we just generated a chat, we might want to queue a reply?
        # Or just pick a random recent chat and if it's not replied to, reply.
        
        # Let's try to find a chat that doesn't have a reply in the thread yet (simplified)
        # Actually, let's just rely on the "unread" status if we had one, but ChatMessage doesn't have "read".
        # We will implement a "reply probability" for recent chats.
        
        pass
