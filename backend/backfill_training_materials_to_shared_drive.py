"""
Script to backfill training materials to shared drive.
This ensures all existing training materials are saved as shared drive files.
"""
import asyncio
import sys
import os
import io

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import get_db
from database.models import TrainingMaterial, SharedDriveFile
from sqlalchemy import select
from business.training_manager import TrainingManager


async def backfill_training_materials():
    """Backfill all training materials to shared drive."""
    async for db in get_db():
        try:
            # Get all training materials
            result = await db.execute(select(TrainingMaterial))
            materials = result.scalars().all()
            
            print(f"Found {len(materials)} training materials to check...")
            
            training_manager = TrainingManager()
            saved_count = 0
            skipped_count = 0
            error_count = 0
            
            for material in materials:
                try:
                    # Check if already in shared drive
                    existing_file = await db.execute(
                        select(SharedDriveFile)
                        .where(SharedDriveFile.file_name.like(f"%{material.topic}%"))
                        .where(SharedDriveFile.file_type == "word")
                        .where(SharedDriveFile.department == material.department)
                        .limit(1)
                    )
                    existing = existing_file.scalar_one_or_none()
                    
                    if existing:
                        print(f"  [SKIP] Skipping {material.topic} (already in shared drive)")
                        skipped_count += 1
                    else:
                        # Save to shared drive
                        print(f"  [SAVE] Saving {material.topic} to shared drive...")
                        saved_file = await training_manager._save_training_material_to_shared_drive(material, db)
                        if saved_file:
                            saved_count += 1
                            print(f"     [OK] Saved successfully")
                        else:
                            error_count += 1
                            print(f"     [FAIL] Failed to save")
                except Exception as e:
                    error_count += 1
                    print(f"  [ERROR] Error processing {material.topic}: {e}")
            
            await db.commit()
            
            print(f"\n[COMPLETE] Backfill complete!")
            print(f"   Saved: {saved_count}")
            print(f"   Skipped: {skipped_count}")
            print(f"   Errors: {error_count}")
            
        except Exception as e:
            print(f"Error in backfill: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(backfill_training_materials())

