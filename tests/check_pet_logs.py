import asyncio
import aiosqlite
import os
from datetime import datetime

async def check_logs():
    db_path = os.path.join(os.path.dirname(__file__), "backend", "office.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    print(f"Checking logs in {db_path}...")
    
    async with aiosqlite.connect(db_path) as db:
        # Check if table exists
        try:
            cursor = await db.execute("SELECT count(*) FROM pet_care_logs")
            count = await cursor.fetchone()
            print(f"Total pet care logs: {count[0]}")
            
            if count[0] > 0:
                print("\nMost recent 5 logs:")
                cursor = await db.execute("""
                    SELECT 
                        l.created_at, 
                        p.name as pet_name, 
                        e.name as employee_name, 
                        l.care_action, 
                        l.ai_reasoning
                    FROM pet_care_logs l
                    JOIN office_pets p ON l.pet_id = p.id
                    JOIN employees e ON l.employee_id = e.id
                    ORDER BY l.created_at DESC
                    LIMIT 5
                """)
                rows = await cursor.fetchall()
                for row in rows:
                    print(f"[{row[0]}] {row[2]} {row[3]}ed {row[1]}")
                    print(f"   Reason: {row[4]}")
                    print("-" * 50)
            else:
                print("No logs found yet.")
                
        except Exception as e:
            print(f"Error querying logs: {e}")

if __name__ == "__main__":
    asyncio.run(check_logs())
