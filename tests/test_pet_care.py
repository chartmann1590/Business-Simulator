import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from database.database import async_session_maker
from business.pet_manager import PetManager
from engine.office_simulator import get_business_context
from config import is_work_hours

async def test_pet_care():
    print(f"Is work hours? {is_work_hours()}")
    
    async with async_session_maker() as db:
        pet_manager = PetManager(db)
        
        # 1. Check pets
        pets = await pet_manager.get_all_pets()
        print(f"Found {len(pets)} pets.")
        for pet in pets:
            stats = await pet_manager.get_pet_stats(pet)
            print(f"  {pet.name}: Happiness={stats['happiness']:.1f}, Hunger={stats['hunger']:.1f}, Energy={stats['energy']:.1f}")
            
        # 2. Check pets needing care
        needing_care = await pet_manager.check_pets_need_care()
        print(f"Pets needing care: {len(needing_care)}")
        for pet in needing_care:
            print(f"  - {pet.name} needs care")
            
        # 3. Run check_and_provide_pet_care
        print("\nRunning check_and_provide_pet_care...")
        business_context = await get_business_context(db)
        care_logs = await pet_manager.check_and_provide_pet_care(business_context)
        
        print(f"\nGenerated {len(care_logs)} care logs.")
        for log in care_logs:
            print(f"  [NEW] {log.care_action} for pet {log.pet_id} by emp {log.employee_id}")
            print(f"  Reason: {log.ai_reasoning}")

if __name__ == "__main__":
    asyncio.run(test_pet_care())
