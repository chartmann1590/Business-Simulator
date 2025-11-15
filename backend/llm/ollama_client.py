import httpx
import json
from typing import Dict, List, Optional
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self._client = None
    
    async def _get_client(self):
        """Lazy initialization of httpx client to avoid SSL context issues during import."""
        if self._client is None:
            # For HTTP connections, we can disable SSL verification
            # Since we're using localhost HTTP, SSL isn't needed
            self._client = httpx.AsyncClient(
                timeout=60.0,
                verify=False  # Disable SSL verification for localhost HTTP
            )
        return self._client
    
    async def generate_decision(
        self,
        employee_name: str,
        employee_title: str,
        employee_backstory: str,
        employee_role: str,
        personality_traits: List[str],
        business_context: Dict,
        available_options: List[str]
    ) -> Dict:
        """Generate a decision for an employee based on their context."""
        
        personality_str = ", ".join(personality_traits) if personality_traits else "balanced"
        
        prompt = f"""You are {employee_name}, {employee_title} at a growing company.

Your backstory: {employee_backstory}

Your role: {employee_role}
Your personality traits: {personality_str}

Current business situation:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
- Employees: {business_context.get('employee_count', 0)}
- Business goals: {business_context.get('goals', [])}

Available actions you could take:
{chr(10).join(f"- {opt}" for opt in available_options)}

Based on your role, personality, backstory, and the current business situation, what decision would you make?

Respond in JSON format with:
{{
    "decision": "brief description of your decision",
    "reasoning": "why you made this decision",
    "action_type": "one of: strategic, tactical, operational",
    "confidence": 0.0-1.0
}}"""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract JSON from response
            response_text = result.get("response", "")
            # Try to parse JSON from the response
            try:
                if response_text.strip().startswith("{"):
                    decision_data = json.loads(response_text)
                else:
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        decision_data = json.loads(json_match.group())
                    else:
                        # Fallback: create a simple decision
                        decision_data = {
                            "decision": response_text[:200],
                            "reasoning": "Based on current situation",
                            "action_type": "operational",
                            "confidence": 0.7
                        }
            except json.JSONDecodeError:
                decision_data = {
                    "decision": response_text[:200] if response_text else "Continue current work",
                    "reasoning": "Based on current situation and role",
                    "action_type": "operational",
                    "confidence": 0.6
                }
            
            return decision_data
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            # Fallback decision
            return {
                "decision": "Continue current work",
                "reasoning": "System default decision",
                "action_type": "operational",
                "confidence": 0.5
            }
    
    async def analyze_situation(self, context: Dict) -> str:
        """Analyze a business situation and provide insights."""
        prompt = f"""Analyze this business situation and provide insights:

{json.dumps(context, indent=2)}

Provide a brief analysis (2-3 sentences) of the situation."""
        
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "Situation analysis unavailable")
        except Exception as e:
            print(f"Error in analyze_situation: {e}")
            return "Analysis unavailable"
    
    async def plan_task(self, task_description: str, employee_context: Dict) -> Dict:
        """Plan how to execute a task."""
        prompt = f"""Plan how to execute this task: {task_description}

Employee context:
- Role: {employee_context.get('role')}
- Skills: {employee_context.get('skills', [])}

Provide a plan in JSON format:
{{
    "steps": ["step1", "step2", ...],
    "estimated_time": "estimate",
    "resources_needed": ["resource1", ...]
}}"""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "")
            
            try:
                if response_text.strip().startswith("{"):
                    return json.loads(response_text)
                else:
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
            except:
                pass
            
            return {
                "steps": ["Analyze requirements", "Implement solution", "Test and verify"],
                "estimated_time": "2-4 hours",
                "resources_needed": []
            }
        except Exception as e:
            print(f"Error in plan_task: {e}")
            return {
                "steps": ["Execute task"],
                "estimated_time": "Unknown",
                "resources_needed": []
            }
    
    async def generate_response(self, prompt: str) -> str:
        """Generate a text response from a prompt."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            print(f"Error in generate_response: {e}")
            return ""
    
    async def generate_email_response(
        self,
        recipient_name: str,
        recipient_title: str,
        recipient_role: str,
        recipient_personality: List[str],
        sender_name: str,
        sender_title: str,
        original_subject: str,
        original_body: str,
        project_context: Optional[str] = None,
        business_context: Dict = None
    ) -> str:
        """Generate an email response to a question or request."""
        personality_str = ", ".join(recipient_personality) if recipient_personality else "balanced"
        business_info = ""
        if business_context:
            business_info = f"""
