from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Task, Project, Decision, Activity, Email, ChatMessage
from llm.ollama_client import OllamaClient
import random

def generate_thread_id(employee_id1: int, employee_id2: int) -> str:
    """Generate a consistent thread ID for a pair of employees.
    The thread ID is the same regardless of who sends the first message."""
    # Sort IDs to ensure consistency
    ids = sorted([employee_id1, employee_id2])
    return f"thread_{ids[0]}_{ids[1]}"

class EmployeeAgent:
    def __init__(self, employee: Employee, db: AsyncSession, llm_client: OllamaClient):
        self.employee = employee
        self.db = db
        self.llm_client = llm_client
    
    async def evaluate_situation(self, business_context: Dict) -> Dict:
        """Evaluate current situation and decide what to do."""
        available_options = await self._get_available_options(business_context)
        
        decision = await self.llm_client.generate_decision(
            employee_name=self.employee.name,
            employee_title=self.employee.title,
            employee_backstory=self.employee.backstory or "",
            employee_role=self.employee.role,
            personality_traits=self.employee.personality_traits or [],
            business_context=business_context,
            available_options=available_options
        )
        
        return decision
    
    async def _get_available_options(self, business_context: Dict) -> List[str]:
        """Get available actions based on role and current state."""
        options = []
        
        if self.employee.role == "CEO":
            options = [
                "Focus on increasing profitability and revenue",
                "Review financial performance and make strategic decisions",
                "Analyze business metrics and optimize operations",
                "Make decisions to improve business success",
                "Prioritize profitable projects and initiatives",
                "Review company performance and profitability",
                "Make strategic decisions for business growth",
                "Focus on making the business successful",
                "Develop strategic initiatives to improve company performance",
                "Identify opportunities for cost optimization and efficiency",
                "Plan market expansion and growth strategies",
                "Make strategic investments in technology and innovation",
                "Optimize resource allocation for maximum impact",
                "Drive operational excellence across the organization",
                "Evaluate competitive position and market opportunities",
                "Make data-driven strategic decisions for long-term success"
            ]
        elif self.employee.role in ["Manager", "CTO", "COO", "CFO"]:
            options = [
                "Focus on business operations and profitability",
                "Review team performance and optimize workflow",
                "Make decisions to improve business success",
                "Coordinate operations to maximize efficiency",
                "Prioritize profitable work and business outcomes",
                "Ensure everything is working smoothly",
                "Focus on what's best for the business",
                "Review and improve operational effectiveness",
                "Implement process improvements to increase efficiency",
                "Optimize resource allocation and workload distribution",
                "Make strategic decisions to improve team productivity",
                "Identify and eliminate operational bottlenecks",
                "Drive quality improvements and reduce waste",
                "Enhance team collaboration and communication",
                "Make data-driven decisions to improve outcomes",
                "Focus on continuous improvement and innovation"
            ]
        else:  # Employee
            options = [
                "Work on assigned task",
                "Complete current task",
                "Request new task",
                "Collaborate with team",
                "Learn new skills"
            ]
        
        # Add role-agnostic options
        if self.employee.current_task_id is None:
            options.append("Request a new task")
        else:
            options.append("Continue working on current task")
        
        return options
    
    async def execute_decision(self, decision: Dict, business_context: Dict) -> Activity:
        """Execute a decision and create activity log."""
        from sqlalchemy import select
        
        # Note: Message checking is now handled by a background task that runs every 2 minutes
        # This check during evaluation is kept as a fallback but at reduced frequency
        # to avoid duplicate processing (background task is primary mechanism)
        if random.random() < 0.3:  # 30% chance as fallback (increased for better responsiveness)
            await self._check_and_respond_to_messages(business_context)
        
        # Create decision record
        decision_record = Decision(
            employee_id=self.employee.id,
            decision_type=decision.get("action_type", "operational"),
            description=decision.get("decision", ""),
            reasoning=decision.get("reasoning", "")
        )
        self.db.add(decision_record)
        await self.db.flush()
        
        # Execute based on decision type
        activity_description = f"{self.employee.name} decided: {decision.get('decision', '')}"
        
        # Create activity
        activity = Activity(
            employee_id=self.employee.id,
            activity_type="decision",
            description=activity_description,
            activity_metadata={
                "decision_id": decision_record.id,
                "reasoning": decision.get("reasoning", ""),
                "confidence": decision.get("confidence", 0.5)
            }
        )
        self.db.add(activity)
        await self.db.flush()
        
        # Generate communications more frequently (85% chance)
        # Teams should always be communicating
        if random.random() < 0.85:
            await self._generate_communication(decision, business_context)
        
        return activity
    
    async def _generate_communication(self, decision: Dict, business_context: Dict):
        """Generate email or chat message based on employee activity."""
        from sqlalchemy import select
        
        # Priority 1: Find employees working on the same project
        project_teammates = []
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task and current_task.project_id:
                # Find other employees working on tasks in the same project
                result = await self.db.execute(
                    select(Task).where(
                        Task.project_id == current_task.project_id,
                        Task.employee_id.isnot(None),
                        Task.employee_id != self.employee.id,
                        Task.status.in_(["pending", "in_progress"])
                    )
                )
                project_tasks = result.scalars().all()
                project_employee_ids = {task.employee_id for task in project_tasks if task.employee_id}
                
                if project_employee_ids:
                    result = await self.db.execute(
                        select(Employee).where(
                            Employee.id.in_(project_employee_ids),
                            Employee.status == "active"
                        )
                    )
                    project_teammates = result.scalars().all()
        
        # Priority 2: Find employees in the same department
        department_teammates = []
        if self.employee.department:
            result = await self.db.execute(
                select(Employee).where(
                    Employee.department == self.employee.department,
                    Employee.id != self.employee.id,
                    Employee.status == "active"
                )
            )
            department_teammates = result.scalars().all()
        
        # Priority 3: Get all other employees as fallback
        result = await self.db.execute(
            select(Employee).where(
                Employee.id != self.employee.id,
                Employee.status == "active"
            )
        )
        all_employees = result.scalars().all()
        
        # Choose recipient with priority: project teammates > department teammates > others
        recipient = None
        if project_teammates:
            # 95% chance to communicate with project teammate (increased for better team collaboration)
            if random.random() < 0.95:
                recipient = random.choice(project_teammates)
        
        if not recipient and department_teammates:
            # 80% chance to communicate with department teammate (increased for better team collaboration)
            if random.random() < 0.8:
                recipient = random.choice(department_teammates)
        
        if not recipient and all_employees:
            recipient = random.choice(all_employees)
        
        if not recipient:
            return
        
        # Get project context if available
        project_context = None
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task and current_task.project_id:
                result = await self.db.execute(
                    select(Project).where(Project.id == current_task.project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    project_context = project
        
        # 60% email, 40% chat (emails for formal, chats for quick)
        if random.random() < 0.6:
            await self._send_email(recipient, decision, business_context, project_context)
        else:
            await self._send_chat(recipient, decision, business_context, project_context)
    
    async def _send_email(self, recipient: Employee, decision: Dict, business_context: Dict, project_context: Optional[Project] = None):
        """Send an email to another employee using Ollama to generate the content."""
        # Get project name if available
        project_name = project_context.name if project_context else None
        
        # Generate email using Ollama
        email_data = await self.llm_client.generate_email(
            sender_name=self.employee.name,
            sender_title=self.employee.title,
            sender_role=self.employee.role,
            sender_personality=self.employee.personality_traits or [],
            recipient_name=recipient.name,
            recipient_title=recipient.title,
            recipient_role=recipient.role,
            decision=decision.get('decision', 'I wanted to reach out'),
            reasoning=decision.get('reasoning', 'I think this would be helpful'),
            project_context=project_name,
            business_context=business_context
        )
        
        # Generate or find existing thread ID for this employee pair
        thread_id = generate_thread_id(self.employee.id, recipient.id)
        
        email = Email(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            subject=email_data.get('subject', 'Question'),
            body=email_data.get('body', 'Hi, I wanted to reach out.'),
            read=False,
            thread_id=thread_id
        )
        self.db.add(email)
        await self.db.flush()
    
    async def _send_chat(self, recipient: Employee, decision: Dict, business_context: Dict, project_context: Optional[Project] = None):
        """Send a chat message to another employee using Ollama to generate the content."""
        # Get project name if available
        project_name = project_context.name if project_context else None
        
        # Generate chat message using Ollama
        chat_message = await self.llm_client.generate_chat(
            sender_name=self.employee.name,
            sender_title=self.employee.title,
            sender_role=self.employee.role,
            sender_personality=self.employee.personality_traits or [],
            recipient_name=recipient.name,
            recipient_title=recipient.title,
            recipient_role=recipient.role,
            decision=decision.get('decision', 'I wanted to reach out'),
            reasoning=decision.get('reasoning', 'I think this would be helpful'),
            project_context=project_name,
            business_context=business_context
        )
        
        # Generate or find existing thread ID for this employee pair
        thread_id = generate_thread_id(self.employee.id, recipient.id)
        
        chat = ChatMessage(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            message=chat_message,
            thread_id=thread_id
        )
        self.db.add(chat)
        await self.db.flush()
        # Note: Response will be handled by the background task (runs every 2 minutes) 
        # or during the recipient's next decision cycle (30% chance fallback check)
    
    async def _check_and_respond_to_messages(self, business_context: Dict):
        """Check for unread messages and respond to all messages."""
        from sqlalchemy import select, desc
        from datetime import datetime, timedelta
        
        # Check for unread emails from the last 48 hours (extended to catch all emails)
        cutoff_time = datetime.utcnow() - timedelta(hours=48)
        result = await self.db.execute(
            select(Email)
            .where(
                Email.recipient_id == self.employee.id,
                Email.read == False,
                Email.timestamp >= cutoff_time
            )
            .order_by(desc(Email.timestamp))
            .limit(100)  # Check up to 100 most recent unread emails to ensure all emails get responses
        )
        unread_emails = result.scalars().all()
        
        # Check for recent chat messages (chats don't have read status, so check last 48 hours)
        # Extended time window to catch all messages and increased limit to ensure all messages get responses
        chat_cutoff = datetime.utcnow() - timedelta(hours=48)
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.recipient_id == self.employee.id,
                ChatMessage.sender_id.isnot(None),  # Only respond to messages from other employees, not from manager/user
                ChatMessage.timestamp >= chat_cutoff
            )
            .order_by(desc(ChatMessage.timestamp))
            .limit(100)  # Check up to 100 most recent chats to ensure all messages get responses
        )
        recent_chats = result.scalars().all()
        
        if unread_emails or recent_chats:
            print(f"📬 {self.employee.name} checking messages: {len(unread_emails)} unread emails, {len(recent_chats)} recent chats")
        
        emails_responded = 0
        chats_responded = 0
        
        # Respond to ALL unread emails (not just those that need response)
        # Process in reverse order (oldest first) to maintain conversation flow
        for email in reversed(unread_emails):
            # Get the thread_id for this conversation
            thread_id = email.thread_id or generate_thread_id(self.employee.id, email.sender_id)

            # IMPROVED: Check if we've already responded to this specific email
            # Look for a response we sent in a time window after receiving this email
            # This prevents false positives where a response to a LATER message is counted as a response to THIS message
            # Time window: 2 seconds to 10 minutes after receiving the email
            time_buffer_start = email.timestamp + timedelta(seconds=2)
            time_buffer_end = email.timestamp + timedelta(minutes=10)

            result = await self.db.execute(
                select(Email)
                .where(
                    Email.sender_id == self.employee.id,
                    Email.recipient_id == email.sender_id,
                    Email.thread_id == thread_id,
                    Email.timestamp >= time_buffer_start,
                    Email.timestamp <= time_buffer_end
                )
                .limit(1)
            )
            already_responded = result.scalar_one_or_none() is not None
            
            # Respond to ALL emails that we haven't responded to yet
            if not already_responded:
                try:
                    # Get sender name for logging
                    sender_result = await self.db.execute(
                        select(Employee).where(Employee.id == email.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    sender_name = sender.name if sender else f"Employee {email.sender_id}"
                    
                    print(f"📧 {self.employee.name} responding to email from {sender_name} (ID: {email.sender_id}, subject: {email.subject[:50]}...)")
                    await self._respond_to_email(email, business_context)
                    await self.db.flush()  # Ensure response is saved immediately
                    email.read = True
                    emails_responded += 1
                    print(f"✅ {self.employee.name} successfully responded to email from {sender_name}")
                except Exception as e:
                    print(f"❌ Error responding to email from {email.sender_id} to {self.employee.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            else:
                # Mark as read even if we already responded
                email.read = True
                print(f"ℹ️  {self.employee.name} already responded to email from {email.sender_id}")
        
        # Respond to ALL chat messages (not just those that need response)
        # Process in reverse order (oldest first) to maintain conversation flow
        for chat in reversed(recent_chats):
            # Skip if sender is None (messages from manager/user are handled separately)
            if chat.sender_id is None:
                continue
            
            # CRITICAL: Skip if sender is the same as recipient (employee replying to themselves)
            # This should never happen, but prevent it just in case
            if chat.sender_id == self.employee.id:
                print(f"⚠️  Skipping chat where {self.employee.name} would reply to themselves (chat ID: {chat.id})")
                continue

            # Get the thread_id for this conversation
            thread_id = chat.thread_id or generate_thread_id(self.employee.id, chat.sender_id)

            # IMPROVED: Check if we've already responded to this specific message
            # Look for a response we sent in a time window after receiving this message
            # This prevents false positives where a response to a LATER message is counted as a response to THIS message
            # Time window: 2 seconds to 10 minutes after receiving the message
            time_buffer_start = chat.timestamp + timedelta(seconds=2)
            time_buffer_end = chat.timestamp + timedelta(minutes=10)

            result = await self.db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.sender_id == self.employee.id,
                    ChatMessage.recipient_id == chat.sender_id,
                    ChatMessage.thread_id == thread_id,
                    ChatMessage.timestamp >= time_buffer_start,
                    ChatMessage.timestamp <= time_buffer_end
                )
                .limit(1)
            )
            already_responded = result.scalar_one_or_none() is not None
            
            # Respond to ALL messages that we haven't responded to yet
            if not already_responded:
                try:
                    # Get sender name for logging
                    sender_result = await self.db.execute(
                        select(Employee).where(Employee.id == chat.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    sender_name = sender.name if sender else f"Employee {chat.sender_id}"
                    
                    print(f"💬 {self.employee.name} responding to chat from {sender_name} (ID: {chat.sender_id}, message: {chat.message[:50]}...)")
                    await self._respond_to_chat(chat, business_context)
                    await self.db.flush()  # Ensure response is saved immediately
                    chats_responded += 1
                    print(f"✅ {self.employee.name} successfully responded to chat from {sender_name}")
                except Exception as e:
                    print(f"❌ Error responding to chat from {chat.sender_id} to {self.employee.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            else:
                print(f"ℹ️  {self.employee.name} already responded to chat from {chat.sender_id}")
        
        # Summary
        if emails_responded > 0 or chats_responded > 0:
            print(f"📊 {self.employee.name} responded to {emails_responded} email(s) and {chats_responded} chat(s)")
    
    async def _message_needs_response(self, message_text: str) -> bool:
        """Check if a message contains a question or request that needs a response."""
        # Simple heuristics to detect questions and requests
        question_indicators = [
            "?", "can you", "could you", "would you", "help", "assist", "need",
            "question", "wondering", "think", "thoughts", "opinion", "advice",
            "when", "how", "what", "why", "where", "who", "please", "request"
        ]
        
        message_lower = message_text.lower()
        
        # Check for question marks
        if "?" in message_text:
            return True
        
        # Check for question/request keywords
        for indicator in question_indicators:
            if indicator in message_lower:
                return True
        
        return False
    
    async def _respond_to_email(self, email: Email, business_context: Dict):
        """Generate and send a response to an email."""
        from sqlalchemy import select
        
        # Get sender information
        result = await self.db.execute(
            select(Employee).where(Employee.id == email.sender_id)
        )
        sender = result.scalar_one_or_none()
        if not sender:
            return
        
        # Get project context if available
        project_context = None
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task and current_task.project_id:
                result = await self.db.execute(
                    select(Project).where(Project.id == current_task.project_id)
                )
                project_context = result.scalar_one_or_none()
        
        # ALWAYS generate a response - with multiple fallback levels
        response = None
        try:
            # Try to generate LLM response
            response = await self.llm_client.generate_email_response(
                recipient_name=self.employee.name,
                recipient_title=self.employee.title,
                recipient_role=self.employee.role,
                recipient_personality=self.employee.personality_traits or [],
                sender_name=sender.name,
                sender_title=sender.title,
                original_subject=email.subject,
                original_body=email.body,
                project_context=project_context.name if project_context else None,
                business_context=business_context
            )
        except Exception as llm_error:
            print(f"[WARNING] LLM error for {self.employee.name}, using fallback: {llm_error}")

        # Ensure we always have a response - use fallback if LLM fails or returns empty
        if not response or len(response.strip()) == 0:
            response = f"Hi {sender.name},\n\nThanks for reaching out. I'll review this and get back to you if needed.\n\nBest regards,\n{self.employee.name}"
        
        # Use the same thread_id as the original email
        thread_id = email.thread_id or generate_thread_id(self.employee.id, email.sender_id)

        # Create reply email - ALWAYS create a response (guaranteed)
        reply_subject = f"Re: {email.subject}" if not email.subject.startswith("Re:") else email.subject

        try:
            reply_email = Email(
                sender_id=self.employee.id,
                recipient_id=email.sender_id,
                subject=reply_subject,
                body=response,
                read=False,
                thread_id=thread_id
            )
            self.db.add(reply_email)
            await self.db.flush()
            print(f"[OK] {self.employee.name} responded to {sender.name}'s email")
        except Exception as db_error:
            print(f"[ERROR] Database error saving email response from {self.employee.name}: {db_error}")
            raise  # Re-raise to ensure we know about DB errors
    
    async def _respond_to_chat(self, chat: ChatMessage, business_context: Dict):
        """Generate and send a response to a chat message."""
        from sqlalchemy import select
        
        # CRITICAL: Prevent employees from replying to themselves
        if chat.sender_id == self.employee.id:
            print(f"⚠️  BLOCKED: {self.employee.name} attempted to reply to their own message (chat ID: {chat.id})")
            return
        
        # Get sender information
        result = await self.db.execute(
            select(Employee).where(Employee.id == chat.sender_id)
        )
        sender = result.scalar_one_or_none()
        if not sender:
            print(f"⚠️  Cannot respond: sender with ID {chat.sender_id} not found")
            return
        
        # Get project context if available
        project_context = None
        if self.employee.current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == self.employee.current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task and current_task.project_id:
                result = await self.db.execute(
                    select(Project).where(Project.id == current_task.project_id)
                )
                project_context = result.scalar_one_or_none()
        
        # ALWAYS generate a response - with multiple fallback levels
        response = None
        try:
            # Try to generate LLM response
            response = await self.llm_client.generate_chat_response(
                recipient_name=self.employee.name,
                recipient_title=self.employee.title,
                recipient_role=self.employee.role,
                recipient_personality=self.employee.personality_traits or [],
                sender_name=sender.name,
                sender_title=sender.title,
                original_message=chat.message,
                project_context=project_context.name if project_context else None,
                business_context=business_context
            )
        except Exception as llm_error:
            print(f"[WARNING] LLM error for {self.employee.name}, using fallback: {llm_error}")

        # Ensure we always have a response - use fallback if LLM fails or returns empty
        if not response or len(response.strip()) == 0:
            response = f"Thanks for reaching out, {sender.name}! I'll get back to you on that."

        # Use the same thread_id as the original chat
        thread_id = chat.thread_id or generate_thread_id(self.employee.id, chat.sender_id)

        # Create reply chat - ALWAYS create a response (guaranteed)
        try:
            reply_chat = ChatMessage(
                sender_id=self.employee.id,
                recipient_id=chat.sender_id,
                message=response,
                thread_id=thread_id
            )
            self.db.add(reply_chat)
            await self.db.flush()
            print(f"[OK] {self.employee.name} responded to {sender.name}'s chat message")
        except Exception as db_error:
            print(f"[ERROR] Database error saving chat response from {self.employee.name}: {db_error}")
            raise  # Re-raise to ensure we know about DB errors

