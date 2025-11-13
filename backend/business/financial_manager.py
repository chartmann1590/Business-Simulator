from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Financial, Project
from sqlalchemy import select, func
from datetime import datetime, timedelta

class FinancialManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_income(self, amount: float, description: str, project_id: int = None):
        """Record income."""
        financial = Financial(
            type="income",
            amount=amount,
            description=description,
            project_id=project_id
        )
        self.db.add(financial)
        
        if project_id:
            project = await self.db.get(Project, project_id)
            if project:
                project.revenue += amount
        
        await self.db.flush()
    
    async def record_expense(self, amount: float, description: str, project_id: int = None):
        """Record expense."""
        financial = Financial(
            type="expense",
            amount=amount,
            description=description,
            project_id=project_id
        )
        self.db.add(financial)
        await self.db.flush()
    
    async def get_total_revenue(self) -> float:
        """Get total revenue."""
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(Financial.type == "income")
        )
        return result.scalar() or 0.0
    
    async def get_total_expenses(self) -> float:
        """Get total expenses."""
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(Financial.type == "expense")
        )
        return result.scalar() or 0.0
    
    async def get_profit(self) -> float:
        """Calculate profit."""
        revenue = await self.get_total_revenue()
        expenses = await self.get_total_expenses()
        return revenue - expenses
    
    async def get_revenue_for_period(self, days: int = 30) -> float:
        """Get revenue for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(
                Financial.type == "income",
                Financial.timestamp >= cutoff
            )
        )
        return result.scalar() or 0.0
    
    async def get_expenses_for_period(self, days: int = 30) -> float:
        """Get expenses for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(
                Financial.type == "expense",
                Financial.timestamp >= cutoff
            )
        )
        return result.scalar() or 0.0

