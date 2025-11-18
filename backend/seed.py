import asyncio
from database.database import init_db, async_session_maker
from database.models import Employee, Project, Financial, Activity, BusinessSettings
from business.project_manager import ProjectManager
from business.financial_manager import FinancialManager
from datetime import datetime
import random

EMPLOYEES_DATA = [
    {
        "name": "Sarah Chen",
        "title": "Chief Executive Officer",
        "role": "CEO",
        "hierarchy_level": 1,
        "department": "Executive",
        "personality_traits": ["strategic", "visionary", "decisive"],
        "backstory": "Sarah started her career as a software engineer at a major tech company. After 10 years of climbing the corporate ladder, she founded this company with a vision to revolutionize how businesses operate. She's known for her bold decisions and ability to see opportunities where others see challenges."
    },
    {
        "name": "Marcus Rodriguez",
        "title": "Chief Technology Officer",
        "role": "CTO",
        "hierarchy_level": 2,
        "department": "Engineering",
        "personality_traits": ["analytical", "innovative", "detail-oriented"],
        "backstory": "Marcus has a PhD in Computer Science and spent years at leading tech companies before joining as CTO. He's passionate about building scalable systems and mentoring engineers. His technical expertise is matched only by his ability to translate complex concepts into actionable plans."
    },
    {
        "name": "Jennifer Martinez",
        "title": "Chief Operating Officer",
        "role": "COO",
        "hierarchy_level": 2,
        "department": "Operations",
        "personality_traits": ["efficient", "organized", "results-driven"],
        "backstory": "Jennifer brings over 15 years of operations experience from Fortune 500 companies. She's known for her ability to streamline processes, improve efficiency, and ensure smooth day-to-day operations. Her systematic approach has transformed multiple organizations, making her an invaluable asset to the executive team."
    },
    {
        "name": "Robert Thompson",
        "title": "Chief Financial Officer",
        "role": "CFO",
        "hierarchy_level": 2,
        "department": "Finance",
        "personality_traits": ["analytical", "strategic", "risk-aware"],
        "backstory": "Robert is a CPA with an MBA from a top business school. He's spent his career managing finances for high-growth tech companies, helping them scale responsibly. His financial acumen and strategic thinking have been crucial in guiding companies through rapid expansion while maintaining fiscal health."
    },
    {
        "name": "Emily Watson",
        "title": "Product Manager",
        "role": "Manager",
        "hierarchy_level": 2,
        "department": "Product",
        "personality_traits": ["collaborative", "user-focused", "organized"],
        "backstory": "Emily transitioned from a UX designer to product management, bringing a unique perspective on user needs. She's known for her ability to bridge the gap between business goals and user experience. Her background in design helps her think creatively about product solutions."
    },
    {
        "name": "James Park",
        "title": "Senior Software Engineer",
        "role": "Employee",
        "hierarchy_level": 3,
        "department": "Engineering",
        "personality_traits": ["curious", "thorough", "problem-solver"],
        "backstory": "James graduated from a top engineering school and has been coding since he was 14. He's passionate about clean code and best practices. When he's not coding, he contributes to open-source projects and enjoys solving complex algorithmic challenges."
    },
    {
        "name": "Priya Sharma",
        "title": "Software Engineer",
        "role": "Employee",
        "hierarchy_level": 3,
        "department": "Engineering",
        "personality_traits": ["creative", "adaptable", "team-player"],
        "backstory": "Priya discovered programming in college and fell in love with it. She's a quick learner who isn't afraid to ask questions. Her positive attitude and willingness to help others make her a valuable team member. She's always looking for ways to improve both her skills and the codebase."
    },
    {
        "name": "David Kim",
        "title": "Software Engineer",
        "role": "Employee",
        "hierarchy_level": 3,
        "department": "Engineering",
        "personality_traits": ["methodical", "reliable", "focused"],
        "backstory": "David is a self-taught developer who worked his way up through various startups. He values stability and quality over speed. His methodical approach to problem-solving has saved the team from many potential issues. He's known for writing comprehensive tests and documentation."
    },
    {
        "name": "Alex Morgan",
        "title": "Marketing Manager",
        "role": "Manager",
        "hierarchy_level": 2,
        "department": "Marketing",
        "personality_traits": ["energetic", "persuasive", "data-driven"],
        "backstory": "Alex has a background in digital marketing and has helped multiple startups grow their customer base. They're skilled at analyzing market trends and creating campaigns that resonate with target audiences. Their creative campaigns have significantly increased brand awareness."
    }
]

