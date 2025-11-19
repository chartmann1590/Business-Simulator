"""Script to create products from real projects that have customer reviews."""
import asyncio
from database.database import init_db, async_session_maker
from database.models import Product, Project, CustomerReview, ProductTeamMember, Employee
from sqlalchemy import select, func, distinct

async def create_real_products():
    """Create products from projects that have customer reviews."""
    print("Creating products from real projects with reviews...")
    
    await init_db()
    
    async with async_session_maker() as db:
        # Get all projects that have customer reviews
        result = await db.execute(
            select(Project.id, Project.name, Project.description, func.count(CustomerReview.id).label('review_count'))
            .join(CustomerReview, Project.id == CustomerReview.project_id, isouter=True)
            .group_by(Project.id, Project.name, Project.description)
            .having(func.count(CustomerReview.id) > 0)
        )
        projects_with_reviews = result.all()
        
        if not projects_with_reviews:
            print("No projects with reviews found.")
            return
        
        print(f"Found {len(projects_with_reviews)} projects with reviews:")
        for proj in projects_with_reviews:
            print(f"  - {proj.name} ({proj.review_count} reviews)")
        
        # Delete all existing products (the fake ones)
        result = await db.execute(select(Product))
        existing_products = result.scalars().all()
        if existing_products:
            print(f"\nDeleting {len(existing_products)} existing products...")
            for product in existing_products:
                await db.delete(product)
            await db.commit()
            print("Deleted existing products")
        
        # Create products from project names
        product_map = {}  # project_id -> product_id
        created_products = []
        
        for proj in projects_with_reviews:
            # Check if a product with this name already exists (in case of duplicates)
            existing_product = None
            for created in created_products:
                if created.name == proj.name:
                    existing_product = created
                    break
            
            if existing_product:
                product_map[proj.id] = existing_product.id
                print(f"Using existing product '{proj.name}' for project {proj.id}")
            else:
                # Create new product
                product = Product(
                    name=proj.name,
                    description=proj.description or f"Product based on {proj.name} project",
                    category="Service",
                    status="active",
                    price=0.0
                )
                db.add(product)
                await db.flush()  # Get the ID
                product_map[proj.id] = product.id
                created_products.append(product)
                print(f"Created product '{product.name}' (ID: {product.id})")
        
        await db.commit()
        print(f"\nCreated {len(created_products)} products")
        
        # Link projects to products
        print("\nLinking projects to products...")
        result = await db.execute(select(Project))
        all_projects = result.scalars().all()
        
        linked_count = 0
        for project in all_projects:
            if project.id in product_map:
                project.product_id = product_map[project.id]
                linked_count += 1
        
        await db.commit()
        print(f"Linked {linked_count} projects to products")
        
        # Link customer reviews to products
        print("\nLinking customer reviews to products...")
        result = await db.execute(select(CustomerReview))
        all_reviews = result.scalars().all()
        
        linked_reviews = 0
        for review in all_reviews:
            if review.project_id and review.project_id in product_map:
                review.product_id = product_map[review.project_id]
                linked_reviews += 1
        
        await db.commit()
        print(f"Linked {linked_reviews} reviews to products")
        
        # Assign team members to products (employees who work on projects for this product)
        print("\nAssigning team members to products...")
        result = await db.execute(select(Employee))
        all_employees = result.scalars().all()
        
        # Get projects grouped by product
        result = await db.execute(select(Project))
        projects_by_product = {}
        for project in result.scalars().all():
            if project.product_id:
                if project.product_id not in projects_by_product:
                    projects_by_product[project.product_id] = []
                projects_by_product[project.product_id].append(project.id)
        
        # For each product, find employees who work on its projects
        from database.models import Task
        team_members_added = 0
        
        for product_id, project_ids in projects_by_product.items():
            # Get employees who have tasks in these projects
            result = await db.execute(
                select(distinct(Task.employee_id))
                .where(Task.project_id.in_(project_ids))
                .where(Task.employee_id != None)
            )
            employee_ids = [eid for eid in result.scalars().all() if eid]
            
            # Also check employees by role/title
            for employee in all_employees:
                if employee.id in employee_ids:
                    # Check if already added
                    existing = await db.execute(
                        select(ProductTeamMember).where(
                            ProductTeamMember.product_id == product_id,
                            ProductTeamMember.employee_id == employee.id
                        )
                    )
                    if not existing.scalar_one_or_none():
                        role = "Team Member"
                        if "manager" in employee.title.lower() or "director" in employee.title.lower():
                            role = "Project Manager"
                        elif "cto" in employee.title.lower() or "ceo" in employee.title.lower():
                            role = "Executive"
                        elif "developer" in employee.title.lower() or "engineer" in employee.title.lower():
                            role = "Developer"
                        
                        team_member = ProductTeamMember(
                            product_id=product_id,
                            employee_id=employee.id,
                            role=role
                        )
                        db.add(team_member)
                        team_members_added += 1
        
        await db.commit()
        print(f"Added {team_members_added} team members to products")
        
        print("\n[OK] Done! Products created from real projects with reviews.")

if __name__ == "__main__":
    asyncio.run(create_real_products())




