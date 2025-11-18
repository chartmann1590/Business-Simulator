"""Script to link existing customer reviews to products based on their project's product_id."""
import asyncio
from database.database import init_db, async_session_maker
from database.models import CustomerReview, Project
from sqlalchemy import select

async def link_reviews_to_products():
    """Link existing customer reviews to products if their project has a product_id."""
    print("Linking customer reviews to products...")
    
    await init_db()
    
    async with async_session_maker() as db:
        # Get all reviews that don't have a product_id but have a project_id
        result = await db.execute(
            select(CustomerReview).where(
                CustomerReview.product_id == None,
                CustomerReview.project_id != None
            )
        )
        reviews = result.scalars().all()
        
        if not reviews:
            print("No reviews need to be linked.")
            return
        
        print(f"Found {len(reviews)} reviews to link...")
        
        # Get all projects with their product_ids
        result = await db.execute(select(Project))
        projects = {p.id: p.product_id for p in result.scalars().all()}
        
        linked_count = 0
        for review in reviews:
            if review.project_id and review.project_id in projects:
                product_id = projects[review.project_id]
                if product_id:
                    review.product_id = product_id
                    linked_count += 1
        
        await db.commit()
        print(f"[OK] Linked {linked_count} reviews to products")

if __name__ == "__main__":
    asyncio.run(link_reviews_to_products())

