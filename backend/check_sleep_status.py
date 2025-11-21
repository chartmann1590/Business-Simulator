"""Script to check who is currently asleep"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import async_session_maker
from business.sleep_manager import SleepManager
from sqlalchemy import select, and_
from database.models import Employee, FamilyMember, HomePet
from config import now

async def check_sleep_status():
    """Display all employees, family members, and pets who are currently asleep."""
    async with async_session_maker() as db:
        sleep_manager = SleepManager(db)
        stats = await sleep_manager.get_sleeping_stats()
        
        # Get sleeping employees
        employees_result = await db.execute(
            select(Employee).where(
                and_(
                    Employee.status == "active",
                    Employee.sleep_state == "sleeping"
                )
            ).order_by(Employee.name)
        )
        sleeping_employees = employees_result.scalars().all()
        
        # Get sleeping family members
        family_result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.sleep_state == "sleeping"
            ).order_by(FamilyMember.employee_id, FamilyMember.name)
        )
        sleeping_family = family_result.scalars().all()
        
        # Get sleeping pets
        pets_result = await db.execute(
            select(HomePet).where(
                HomePet.sleep_state == "sleeping"
            ).order_by(HomePet.employee_id, HomePet.name)
        )
        sleeping_pets = pets_result.scalars().all()
        
        # Get employee names for family and pets
        employee_ids = set()
        employee_ids.update([fm.employee_id for fm in sleeping_family])
        employee_ids.update([pet.employee_id for pet in sleeping_pets])
        
        employee_map = {}
        if employee_ids:
            emp_result = await db.execute(
                select(Employee).where(Employee.id.in_(employee_ids))
            )
            for emp in emp_result.scalars().all():
                employee_map[emp.id] = emp.name
        
        current_time = now()
        
        print(f"\n{'='*70}")
        print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"{'='*70}\n")
        
        print(f"SLEEP STATISTICS")
        print(f"   Sleeping Employees: {stats['sleeping_employees']}")
        print(f"   Awake Employees: {stats['awake_employees']}")
        print(f"   Sleeping Family Members: {stats['sleeping_family']}")
        print(f"\n{'='*70}\n")
        
        if sleeping_employees:
            print(f"SLEEPING EMPLOYEES ({len(sleeping_employees)}):")
            print(f"{'-'*70}")
            for emp in sleeping_employees:
                print(f"  • {emp.name} ({emp.title})")
                print(f"    Department: {emp.department}")
                print(f"    Activity State: {emp.activity_state}")
                
                # Show their sleeping family
                emp_family = [fm for fm in sleeping_family if fm.employee_id == emp.id]
                if emp_family:
                    print(f"    Family Members Also Sleeping:")
                    for fm in emp_family:
                        print(f"      - {fm.name} ({fm.relationship_type}, age {fm.age})")
                
                # Show their sleeping pets
                emp_pets = [pet for pet in sleeping_pets if pet.employee_id == emp.id]
                if emp_pets:
                    print(f"    Pets Also Sleeping:")
                    for pet in emp_pets:
                        print(f"      - {pet.name} ({pet.pet_type})")
                print()
        else:
            print("No employees are currently asleep.\n")
        
        # Show family members sleeping without their employee (shouldn't happen, but check)
        employees_with_family = {emp.id for emp in sleeping_employees}
        orphaned_family = [fm for fm in sleeping_family if fm.employee_id not in employees_with_family]
        if orphaned_family:
            print(f"WARNING: Family Members Sleeping (Employee Awake):")
            print(f"{'-'*70}")
            for fm in orphaned_family:
                emp_name = employee_map.get(fm.employee_id, f"Employee ID {fm.employee_id}")
                print(f"  • {fm.name} ({fm.relationship_type}, age {fm.age}) - Family of {emp_name}")
            print()
        
        # Show pets sleeping without their employee
        orphaned_pets = [pet for pet in sleeping_pets if pet.employee_id not in employees_with_family]
        if orphaned_pets:
            print(f"WARNING: Pets Sleeping (Employee Awake):")
            print(f"{'-'*70}")
            for pet in orphaned_pets:
                emp_name = employee_map.get(pet.employee_id, f"Employee ID {pet.employee_id}")
                print(f"  • {pet.name} ({pet.pet_type}) - Pet of {emp_name}")
            print()

if __name__ == "__main__":
    asyncio.run(check_sleep_status())

