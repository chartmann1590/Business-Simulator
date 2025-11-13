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
        self.client = httpx.AsyncClient(timeout=60.0)
    
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
            response = await self.client.post(
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
            response = await self.client.post(
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
            response = await self.client.post(
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
    
    async def close(self):
        await self.client.aclose()

