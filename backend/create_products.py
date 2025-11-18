"""Script to create products from existing business data."""
import asyncio
from database.database import init_db, async_session_maker
from database.models import Product, Project, BusinessSettings, Employee, ProductTeamMember
from sqlalchemy import select
from datetime import datetime

async def create_products():
    """Create products from existing business settings only - no sample data."""
    print("Creating products from existing business data...")
    
    await init_db()
    
    async with async_session_maker() as db:
        # Check if products already exist
        result = await db.execute(select(Product))
        existing_products = result.scalars().all()
        
        if existing_products:
            print(f"Products already exist ({len(existing_products)} products). Skipping...")
            return
        
        # Get business settings to see if there's a product name
        result = await db.execute(select(BusinessSettings))
        settings = {s.setting_key: s.setting_value for s in result.scalars().all()}
        
        # Only create product if we have product_name in settings
        product_name = settings.get("product_name")
        if not product_name:
            print("No product_name found in business settings. Products will be created when business settings are configured.")
            return
        
        product_description = settings.get("product_description", "")
        industry = settings.get("industry", "SaaS")
        
        # Create product from business settings
        main_product = Product(
            name=product_name,
            description=product_description,
            category=industry,
            status="active",
            price=0.0,
            launch_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(main_product)
        await db.flush()
        
        print(f"Created product from business settings: {product_name}")
        
        # Get employees to assign as team members (only if they exist)
        result = await db.execute(select(Employee).where(Employee.status == "active"))
        employees = result.scalars().all()
        
        # Assign key employees to the product based on their actual roles
        team_members = []
        
        for emp in employees:
            if emp.title == "Product Manager" or (emp.department and "Product" in emp.department):
                team_members.append(ProductTeamMember(
                    product_id=main_product.id,
                    employee_id=emp.id,
                    role="Product Manager",
                    responsibility="Product strategy, roadmap, and feature prioritization"
                ))
            elif emp.title == "Chief Technology Officer" or emp.role == "CTO":
                team_members.append(ProductTeamMember(
                    product_id=main_product.id,
                    employee_id=emp.id,
                    role="Technical Lead",
                    responsibility="Technical architecture and engineering oversight"
                ))
            elif emp.role == "CEO":
                team_members.append(ProductTeamMember(
                    product_id=main_product.id,
                    employee_id=emp.id,
                    role="Executive Sponsor",
                    responsibility="Strategic direction and executive oversight"
                ))
        
        for tm in team_members:
            db.add(tm)
        
        await db.flush()
        print(f"Added {len(team_members)} team members to product")
        
        # Link existing projects to the product if they don't have a product_id
        result = await db.execute(select(Project).where(Project.product_id == None))
        projects = result.scalars().all()
        
        linked_count = 0
        for project in projects:
            project.product_id = main_product.id
            linked_count += 1
        
        await db.commit()
        print(f"Linked {linked_count} existing projects to product")
        print("✓ Product created from existing business data!")

if __name__ == "__main__":
    asyncio.run(create_products())

