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
                "Launch a new strategic project",
                "Analyze market opportunities",
                "Review company performance",
                "Make a major business decision",
                "Plan for growth"
            ]
        elif self.employee.role == "Manager":
            options = [
                "Assign tasks to team members",
                "Review project progress",
                "Plan project milestones",
                "Coordinate with other departments",
                "Optimize resource allocation"
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
        
        # First, check for unread messages and respond to questions/requests (high priority)
        # 70% chance to check messages - employees should be responsive
        if random.random() < 0.7:
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
        
        # Generate communications more frequently (60% chance)
        # Teams should always be communicating
        if random.random() < 0.6:
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
            # 80% chance to communicate with project teammate
            if random.random() < 0.8:
                recipient = random.choice(project_teammates)
        
        if not recipient and department_teammates:
            # 60% chance to communicate with department teammate
            if random.random() < 0.6:
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
        """Send an email to another employee."""
        # Generate email content based on decision and context
        project_name = project_context.name if project_context else None
        
        if project_name:
            subject_templates = [
                f"Question about {project_name}",
                f"Need help with {project_name}",
                f"Update on {project_name}",
                f"Progress update: {project_name}",
                f"Collaboration needed for {project_name}",
                f"Status update: {project_name}",
                f"Request regarding {project_name}"
            ]
            
            # Extract strings to avoid f-string syntax errors
            progress_msg = "We're making good progress"
            track_msg = "We're on track with the project goals"
            decision_text = decision.get('decision', 'Can you help me understand the requirements?')
            reasoning_text = decision.get('reasoning', "I want to make sure I'm on the right track.")
            decision_text2 = decision.get('decision', 'Could you assist with this?')
            reasoning_text2 = decision.get('reasoning', 'Your expertise would be valuable here.')
            decision_text3 = decision.get('decision', 'What should I do next?')
            reasoning_text3 = decision.get('reasoning', 'I want to make sure we coordinate properly.')
            decision_text4 = decision.get('decision', progress_msg)
            reasoning_text4 = decision.get('reasoning', 'This is important for the project timeline.')
            decision_text5 = decision.get('decision', 'We need to coordinate on this')
            reasoning_text5 = decision.get('reasoning', 'What do you think about this approach?')
            decision_text6 = decision.get('decision', 'We should sync on this')
            reasoning_text6 = decision.get('reasoning', 'When would be a good time to discuss?')
            decision_text7 = decision.get('decision', 'Things are progressing well')
            reasoning_text7 = decision.get('reasoning', track_msg)
            
            body_templates = [
                f"Hi {recipient.name},\n\nI have a question about {project_name}. {decision_text} {reasoning_text}\n\nThanks!\n\nBest regards,\n{self.employee.name}",
                f"Hello {recipient.name},\n\nI need your help with {project_name}. {decision_text2} {reasoning_text2}\n\nWhat do you think?\n\nThanks,\n{self.employee.name}",
                f"Hi {recipient.name},\n\nQuick question about {project_name}: {decision_text3} {reasoning_text3}\n\nLet me know your thoughts!\n\nBest,\n{self.employee.name}",
                f"Dear {recipient.name},\n\nI wanted to update you on {project_name}. {decision_text4}. {reasoning_text4}\n\nDo you have any feedback or suggestions?\n\nRegards,\n{self.employee.name}",
                f"Hi {recipient.name},\n\nI need your input on {project_name}. {decision_text5}. {reasoning_text5}\n\nThanks,\n{self.employee.name}",
                f"Hello {recipient.name},\n\nFollowing up on {project_name}. {decision_text6}. {reasoning_text6}\n\nBest regards,\n{self.employee.name}",
                f"Hi {recipient.name},\n\nQuick update on {project_name}: {decision_text7}. {reasoning_text7}\n\nDo you have any questions?\n\nBest,\n{self.employee.name}"
            ]
        else:
            # Extract decision values for subject templates
            decision_subj1 = decision.get('decision', 'current work')
            decision_subj2 = decision.get('decision', 'project')
            decision_subj3 = decision.get('decision', 'current work')
            
            subject_templates = [
                f"Question about {decision_subj1}",
                f"Need help with {decision_subj2}",
                f"Request regarding {decision_subj2}",
                f"Update on {decision_subj3}",
                f"Status update from {self.employee.name}",
                f"Collaboration needed for {decision_subj2}"
            ]
            
            # Extract decision values to avoid f-string syntax issues
            decision_val1 = decision.get('decision', 'my current work')
            reasoning_val1 = decision.get('reasoning', 'Can you help me understand this better?')
            decision_val2 = decision.get('decision', 'this matter')
            reasoning_val2 = decision.get('reasoning', 'Could you assist me?')
            decision_val3 = decision.get('decision', 'What should I do next?')
            reasoning_val3 = decision.get('reasoning', "I want to make sure I'm on the right track.")
            decision_val4 = decision.get('decision', 'my current work')
            reasoning_val4 = decision.get('reasoning', 'This is important for our team.')
            decision_val5 = decision.get('decision', 'this matter')
            reasoning_val5 = decision.get('reasoning', 'What are your thoughts?')
            decision_val6 = decision.get('decision', 'our discussion')
            reasoning_val6 = decision.get('reasoning', 'I think this is the right approach.')
            
            body_templates = [
                f"Hi {recipient.name},\n\nI have a question about {decision_val1}. {reasoning_val1}\n\nWhat do you think?\n\nBest regards,\n{self.employee.name}",
                f"Hello {recipient.name},\n\nI need your help with {decision_val2}. {reasoning_val2} Your expertise would be valuable.\n\nThanks,\n{self.employee.name}",
                f"Hi {recipient.name},\n\nQuick question: {decision_val3} {reasoning_val3}\n\nLet me know!\n\nBest,\n{self.employee.name}",
                f"Dear {recipient.name},\n\nI wanted to update you on {decision_val4}. {reasoning_val4}\n\nDo you have any feedback?\n\nRegards,\n{self.employee.name}",
                f"Hello {recipient.name},\n\nI need your input on {decision_val5}. {reasoning_val5}\n\nThanks,\n{self.employee.name}",
                f"Hi {recipient.name},\n\nFollowing up on {decision_val6}. {reasoning_val6}\n\nWhen can we discuss this further?\n\nBest regards,\n{self.employee.name}"
            ]
        
        # Generate or find existing thread ID for this employee pair
        thread_id = generate_thread_id(self.employee.id, recipient.id)
        
        email = Email(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            subject=random.choice(subject_templates),
            body=random.choice(body_templates),
            read=False,
            thread_id=thread_id
        )
        self.db.add(email)
        await self.db.flush()
    
    async def _send_chat(self, recipient: Employee, decision: Dict, business_context: Dict, project_context: Optional[Project] = None):
        """Send a chat message to another employee."""
        project_name = project_context.name if project_context else None
        
        if project_name:
            # Extract decision values for chat templates
            chat_decision1 = decision.get('decision', 'can you help?')
            chat_decision2 = decision.get('decision', 'Making good progress')
            chat_reasoning2 = decision.get('reasoning', 'What do you think?')
            chat_reasoning3 = decision.get('reasoning', 'I need some guidance')
            chat_decision4 = decision.get('decision', 'What should I do next?')
            chat_reasoning5 = decision.get('reasoning', 'when can we discuss?')
            chat_decision6 = decision.get('decision', 'things are going well')
            chat_reasoning6 = decision.get('reasoning', 'Thoughts?')
            chat_reasoning7 = decision.get('reasoning', 'We should coordinate')
            chat_decision8 = decision.get('decision', 'can you help with this?')
            chat_decision9 = decision.get('decision', 'What do you think about this approach?')
            chat_reasoning10 = decision.get('reasoning', 'Can you help?')
            
            chat_templates = [
                f"Hey {recipient.name}, quick question about {project_name} - {chat_decision1}",
                f"Hi! Working on {project_name}. {chat_decision2}. {chat_reasoning2}",
                f"{recipient.name}, can you help me with {project_name}? {chat_reasoning3}",
                f"Quick question about {project_name}: {chat_decision4}",
                f"Hey! Need your input on {project_name} - {chat_reasoning5}",
                f"Update on {project_name}: {chat_decision6}. {chat_reasoning6}",
                f"Hey {recipient.name}, how's your part of {project_name} going? {chat_reasoning7}",
                f"Quick check-in on {project_name} - {chat_decision8}",
                f"Hi {recipient.name}! Question about {project_name}: {chat_decision9}",
                f"Hey, need assistance with {project_name}. {chat_reasoning10}"
            ]
        else:
            # Extract decision values for chat templates
            chat_dec1 = decision.get('decision', 'Can you help me with this?')
            chat_dec2 = decision.get('decision', 'this task')
            chat_rea2 = decision.get('reasoning', 'What do you think?')
            chat_dec3 = decision.get('decision', 'this')
            chat_rea3 = decision.get('reasoning', 'I need some guidance')
            chat_dec4 = decision.get('decision', 'What should I do next?')
            chat_dec5 = decision.get('decision', 'Need to sync')
            chat_rea5 = decision.get('reasoning', 'when works for you?')
            chat_dec6 = decision.get('decision', 'this matter')
            chat_rea6 = decision.get('reasoning', 'Thoughts?')
            chat_dec7 = decision.get('decision', 'making progress')
            chat_rea7 = decision.get('reasoning', 'Do you have any feedback?')
            chat_dec8 = decision.get('decision', 'this')
            chat_rea8 = decision.get('reasoning', 'I could use some help')
            
            chat_templates = [
                f"Hey {recipient.name}, quick question: {chat_dec1}",
                f"Hi! Working on {chat_dec2}. {chat_rea2}",
                f"{recipient.name}, can you help with {chat_dec3}? {chat_rea3}",
                f"Quick question: {chat_dec4}",
                f"Hey! {chat_dec5} - {chat_rea5}",
                f"Hi {recipient.name}, need your input on {chat_dec6}. {chat_rea6}",
                f"Quick update: {chat_dec7}. {chat_rea7}",
                f"Hey, can you assist with {chat_dec8}? {chat_rea8}"
            ]
        
        # Generate or find existing thread ID for this employee pair
        thread_id = generate_thread_id(self.employee.id, recipient.id)
        
        chat = ChatMessage(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            message=random.choice(chat_templates),
            thread_id=thread_id
        )
        self.db.add(chat)
        await self.db.flush()
    
    async def _check_and_respond_to_messages(self, business_context: Dict):
        """Check for unread messages and respond to questions/requests."""
        from sqlalchemy import select, desc
        from datetime import datetime, timedelta
        
        # Check for unread emails from the last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        result = await self.db.execute(
            select(Email)
            .where(
                Email.recipient_id == self.employee.id,
                Email.read == False,
                Email.timestamp >= cutoff_time
            )
            .order_by(desc(Email.timestamp))
            .limit(5)  # Check up to 5 most recent unread emails
        )
        unread_emails = result.scalars().all()
        
        # Check for recent chat messages (chats don't have read status, so check last 2 hours)
        chat_cutoff = datetime.utcnow() - timedelta(hours=2)
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.recipient_id == self.employee.id,
                ChatMessage.timestamp >= chat_cutoff
            )
            .order_by(desc(ChatMessage.timestamp))
            .limit(3)  # Check up to 3 most recent chats
        )
        recent_chats = result.scalars().all()
        
        # Respond to emails that contain questions or requests
        for email in unread_emails:
            if await self._message_needs_response(email.subject + " " + email.body):
                await self._respond_to_email(email, business_context)
                email.read = True
        
        # Respond to chat messages that contain questions or requests
        for chat in recent_chats:
            # Check if we've already responded to this chat (check if we sent a message to the sender after receiving this)
            result = await self.db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.sender_id == self.employee.id,
                    ChatMessage.recipient_id == chat.sender_id,
                    ChatMessage.timestamp > chat.timestamp
                )
                .limit(1)
            )
            already_responded = result.scalar_one_or_none() is not None
            
            if not already_responded and await self._message_needs_response(chat.message):
                await self._respond_to_chat(chat, business_context)
    
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
        
        # Generate response using LLM
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
        
        if response:
            # Use the same thread_id as the original email
            thread_id = email.thread_id or generate_thread_id(self.employee.id, email.sender_id)
            
            # Create reply email
            reply_subject = f"Re: {email.subject}" if not email.subject.startswith("Re:") else email.subject
            
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
    
    async def _respond_to_chat(self, chat: ChatMessage, business_context: Dict):
        """Generate and send a response to a chat message."""
        from sqlalchemy import select
        
        # Get sender information
        result = await self.db.execute(
            select(Employee).where(Employee.id == chat.sender_id)
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
        
        # Generate response using LLM
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
        
        if response:
            # Use the same thread_id as the original chat
            thread_id = chat.thread_id or generate_thread_id(self.employee.id, chat.sender_id)
            
            # Create reply chat
            reply_chat = ChatMessage(
                sender_id=self.employee.id,
                recipient_id=chat.sender_id,
                message=response,
                thread_id=thread_id
            )
            self.db.add(reply_chat)
            await self.db.flush()

