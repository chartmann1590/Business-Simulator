import httpx
import json
from typing import Dict, List, Optional
import os
import random

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_FALLBACK_URL = os.getenv("OLLAMA_FALLBACK_URL", None)
# Default to llama3.2 or gemma3, preferring llama3.2
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.fallback_url = OLLAMA_FALLBACK_URL
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
    
    async def _make_request_with_fallback(self, endpoint: str, json_data: Dict) -> httpx.Response:
        """
        Make an HTTP request to Ollama with automatic fallback to fallback URL if main URL fails.
        
        Args:
            endpoint: API endpoint (e.g., "/api/generate")
            json_data: JSON payload for the request
            
        Returns:
            httpx.Response object
            
        Raises:
            Exception: If both main and fallback URLs fail
        """
        client = await self._get_client()
        
        # Try main URL first
        try:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=json_data
            )
            response.raise_for_status()
            return response
        except Exception as e:
            # If main URL fails and we have a fallback URL, try it
            if self.fallback_url:
                print(f"⚠️  Main Ollama server ({self.base_url}) failed: {e}")
                print(f"🔄 Attempting fallback to {self.fallback_url}")
                try:
                    response = await client.post(
                        f"{self.fallback_url}{endpoint}",
                        json=json_data
                    )
                    response.raise_for_status()
                    print(f"✅ Successfully connected to fallback Ollama server")
                    return response
                except Exception as fallback_error:
                    print(f"❌ Fallback Ollama server ({self.fallback_url}) also failed: {fallback_error}")
                    raise fallback_error
            else:
                # No fallback URL configured, raise the original error
                raise e
    
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
        """Generate an email response to any type of email (questions, updates, information, etc.)."""
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
1. Always respond - acknowledge the email even if it's just an update or information sharing
2. If there's a question or request, address it directly
3. If it's an update or information, acknowledge it and add a brief relevant comment or follow-up
4. Be appropriate for your role and personality
5. Be concise but complete (2-4 sentences)
6. Use a professional but friendly tone
7. Keep the conversation going naturally - show engagement with the content
8. If you don't know something, offer to help find out or suggest next steps

