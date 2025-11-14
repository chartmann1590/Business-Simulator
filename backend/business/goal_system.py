from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BusinessMetric
from business.financial_manager import FinancialManager
from business.project_manager import ProjectManager
from sqlalchemy import select

class GoalSystem:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.financial_manager = FinancialManager(db)
        self.project_manager = ProjectManager(db)
    
    async def get_business_goals(self) -> List[str]:
        """Get current business goals."""
        return [
            "Increase monthly revenue by 15%",
            "Maintain profitability above 20%",
            "Complete 3+ projects per quarter",
            "Expand team capabilities",
            "Improve customer satisfaction"
        ]
    
    async def evaluate_goals(self) -> Dict[str, bool]:
        """Evaluate progress towards goals."""
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        
        active_projects = await self.project_manager.get_active_projects()
        completed_projects = await self._get_completed_projects_count()
        
        return {
            "revenue_growth": revenue > 0,
            "profitability": profit_margin >= 20,
            "project_completion": completed_projects >= 3,
            "team_expansion": True,  # Placeholder
            "customer_satisfaction": True  # Placeholder
        }
    
    async def _get_completed_projects_count(self) -> int:
        """Get count of completed projects."""
        from database.models import Project
        result = await self.db.execute(
            select(Project).where(Project.status == "completed")
        )
        return len(list(result.scalars().all()))
    
    async def update_metrics(self):
        """Update business metrics."""
        revenue = await self.financial_manager.get_total_revenue()
        profit = await self.financial_manager.get_profit()
        active_projects = len(await self.project_manager.get_active_projects())
        
        metrics = [
            BusinessMetric(metric_name="total_revenue", value=revenue),
            BusinessMetric(metric_name="total_profit", value=profit),
            BusinessMetric(metric_name="active_projects", value=active_projects)
        ]
        
        for metric in metrics:
            self.db.add(metric)
        
        await self.db.flush()


