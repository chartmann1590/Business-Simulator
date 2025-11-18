"""
New Game/Simulation Script

This script allows users to start a fresh simulation by:
1. Optionally backing up the existing database
2. Wiping all data from the database
3. Generating a new company with random name, product, and management team
4. Seeding the database with the new company data
"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
import json
import random

from database.database import init_db, async_session_maker, engine, Base
from database.models import (
    Employee, Project, Task, Decision, Financial, Activity, 
    BusinessMetric, Email, ChatMessage, BusinessSettings, 
    EmployeeReview, Notification, CustomerReview, Meeting, BusinessGoal
)
from business.project_manager import ProjectManager
from business.financial_manager import FinancialManager
from llm.ollama_client import OllamaClient

# Get database path
_db_path = os.path.join(os.path.dirname(__file__), "office.db")
_backup_dir = os.path.join(os.path.dirname(__file__), "backups")

def ask_user(prompt: str) -> str:
    """Ask user for input."""
    return input(prompt).strip().lower()

def create_backup() -> str:
    """Create a backup of the current database."""
    if not os.path.exists(_db_path):
        print("No existing database found. Skipping backup.")
        return None
    
    # Create backups directory if it doesn't exist
    os.makedirs(_backup_dir, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"office_backup_{timestamp}.db"
    backup_path = os.path.join(_backup_dir, backup_filename)
    
    try:
        # Copy database file
        shutil.copy2(_db_path, backup_path)
        
        # Also backup WAL and SHM files if they exist
        wal_path = _db_path + "-wal"
        shm_path = _db_path + "-shm"
        
        if os.path.exists(wal_path):
            shutil.copy2(wal_path, backup_path + "-wal")
        if os.path.exists(shm_path):
            shutil.copy2(shm_path, backup_path + "-shm")
        
        print(f"✓ Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

async def wipe_database():
    """Wipe all data from the database."""
    print("\nWiping database...")
    
    try:
        from sqlalchemy import text
        
        async with async_session_maker() as db:
            # Delete all data from all tables (in correct order to respect foreign keys)
            print("  Deleting customer reviews...")
            await db.execute(text("DELETE FROM customer_reviews"))
            
            print("  Deleting notifications...")
            await db.execute(text("DELETE FROM notifications"))
            
            print("  Deleting employee reviews...")
            await db.execute(text("DELETE FROM employee_reviews"))
            
            print("  Deleting meetings...")
            await db.execute(text("DELETE FROM meetings"))
            
            print("  Deleting chat messages...")
            await db.execute(text("DELETE FROM chat_messages"))
            
            print("  Deleting emails...")
            await db.execute(text("DELETE FROM emails"))
            
            print("  Deleting activities...")
            await db.execute(text("DELETE FROM activities"))
            
            print("  Deleting decisions...")
            await db.execute(text("DELETE FROM decisions"))
            
            print("  Deleting tasks...")
            await db.execute(text("DELETE FROM tasks"))
            
            print("  Deleting financials...")
            await db.execute(text("DELETE FROM financials"))
            
            print("  Deleting business metrics...")
            await db.execute(text("DELETE FROM business_metrics"))
            
            print("  Deleting business goals...")
            await db.execute(text("DELETE FROM business_goals"))
            
            print("  Deleting projects...")
            await db.execute(text("DELETE FROM projects"))
            
            print("  Deleting employees...")
            await db.execute(text("DELETE FROM employees"))
            
            print("  Deleting business settings...")
            await db.execute(text("DELETE FROM business_settings"))
            
            await db.commit()
            print("✓ Database wiped successfully!")
    except Exception as e:
        print(f"Error wiping database: {e}")
        import traceback
        traceback.print_exc()
        raise

async def generate_company_data(llm_client: OllamaClient) -> dict:
    """Generate new company data using LLM."""
    print("\nGenerating new company data using LLM...")
    
    prompt = """Generate a creative and realistic tech startup company. 