Current business situation:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
"""
        
        project_info = f"\nYou are currently working on project: {project_context}" if project_context else ""
        
        prompt = f"""You are {recipient_name}, {recipient_title} at a company. You received an email from {sender_name} ({sender_title}).

Your personality traits: {personality_str}
Your role: {recipient_role}
{project_info}
{business_info}

Original email from {sender_name}:
Subject: {original_subject}

{original_body}

Write a professional, helpful email response. The response should:
1. Address the question or request directly
2. Be appropriate for your role and personality
3. Be concise but complete (2-4 sentences)
4. Use a professional but friendly tone
5. If you don't know something, offer to help find out or suggest next steps

Write only the email body (no subject line, no signature - just the message content)."""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'```[^\n]*\n', '', response_text)
                response_text = re.sub(r'\n```', '', response_text)
            
            # Add signature
            return f"{response_text}\n\nBest regards,\n{recipient_name}"
        except Exception as e:
            print(f"Error generating email response: {e}")
            # Fallback response
            return f"Hi {sender_name},\n\nThanks for reaching out. I'll look into this and get back to you soon.\n\nBest regards,\n{recipient_name}"
    
    async def generate_chat_response(
        self,
        recipient_name: str,
        recipient_title: str,
        recipient_role: str,
        recipient_personality: List[str],
        sender_name: str,
        sender_title: str,
        original_message: str,
        project_context: Optional[str] = None,
        business_context: Dict = None
    ) -> str:
        """Generate a chat response to a question or request."""
        personality_str = ", ".join(recipient_personality) if recipient_personality else "balanced"
        
        # Build work context section
        work_context_section = ""
        if project_context:
            work_context_section = f"\nCurrent work context: {project_context}"
        
        # Build business context section
        business_context_section = ""
        if business_context:
            business_parts = []
            if business_context.get("revenue"):
                business_parts.append(f"Company revenue: ${business_context['revenue']:,.2f}")
            if business_context.get("profit"):
                business_parts.append(f"Company profit: ${business_context['profit']:,.2f}")
            if business_context.get("active_projects"):
                business_parts.append(f"Active projects: {business_context['active_projects']}")
            if business_parts:
                business_context_section = f"\nCompany status: {', '.join(business_parts)}"
        
        prompt = f"""You are {recipient_name}, {recipient_title} at a company. You received a chat message from {sender_name} ({sender_title}).

Your personality traits: {personality_str}
Your role: {recipient_role}{work_context_section}{business_context_section}

Message from {sender_name}:
{original_message}