Write only the email body (no subject line, no signature - just the message content)."""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
1. Always respond - acknowledge the message even if it's just an update or statement
2. Answer any questions or address requests directly
3. Match your personality (e.g., if you're analytical, be precise; if creative, be enthusiastic)
4. Be conversational and appropriate for a chat message
5. Reference your current work if relevant
6. If it's just an update or statement, acknowledge it and add a brief relevant comment
7. Keep the conversation going naturally

Write only the response message, nothing else."""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
    
    async def generate_casual_conversation(
        self,
        employee1_name: str,
        employee1_title: str,
        employee1_role: str,
        employee1_personality: List[str],
        employee2_name: str,
        employee2_title: str,
        employee2_role: str,
        employee2_personality: List[str],
        business_context: Dict = None,
        conversation_type: str = "mixed"  # "work", "personal", or "mixed"
    ) -> Dict[str, str]:
        """Generate a casual conversation between two employees."""
        personality1_str = ", ".join(employee1_personality) if employee1_personality else "balanced"
        personality2_str = ", ".join(employee2_personality) if employee2_personality else "balanced"
        
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
        
        # Determine conversation topic
        topic_instruction = ""
        if conversation_type == "work":
            topic_instruction = "Focus the conversation on work-related topics like projects, tasks, deadlines, or work challenges."
        elif conversation_type == "personal":
            topic_instruction = "Focus the conversation on personal topics like weekend plans, hobbies, family, or casual life updates."
        else:  # mixed
            topic_instruction = "Mix work and personal topics naturally - they might discuss a project briefly, then chat about weekend plans or casual topics."
        
        prompt = f"""Generate a brief, natural conversation between two coworkers in an office setting.

Employee 1: {employee1_name}, {employee1_title} ({employee1_role})
Personality: {personality1_str}

Employee 2: {employee2_name}, {employee2_title} ({employee2_role})
Personality: {personality2_str}
{business_context_section}

{topic_instruction}

The conversation should:
1. Be brief (2-4 exchanges total)
2. Sound natural and conversational
3. Match each person's personality
4. Be appropriate for an office setting
5. Feel authentic and realistic

Format the response as JSON with this structure:
{{
  "message1": {{
    "speaker": "{employee1_name}",
    "text": "first message from employee1"
  }},
  "message2": {{
    "speaker": "{employee2_name}",
    "text": "response from employee2"
  }},
  "message3": {{
    "speaker": "{employee1_name}",
    "text": "optional follow-up from employee1"
  }},
  "message4": {{
    "speaker": "{employee2_name}",
    "text": "optional final response from employee2"
  }}
}}

Only include message1 and message2 as required. Add message3 and message4 only if the conversation naturally continues.
Keep each message to 1-2 sentences maximum."""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'```[^\n]*\n', '', response_text)
                response_text = re.sub(r'\n```', '', response_text)
            
            # Try to parse JSON
            try:
                conversation = json.loads(response_text)
                # Validate structure
                messages = []
                for key in ["message1", "message2", "message3", "message4"]:
                    if key in conversation and conversation[key]:
                        msg = conversation[key]
                        if "speaker" in msg and "text" in msg:
                            messages.append({
                                "speaker": msg["speaker"],
                                "text": msg["text"]
                            })
                
                if len(messages) >= 2:
                    return {"messages": messages}
                else:
                    raise ValueError("Not enough valid messages")
            except (json.JSONDecodeError, ValueError) as e:
                # Fallback: create a simple conversation
                print(f"Error parsing conversation JSON: {e}, response: {response_text[:200]}")
                return {
                    "messages": [
                        {"speaker": employee1_name, "text": f"Hey {employee2_name.split()[0]}, how's it going?"},
                        {"speaker": employee2_name, "text": "Pretty good! Just working on some tasks. How about you?"}
                    ]
                }
        except Exception as e:
            print(f"Error generating casual conversation: {e}")
            # Fallback conversation
            return {
                "messages": [
                    {"speaker": employee1_name, "text": f"Hey {employee2_name.split()[0]}, how's your day going?"},
                    {"speaker": employee2_name, "text": "It's going well, thanks for asking!"}
                ]
            }
    
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
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
    
    def _is_valid_name(self, name: str) -> bool:
        """Validate that a name is a proper employee name."""
        if not name or len(name.strip()) < 3:
            return False
        
        name_lower = name.lower().strip()
        
        # Invalid patterns - phrases, contractions, common words
        # Note: We check for these as whole words/phrases, not substrings
        invalid_patterns = [
            "i can't", "i can ", "i will", "i won't", "i'm ", "i am ", "i have ",
            " can't", " won't", " don't", " isn't", " aren't", " wasn't", " weren't",
            "the ", "a ", "an ", "this ", "that ", "these ", "those ",
            "yes ", "no ", "maybe ", "perhaps ", "sure ", "okay ", "ok ",
            "hello ", "hi ", "hey ", "thanks ", "thank you",
            "here is", "here's", "there is", "there's",
            "my name", "name is", " called", " named",
            " employee", " worker", " staff", " person", " human",
            " example", " sample", " test", " demo", " placeholder"
        ]
        
        # Check for invalid patterns (must match as whole phrase, not substring)
        for pattern in invalid_patterns:
            # Check if pattern appears at start or as a separate word
            if name_lower.startswith(pattern) or f" {pattern}" in name_lower:
                return False
        
        # Must be exactly two words (first and last name)
        parts = name.split()
        if len(parts) != 2:
            return False
        
        first, last = parts
        
        # Each part must be at least 2 characters
        if len(first) < 2 or len(last) < 2:
            return False
        
        # Each part should start with a capital letter (or be all caps)
        if not (first[0].isupper() or first.isupper()):
            return False
        if not (last[0].isupper() or last.isupper()):
            return False
        
        # Should only contain letters, hyphens, and apostrophes (for names like O'Brien)
        import re
        name_pattern = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
        if not name_pattern.match(first) or not name_pattern.match(last):
            return False
        
        # Reject if it's a common phrase or sentence (but allow names that contain these as substrings)
        # Only reject if the name starts with these words (indicating a phrase)
        invalid_starters = ["the ", "a ", "an ", "and ", "or ", "but ", "is ", "are ", "was ", "were "]
        if any(name_lower.startswith(starter) for starter in invalid_starters):
            return False
        
        return True
    
    async def generate_unique_employee_name(
        self,
        existing_names: List[str],
        department: Optional[str] = None,
        role: Optional[str] = None
    ) -> str:
        """Generate a unique employee name using AI, avoiding duplicates with existing names."""
        existing_names_str = ", ".join(existing_names) if existing_names else "none"
        
        prompt = f"""You are generating a REAL PERSON'S NAME for an employee in a business simulation.

CRITICAL REQUIREMENTS:
1. Generate ONLY a proper first name and last name (e.g., "Sarah Chen", "Marcus Rodriguez", "Emily Watson")
2. The name must be TWO WORDS ONLY - a first name and a last name
3. Each name part must be a REAL, PROPER NAME (not a phrase, not a sentence, not a contraction)
4. DO NOT use phrases like "I can't", "I will", "Here is", "My name is", etc.
5. DO NOT use contractions like "can't", "won't", "don't"
6. DO NOT use common words like "the", "a", "employee", "person"
7. The name should be DISTINCT from these existing names: {existing_names_str}
8. Make it diverse, professional, and realistic
9. Return ONLY the name in format "FirstName LastName" with no other text

EXAMPLES OF GOOD NAMES:
- "Alexandra Bennett"
- "Benjamin Chen"
- "Catherine Rodriguez"
- "Daniel Kim"

EXAMPLES OF BAD NAMES (DO NOT GENERATE THESE):
- "I can't" (this is a phrase, not a name)
- "Here is John" (this is a sentence)
- "My name is Sarah" (this is a sentence)
- "Employee Smith" (contains common word)

{f"Department: {department}" if department else ""}
{f"Role: {role}" if role else ""}

Generate the name now (ONLY the name, nothing else):"""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Clean up the response - extract just the name
            import re
            # Remove markdown code blocks if present
            response_text = re.sub(r'```[^\n]*\n?', '', response_text)
            response_text = re.sub(r'\n?```', '', response_text)
            
            # Try to extract name from JSON if present
            json_match = re.search(r'"name"\s*:\s*"([^"]+)"', response_text)
            if json_match:
                response_text = json_match.group(1)
            
            # Extract first and last name (should be exactly two words)
            name_parts = [part.strip() for part in response_text.split() if part.strip()]
            
            # Try to extract just the first two words (in case AI added extra text)
            if len(name_parts) >= 2:
                name = f"{name_parts[0]} {name_parts[1]}"
            elif len(name_parts) == 1:
                # If only one word, add a common last name
                name = f"{name_parts[0]} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'])}"
            else:
                # Fallback if no valid name found
                name = None
            
            # CRITICAL: Validate the name before using it
            if name and self._is_valid_name(name):
                name_lower = name.lower()
                # Verify it's not in existing names (case-insensitive)
                if any(existing.lower() == name_lower for existing in existing_names):
                    # If duplicate, try once more with emphasis
                    return await self._generate_name_retry(existing_names, department, role)
                # Name is valid and unique - return it
                return name
            else:
                # Invalid name generated - log and use fallback
                print(f"⚠️  AI generated invalid name: '{response_text}' - using fallback")
                return await self._generate_name_fallback(existing_names)
                
        except Exception as e:
            print(f"Error generating employee name with AI: {e}")
            return await self._generate_name_fallback(existing_names)
    
    async def _generate_name_retry(
        self,
        existing_names: List[str],
        department: Optional[str] = None,
        role: Optional[str] = None
    ) -> str:
        """Retry name generation with stronger emphasis on uniqueness."""
        existing_names_str = ", ".join(existing_names)
        
        prompt = f"""Generate a COMPLETELY DIFFERENT REAL PERSON'S NAME from these existing names: {existing_names_str}

CRITICAL REQUIREMENTS:
1. Generate ONLY a proper first name and last name (e.g., "Sarah Chen", "Marcus Rodriguez")
2. The name must be TWO WORDS ONLY - a first name and a last name
3. DO NOT use phrases, sentences, contractions, or common words
4. The name must be VERY DIFFERENT - different first letter, different sound, completely unique
5. Return ONLY the name in format "FirstName LastName" with no other text

EXAMPLES OF GOOD NAMES: "Alexandra Bennett", "Benjamin Chen", "Catherine Rodriguez"
BAD (DO NOT USE): "I can't", "Here is John", "My name is Sarah"

Generate the name now (ONLY the name):"""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            result = response.json()
            response_text = result.get("response", "").strip()
            
            import re
            response_text = re.sub(r'```[^\n]*\n?', '', response_text)
            response_text = re.sub(r'\n?```', '', response_text)
            
            name_parts = [part.strip() for part in response_text.split() if part.strip()]
            
            if len(name_parts) >= 2:
                name = f"{name_parts[0]} {name_parts[1]}"
                # Validate the name
                if self._is_valid_name(name):
                    name_lower = name.lower()
                    if not any(existing.lower() == name_lower for existing in existing_names):
                        return name
            
            # Invalid or duplicate - use fallback
            print(f"⚠️  Retry generated invalid/duplicate name: '{response_text}' - using fallback")
            return await self._generate_name_fallback(existing_names)
        except:
            return await self._generate_name_fallback(existing_names)
    
    async def _generate_name_fallback(self, existing_names: List[str]) -> str:
        """Fallback name generation using diverse name pools."""
        
        # Diverse first names
        first_names = [
            "Alexandra", "Benjamin", "Catherine", "Daniel", "Elena", "Felix", "Gabriela", "Hector",
            "Isabella", "Julian", "Katherine", "Lucas", "Maya", "Nathan", "Olivia", "Parker",
            "Quinn", "Rachel", "Samuel", "Tessa", "Victor", "Wendy", "Xavier", "Yara", "Zoe",
            "Adrian", "Brianna", "Caleb", "Diana", "Ethan", "Fiona", "George", "Hannah",
            "Ian", "Jasmine", "Kevin", "Lily", "Marcus", "Nora", "Oscar", "Penelope"
        ]
        
        # Diverse last names
        last_names = [
            "Anderson", "Bennett", "Chen", "Davis", "Evans", "Foster", "Garcia", "Hughes",
            "Ivanov", "Jackson", "Kim", "Lopez", "Martinez", "Nguyen", "O'Brien", "Patel",
            "Quinn", "Rodriguez", "Singh", "Thompson", "Ueda", "Vargas", "Wang", "Xu",
            "Yamamoto", "Zhang", "Adams", "Brown", "Clark", "Diaz", "Edwards", "Fisher",
            "Green", "Hall", "Irwin", "Johnson", "Kumar", "Lee", "Moore", "Nelson"
        ]
        
        # Try up to 20 times to find a unique name
        for _ in range(20):
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            name_lower = name.lower()
            if not any(existing.lower() == name_lower for existing in existing_names):
                return name
        
        # If still duplicate, add a number
        base_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        counter = 1
        while f"{base_name} {counter}" in existing_names:
            counter += 1
        return f"{base_name} {counter}"
    
    async def generate_screen_activity(
        self,
        employee_name: str,
        employee_title: str,
        employee_role: str,
        personality_traits: List[str],
        current_task: Optional[str] = None,
        project_name: Optional[str] = None,
        project_description: Optional[str] = None,
        recent_emails: List[Dict] = None,
        recent_chats: List[Dict] = None,
        shared_drive_files: List[Dict] = None,
        business_context: Dict = None
    ) -> Dict:
        """Generate realistic screen activity for an employee based on their work context."""
        
        personality_str = ", ".join(personality_traits) if personality_traits else "balanced"
        
        # Build work context
        work_context_parts = []
        if project_name:
            work_context_parts.append(f"working on the '{project_name}' project")
        if project_description:
            work_context_parts.append(f"project description: {project_description}")
        if current_task:
            work_context_parts.append(f"current task: {current_task}")
        
        work_context = ". ".join(work_context_parts) if work_context_parts else "available for work"
        
        # Build recent activity context with actual data
        activity_context = ""
        if recent_emails and len(recent_emails) > 0:
            activity_context += f"\nRecent emails ({len(recent_emails)}):\n"
            for email in recent_emails[:3]:  # Show first 3
                activity_context += f"  - From: {email.get('sender_name', 'Unknown')}, Subject: {email.get('subject', 'No Subject')}\n"
                if email.get('body'):
                    body_preview = email.get('body', '')[:150]
                    activity_context += f"    Preview: {body_preview}...\n"
        if recent_chats and len(recent_chats) > 0:
            activity_context += f"\nRecent Teams messages ({len(recent_chats)}):\n"
            for chat in recent_chats[:3]:  # Show first 3
                activity_context += f"  - {chat.get('sender_name', 'Unknown')}: {chat.get('message', '')[:100]}...\n"
        if shared_drive_files and len(shared_drive_files) > 0:
            activity_context += f"\nAvailable documents ({len(shared_drive_files)}):\n"
            for file in shared_drive_files[:3]:  # Show first 3
                activity_context += f"  - {file.get('file_name', 'Unknown')} ({file.get('file_type', 'file')})\n"
        
        # Build business context string
        business_context_section = ""
        if business_context:
            business_parts = []
            if business_context.get('revenue'):
                business_parts.append(f"revenue: ${business_context.get('revenue', 0):,.2f}")
            if business_context.get('profit'):
                business_parts.append(f"profit: ${business_context.get('profit', 0):,.2f}")
            if business_context.get('active_projects'):
                business_parts.append(f"active projects: {business_context.get('active_projects', 0)}")
            if business_parts:
                business_context_section = f"\nCompany status: {', '.join(business_parts)}"
        
        prompt = f"""You are simulating what {employee_name} ({employee_title}) is currently doing on their computer screen.

Employee context:
- Name: {employee_name}
- Title: {employee_title}
- Role: {employee_role}
- Personality: {personality_str}
- Current work: {work_context}
{activity_context}{business_context_section}

Based on this context, determine what application they are actively using and what they are doing. Choose ONE of these applications:
1. Outlook (email) - if they should be sending/reading emails
2. Teams (chat) - if they should be messaging colleagues
3. Browser (web) - if they should be researching or browsing
4. ShareDrive (documents) - if they should be working on documents

Generate realistic content for the chosen application that matches their current work context and personality.

IMPORTANT: When generating content, use the actual data provided above when available:
- For Outlook: Use actual email subjects, senders, and content from recent emails
- For Teams: Use actual messages and sender names from recent chats
- For ShareDrive: Use actual file names and content from available documents
- For Browser: Generate realistic web content related to their work

If viewing/reading, show actual content from the data above. If composing/editing, create new content that relates to the actual data.

Return a JSON object with this exact structure:
{{
    "application": "outlook|teams|browser|sharedrive",
    "action": "composing|reading|replying|browsing|viewing|editing",
    "content": {{
        // Application-specific content
        // For Outlook: subject, recipient, sender, body (use actual email data if viewing)
        // For Teams: conversation_with (colleague name), messages array (use actual messages if viewing)
        // For Browser: url, page_title, page_content (HTML content that will be rendered)
        // For ShareDrive: file_name, file_type, document_content (use actual file content if viewing)
    }},
    "mouse_position": {{"x": 0-100, "y": 0-100}},
    "window_state": "active|minimized|maximized"
}}

Make the content realistic and relevant to their current task and project. Use actual data when available."""

        try:
            response = await self._make_request_with_fallback(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Parse JSON response
            try:
                # Remove markdown code blocks if present
                if response_text.startswith("```"):
                    import re
                    response_text = re.sub(r'```json\s*', '', response_text)
                    response_text = re.sub(r'```\s*', '', response_text)
                
                activity_data = json.loads(response_text)
                
                # Validate and set defaults
                if "application" not in activity_data:
                    activity_data["application"] = random.choice(["outlook", "teams", "browser", "sharedrive"])
                
                if "action" not in activity_data:
                    activity_data["action"] = "viewing"
                
                if "content" not in activity_data:
                    activity_data["content"] = {}
                
                if "mouse_position" not in activity_data:
                    activity_data["mouse_position"] = {"x": random.randint(20, 80), "y": random.randint(20, 80)}
                
                if "window_state" not in activity_data:
                    activity_data["window_state"] = "active"
                
                return activity_data
                
            except json.JSONDecodeError as e:
                print(f"Error parsing screen activity JSON: {e}")
                print(f"Response was: {response_text[:500]}")
                # Return fallback activity
                return {
                    "application": "outlook",
                    "action": "viewing",
                    "content": {
                        "subject": "Work Update",
                        "recipient": "Team",
                        "body": f"{employee_name} is reviewing emails related to their current work."
                    },
                    "mouse_position": {"x": 50, "y": 50},
                    "window_state": "active"
                }
                
        except Exception as e:
            print(f"Error generating screen activity: {e}")
            # Return fallback activity
            return {
                "application": "outlook",
                "action": "viewing",
                "content": {
                    "subject": "Work Update",
                    "recipient": "Team",
                    "body": f"{employee_name} is working on their current tasks."
                },
                "mouse_position": {"x": 50, "y": 50},
                "window_state": "active"
            }
    
    async def close(self):
        if self._client is not None:
            await self._client.aclose()

