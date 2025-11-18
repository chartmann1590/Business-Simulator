"""
Customer Review Manager - Handles AI-generated customer reviews for completed projects/products.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from database.models import Project, CustomerReview
from datetime import datetime, timedelta
import random
from typing import Optional, List
from llm.ollama_client import OllamaClient


class CustomerReviewManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_reviews_for_completed_projects(self, hours_since_completion: float = 24.0):
        """
        Generate customer reviews for completed projects that don't have reviews yet.
        Reviews are generated 24 hours after project completion by default.
        """
        now = datetime.utcnow()
        cutoff_date = now - timedelta(hours=hours_since_completion)
        
        # Get all completed projects
        result = await self.db.execute(
            select(Project).where(Project.status == "completed")
        )
        completed_projects = result.scalars().all()
        
        if not completed_projects:
            print("ℹ️  No completed projects found")
            return []
        
        reviews_created = []
        
        for project in completed_projects:
            # If hours_since_completion is 0, generate for all completed projects (initial generation)
            # Otherwise, check if project was completed long enough ago
            if hours_since_completion > 0:
                if not project.completed_at:
                    continue
                
                completed_at = project.completed_at.replace(tzinfo=None) if project.completed_at.tzinfo else project.completed_at
                hours_since = (now - completed_at).total_seconds() / 3600
                
                if hours_since < hours_since_completion:
                    continue
            
            # Check if project already has reviews
            result = await self.db.execute(
                select(CustomerReview).where(CustomerReview.project_id == project.id)
            )
            existing_reviews = result.scalars().all()
            num_existing = len(existing_reviews)
            
            # Determine how many reviews to generate
            # - If project has no reviews, generate 2-5 initial reviews
            # - If project has reviews but less than 10, generate 1-2 additional reviews periodically
            # - If project has 10+ reviews, skip (reasonable cap)
            if num_existing == 0:
                num_reviews_to_generate = random.randint(2, 5)
            elif num_existing < 10:
                # Generate 1-2 additional reviews for projects that already have some
                num_reviews_to_generate = random.randint(1, 2)
            else:
                # Project already has enough reviews (10+)
                continue
            
            print(f"📝 Generating {num_reviews_to_generate} customer review(s) for project: {project.name}")
            
            for _ in range(num_reviews_to_generate):
                try:
                    review = await self._generate_customer_review(project)
                    if review:
                        reviews_created.append(review)
                        print(f"  ✅ Created review from {review.customer_name}")
                except Exception as e:
                    import traceback
                    print(f"  ❌ Error generating review: {e}")
                    print(f"  Traceback: {traceback.format_exc()}")
        
        if reviews_created:
            try:
                await self.db.flush()
                await self.db.commit()
                print(f"✅ Committed {len(reviews_created)} customer review(s) to database")
                
                # Sync products from reviews after creating reviews
                await self._sync_products_from_reviews()
            except Exception as e:
                import traceback
                print(f"❌ Error committing reviews: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                await self.db.rollback()
        
        return reviews_created
    
    async def _sync_products_from_reviews(self):
        """Sync products from reviews after generating new reviews."""
        try:
            from database.models import Product
            
            # Find all unique projects that have reviews
            result = await self.db.execute(
                select(Project)
                .join(CustomerReview, CustomerReview.project_id == Project.id)
                .where(CustomerReview.project_id.isnot(None))
                .distinct()
            )
            projects_with_reviews = result.scalars().all()
            
            if not projects_with_reviews:
                return
            
            products_created = 0
            products_updated = 0
            
            for project in projects_with_reviews:
                if not project:
                    continue
                
                # Check if product already exists for this project
                existing_product = None
                if project.product_id:
                    result = await self.db.execute(select(Product).where(Product.id == project.product_id))
                    existing_product = result.scalar_one_or_none()
                
                # If no product linked, check if a product with the same name exists
                if not existing_product:
                    result = await self.db.execute(select(Product).where(Product.name == project.name))
                    existing_product = result.scalar_one_or_none()
                
                if existing_product:
                    # Product exists, ensure project and reviews are linked
                    if project.product_id != existing_product.id:
                        project.product_id = existing_product.id
                        products_updated += 1
                    
                    # Update reviews to link to this product
                    result = await self.db.execute(
                        select(CustomerReview).where(
                            CustomerReview.project_id == project.id,
                            CustomerReview.product_id.is_(None)
                        )
                    )
                    unlinked_reviews = result.scalars().all()
                    for review in unlinked_reviews:
                        review.product_id = existing_product.id
                        products_updated += 1
                else:
                    # Create new product from project
                    new_product = Product(
                        name=project.name,
                        description=project.description or f"Product based on {project.name} project",
                        category="Service",
                        status="active" if project.status == "completed" else "development",
                        price=0.0,
                        launch_date=project.completed_at if project.completed_at else project.created_at,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    self.db.add(new_product)
                    await self.db.flush()  # Get the ID
                    
                    # Link project to product
                    project.product_id = new_product.id
                    
                    # Link all reviews for this project to the product
                    result = await self.db.execute(
                        select(CustomerReview).where(CustomerReview.project_id == project.id)
                    )
                    reviews = result.scalars().all()
                    for review in reviews:
                        review.product_id = new_product.id
                    
                    products_created += 1
            
            if products_created > 0 or products_updated > 0:
                await self.db.commit()
                print(f"✅ Auto-synced products from reviews: {products_created} created, {products_updated} updated")
        except Exception as e:
            print(f"⚠️  Error auto-syncing products from reviews: {e}")
            # Don't raise - this is a background sync, shouldn't fail the review generation
    
    async def _generate_customer_review(self, project: Project) -> Optional[CustomerReview]:
        """
        Generate a realistic customer review for a completed project/product.
        """
        # Generate customer information
        customer_name, customer_title, company_name = self._generate_customer_info()
        
        # Generate rating (weighted towards positive but realistic distribution)
        # 60% chance of 4-5 stars, 30% chance of 3-4 stars, 10% chance of 1-3 stars
        rand = random.random()
        if rand < 0.6:
            rating = round(random.uniform(4.0, 5.0), 1)
        elif rand < 0.9:
            rating = round(random.uniform(3.0, 4.0), 1)
        else:
            rating = round(random.uniform(1.0, 3.0), 1)
        
        # Generate review text using Ollama
        review_text = await self._generate_review_text_with_ollama(
            project, customer_name, customer_title, company_name, rating
        )
        
        # Create review - link to product if project has a product_id
        review = CustomerReview(
            project_id=project.id,
            product_id=project.product_id if hasattr(project, 'product_id') and project.product_id else None,
            customer_name=customer_name,
            customer_title=customer_title,
            company_name=company_name,
            rating=rating,
            review_text=review_text,
            verified_purchase=True,
            helpful_count=random.randint(0, 15)  # Random helpful votes
        )
        
        self.db.add(review)
        return review
    
    def _generate_customer_info(self) -> tuple:
        """
        Generate realistic customer name, title, and company name.
        """
        first_names = [
            "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Amanda", "Robert",
            "Jennifer", "William", "Lisa", "Richard", "Michelle", "Joseph", "Ashley",
            "Thomas", "Melissa", "Christopher", "Nicole", "Daniel", "Stephanie", "Matthew",
            "Rebecca", "Anthony", "Laura", "Mark", "Kimberly", "Donald", "Amy", "Steven",
            "Angela", "Paul", "Sharon", "Andrew", "Cynthia", "Joshua", "Kathleen", "Kenneth",
            "Samantha", "Kevin", "Deborah", "Brian", "Rachel", "George", "Carolyn", "Edward",
            "Janet", "Ronald", "Catherine", "Timothy", "Maria", "Jason", "Frances", "Jeffrey",
            "Christine", "Ryan", "Sandra", "Jacob", "Donna", "Gary", "Emily", "Nicholas"
        ]
        
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
            "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
            "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen",
            "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
            "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter",
            "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz"
        ]
        
        titles = [
            "CEO", "CTO", "CFO", "VP of Engineering", "VP of Sales", "VP of Marketing",
            "Director of Operations", "Director of Product", "Product Manager", "Engineering Manager",
            "Sales Manager", "Marketing Manager", "Operations Manager", "IT Director",
            "Business Development Manager", "Project Manager", "Senior Engineer", "Lead Developer"
        ]
        
        company_types = [
            "Tech", "Solutions", "Systems", "Innovations", "Digital", "Global", "Enterprise",
            "Services", "Group", "Corp", "Industries", "Ventures", "Partners", "Labs"
        ]
        
        company_names = [
            "Acme", "Vertex", "Nexus", "Apex", "Summit", "Pinnacle", "Catalyst", "Momentum",
            "Synergy", "Horizon", "Velocity", "Quantum", "Phoenix", "Titan", "Aurora", "Nova"
        ]
        
        customer_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        customer_title = random.choice(titles)
        company_name = f"{random.choice(company_names)} {random.choice(company_types)}"
        
        return customer_name, customer_title, company_name
    
    async def _generate_review_text_with_ollama(
        self, project: Project, customer_name: str, customer_title: str, 
        company_name: str, rating: float
    ) -> str:
        """
        Generate realistic customer review text using Ollama.
        """
        # Determine sentiment based on rating
        if rating >= 4.5:
            sentiment = "very positive"
        elif rating >= 4.0:
            sentiment = "positive"
        elif rating >= 3.0:
            sentiment = "mixed"
        elif rating >= 2.0:
            sentiment = "negative"
        else:
            sentiment = "very negative"
        
        # Build prompt
        prompt = f"""You are {customer_name}, {customer_title} at {company_name}. You are writing a customer review for a product/service you recently purchased and used.

