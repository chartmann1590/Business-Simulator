from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import OfficePet, Employee, Activity, PetCareLog
from sqlalchemy import select
from config import now as local_now
from llm.ollama_client import OllamaClient
from engine.movement_system import update_employee_location
import random
import os
import json

class PetManager:
    def __init__(self, db: AsyncSession, llm_client: Optional[OllamaClient] = None):
        self.db = db
        self.llm_client = llm_client or OllamaClient()
    
    async def initialize_pets(self) -> List[OfficePet]:
        """Initialize office pets from available avatars."""
        # Check if pets already exist
        result = await self.db.execute(select(OfficePet))
        existing_pets = result.scalars().all()
        if existing_pets:
            return existing_pets
        
        # Get available pet avatars
        pet_avatars = [
            ("cat_black.png", "cat", "Midnight"),
            ("cat_calico.png", "cat", "Patches"),
            ("cat_gray.png", "cat", "Smokey"),
            ("cat_orange.png", "cat", "Ginger"),
            ("dog_black.png", "dog", "Shadow"),
            ("dog_brown.png", "dog", "Brownie"),
            ("dog_spotted.png", "dog", "Spot"),
            ("dog_white.png", "dog", "Snowball")
        ]
        
        # Create 3-5 random pets
        num_pets = random.randint(3, 5)
        selected_pets = random.sample(pet_avatars, min(num_pets, len(pet_avatars)))
        
        pets = []
        for avatar_file, pet_type, name in selected_pets:
            # Get random employee as favorite
            result = await self.db.execute(
                select(Employee)
                .where(Employee.status == "active")
            )
            employees = result.scalars().all()
            favorite = random.choice(employees) if employees else None
            
            personalities = [
                "Playful and energetic, loves attention",
                "Calm and friendly, great for stress relief",
                "Curious and adventurous, explores the office",
                "Cuddly and affectionate, everyone's favorite",
                "Independent but friendly, keeps to themselves"
            ]
            
            pet = OfficePet(
                name=name,
                pet_type=pet_type,
                avatar_path=f"/avatars/{avatar_file}",
                current_room="breakroom",  # Start in breakroom
                floor=random.randint(1, 3),
                personality=random.choice(personalities),
                favorite_employee_id=favorite.id if favorite else None
            )
            self.db.add(pet)
            pets.append(pet)
        
        await self.db.commit()
        
        # Create activities for pet arrivals
        for pet in pets:
            activity = Activity(
                employee_id=None,
                activity_type="pet_arrival",
                description=f"🐾 {pet.name} the {pet_type} has joined the office!",
                activity_metadata={
                    "pet_id": pet.id,
                    "pet_name": pet.name,
                    "pet_type": pet_type
                }
            )
            self.db.add(activity)
        
        await self.db.commit()
        
        return pets
    
    async def get_all_pets(self) -> List[OfficePet]:
        """Get all office pets."""
        result = await self.db.execute(select(OfficePet))
        return result.scalars().all()
    
    async def move_pet_randomly(self, pet: OfficePet):
        """Move a pet to a random room (occasionally)."""
        # 20% chance to move (more frequent wandering)
        if random.random() > 0.2:
            return
        
        from employees.room_assigner import (
            ROOM_BREAKROOM, ROOM_LOUNGE, ROOM_OPEN_OFFICE, ROOM_CUBICLES,
            ROOM_CONFERENCE_ROOM, ROOM_MANAGER_OFFICE, ROOM_RECEPTION
        )
        
        # Rooms pets can visit
        room_options = [
            (ROOM_BREAKROOM, 1),
            (f"{ROOM_BREAKROOM}_floor2", 2),
            (ROOM_LOUNGE, 1),
            (f"{ROOM_LOUNGE}_floor2", 2),
            (ROOM_OPEN_OFFICE, 1),
            (f"{ROOM_CUBICLES}_floor2", 2),
            (ROOM_CUBICLES, 1),
            (ROOM_RECEPTION, 1),
        ]
        
        new_room, new_floor = random.choice(room_options)
        
        pet.current_room = new_room
        pet.floor = new_floor
        self.db.add(pet)
        
        # Create activity
        activity = Activity(
            employee_id=None,
            activity_type="pet_movement",
            description=f"🐾 {pet.name} is wandering around the {new_room.replace('_floor2', '').replace('_', ' ')} on floor {new_floor}",
            activity_metadata={
                "pet_id": pet.id,
                "room": new_room,
                "floor": new_floor
            }
        )
        self.db.add(activity)
        
        await self.db.commit()
    
    async def check_pet_interactions(self) -> List[Activity]:
        """Check if any employees should interact with pets and move them to pet locations."""
        from engine.movement_system import update_employee_location
        from sqlalchemy import select
        
        activities = []
        
        # Get all pets
        pets_result = await self.db.execute(select(OfficePet))
        pets = pets_result.scalars().all()
        
        if not pets:
            return activities
        
        # Get all active employees
        employees_result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
        )
        employees = employees_result.scalars().all()
        
        # 30% chance per employee to interact with a pet - MUCH HIGHER CHANCE
        for employee in employees:
            if random.random() > 0.30:
                continue
            
            # Find a pet in the same floor or nearby
            nearby_pets = [p for p in pets if abs(p.floor - employee.floor) <= 1]
            if not nearby_pets:
                continue
            
            pet = random.choice(nearby_pets)
            
            # Move employee to pet's location
            await update_employee_location(employee, pet.current_room, "break", self.db)
            employee.floor = pet.floor
            
            # Get pet stats before interaction
            stats_before = await self.get_pet_stats(pet)
            
            # Determine care action and calculate stat changes
            # Randomly choose between feed, play, or pet based on pet needs
            if stats_before["hunger"] > 70:
                action = "feed"
                stats_after = stats_before.copy()
                hunger_reduction = 20 + random.randint(0, 15)  # 20-35
                happiness_increase = 3 + random.randint(0, 10)  # 3-13
                stats_after["hunger"] = max(0, stats_after["hunger"] - hunger_reduction)
                stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
                interaction_desc = f"🍖 {employee.name} fed {pet.name} treats"
            elif stats_before["energy"] > 40 and stats_before["happiness"] < 70:
                action = "play"
                stats_after = stats_before.copy()
                energy_reduction = 10 + random.randint(0, 10)  # 10-20
                happiness_increase = 5 + random.randint(0, 15)  # 5-20
                stats_after["energy"] = max(0, stats_after["energy"] - energy_reduction)
                stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
                interaction_desc = f"🎾 {employee.name} played with {pet.name}"
            else:
                action = "pet"
                stats_after = stats_before.copy()
                happiness_increase = 3 + random.randint(0, 10)  # 3-13
                energy_increase = 1 + random.randint(0, 5)  # 1-6
                stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
                stats_after["energy"] = min(100, stats_after["energy"] + energy_increase)
                interaction_desc = f"❤️ {employee.name} petted {pet.name}"
            
            # Create PetCareLog entry
            care_log = PetCareLog(
                pet_id=pet.id,
                employee_id=employee.id,
                care_action=action,
                pet_happiness_before=stats_before["happiness"],
                pet_hunger_before=stats_before["hunger"],
                pet_energy_before=stats_before["energy"],
                pet_happiness_after=stats_after["happiness"],
                pet_hunger_after=stats_after["hunger"],
                pet_energy_after=stats_after["energy"],
                ai_reasoning=f"Automatic interaction: {employee.name} noticed {pet.name} and provided care"
            )
            self.db.add(care_log)
            
            # Create interaction activity
            activity = Activity(
                employee_id=employee.id,
                activity_type="pet_care",
                description=interaction_desc,
                activity_metadata={
                    "pet_id": pet.id,
                    "pet_name": pet.name,
                    "room": pet.current_room,
                    "floor": pet.floor,
                    "care_action": action,
                    "care_log_id": care_log.id
                }
            )
            self.db.add(activity)
            activities.append(activity)
        
        if activities:
            await self.db.commit()
            # Refresh care logs to ensure they're saved
            for activity in activities:
                await self.db.refresh(activity)
                # Also refresh the care log if it exists in metadata
                if hasattr(activity, 'activity_metadata') and activity.activity_metadata:
                    care_log_id = activity.activity_metadata.get('care_log_id')
                    if care_log_id:
                        from database.models import PetCareLog
                        result = await self.db.execute(
                            select(PetCareLog).where(PetCareLog.id == care_log_id)
                        )
                        care_log = result.scalar_one_or_none()
                        if care_log:
                            await self.db.refresh(care_log)
        
        return activities
    
    async def pet_interaction(self, pet: OfficePet, employee: Employee) -> Activity:
        """Create a pet interaction activity (legacy method for direct calls)."""
        interactions = [
            f"🐾 {employee.name} is petting {pet.name}",
            f"🐾 {pet.name} is keeping {employee.name} company",
            f"🐾 {employee.name} is playing with {pet.name}",
            f"🐾 {pet.name} is sitting with {employee.name}",
            f"🐾 {employee.name} is feeding {pet.name} treats"
        ]
        
        activity = Activity(
            employee_id=employee.id,
            activity_type="pet_interaction",
            description=random.choice(interactions),
            activity_metadata={
                "pet_id": pet.id,
                "pet_name": pet.name
            }
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)
        
        return activity
    
    async def get_pet_stats(self, pet: OfficePet) -> Dict[str, float]:
        """Get current pet stats. In a real implementation, these would be stored in the database.
        For now, we'll simulate them based on pet needs."""
        # Simulate pet stats - in production, these would be stored in the OfficePet model
        # For now, we'll use a simple heuristic based on time since last care
        from datetime import datetime, timedelta
        
        # Get last care log for this pet
        result = await self.db.execute(
            select(PetCareLog)
            .where(PetCareLog.pet_id == pet.id)
            .order_by(PetCareLog.created_at.desc())
            .limit(1)
        )
        last_care = result.scalar_one_or_none()
        
        if last_care:
            # Use stats from last care, but degrade them over time
            time_since_care = (local_now() - last_care.created_at).total_seconds() / 60  # minutes (faster degradation)
            degradation = min(time_since_care * 0.5, 50)  # Degrade faster - 0.5 per minute
            
            happiness = max(0, (last_care.pet_happiness_after or 75) - degradation)
            hunger = min(100, (last_care.pet_hunger_after or 30) + degradation * 1.5)
            energy = max(0, (last_care.pet_energy_after or 70) - degradation * 0.8)
        else:
            # No previous care - use default values that will trigger care
            happiness = 40  # Low enough to trigger care
            hunger = 80  # High enough to trigger care
            energy = 30  # Low enough to trigger care
        
        return {
            "happiness": max(0, min(100, happiness)),
            "hunger": max(0, min(100, hunger)),
            "energy": max(0, min(100, energy))
        }
    
    async def check_pets_need_care(self) -> List[OfficePet]:
        """Check which pets need care based on their stats."""
        pets_result = await self.db.execute(select(OfficePet))
        all_pets = pets_result.scalars().all()
        
        pets_needing_care = []
        for pet in all_pets:
            stats = await self.get_pet_stats(pet)
            
            # Pet needs care if:
            # - Happiness is below 80 (LOWERED from 50)
            # - Hunger is above 50 (LOWERED from 70)
            # - Energy is below 50 (LOWERED from 30)
            # This makes pets need care much more often
            if stats["happiness"] < 80 or stats["hunger"] > 50 or stats["energy"] < 50:
                pets_needing_care.append(pet)
        
        return pets_needing_care
    
    async def select_employee_for_pet_care(self, pet: OfficePet, available_employees: List[Employee], business_context: Dict) -> Tuple[Optional[Employee], str]:
        """Use AI to select the best employee to care for a pet."""
        if not available_employees:
            return None, "No available employees"
        
        # Build employee context
        employee_contexts = []
        for emp in available_employees:
            # Check if employee is on the same floor or nearby
            distance = abs(emp.floor - pet.floor)
            same_floor = distance == 0
            nearby = distance <= 1
            
            # Check if this is the pet's favorite employee
            is_favorite = emp.id == pet.favorite_employee_id
            
            employee_contexts.append({
                "id": emp.id,
                "name": emp.name,
                "title": emp.title,
                "role": emp.role,
                "department": emp.department or "General",
                "personality": emp.personality_traits or [],
                "same_floor": same_floor,
                "nearby": nearby,
                "is_favorite": is_favorite,
                "current_room": emp.current_room,
                "activity_state": emp.activity_state
            })
        
        # Create prompt for AI
        prompt = f"""You are helping to select which employee should care for {pet.name}, a {pet.pet_type} in the office.

Pet Information:
- Name: {pet.name}
- Type: {pet.pet_type}
- Personality: {pet.personality or "Friendly"}
- Current Location: Floor {pet.floor}, Room: {pet.current_room or "Unknown"}
- Favorite Employee: {pet.favorite_employee.name if pet.favorite_employee else "None"}

Available Employees:
{json.dumps(employee_contexts, indent=2)}

Business Context:
- Revenue: ${business_context.get('revenue', 0):,.2f}
- Active Projects: {business_context.get('active_projects', 0)}
- Total Employees: {business_context.get('employee_count', 0)}

Select the best employee to care for {pet.name}. Consider:
1. Who is nearby or on the same floor (easier to reach the pet)
2. Who is the pet's favorite employee (if applicable)
3. Who has a personality that matches caring for pets
4. Who is not too busy (activity_state should not be "meeting" or "working" on critical tasks)
5. Who might benefit from a pet interaction (stress relief, break from work)

Respond in JSON format:
{{
    "selected_employee_id": <employee_id>,
    "reasoning": "brief explanation of why this employee was chosen"
}}"""

        try:
            response_text = await self.llm_client.generate_response(prompt)
            
            # Try to parse JSON from response
            try:
                if response_text.strip().startswith("{"):
                    decision = json.loads(response_text)
                else:
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        decision = json.loads(json_match.group())
                    else:
                        raise ValueError("No JSON found")
                
                selected_id = decision.get("selected_employee_id")
                reasoning = decision.get("reasoning", "Selected based on availability and proximity")
                
                # Find the employee
                selected_employee = next((e for e in available_employees if e.id == selected_id), None)
                
                if selected_employee:
                    return selected_employee, reasoning
                else:
                    # Fallback: choose randomly from nearby employees
                    nearby_employees = [e for e in available_employees if abs(e.floor - pet.floor) <= 1]
                    if nearby_employees:
                        return random.choice(nearby_employees), "Selected nearby employee (AI selection failed)"
                    return random.choice(available_employees), "Selected random employee (AI selection failed)"
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing AI response for pet care selection: {e}")
                # Fallback: choose favorite employee or nearby employee
                if pet.favorite_employee_id:
                    favorite = next((e for e in available_employees if e.id == pet.favorite_employee_id), None)
                    if favorite:
                        return favorite, "Selected pet's favorite employee (fallback)"
                
                nearby_employees = [e for e in available_employees if abs(e.floor - pet.floor) <= 1]
                if nearby_employees:
                    return random.choice(nearby_employees), "Selected nearby employee (fallback)"
                return random.choice(available_employees), "Selected random employee (fallback)"
        except Exception as e:
            print(f"Error in AI pet care selection: {e}")
            # Fallback logic
            if pet.favorite_employee_id:
                favorite = next((e for e in available_employees if e.id == pet.favorite_employee_id), None)
                if favorite:
                    return favorite, "Selected pet's favorite employee (error fallback)"
            
            nearby_employees = [e for e in available_employees if abs(e.floor - pet.floor) <= 1]
            if nearby_employees:
                return random.choice(nearby_employees), "Selected nearby employee (error fallback)"
            return random.choice(available_employees), "Selected random employee (error fallback)"
    
    async def select_care_action(self, pet: OfficePet, stats: Dict[str, float], employee: Employee, business_context: Dict) -> Tuple[str, str]:
        """Use AI to select what care action to take (feed, play, or pet)."""
        prompt = f"""You are helping {employee.name} ({employee.title}) decide how to care for {pet.name}, a {pet.pet_type} in the office.

Pet Information:
- Name: {pet.name}
- Type: {pet.pet_type}
- Personality: {pet.personality or "Friendly"}

Current Pet Stats:
- Happiness: {stats['happiness']:.1f}/100 (higher is better)
- Hunger: {stats['hunger']:.1f}/100 (lower is better)
- Energy: {stats['energy']:.1f}/100 (higher is better)

Employee Information:
- Name: {employee.name}
- Title: {employee.title}
- Role: {employee.role}
- Personality: {', '.join(employee.personality_traits or [])}

Available Actions:
1. "feed" - Reduces hunger significantly, increases happiness moderately. Best when hunger > 60.
2. "play" - Increases happiness significantly, but reduces energy. Best when energy > 40 and happiness < 70.
3. "pet" - Increases happiness moderately, increases energy slightly. Best for general care and comfort.

Based on the pet's current needs and the employee's personality, select the best action.

Respond in JSON format:
{{
    "action": "feed" | "play" | "pet",
    "reasoning": "brief explanation of why this action was chosen"
}}"""

        try:
            response_text = await self.llm_client.generate_response(prompt)
            
            # Try to parse JSON
            try:
                if response_text.strip().startswith("{"):
                    decision = json.loads(response_text)
                else:
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        decision = json.loads(json_match.group())
                    else:
                        raise ValueError("No JSON found")
                
                action = decision.get("action", "pet").lower()
                reasoning = decision.get("reasoning", "Selected based on pet needs")
                
                # Validate action
                if action not in ["feed", "play", "pet"]:
                    # Fallback: choose based on stats
                    if stats["hunger"] > 70:
                        action = "feed"
                    elif stats["energy"] > 40 and stats["happiness"] < 70:
                        action = "play"
                    else:
                        action = "pet"
                    reasoning = f"Selected {action} based on pet stats (AI validation failed)"
                
                return action, reasoning
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing AI response for care action: {e}")
                # Fallback: choose based on stats
                if stats["hunger"] > 70:
                    return "feed", "Selected feed based on high hunger (fallback)"
                elif stats["energy"] > 40 and stats["happiness"] < 70:
                    return "play", "Selected play based on energy and happiness (fallback)"
                else:
                    return "pet", "Selected pet for general care (fallback)"
        except Exception as e:
            print(f"Error in AI care action selection: {e}")
            # Fallback logic
            if stats["hunger"] > 70:
                return "feed", "Selected feed based on high hunger (error fallback)"
            elif stats["energy"] > 40 and stats["happiness"] < 70:
                return "play", "Selected play based on energy and happiness (error fallback)"
            else:
                return "pet", "Selected pet for general care (error fallback)"
    
    async def execute_pet_care(self, pet: OfficePet, employee: Employee, action: str, stats_before: Dict[str, float], ai_reasoning: str) -> PetCareLog:
        """Execute a pet care action and update pet stats."""
        # Calculate stat changes based on action
        stats_after = stats_before.copy()
        
        if action == "feed":
            # Feed: reduces hunger significantly, increases happiness moderately
            hunger_reduction = 30 + random.randint(0, 20)  # 30-50
            happiness_increase = 5 + random.randint(0, 15)  # 5-20
            stats_after["hunger"] = max(0, stats_after["hunger"] - hunger_reduction)
            stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
        elif action == "play":
            # Play: increases happiness significantly, but reduces energy
            if stats_after["energy"] < 15:
                # Can't play if too tired - convert to pet instead
                action = "pet"
                happiness_increase = 5 + random.randint(0, 10)  # 5-15
                energy_increase = 2 + random.randint(0, 5)  # 2-7
                stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
                stats_after["energy"] = min(100, stats_after["energy"] + energy_increase)
            else:
                energy_reduction = 15 + random.randint(0, 15)  # 15-30
                happiness_increase = 10 + random.randint(0, 20)  # 10-30
                stats_after["energy"] = max(0, stats_after["energy"] - energy_reduction)
                stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
        else:  # pet
            # Pet: increases happiness moderately, increases energy slightly
            happiness_increase = 5 + random.randint(0, 15)  # 5-20
            energy_increase = 2 + random.randint(0, 8)  # 2-10
            stats_after["happiness"] = min(100, stats_after["happiness"] + happiness_increase)
            stats_after["energy"] = min(100, stats_after["energy"] + energy_increase)
        
        # Create care log
        care_log = PetCareLog(
            pet_id=pet.id,
            employee_id=employee.id,
            care_action=action,
            pet_happiness_before=stats_before["happiness"],
            pet_hunger_before=stats_before["hunger"],
            pet_energy_before=stats_before["energy"],
            pet_happiness_after=stats_after["happiness"],
            pet_hunger_after=stats_after["hunger"],
            pet_energy_after=stats_after["energy"],
            ai_reasoning=ai_reasoning
        )
        self.db.add(care_log)
        
        # Move employee to pet's location
        await update_employee_location(employee, pet.current_room, "break", self.db)
        employee.floor = pet.floor
        
        # Create activity
        action_descriptions = {
            "feed": f"🍖 {employee.name} fed {pet.name}",
            "play": f"🎾 {employee.name} played with {pet.name}",
            "pet": f"❤️ {employee.name} petted and comforted {pet.name}"
        }
        
        activity = Activity(
            employee_id=employee.id,
            activity_type="pet_care",
            description=action_descriptions.get(action, f"🐾 {employee.name} cared for {pet.name}"),
            activity_metadata={
                "pet_id": pet.id,
                "pet_name": pet.name,
                "care_action": action,
                "care_log_id": care_log.id,
                "happiness_change": stats_after["happiness"] - stats_before["happiness"],
                "hunger_change": stats_after["hunger"] - stats_before["hunger"],
                "energy_change": stats_after["energy"] - stats_before["energy"]
            }
        )
        self.db.add(activity)
        
        await self.db.commit()
        await self.db.refresh(care_log)
        
        return care_log
    
    async def check_and_provide_pet_care(self, business_context: Dict) -> List[PetCareLog]:
        """Check if pets need care and use AI to have employees care for them."""
        # Get pets that need care
        pets_needing_care = await self.check_pets_need_care()
        
        if not pets_needing_care:
            return []
        
        # Get available employees (not too busy)
        result = await self.db.execute(
            select(Employee)
            .where(Employee.status == "active")
            .where(Employee.activity_state.notin_(["meeting", "training"]))
        )
        available_employees = result.scalars().all()
        
        if not available_employees:
            return []
        
        care_logs = []
        
        # Process up to 5 pets per tick to get more activity
        pets_to_care = pets_needing_care[:5]
        
        for pet in pets_to_care:
            try:
                # Get current stats
                stats = await self.get_pet_stats(pet)
                
                # Use AI to select employee
                employee_result = await self.select_employee_for_pet_care(pet, available_employees, business_context)
                if isinstance(employee_result, tuple):
                    selected_employee, employee_reasoning = employee_result
                else:
                    selected_employee = employee_result
                    employee_reasoning = "Selected based on availability"
                
                if not selected_employee:
                    continue
                
                # Use AI to select care action
                action, action_reasoning = await self.select_care_action(pet, stats, selected_employee, business_context)
                
                # Combine reasoning
                full_reasoning = f"{employee_reasoning}. {action_reasoning}"
                
                # Execute care
                care_log = await self.execute_pet_care(pet, selected_employee, action, stats, full_reasoning)
                care_logs.append(care_log)
                
                print(f"✅ {selected_employee.name} {action}ed {pet.name} (Happiness: {stats['happiness']:.1f}→{care_log.pet_happiness_after:.1f}, Hunger: {stats['hunger']:.1f}→{care_log.pet_hunger_after:.1f}, Energy: {stats['energy']:.1f}→{care_log.pet_energy_after:.1f})")
                
            except Exception as e:
                print(f"Error providing care for {pet.name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return care_logs