async def seed_database():
    """Seed the database with initial data."""
    print("Seeding database...")
    
    # Initialize database
    await init_db()
    
    async with async_session_maker() as db:
        # Check if employees already exist
        from sqlalchemy import select
        result = await db.execute(select(Employee))
        existing_employees = result.scalars().all()
        
        if existing_employees:
            print("Database already seeded. Skipping...")
            return
        
        # Create employees
        employees = []
        hobbies_list = [
            ["reading", "hiking", "photography"],
            ["cooking", "traveling", "yoga"],
            ["gaming", "music", "movies"],
            ["sports", "fitness", "cycling"],
            ["art", "writing", "gardening"],
            ["coding", "tech", "electronics"],
            ["dancing", "music", "socializing"],
            ["reading", "chess", "puzzles"]
        ]
        
        for emp_data in EMPLOYEES_DATA:
            # Set default values for new fields if not present
            if 'avatar_path' not in emp_data:
                emp_data['avatar_path'] = None
            if 'hired_at' not in emp_data:
                emp_data['hired_at'] = datetime.utcnow()
            if 'fired_at' not in emp_data:
                emp_data['fired_at'] = None
            # Add birthday (random month and day)
            if 'birthday_month' not in emp_data:
                emp_data['birthday_month'] = random.randint(1, 12)
            if 'birthday_day' not in emp_data:
                # Handle different month lengths
                month = emp_data['birthday_month']
                if month in [1, 3, 5, 7, 8, 10, 12]:
                    max_day = 31
                elif month in [4, 6, 9, 11]:
                    max_day = 30
                else:  # February
                    max_day = 28
                emp_data['birthday_day'] = random.randint(1, max_day)
            # Add hobbies
            if 'hobbies' not in emp_data:
                emp_data['hobbies'] = random.choice(hobbies_list)
            employee = Employee(**emp_data)
            db.add(employee)
            employees.append(employee)
        
        await db.flush()
        print(f"Created {len(employees)} employees")
        
        # Create initial projects
        project_manager = ProjectManager(db)
        
        projects = [
            await project_manager.create_project(
                name="Customer Portal Redesign",
                description="Modernize the customer-facing portal with improved UX and new features",
                priority="high",
                budget=75000.0
            ),
            await project_manager.create_project(
                name="API Infrastructure Upgrade",
                description="Upgrade backend infrastructure to support increased load and new features",
                priority="high",
                budget=100000.0
            ),
            await project_manager.create_project(
                name="Mobile App Development",
                description="Develop native mobile applications for iOS and Android",
                priority="medium",
                budget=150000.0
            )
        ]
        
        await db.flush()
        print(f"Created {len(projects)} initial projects")
        
        # Create initial financial records
        financial_manager = FinancialManager(db)
        
        # Initial investment
        await financial_manager.record_income(
            500000.0,
            "Initial seed funding"
        )
        
        # Initial expenses
        await financial_manager.record_expense(
            25000.0,
            "Office setup and equipment"
        )
        await financial_manager.record_expense(
            15000.0,
            "Software licenses and tools"
        )
        
        # Assign some initial expenses to projects
        for project in projects[:2]:
            await financial_manager.record_expense(
                project.budget * 0.1,
                f"Initial setup for {project.name}",
                project.id
            )
        
        await db.flush()
        print("Created initial financial records")
        
        # Create initial activity
        activity = Activity(
            employee_id=employees[0].id,  # CEO
            activity_type="system_init",
            description="Office simulation initialized and ready to operate",
            activity_metadata={"type": "initialization"}
        )
        db.add(activity)
        
        # Set default business name
        business_name = BusinessSettings(
            setting_key="business_name",
            setting_value="TechFlow Solutions"
        )
        db.add(business_name)
        
        # Create product from business settings
        from database.models import Product, ProductTeamMember
        product = Product(
            name="Business Platform",
            description="A comprehensive business management platform",
            category="SaaS",
            status="active",
            price=0.0,
            launch_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(product)
        await db.flush()
        
        # Add key employees as team members
        for emp in employees:
            if emp.role == "CEO" or emp.title == "Product Manager" or (emp.department and "Product" in emp.department):
                tm = ProductTeamMember(
                    product_id=product.id,
                    employee_id=emp.id,
                    role="Product Manager" if "Product" in emp.title else "Executive Sponsor",
                    responsibility="Product strategy and oversight"
                )
                db.add(tm)
        
        # Link projects to product
        for project in projects:
            project.product_id = product.id
        
        await db.commit()
        print("Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())

