from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Weather
from sqlalchemy import select, func
from datetime import datetime, date
from config import now as local_now
import random

class WeatherManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_today_weather(self) -> Optional[Weather]:
        """Get today's weather, creating it if it doesn't exist."""
        today = local_now().date()
        
        result = await self.db.execute(
            select(Weather)
            .where(func.date(Weather.date) == today)
        )
        weather = result.scalar_one_or_none()
        
        if weather:
            return weather
        
        # Generate new weather for today
        conditions = ["sunny", "cloudy", "rainy", "stormy", "snowy"]
        condition = random.choice(conditions)
        
        # Temperature based on condition
        temps = {
            "sunny": (70, 85),
            "cloudy": (60, 75),
            "rainy": (55, 70),
            "stormy": (50, 65),
            "snowy": (25, 40)
        }
        temp_range = temps.get(condition, (60, 75))
        temperature = random.uniform(temp_range[0], temp_range[1])
        
        # Productivity modifier based on weather
        modifiers = {
            "sunny": (0.95, 1.05),  # Slightly lower (want to be outside) to slightly higher
            "cloudy": (1.0, 1.1),   # Good for productivity
            "rainy": (0.85, 0.95),  # Lower productivity
            "stormy": (0.7, 0.85),  # Much lower productivity
            "snowy": (0.8, 0.9)     # Lower productivity
        }
        mod_range = modifiers.get(condition, (0.9, 1.0))
        productivity_modifier = random.uniform(mod_range[0], mod_range[1])
        
        descriptions = {
            "sunny": "Beautiful sunny day with clear skies",
            "cloudy": "Overcast skies with mild temperatures",
            "rainy": "Light to moderate rain throughout the day",
            "stormy": "Heavy storms with thunder and lightning",
            "snowy": "Snow falling, creating a winter wonderland"
        }
        
        weather = Weather(
            condition=condition,
            temperature=temperature,
            productivity_modifier=productivity_modifier,
            description=descriptions.get(condition, "Normal weather conditions"),
            date=local_now()
        )
        self.db.add(weather)
        await self.db.commit()
        await self.db.refresh(weather)
        
        return weather
    
    async def get_productivity_modifier(self) -> float:
        """Get current productivity modifier from weather."""
        weather = await self.get_today_weather()
        if weather:
            return weather.productivity_modifier
        return 1.0  # Default no modifier