Provide the following information in JSON format (ONLY JSON, no other text):
{
    "company_name": "A creative, modern company name (e.g., 'NexusFlow', 'QuantumSync', 'AuroraTech', 'DataVault', 'CloudForge')",
    "product_name": "The main product or service the company offers (be specific, e.g., 'AI-powered project management platform', 'Cloud-based accounting software', 'Mobile fitness tracking app', 'Enterprise collaboration suite')",
    "product_description": "A brief 2-3 sentence description of what the product/service does and its key benefits",
    "industry": "The industry sector (e.g., 'SaaS', 'FinTech', 'HealthTech', 'EdTech', 'Enterprise Software')"
}

Requirements:
- Company name should be unique, modern, and memorable
- Product should be specific and realistic for a tech startup
- Industry should match the product type
- Make it creative but believable

Return ONLY valid JSON, nothing else."""
    
    try:
        # Try using JSON format first
        try:
            import httpx
            client = httpx.AsyncClient(timeout=60.0, verify=False)
            response = await client.post(
                f"{llm_client.base_url}/api/generate",
                json={
                    "model": llm_client.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            await client.aclose()
        except:
            # Fallback to regular generate_response
            response_text = await llm_client.generate_response(prompt)
        
        # Try to parse JSON from response
        import re
        company_data = None
        
        # First, try direct JSON parse
        try:
            if response_text.strip().startswith("{"):
                company_data = json.loads(response_text)
        except:
            pass
        
        # If that failed, try to extract JSON from markdown code blocks or text
        if not company_data:
            # Try to find JSON in code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    company_data = json.loads(json_match.group(1))
                except:
                    pass
        
        # If still no luck, try to find any JSON object
        if not company_data:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    company_data = json.loads(json_match.group())
                except:
                    pass
        
        # Validate and use fallback if needed
        if not company_data or not company_data.get("company_name"):
            print("  Warning: LLM response parsing failed, using fallback data")
            company_data = {
                "company_name": f"TechStart{random.randint(1000, 9999)}",
                "product_name": "AI-powered business management platform",
                "product_description": "A comprehensive platform that helps businesses manage their operations, projects, and teams using artificial intelligence.",
                "industry": "SaaS"
            }
        else:
            # Ensure all required fields exist
            if not company_data.get("product_name"):
                company_data["product_name"] = "Business management platform"
            if not company_data.get("product_description"):
                company_data["product_description"] = f"A comprehensive solution for {company_data.get('industry', 'business')} needs."
            if not company_data.get("industry"):
                company_data["industry"] = "SaaS"
        
        print(f"  ✓ Company: {company_data.get('company_name', 'Unknown')}")
        print(f"  ✓ Product: {company_data.get('product_name', 'Unknown')}")
        print(f"  ✓ Industry: {company_data.get('industry', 'Unknown')}")
        
        return company_data
    except Exception as e:
        print(f"  Error generating company data: {e}")
        print("  Using fallback company data...")
        # Fallback
        return {
            "company_name": f"TechStart{random.randint(1000, 9999)}",
            "product_name": "AI-powered business management platform",
            "product_description": "A comprehensive platform that helps businesses manage their operations, projects, and teams using artificial intelligence.",
            "industry": "SaaS"
        }

async def generate_management_team(llm_client: OllamaClient, company_name: str, product_name: str) -> list:
    """Generate management team members using LLM."""
    print("\nGenerating management team...")
    
    # First, generate CEO
    ceo_prompt = f"""Generate a CEO for {company_name}, a company that offers {product_name}.

Provide in JSON format:
{{
    "name": "Full name (first and last",
    "title": "Chief Executive Officer",
    "personality_traits": ["trait1", "trait2", "trait3"],
    "backstory": "A 2-3 sentence backstory about their career and how they came to found/lead this company"
}}

