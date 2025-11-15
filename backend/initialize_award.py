"""Simple script to initialize the performance award for existing reviews."""
import asyncio
from database.database import get_db
from business.review_manager import ReviewManager

async def initialize_award():
    """Initialize the performance award."""
    async for db in get_db():
        try:
            review_manager = ReviewManager(db)
            await review_manager._update_performance_award()
            await db.commit()
            print("[OK] Performance award initialized successfully!")
        except Exception as e:
            print(f"[ERROR] Error initializing award: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()
        break

if __name__ == "__main__":
    asyncio.run(initialize_award())

