from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Employee, Task, Project, Decision, Activity, Email, ChatMessage
from llm.ollama_client import OllamaClient
import random

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
        
        # Occasionally generate communications (30% chance)
        if random.random() < 0.3:
            await self._generate_communication(decision, business_context)
        
        return activity
    
    async def _generate_communication(self, decision: Dict, business_context: Dict):
        """Generate email or chat message based on employee activity."""
        from sqlalchemy import select
        
        # Get other employees to communicate with
        result = await self.db.execute(
            select(Employee).where(
                Employee.id != self.employee.id,
                Employee.status == "active"
            )
        )
        other_employees = result.scalars().all()
        
        if not other_employees:
            return
        
        recipient = random.choice(other_employees)
        
        # 60% email, 40% chat (emails for formal, chats for quick)
        if random.random() < 0.6:
            await self._send_email(recipient, decision, business_context)
        else:
            await self._send_chat(recipient, decision, business_context)
    
    async def _send_email(self, recipient: Employee, decision: Dict, business_context: Dict):
        """Send an email to another employee."""
        # Generate email content based on decision and context
        subject_templates = [
            f"Update on {decision.get('decision', 'current work')}",
            f"Request regarding {decision.get('decision', 'project')}",
            f"Status update from {self.employee.name}",
            f"Question about {decision.get('decision', 'current task')}",
            f"Collaboration needed for {decision.get('decision', 'project')}"
        ]
        
        body_templates = [
            f"Hi {recipient.name},\n\nI wanted to update you on {decision.get('decision', 'my current work')}. {decision.get('reasoning', 'This is important for our team.')}\n\nBest regards,\n{self.employee.name}",
            f"Hello {recipient.name},\n\nI need your input on {decision.get('decision', 'this matter')}. {decision.get('reasoning', 'Your expertise would be valuable.')}\n\nThanks,\n{self.employee.name}",
            f"Dear {recipient.name},\n\nFollowing up on {decision.get('decision', 'our discussion')}. {decision.get('reasoning', 'I think this is the right approach.')}\n\nRegards,\n{self.employee.name}"
        ]
        
        email = Email(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            subject=random.choice(subject_templates),
            body=random.choice(body_templates),
            read=False
        )
        self.db.add(email)
        await self.db.flush()
    
    async def _send_chat(self, recipient: Employee, decision: Dict, business_context: Dict):
        """Send a chat message to another employee."""
        chat_templates = [
            f"Hey {recipient.name}, quick question about {decision.get('decision', 'the project')}",
            f"Hi! Working on {decision.get('decision', 'this task')}. {decision.get('reasoning', 'Thoughts?')}",
            f"{recipient.name}, can you help with {decision.get('decision', 'this')}?",
            f"Quick update: {decision.get('decision', 'making progress')}",
            f"Hey! {decision.get('decision', 'Need to sync')} - {decision.get('reasoning', 'when works?')}"
        ]
        
        chat = ChatMessage(
            sender_id=self.employee.id,
            recipient_id=recipient.id,
            message=random.choice(chat_templates)
        )
        self.db.add(chat)
        await self.db.flush()

