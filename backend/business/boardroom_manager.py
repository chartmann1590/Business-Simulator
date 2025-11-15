"""
Boardroom Manager - Handles continuous boardroom meetings and discussions.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Employee, ChatMessage
from datetime import datetime, timedelta
import random
from typing import List, Optional
from llm.ollama_client import OllamaClient
from employees.base import generate_thread_id

# Module-level state to persist across instances
_boardroom_state = {
    'last_rotation_time': None,
    'current_executives': [],
    'last_discussion_time': None
}


class BoardroomManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_current_boardroom_executives(self) -> List[Employee]:
        """Get the executives currently in the boardroom based on rotation schedule."""
        # Get all leadership team
        result = await self.db.execute(
            select(Employee).where(
                Employee.role.in_(["CEO", "Manager"]),
                Employee.status == "active"
            )
        )
        all_executives = result.scalars().all()
        
        if len(all_executives) < 2:
            return []
        
        # Calculate rotation based on time
        now = datetime.utcnow()
        ROTATION_INTERVAL = timedelta(minutes=30)
        
        # Initialize or check if rotation is needed
        if _boardroom_state['last_rotation_time'] is None:
            # First time - select initial executives
            _boardroom_state['last_rotation_time'] = now
            self._select_executives(all_executives)
        else:
            # Check if 30 minutes have passed
            last_rotation = _boardroom_state['last_rotation_time']
            if isinstance(last_rotation, str):
                # Handle string timestamp from storage
                last_rotation = datetime.fromisoformat(last_rotation.replace('Z', '+00:00'))
            time_since_rotation = now - last_rotation
            if time_since_rotation >= ROTATION_INTERVAL:
                # Rotate executives
                self._select_executives(all_executives, is_rotation=True)
                _boardroom_state['last_rotation_time'] = now
        
        # Get current executives by ID
        if not _boardroom_state['current_executives']:
            self._select_executives(all_executives)
        
        result = await self.db.execute(
            select(Employee).where(Employee.id.in_(_boardroom_state['current_executives']))
        )
        return result.scalars().all()
    
    def _select_executives(self, all_executives: List[Employee], is_rotation: bool = False):
        """Select 7 executives for the boardroom (CEO always stays)."""
        max_in_room = 7
        ceo = next((e for e in all_executives if e.role == "CEO"), None)
        
        # Get current CEO if rotating
        current_ceo_id = None
        if is_rotation and _boardroom_state['current_executives']:
            # Find CEO in current executives
            for eid in _boardroom_state['current_executives']:
                emp = next((e for e in all_executives if e.id == eid), None)
                if emp and emp.role == "CEO":
                    current_ceo_id = eid
                    break
        
        selected_ceo = ceo if ceo else (next((e for e in all_executives if e.id == current_ceo_id), None) if current_ceo_id else None)
        
        # Get other executives
        others = [e for e in all_executives if e.role != "CEO" and e.id != (selected_ceo.id if selected_ceo else None)]
        
        if is_rotation and _boardroom_state['current_executives']:
            # Exclude current executives (except CEO) from selection
            current_other_ids = {eid for eid in _boardroom_state['current_executives'] if eid != (selected_ceo.id if selected_ceo else None)}
            available = [e for e in others if e.id not in current_other_ids]
            random.shuffle(available)
            selected_others = available[:max_in_room - 1] if selected_ceo else available[:max_in_room]
        else:
            # Initial selection - random
            random.shuffle(others)
            selected_others = others[:max_in_room - 1] if selected_ceo else others[:max_in_room]
        
        # Combine CEO with selected others
        if selected_ceo:
            _boardroom_state['current_executives'] = [selected_ceo.id] + [e.id for e in selected_others]
        else:
            _boardroom_state['current_executives'] = [e.id for e in selected_others[:max_in_room]]
    
    async def generate_boardroom_discussions(self) -> int:
        """Generate discussions between executives currently in the boardroom."""
        executives = await self.get_current_boardroom_executives()
        
        if len(executives) < 2:
            return 0
        
        # Get business context
        from engine.office_simulator import get_business_context
        business_context = await get_business_context(self.db)
        
        llm_client = OllamaClient()
        chats_created = 0
        
        # Create list of all executives in the room for context
        executives_in_room = [f"{e.name} ({e.title})" for e in executives]
        room_context = ", ".join(executives_in_room)
        
        # Generate diverse strategic boardroom discussion topics
        discussion_topics = [
            "strategic planning for Q4 revenue growth",
            "resource allocation for upcoming projects",
            "market expansion opportunities",
            "operational efficiency improvements",
            "team performance and productivity",
            "budget optimization strategies",
            "technology investment priorities",
            "customer acquisition initiatives",
            "competitive positioning analysis",
            "risk management and mitigation",
            "quarterly financial performance review",
            "hiring and talent acquisition strategy",
            "product development roadmap",
            "customer retention programs",
            "supply chain optimization",
            "digital transformation initiatives",
            "partnership and alliance opportunities",
            "brand positioning and marketing strategy",
            "workplace culture and employee engagement",
            "sustainability and corporate responsibility",
            "merger and acquisition opportunities",
            "international expansion plans",
            "innovation and R&D investments",
            "cost reduction initiatives",
            "sales strategy and pipeline management",
            "customer service improvements",
            "data analytics and business intelligence",
            "cybersecurity and data protection",
            "regulatory compliance and governance",
            "vendor and supplier relationships",
            "project portfolio management",
            "quality assurance and process improvement",
            "employee training and development",
            "succession planning and leadership development",
            "market research and customer insights",
            "pricing strategy and revenue optimization",
            "channel partner relationships",
            "product launch planning",
            "customer feedback and satisfaction",
            "operational metrics and KPIs",
            "strategic partnerships",
            "workforce planning and optimization",
            "customer experience enhancement",
            "business continuity planning",
            "change management initiatives"
        ]
        
        # Shuffle topics to ensure variety
        available_topics = discussion_topics.copy()
        random.shuffle(available_topics)
        topic_index = 0
        
        # Generate 3-6 discussions between random pairs
        num_discussions = random.randint(3, min(6, max(3, len(executives))))
        used_pairs = set()
        used_topics_in_batch = set()
        
        for _ in range(num_discussions):
            if len(executives) < 2:
                break
            
            sender, recipient = random.sample(executives, 2)
            pair_key = tuple(sorted([sender.id, recipient.id]))
            
            if pair_key in used_pairs:
                continue
            used_pairs.add(pair_key)
            
            # Select a unique topic for this discussion
            topic = None
            attempts = 0
            while topic is None or topic in used_topics_in_batch:
                if topic_index >= len(available_topics):
                    available_topics = discussion_topics.copy()
                    random.shuffle(available_topics)
                    topic_index = 0
                    used_topics_in_batch.clear()
                
                topic = available_topics[topic_index]
                topic_index += 1
                attempts += 1
                
                if attempts > len(discussion_topics):
                    topic = random.choice(discussion_topics)
                    break
            
            used_topics_in_batch.add(topic)
            
            # Generate message using LLM
            personality_str = ", ".join(sender.personality_traits or ["strategic", "analytical"])
            recipient_personality = ", ".join(recipient.personality_traits or ["strategic", "analytical"])
            
            prompt = f"""You are {sender.name}, {sender.title} at a company. You are currently in a boardroom meeting with the following executives: {room_context}.