Make it realistic and compelling."""
    
    # Generate C-level executives
    exec_roles = [
        ("CTO", "Chief Technology Officer", "Engineering"),
        ("COO", "Chief Operating Officer", "Operations"),
        ("CFO", "Chief Financial Officer", "Finance")
    ]
    
    employees_data = []
    
    try:
        # Generate CEO with better JSON parsing
        ceo_response = await llm_client.generate_response(ceo_prompt)
        import re
        ceo_data = None
        
        # Try to parse JSON
        try:
            if ceo_response.strip().startswith("{"):
                ceo_data = json.loads(ceo_response)
        except:
            pass
        
        if not ceo_data:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ceo_response, re.DOTALL)
            if json_match:
                try:
                    ceo_data = json.loads(json_match.group())
                except:
                    pass
        
        if ceo_data and ceo_data.get("name"):
            ceo_data["role"] = "CEO"
            ceo_data["hierarchy_level"] = 1
            ceo_data["department"] = "Executive"
            if "personality_traits" not in ceo_data or not ceo_data["personality_traits"]:
                ceo_data["personality_traits"] = ["strategic", "visionary", "decisive"]
            if "backstory" not in ceo_data or not ceo_data["backstory"]:
                ceo_data["backstory"] = f"Founded {company_name} with a vision to revolutionize the industry through innovative technology solutions."
            employees_data.append(ceo_data)
            print(f"  Generated CEO: {ceo_data.get('name', 'Unknown')}")
        else:
            # Fallback CEO
            employees_data.append({
                "name": f"{random.choice(['Sarah', 'Alex', 'Jordan', 'Taylor'])} {random.choice(['Chen', 'Rodriguez', 'Martinez', 'Thompson'])}",
                "title": "Chief Executive Officer",
                "role": "CEO",
                "hierarchy_level": 1,
                "department": "Executive",
                "personality_traits": ["strategic", "visionary", "decisive"],
                "backstory": f"Founded {company_name} with a vision to revolutionize the industry through innovative technology solutions."
            })
            print(f"  Generated CEO: {employees_data[-1]['name']} (fallback)")
        
        # Generate C-level executives
        for role, title, dept in exec_roles:
            exec_prompt = f"""Generate a {title} for {company_name}, a company that offers {product_name}.

Provide in JSON format (ONLY JSON, no other text):
{{
    "name": "Full name (first and last)",
    "title": "{title}",
    "personality_traits": ["trait1", "trait2", "trait3"],
    "backstory": "A 2-3 sentence backstory about their career and expertise"
}}

Make it realistic and professional. Return ONLY valid JSON."""
            
            exec_response = await llm_client.generate_response(exec_prompt)
            exec_data = None
            
            # Try to parse JSON
            try:
                if exec_response.strip().startswith("{"):
                    exec_data = json.loads(exec_response)
            except:
                pass
            
            if not exec_data:
                exec_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', exec_response, re.DOTALL)
                if exec_match:
                    try:
                        exec_data = json.loads(exec_match.group())
                    except:
                        pass
            
            if exec_data and exec_data.get("name"):
                exec_data["role"] = role
                exec_data["hierarchy_level"] = 2
                exec_data["department"] = dept
                if "personality_traits" not in exec_data or not exec_data["personality_traits"]:
                    exec_data["personality_traits"] = ["analytical", "strategic", "results-driven"]
                if "backstory" not in exec_data or not exec_data["backstory"]:
                    exec_data["backstory"] = f"Brings extensive experience in {dept.lower()} to {company_name}."
                employees_data.append(exec_data)
                print(f"  Generated {role}: {exec_data.get('name', 'Unknown')}")
            else:
                # Fallback
                employees_data.append({
                    "name": f"{random.choice(['Marcus', 'Jennifer', 'Robert', 'Emily'])} {random.choice(['Rodriguez', 'Martinez', 'Thompson', 'Watson'])}",
                    "title": title,
                    "role": role,
                    "hierarchy_level": 2,
                    "department": dept,
                    "personality_traits": ["analytical", "strategic", "results-driven"],
                    "backstory": f"Brings extensive experience in {dept.lower()} to {company_name}."
                })
                print(f"  Generated {role}: {employees_data[-1]['name']} (fallback)")
        
        # Generate managers (Product, Marketing, Engineering Manager)
        manager_roles = [
            ("Manager", "Product Manager", "Product"),
            ("Manager", "Marketing Manager", "Marketing"),
            ("Manager", "Engineering Manager", "Engineering")
        ]
        
        for role, title, dept in manager_roles:
            manager_prompt = f"""Generate a {title} for {company_name}.