Product/Service Name: {project.name}
Product/Service Description: {project.description or "A business product/service"}

Your rating: {rating}/5.0 stars
Sentiment: {sentiment}

Write a realistic customer review (2-4 sentences) that:
1. Feels authentic and natural, like a real customer wrote it
2. Mentions specific aspects of the product/service (be creative but realistic)
3. Matches the rating - if rating is high, be positive; if low, mention issues constructively
4. Includes personal experience or use case
5. Is conversational and genuine (not overly formal)
6. May include minor details like "I've been using it for a few weeks" or "Our team implemented this"

Examples of good reviews:
- "We've been using this for about 3 months now and it's been a game-changer for our workflow. The interface is intuitive and the support team is responsive. Highly recommend!"
- "Solid product overall. Does what it says on the tin, though I wish there were more customization options. Good value for the price."
- "Had some issues with the initial setup, but once we got it running, it's been working well. Customer support was helpful in resolving our questions."

Write only the review text, nothing else. Make it feel like a real customer review from {customer_name}."""

        try:
            llm_client = OllamaClient()
            response_text = await llm_client.generate_response(prompt)
            
            # Clean up the response
            review_text = response_text.strip()
            
            # Remove quotes if present
            if review_text.startswith('"') and review_text.endswith('"'):
                review_text = review_text[1:-1]
            if review_text.startswith("'") and review_text.endswith("'"):
                review_text = review_text[1:-1]
            
            # Ensure we have content
            if not review_text or len(review_text) < 20:
                # Fallback review
                if rating >= 4.0:
                    review_text = f"Great product! We've been using {project.name} for a while now and it's been very helpful for our business. Would definitely recommend to others."
                elif rating >= 3.0:
                    review_text = f"{project.name} is a solid solution. It does what we need, though there's room for some improvements. Overall satisfied with the purchase."
                else:
                    review_text = f"We had some challenges with {project.name}. While it has potential, we encountered some issues during implementation. Hoping for improvements in future updates."
            
            return review_text
            
        except Exception as e:
            print(f"  ⚠️  Error generating review text with Ollama: {e}")
            # Fallback review based on rating
            if rating >= 4.0:
                return f"Excellent product! {project.name} has been a great addition to our workflow. Highly recommend it to other businesses looking for a reliable solution."
            elif rating >= 3.0:
                return f"{project.name} is a decent product that meets our basic needs. It works as expected, though there are some areas that could be improved."
            else:
                return f"We had some issues with {project.name}. While it has some good features, we encountered difficulties that affected our experience. Hoping for better support and updates."
    
    async def get_reviews_for_project(self, project_id: int) -> List[CustomerReview]:
        """
        Get all reviews for a specific project.
        """
        result = await self.db.execute(
            select(CustomerReview)
            .where(CustomerReview.project_id == project_id)
            .order_by(desc(CustomerReview.created_at))
        )
        return result.scalars().all()
    
    async def get_all_reviews(self, limit: int = 1000) -> List[CustomerReview]:
        """
        Get all customer reviews, ordered by most recent.
        """
        result = await self.db.execute(
            select(CustomerReview)
            .order_by(desc(CustomerReview.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_average_rating_for_project(self, project_id: int) -> Optional[float]:
        """
        Get the average rating for a specific project.
        """
        result = await self.db.execute(
            select(func.avg(CustomerReview.rating))
            .where(CustomerReview.project_id == project_id)
        )
        avg_rating = result.scalar_one_or_none()
        return round(avg_rating[0], 1) if avg_rating and avg_rating[0] else None