You are directly addressing {recipient.name} ({recipient.title}) who is sitting across the table from you in this boardroom meeting. You're discussing {topic} together.

Your personality traits: {personality_str}
Your role: {sender.role}
{recipient.name}'s personality traits: {recipient_personality}
{recipient.name}'s role: {recipient.role}

Current business context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}
- Employees: {business_context.get('employee_count', 0)}

Write a brief, direct boardroom discussion message (1-2 sentences) to {recipient.name} about {topic}. The message should:
1. Be conversational and direct, as if speaking face-to-face in the boardroom
2. Address {recipient.name} directly by name
3. Be strategic and business-focused
4. Match your executive role and personality
5. Be appropriate for a boardroom setting where you can see each other
6. Reference the business context naturally
7. Feel like a natural conversation between colleagues in the same room

Write only the message, nothing else. Make it feel like you're talking directly to them in person."""

            try:
                client = await llm_client._get_client()
                response = await client.post(
                    f"{llm_client.base_url}/api/generate",
                    json={
                        "model": llm_client.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message = result.get("response", "").strip()
                    message = message.strip('"').strip("'").strip()
                    
                    if not message:
                        message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
                else:
                    message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
            except Exception as e:
                print(f"Error generating boardroom message: {e}")
                message = f"{recipient.name}, I'd like to get your thoughts on {topic}. What's your take on this?"
            
            # Create chat message
            thread_id = generate_thread_id(sender.id, recipient.id)
            chat = ChatMessage(
                sender_id=sender.id,
                recipient_id=recipient.id,
                message=message,
                thread_id=thread_id
            )
            self.db.add(chat)
            chats_created += 1
        
        await self.db.commit()
        return chats_created