Provide in JSON format (ONLY JSON, no other text):
{{
    "name": "Full name (first and last)",
    "title": "{title}",
    "personality_traits": ["trait1", "trait2", "trait3"],
    "backstory": "A 2-3 sentence backstory about their career"
}}

Make it realistic. Return ONLY valid JSON."""
            
            manager_response = await llm_client.generate_response(manager_prompt)
            manager_data = None
            
            # Try to parse JSON
            try:
                if manager_response.strip().startswith("{"):
                    manager_data = json.loads(manager_response)
            except:
                pass
            
            if not manager_data:
                manager_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', manager_response, re.DOTALL)
                if manager_match:
                    try:
                        manager_data = json.loads(manager_match.group())
                    except:
                        pass
            
            if manager_data and manager_data.get("name"):
                manager_data["role"] = "Manager"
                manager_data["hierarchy_level"] = 2
                manager_data["department"] = dept
                if "personality_traits" not in manager_data or not manager_data["personality_traits"]:
                    manager_data["personality_traits"] = ["collaborative", "organized", "results-driven"]
                if "backstory" not in manager_data or not manager_data["backstory"]:
                    manager_data["backstory"] = f"Experienced {title.lower()} with a track record of success."
                employees_data.append(manager_data)
                print(f"  Generated {title}: {manager_data.get('name', 'Unknown')}")
            else:
                # Fallback
                employees_data.append({
                    "name": f"{random.choice(['James', 'Priya', 'David', 'Alex'])} {random.choice(['Park', 'Sharma', 'Kim', 'Morgan'])}",
                    "title": title,
                    "role": "Manager",
                    "hierarchy_level": 2,
                    "department": dept,
                    "personality_traits": ["collaborative", "organized", "results-driven"],
                    "backstory": f"Experienced {title.lower()} with a track record of success."
                })
                print(f"  Generated {title}: {employees_data[-1]['name']} (fallback)")
        
        # Generate some initial employees
        employee_titles = [
            ("Employee", "Senior Software Engineer", "Engineering"),
            ("Employee", "Software Engineer", "Engineering"),
            ("Employee", "Software Engineer", "Engineering"),
        ]
        
        # Get existing names from already generated employees (managers, executives)
        existing_names = [emp.get("name") for emp in employees_data if emp.get("name")]
        
        personality_pools = [
            ["curious", "thorough", "problem-solver"],
            ["creative", "adaptable", "team-player"],
            ["methodical", "reliable", "focused"]
        ]
        
        # Generate unique names for regular employees using AI
        for role, title, dept in employee_titles:
            # Generate unique name using AI
            name = await llm_client.generate_unique_employee_name(
                existing_names=existing_names,
                department=dept,
                role=role
            )
            existing_names.append(name)  # Add to existing names to avoid duplicates in next iteration
            
            employees_data.append({
                "name": name,
                "title": title,
                "role": "Employee",
                "hierarchy_level": 3,
                "department": dept,
                "personality_traits": random.choice(personality_pools),
                "backstory": f"Passionate {title.lower()} who joined {company_name} to help build innovative solutions."
            })
        
        print(f"✓ Generated {len(employees_data)} team members")
        return employees_data
        
    except Exception as e:
        print(f"Error generating management team: {e}")
        import traceback
        traceback.print_exc()
        # Return fallback team
        return [
            {
                "name": "Sarah Chen",
                "title": "Chief Executive Officer",
                "role": "CEO",
                "hierarchy_level": 1,
                "department": "Executive",
                "personality_traits": ["strategic", "visionary", "decisive"],
                "backstory": f"Founded {company_name} with a vision to revolutionize the industry."
            },
            {
                "name": "Marcus Rodriguez",
                "title": "Chief Technology Officer",
                "role": "CTO",
                "hierarchy_level": 2,
                "department": "Engineering",
                "personality_traits": ["analytical", "innovative", "detail-oriented"],
                "backstory": "Experienced technology leader with a passion for building scalable systems."
            },
            {
                "name": "Jennifer Martinez",
                "title": "Chief Operating Officer",
                "role": "COO",
                "hierarchy_level": 2,
                "department": "Operations",
                "personality_traits": ["efficient", "organized", "results-driven"],
                "backstory": "Operations expert with a track record of streamlining processes."
            },
            {
                "name": "Robert Thompson",
                "title": "Chief Financial Officer",
                "role": "CFO",
                "hierarchy_level": 2,
                "department": "Finance",
                "personality_traits": ["analytical", "strategic", "risk-aware"],
                "backstory": "Financial strategist with experience managing high-growth companies."
            }
        ]

async def seed_new_company(company_data: dict, employees_data: list):
    """Seed the database with new company data."""
    print("\nSeeding new company data...")
    
    await init_db()
    
    async with async_session_maker() as db:
        # Create employees
        employees = []
        hobbies_list = [
            ["photography", "hiking", "cooking"],
            ["reading", "yoga", "gardening"],
            ["gaming", "music", "traveling"],
            ["sports", "writing", "painting"],
            ["reading", "chess", "puzzles"]
        ]
        for emp_data in employees_data:
            # Assign random birthday if not provided
            if 'birthday_month' not in emp_data:
                birthday_month = random.randint(1, 12)
            else:
                birthday_month = emp_data['birthday_month']
            
            if 'birthday_day' not in emp_data:
                if birthday_month in [1, 3, 5, 7, 8, 10, 12]:
                    max_day = 31
                elif birthday_month in [4, 6, 9, 11]:
                    max_day = 30
                else:  # February
                    max_day = 28
                birthday_day = random.randint(1, max_day)
            else:
                birthday_day = emp_data['birthday_day']
            
            # Assign random hobbies if not provided
            if 'hobbies' not in emp_data:
                hobbies = random.choice(hobbies_list)
            else:
                hobbies = emp_data['hobbies']
            
            employee = Employee(
                name=emp_data["name"],
                title=emp_data["title"],
                role=emp_data["role"],
                hierarchy_level=emp_data["hierarchy_level"],
                department=emp_data.get("department", "Operations"),
                personality_traits=emp_data.get("personality_traits", []),
                backstory=emp_data.get("backstory", ""),
                avatar_path=None,
                hired_at=datetime.utcnow(),
                fired_at=None,
                status="active",
                birthday_month=birthday_month,
                birthday_day=birthday_day,
                hobbies=hobbies
            )
            db.add(employee)
            employees.append(employee)
        
        await db.flush()
        print(f"  Created {len(employees)} employees")
        
        # Create initial projects related to the product
        project_manager = ProjectManager(db)
        
        product_name = company_data.get("product_name", "Business Platform")
        product_desc = company_data.get("product_description", "")
        
        projects = [
            await project_manager.create_project(
                name=f"{product_name} - Core Development",
                description=f"Develop the core features and functionality for {product_name}. {product_desc}",
                priority="high",
                budget=100000.0
            ),
            await project_manager.create_project(
                name=f"{product_name} - User Interface",
                description=f"Design and implement the user interface for {product_name}",
                priority="high",
                budget=75000.0
            ),
            await project_manager.create_project(
                name=f"{product_name} - Infrastructure Setup",
                description=f"Set up cloud infrastructure and deployment pipeline for {product_name}",
                priority="medium",
                budget=50000.0
            )
        ]
        
        await db.flush()
        print(f"  Created {len(projects)} initial projects")
        
        # Create initial financial records
        financial_manager = FinancialManager(db)
        
        # Initial seed funding
        await financial_manager.record_income(
            500000.0,
            "Initial seed funding"
        )
        
        # Initial expenses
        await financial_manager.record_expense(
            30000.0,
            "Office setup and equipment"
        )
        await financial_manager.record_expense(
            20000.0,
            "Software licenses and development tools"
        )
        
        # Assign some initial expenses to projects
        for project in projects[:2]:
            await financial_manager.record_expense(
                project.budget * 0.1,
                f"Initial setup for {project.name}",
                project.id
            )
        
        await db.flush()
        print("  Created initial financial records")
        
        # Create initial activity
        activity = Activity(
            employee_id=employees[0].id,  # CEO
            activity_type="system_init",
            description=f"{company_data.get('company_name', 'Company')} simulation initialized and ready to operate",
            activity_metadata={"type": "initialization", "company": company_data.get('company_name')}
        )
        db.add(activity)
        
        # Set business name and product info
        business_name = BusinessSettings(
            setting_key="business_name",
            setting_value=company_data.get("company_name", "New Company")
        )
        db.add(business_name)
        
        product_setting = BusinessSettings(
            setting_key="product_name",
            setting_value=company_data.get("product_name", "Product")
        )
        db.add(product_setting)
        
        product_desc_setting = BusinessSettings(
            setting_key="product_description",
            setting_value=company_data.get("product_description", "")
        )
        db.add(product_desc_setting)
        
        industry_setting = BusinessSettings(
            setting_key="industry",
            setting_value=company_data.get("industry", "Tech")
        )
        db.add(industry_setting)
        
        await db.commit()
        print("✓ Database seeded successfully!")

async def main():
    """Main function to run the new game script."""
    print("=" * 60)
    print("NEW GAME / SIMULATION SETUP")
    print("=" * 60)
    print("\nThis will:")
    print("  1. Optionally backup your current database")
    print("  2. Wipe all existing data")
    print("  3. Generate a new company with random name, product, and team")
    print("  4. Seed the database with the new company")
    print()
    
    # Ask about backup
    backup_choice = ask_user("Do you want to backup your current database? (yes/no): ")
    backup_path = None
    
    if backup_choice in ['yes', 'y']:
        backup_path = create_backup()
        if not backup_path:
            confirm = ask_user("\nBackup failed. Continue anyway? (yes/no): ")
            if confirm not in ['yes', 'y']:
                print("Cancelled.")
                return
    else:
        confirm = ask_user("\nNo backup will be created. Continue? (yes/no): ")
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return
    
    # Initialize LLM client
    print("\nInitializing LLM client...")
    llm_client = OllamaClient()
    
    try:
        # Generate company data
        company_data = await generate_company_data(llm_client)
        
        # Generate management team
        employees_data = await generate_management_team(
            llm_client, 
            company_data.get("company_name", "Company"),
            company_data.get("product_name", "Product")
        )
        
        # Wipe database
        await wipe_database()
        
        # Seed new company
        await seed_new_company(company_data, employees_data)
        
        print("\n" + "=" * 60)
        print("NEW GAME SETUP COMPLETE!")
        print("=" * 60)
        print(f"\nCompany: {company_data.get('company_name', 'Unknown')}")
        print(f"Product: {company_data.get('product_name', 'Unknown')}")
        print(f"Team Size: {len(employees_data)} employees")
        if backup_path:
            print(f"\nBackup saved to: {backup_path}")
        print("\nYou can now start the simulation with: python main.py")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during setup: {e}")
        import traceback
        traceback.print_exc()
        if backup_path:
            print(f"\nYour backup is available at: {backup_path}")
    finally:
        await llm_client.close()

if __name__ == "__main__":
    asyncio.run(main())