Write a brief, friendly chat response (1-3 sentences). The response should:
1. Answer the question or address the request directly
2. Match your personality (e.g., if you're analytical, be precise; if creative, be enthusiastic)
3. Be conversational and appropriate for a chat message
4. Reference your current work if relevant to the question
5. If you can't help directly, offer to assist or find someone who can

Write only the response message, nothing else."""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'```[^\n]*\n', '', response_text)
                response_text = re.sub(r'\n```', '', response_text)
            
            # Limit length for chat messages
            if len(response_text) > 200:
                response_text = response_text[:197] + "..."
            
            return response_text
        except Exception as e:
            print(f"Error generating chat response: {e}")
            # Fallback response
            return f"Sure, I can help with that! Let me get back to you shortly."
    
    async def generate_email(
        self,
        sender_name: str,
        sender_title: str,
        sender_role: str,
        sender_personality: List[str],
        recipient_name: str,
        recipient_title: str,
        recipient_role: str,
        decision: str,
        reasoning: str,
        project_context: Optional[str] = None,
        business_context: Dict = None
    ) -> Dict[str, str]:
        """Generate an initial email from one employee to another based on their decision and context."""
        personality_str = ", ".join(sender_personality) if sender_personality else "balanced"
        
        # Build work context section
        work_context_section = ""
        if project_context:
            work_context_section = f"\nYou are currently working on project: {project_context}"
        
        # Build business context section
        business_context_section = ""
        if business_context:
            business_parts = []
            if business_context.get("revenue"):
                business_parts.append(f"Company revenue: ${business_context['revenue']:,.2f}")
            if business_context.get("profit"):
                business_parts.append(f"Company profit: ${business_context['profit']:,.2f}")
            if business_context.get("active_projects"):
                business_parts.append(f"Active projects: {business_context['active_projects']}")
            if business_parts:
                business_context_section = f"\nCurrent business situation: {', '.join(business_parts)}"
        
        prompt = f"""You are {sender_name}, {sender_title} at a company. You want to send an email to {recipient_name} ({recipient_title}).

Your personality traits: {personality_str}
Your role: {sender_role}
Recipient's role: {recipient_role}
{work_context_section}
{business_context_section}

You recently made a decision: {decision}
Your reasoning: {reasoning}

Write a professional email to {recipient_name}. The email should:
1. Have an appropriate subject line (brief and relevant)
2. Have a professional but friendly body (2-4 sentences)
3. Match your personality and role
4. Reference your decision and reasoning naturally
5. Be appropriate for the recipient's role
6. Include a professional closing with your name

Respond in JSON format with:
{{
    "subject": "email subject line",
    "body": "email body content"
}}

Write only the JSON, nothing else."""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Try to parse JSON from the response
            try:
                if response_text.strip().startswith("{"):
                    email_data = json.loads(response_text)
                else:
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        email_data = json.loads(json_match.group())
                    else:
                        raise ValueError("No JSON found in response")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing email JSON: {e}")
                # Fallback: generate simple email
                email_data = {
                    "subject": f"Question about {decision[:50]}",
                    "body": f"Hi {recipient_name},\n\nI wanted to reach out regarding {decision}. {reasoning}\n\nWhat do you think?\n\nBest regards,\n{sender_name}"
                }
            
            # Ensure both subject and body exist
            if "subject" not in email_data:
                email_data["subject"] = f"Question about {decision[:50]}"
            if "body" not in email_data:
                email_data["body"] = f"Hi {recipient_name},\n\nI wanted to reach out regarding {decision}. {reasoning}\n\nBest regards,\n{sender_name}"
            
            return email_data
        except Exception as e:
            print(f"Error generating email: {e}")
            # Fallback email
            return {
                "subject": f"Question about {decision[:50]}",
                "body": f"Hi {recipient_name},\n\nI wanted to reach out regarding {decision}. {reasoning}\n\nWhat do you think?\n\nBest regards,\n{sender_name}"
            }
    
    async def generate_chat(
        self,
        sender_name: str,
        sender_title: str,
        sender_role: str,
        sender_personality: List[str],
        recipient_name: str,
        recipient_title: str,
        recipient_role: str,
        decision: str,
        reasoning: str,
        project_context: Optional[str] = None,
        business_context: Dict = None
    ) -> str:
        """Generate an initial chat message from one employee to another based on their decision and context."""
        personality_str = ", ".join(sender_personality) if sender_personality else "balanced"
        
        # Build work context section
        work_context_section = ""
        if project_context:
            work_context_section = f"\nYou are currently working on project: {project_context}"
        
        # Build business context section
        business_context_section = ""
        if business_context:
            business_parts = []
            if business_context.get("revenue"):
                business_parts.append(f"Company revenue: ${business_context['revenue']:,.2f}")
            if business_context.get("profit"):
                business_parts.append(f"Company profit: ${business_context['profit']:,.2f}")
            if business_context.get("active_projects"):
                business_parts.append(f"Active projects: {business_context['active_projects']}")
            if business_parts:
                business_context_section = f"\nCurrent business situation: {', '.join(business_parts)}"
        
        prompt = f"""You are {sender_name}, {sender_title} at a company. You want to send a chat message to {recipient_name} ({recipient_title}).

Your personality traits: {personality_str}
Your role: {sender_role}
Recipient's role: {recipient_role}
{work_context_section}
{business_context_section}

You recently made a decision: {decision}
Your reasoning: {reasoning}

Write a brief, friendly chat message (1-3 sentences) to {recipient_name}. The message should:
1. Be conversational and appropriate for a chat message
2. Match your personality (e.g., if you're analytical, be precise; if creative, be enthusiastic)
3. Reference your decision and reasoning naturally
4. Be appropriate for the recipient's role
5. Feel like a natural, friendly message between colleagues

Write only the chat message, nothing else."""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'```[^\n]*\n', '', response_text)
                response_text = re.sub(r'\n```', '', response_text)
            
            # Limit length for chat messages
            if len(response_text) > 200:
                response_text = response_text[:197] + "..."
            
            return response_text
        except Exception as e:
            print(f"Error generating chat: {e}")
            # Fallback chat message
            return f"Hey {recipient_name}, quick question: {decision[:100]}"
    
    async def generate_employee_thoughts(
        self,
        employee_name: str,
        employee_title: str,
        employee_role: str,
        personality_traits: List[str],
        backstory: Optional[str],
        recent_activities: List[Dict],
        recent_decisions: List[Dict],
        recent_emails: List[Dict],
        recent_chats: List[Dict],
        recent_reviews: List[Dict],
        current_status: str,
        current_task: Optional[str],
        business_context: Dict
    ) -> str:
        """Generate AI thoughts from the employee's perspective based on their context."""
        personality_str = ", ".join(personality_traits) if personality_traits else "balanced"
        
        # Build recent activities summary
        activities_summary = ""
        if recent_activities:
            activities_summary = "\nRecent activities:\n" + "\n".join([
                f"- {act.get('description', 'N/A')}" for act in recent_activities[:5]
            ])
        
        # Build recent decisions summary
        decisions_summary = ""
        if recent_decisions:
            decisions_summary = "\nRecent decisions:\n" + "\n".join([
                f"- {dec.get('description', 'N/A')}" for dec in recent_decisions[:3]
            ])
        
        # Build recent communications summary
        communications_summary = ""
        if recent_emails or recent_chats:
            comms = []
            if recent_emails:
                comms.extend([f"Email: {email.get('subject', 'N/A')}" for email in recent_emails[:3]])
            if recent_chats:
                comms.extend([f"Chat: {chat.get('message', 'N/A')[:50]}..." for chat in recent_chats[:3]])
            if comms:
                communications_summary = "\nRecent communications:\n" + "\n".join(comms)
        
        # Build reviews summary
        reviews_summary = ""
        if recent_reviews:
            reviews_summary = "\nRecent performance reviews:\n" + "\n".join([
                f"- Rating: {rev.get('overall_rating', 'N/A')}/5.0 - {rev.get('comments', 'No comments')[:100]}"
                for rev in recent_reviews[:2]
            ])
        
        # Build business context
        business_info = f"""
Current business situation:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Profit: ${business_context.get('profit', 0):,.2f}
- Active projects: {business_context.get('active_projects', 0)}
- Total employees: {business_context.get('employee_count', 0)}
"""
        
        current_work = f"\nCurrent work: {current_task}" if current_task else "\nCurrent work: Available for new tasks"
        
        prompt = f"""You are {employee_name}, {employee_title} at a company.

Your personality traits: {personality_str}
Your role: {employee_role}
Your backstory: {backstory or "A dedicated team member"}
Current status: {current_status}
{current_work}
{business_info}
{activities_summary}
{decisions_summary}
{communications_summary}
{reviews_summary}

Based on your personality, role, recent activities, decisions, communications, and the current business situation, what are you thinking about right now? 

Write 2-3 sentences from your first-person perspective that capture:
1. What's on your mind (work-related thoughts, concerns, ideas, or observations)
2. How you're feeling about your current situation
3. What you might be planning or considering

Write as if you're thinking to yourself - be authentic to your personality and role. Use first-person ("I", "my", "me"). Keep it natural and realistic.

Write only the thoughts, nothing else."""

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'```[^\n]*\n', '', response_text)
                response_text = re.sub(r'\n```', '', response_text)
            
            # Ensure it's not empty
            if not response_text:
                response_text = f"I'm focused on my current work and thinking about how to contribute effectively to the team."
            
            return response_text
        except Exception as e:
            print(f"Error generating employee thoughts: {e}")
            # Fallback thoughts
            return f"I'm thinking about my current work and how I can best contribute to the team's success."
    
    async def close(self):
        if self._client is not None:
            await self._client.aclose()

