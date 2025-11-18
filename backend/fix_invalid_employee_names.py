"""
Script to find and fix employees with invalid names.
This will check all employees and regenerate names for any that fail validation.
"""
import asyncio
from database.database import async_session_maker
from database.models import Employee
from sqlalchemy import select
from llm.ollama_client import OllamaClient

async def fix_invalid_employee_names():
    """Find and fix all employees with invalid names."""
    llm_client = OllamaClient()
    
    async with async_session_maker() as db:
        # Get all employees
        result = await db.execute(select(Employee))
        all_employees = result.scalars().all()
        
        print(f"Checking {len(all_employees)} employees for invalid names...")
        
        invalid_employees = []
        valid_names = []
        
        # First pass: identify invalid names and collect valid ones
        for emp in all_employees:
            if not llm_client._is_valid_name(emp.name):
                invalid_employees.append(emp)
                print(f"[INVALID] Invalid name found: Employee ID {emp.id} - '{emp.name}'")
            else:
                valid_names.append(emp.name)
        
        if not invalid_employees:
            print("[OK] All employee names are valid!")
            return
        
        print(f"\nFound {len(invalid_employees)} employees with invalid names. Fixing...")
        
        # Second pass: fix invalid names
        fixed_count = 0
        for emp in invalid_employees:
            try:
                # Generate a new valid name
                new_name = await llm_client.generate_unique_employee_name(
                    existing_names=valid_names,
                    department=emp.department,
                    role=emp.role
                )
                
                # Double-check it's valid
                if llm_client._is_valid_name(new_name):
                    old_name = emp.name
                    emp.name = new_name
                    valid_names.append(new_name)
                    fixed_count += 1
                    print(f"[FIXED] Employee ID {emp.id}: '{old_name}' -> '{new_name}'")
                else:
                    print(f"[WARNING] Generated name still invalid for Employee ID {emp.id}, using fallback")
                    # Use fallback
                    new_name = await llm_client._generate_name_fallback(valid_names)
                    emp.name = new_name
                    valid_names.append(new_name)
                    fixed_count += 1
                    print(f"[FIXED] Employee ID {emp.id} (fallback): '{old_name}' -> '{new_name}'")
                    
            except Exception as e:
                print(f"[ERROR] Error fixing Employee ID {emp.id}: {e}")
                # Use fallback
                try:
                    new_name = await llm_client._generate_name_fallback(valid_names)
                    emp.name = new_name
                    valid_names.append(new_name)
                    fixed_count += 1
                    print(f"[FIXED] Employee ID {emp.id} (fallback after error): '{emp.name}' -> '{new_name}'")
                except Exception as e2:
                    print(f"[CRITICAL] Could not fix Employee ID {emp.id}: {e2}")
        
        # Commit all changes
        await db.commit()
        print(f"\n[SUCCESS] Successfully fixed {fixed_count} out of {len(invalid_employees)} invalid employee names!")
        
        # Verify all names are now valid
        result = await db.execute(select(Employee))
        all_employees = result.scalars().all()
        remaining_invalid = [emp for emp in all_employees if not llm_client._is_valid_name(emp.name)]
        
        if remaining_invalid:
            print(f"[WARNING] {len(remaining_invalid)} employees still have invalid names:")
            for emp in remaining_invalid:
                print(f"   - Employee ID {emp.id}: '{emp.name}'")
        else:
            print("[OK] Verification: All employee names are now valid!")

if __name__ == "__main__":
    asyncio.run(fix_invalid_employee_names())

