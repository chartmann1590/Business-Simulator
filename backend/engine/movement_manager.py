import asyncio
import logging
import traceback
from database.database import async_session_maker
from engine.movement_system import fix_walking_employees_without_destination

logger = logging.getLogger(__name__)

class MovementManager:
    """
    Dedicated manager to handle high-frequency employee movement updates.
    Runs independently of the main simulation loop to ensure smooth animation.
    """
    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):
        """Start the movement manager loop."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._movement_loop())
        logger.info("Movement Manager started")

    async def stop(self):
        """Stop the movement manager loop."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Movement Manager stopped")

    async def _movement_loop(self):
        """Main loop for processing movement."""
        logger.info("Movement Manager loop running")
        
        while self.running:
            try:
                async with async_session_maker() as db:
                    # This function handles:
                    # 1. Completing journeys for arrived employees
                    # 2. Assigning destinations to stuck walking employees
                    # 3. Moving walking employees one step forward
                    await fix_walking_employees_without_destination(db)
                    await db.commit()
            except Exception as e:
                logger.error(f"Error in Movement Manager loop: {e}")
                logger.error(traceback.format_exc())
            
            # Run frequently (every 2 seconds) to ensure smooth movement
            await asyncio.sleep(2)
