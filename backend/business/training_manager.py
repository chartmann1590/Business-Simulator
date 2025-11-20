"""Training manager to track employee training sessions and generate training materials."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import Employee, TrainingSession, TrainingMaterial, SharedDriveFile
from datetime import datetime, timedelta
from llm.ollama_client import OllamaClient
from employees.room_assigner import ROOM_TRAINING_ROOM
import json
import os
import re
from config import now as local_now, now_naive

class TrainingManager:
    def __init__(self):
        self.ollama_client = OllamaClient()
        # Base directory for shared drive files
        self.base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared_drive")
        os.makedirs(self.base_dir, exist_ok=True)
    
    async def start_training_session(
        self,
        employee: Employee,
        training_room: str,
        db_session: AsyncSession
    ) -> TrainingSession:
        """Start a new training session when employee enters a training room."""
        # Check if there's an existing in-progress session
        existing_session = await db_session.execute(
            select(TrainingSession)
            .where(TrainingSession.employee_id == employee.id)
            .where(TrainingSession.status == "in_progress")
        )
        existing = existing_session.scalar_one_or_none()
        
        if existing:
            # Update existing session if they're in a different room
            if existing.training_room != training_room:
                existing.training_room = training_room
            return existing
        
        # Determine training topic based on employee role, department, and AI
        training_topic = await self._determine_training_topic(employee, db_session)
        
        # Find or create training material for this topic
        training_material = await self._get_or_create_training_material(
            training_topic,
            employee.department,
            db_session
        )
        
        # Create new training session
        # Use now_naive() to ensure timezone-naive datetime for database consistency
        session = TrainingSession(
            employee_id=employee.id,
            training_room=training_room,
            training_topic=training_topic,
            training_material_id=training_material.id if training_material else None,
            start_time=now_naive(),
            status="in_progress"
        )
        
        db_session.add(session)
        await db_session.flush()
        
        return session
    
    async def end_training_session(
        self,
        employee: Employee,
        db_session: AsyncSession
    ) -> TrainingSession | None:
        """End the current training session when employee leaves training room."""
        # Find in-progress session
        result = await db_session.execute(
            select(TrainingSession)
            .where(TrainingSession.employee_id == employee.id)
            .where(TrainingSession.status == "in_progress")
        )
        session = result.scalar_one_or_none()
        
        if session:
            # Use now_naive() for consistency with start_time
            session.end_time = now_naive()
            session.status = "completed"
            
            # Calculate duration in minutes
            if session.start_time and session.end_time:
                # Ensure both are naive for comparison
                start = session.start_time.replace(tzinfo=None) if session.start_time.tzinfo else session.start_time
                end = session.end_time.replace(tzinfo=None) if session.end_time.tzinfo else session.end_time
                duration = end - start
                session.duration_minutes = int(duration.total_seconds() / 60)
            
            await db_session.flush()
            return session
        
        return None
    
    async def _determine_training_topic(
        self,
        employee: Employee,
        db_session: AsyncSession
    ) -> str:
        """Use AI to determine what the employee should be trained on."""
        # Get employee's recent training history
        recent_sessions = await db_session.execute(
            select(TrainingSession)
            .where(TrainingSession.employee_id == employee.id)
            .where(TrainingSession.status == "completed")
            .order_by(TrainingSession.start_time.desc())
            .limit(5)
        )
        recent_topics = [s.training_topic for s in recent_sessions.scalars().all()]
        
        # Use AI to determine appropriate training topic
        try:
            prompt = f"""Determine an appropriate training topic for {employee.name}, a {employee.title} in the {employee.department or 'general'} department.

Employee context:
- Name: {employee.name}
- Title: {employee.title}
- Department: {employee.department or 'general'}
- Role: {employee.role}

Recent training topics: {', '.join(recent_topics) if recent_topics else 'None'}

Generate a specific, relevant training topic that would benefit this employee. Examples:
- "Customer Service Best Practices"
- "Project Management Fundamentals"
- "Advanced Excel Techniques"
- "Communication Skills"
- "Time Management"
- "Software Development Best Practices"
- "Sales Techniques"
- "Data Analysis Fundamentals"

Return ONLY the training topic name (2-5 words), nothing else."""
            
            response = await self.ollama_client.generate_response(prompt)
            topic = response.strip()
            
            # Clean up the response
            if len(topic) > 100:
                topic = topic[:100]
            
            # Fallback if AI doesn't return a good topic
            if not topic or len(topic) < 3:
                topic = self._get_default_training_topic(employee)
            
            return topic
        except Exception as e:
            print(f"Error determining training topic with AI: {e}")
            return self._get_default_training_topic(employee)
    
    def _get_default_training_topic(self, employee: Employee) -> str:
        """Get a default training topic based on employee role/department."""
        department = (employee.department or "").lower()
        title = (employee.title or "").lower()
        
        if "developer" in title or "engineer" in title or "programmer" in title:
            return "Software Development Best Practices"
        elif "manager" in title or "lead" in title:
            return "Leadership and Team Management"
        elif "sales" in title or "sales" in department:
            return "Sales Techniques and Customer Relations"
        elif "marketing" in title or "marketing" in department:
            return "Digital Marketing Strategies"
        elif "hr" in title or "human resources" in department:
            return "HR Policies and Employee Relations"
        elif "finance" in title or "accounting" in title or "finance" in department:
            return "Financial Analysis and Reporting"
        elif "design" in title or "designer" in title:
            return "Design Principles and Tools"
        elif "support" in title or "customer" in title:
            return "Customer Service Excellence"
        else:
            return "Professional Development and Skills Enhancement"
    
    async def _get_or_create_training_material(
        self,
        topic: str,
        department: str | None,
        db_session: AsyncSession
    ) -> TrainingMaterial | None:
        """Get existing training material or create new one using AI."""
        # Try to find existing material for this topic
        result = await db_session.execute(
            select(TrainingMaterial)
            .where(TrainingMaterial.topic == topic)
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update usage count
            existing.usage_count = (existing.usage_count or 0) + 1
            await db_session.flush()
            
            # Ensure it's saved to shared drive (in case it wasn't before)
            try:
                await self._save_training_material_to_shared_drive(existing, db_session)
            except Exception as e:
                print(f"Error ensuring training material in shared drive: {e}")
                # Don't fail if shared drive save fails
            
            return existing
        
        # Create new training material using AI
        try:
            material = await self._generate_training_material(topic, department, db_session)
            if material:
                db_session.add(material)
                await db_session.flush()
                return material
        except Exception as e:
            print(f"Error generating training material: {e}")
        
        return None
    
    async def _generate_training_material(
        self,
        topic: str,
        department: str | None,
        db_session: AsyncSession
    ) -> TrainingMaterial | None:
        """Generate training material content using AI."""
        try:
            prompt = f"""Create comprehensive training material for: {topic}

{f"Department: {department}" if department else ""}

Generate a well-structured training guide that includes:
1. Overview and objectives
2. Key concepts and principles
3. Practical examples and applications
4. Best practices
5. Summary and next steps

Make it professional, clear, and actionable. The content should be suitable for employees to learn from during a training session.

Format the response as clear, readable text with sections. Do not use markdown formatting."""
            
            content = await self.ollama_client.generate_response(prompt)
            
            if not content or len(content) < 100:
                # Fallback content
                content = f"""Training Material: {topic}

Overview:
This training session covers {topic}, providing essential knowledge and skills for professional development.

Key Concepts:
- Understanding the fundamentals of {topic}
- Applying best practices
- Practical implementation strategies

Best Practices:
1. Focus on understanding core principles
2. Practice with real-world examples
3. Apply learning to daily work activities

Summary:
This training provides a foundation in {topic} that can be applied to improve job performance and professional growth."""
            
            # Determine difficulty level and estimated duration
            difficulty = "intermediate"
            duration = 30
            
            if "advanced" in topic.lower() or "expert" in topic.lower():
                difficulty = "advanced"
                duration = 45
            elif "introduction" in topic.lower() or "fundamentals" in topic.lower() or "basics" in topic.lower():
                difficulty = "beginner"
                duration = 20
            
            material = TrainingMaterial(
                title=f"Training: {topic}",
                topic=topic,
                content=content,
                description=f"Comprehensive training material covering {topic}",
                difficulty_level=difficulty,
                estimated_duration_minutes=duration,
                department=department,
                created_by_ai=True,
                usage_count=1
            )
            
            # Save to shared drive after material is created
            try:
                await self._save_training_material_to_shared_drive(material, db_session)
            except Exception as e:
                print(f"Error saving training material to shared drive: {e}")
                # Don't fail the whole operation if shared drive save fails
            
            return material
        except Exception as e:
            print(f"Error generating training material with AI: {e}")
            return None
    
    async def check_and_end_expired_sessions(
        self,
        db_session: AsyncSession
    ) -> int:
        """Check for training sessions that have exceeded 30 minutes and end them."""
        from datetime import datetime, timedelta
        from sqlalchemy import select, and_, func
        from config import now_naive
        
        # Use timezone-naive datetime for comparison (consistent with how sessions are created)
        now = now_naive()
        thirty_minutes_ago = now - timedelta(minutes=30)
        
        # Find all in-progress sessions
        result = await db_session.execute(
            select(TrainingSession)
            .where(
                and_(
                    TrainingSession.status == "in_progress",
                    TrainingSession.start_time.isnot(None)
                )
            )
        )
        all_sessions = result.scalars().all()
        
        expired_sessions = []
        for session in all_sessions:
            if session.start_time:
                # Normalize start_time to timezone-naive for comparison
                start_time = session.start_time
                if start_time.tzinfo:
                    # Convert to naive datetime for comparison
                    start_time = start_time.replace(tzinfo=None)
                
                # Check if more than 30 minutes have passed
                time_diff = (now - start_time).total_seconds() / 60
                if time_diff >= 30:
                    expired_sessions.append(session)
        
        ended_count = 0
        for session in expired_sessions:
            try:
                # End the session
                session.end_time = now
                session.status = "completed"
                
                # Calculate duration (should be around 30 minutes)
                if session.start_time and session.end_time:
                    # Both should be naive now
                    start = session.start_time.replace(tzinfo=None) if session.start_time.tzinfo else session.start_time
                    end = now  # Already naive
                    duration = end - start
                    session.duration_minutes = int(duration.total_seconds() / 60)
                
                # Get the employee and move them out of training room
                employee_result = await db_session.execute(
                    select(Employee).where(Employee.id == session.employee_id)
                )
                employee = employee_result.scalar_one_or_none()
                
                if employee:
                    # Check if employee is still in a training room
                    from employees.room_assigner import ROOM_TRAINING_ROOM
                    is_in_training_room = (
                        employee.current_room == ROOM_TRAINING_ROOM or
                        (employee.current_room and employee.current_room.startswith(f"{ROOM_TRAINING_ROOM}_floor"))
                    )
                    
                    if is_in_training_room:
                        # Move employee to their home room or a suitable alternative
                        from engine.movement_system import update_employee_location
                        target_room = employee.home_room
                        if not target_room:
                            # Fallback to cubicles or open office
                            from employees.room_assigner import ROOM_CUBICLES, ROOM_OPEN_OFFICE
                            employee_floor = getattr(employee, 'floor', 1)
                            target_room = f"{ROOM_CUBICLES}_floor{employee_floor}" if employee_floor > 1 else ROOM_CUBICLES
                        
                        try:
                            await update_employee_location(employee, target_room, "working", db_session)
                            print(f"✅ Moved {employee.name} out of training room after {session.duration_minutes} minutes")
                        except Exception as e:
                            print(f"Error moving employee {employee.name} out of training room: {e}")
                            import traceback
                            traceback.print_exc()
                
                ended_count += 1
            except Exception as e:
                print(f"Error ending training session {session.id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if ended_count > 0:
            await db_session.flush()
            print(f"✅ Ended {ended_count} expired training sessions")
        
        return ended_count
    
    async def get_employee_training_summary(
        self,
        employee_id: int,
        db_session: AsyncSession
    ) -> dict:
        """Get training summary for an employee."""
        # Get all completed sessions
        result = await db_session.execute(
            select(TrainingSession)
            .where(TrainingSession.employee_id == employee_id)
            .where(TrainingSession.status == "completed")
            .order_by(TrainingSession.start_time.desc())
        )
        sessions = result.scalars().all()
        
        # Calculate totals
        total_sessions = len(sessions)
        total_minutes = sum(s.duration_minutes or 0 for s in sessions)
        unique_topics = len(set(s.training_topic for s in sessions))
        
        # Get current in-progress session
        current_result = await db_session.execute(
            select(TrainingSession)
            .where(TrainingSession.employee_id == employee_id)
            .where(TrainingSession.status == "in_progress")
        )
        current_session = current_result.scalar_one_or_none()
        
        return {
            "total_sessions": total_sessions,
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 1),
            "unique_topics": unique_topics,
            "current_session": {
                "id": current_session.id,
                "topic": current_session.training_topic,
                "room": current_session.training_room,
                "training_material_id": current_session.training_material_id,
                "start_time": current_session.start_time.isoformat() if current_session.start_time else None,
            } if current_session else None,
            "recent_sessions": [
                {
                    "id": s.id,
                    "topic": s.training_topic,
                    "room": s.training_room,
                    "training_material_id": s.training_material_id,
                    "duration_minutes": s.duration_minutes,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                }
                for s in sessions[:10]  # Last 10 sessions
            ]
        }
    
    def _get_training_file_path(self, department: str | None, topic: str) -> str:
        """Generate file path for training material in shared drive."""
        # Sanitize names for filesystem
        safe_dept = re.sub(r'[^\w\s-]', '', department or "General").strip() if department else "General"
        safe_topic = re.sub(r'[^\w\s-]', '', topic).strip()
        
        # Create path: Training/Department/Topic.html
        dir_path = os.path.join(self.base_dir, "Training", safe_dept)
        os.makedirs(dir_path, exist_ok=True)
        
        # Create safe filename
        safe_file = re.sub(r'[^\w\s.-]', '', topic).strip()
        if not safe_file.endswith('.html'):
            if '.' in safe_file:
                safe_file = safe_file.rsplit('.', 1)[0] + '.html'
            else:
                safe_file += '.html'
        
        return os.path.join(dir_path, safe_file)
    
    def _format_training_material_as_html(self, material: TrainingMaterial) -> str:
        """Format training material content as HTML document."""
        # Convert plain text content to structured HTML
        content = material.content or ""
        
        # Split content into paragraphs (assuming double newlines separate paragraphs)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        # Build HTML structure
        html_parts = []
        html_parts.append('<div style="font-family: \'Times New Roman\', serif; font-size: 12pt; margin: 1in; line-height: 1.5; color: #000000; background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 40px;">')
        
        # Title
        html_parts.append(f'<h1 style="text-align: center; font-size: 18pt; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px;">{material.title}</h1>')
        
        # Header info
        html_parts.append('<div style="margin-bottom: 30px; padding-bottom: 15px; border-bottom: 1px solid #ccc;">')
        html_parts.append(f'<p style="margin: 5px 0;"><strong>Topic:</strong> {material.topic}</p>')
        if material.department:
            html_parts.append(f'<p style="margin: 5px 0;"><strong>Department:</strong> {material.department}</p>')
        html_parts.append(f'<p style="margin: 5px 0;"><strong>Difficulty Level:</strong> {material.difficulty_level or "N/A"}</p>')
        html_parts.append(f'<p style="margin: 5px 0;"><strong>Estimated Duration:</strong> {material.estimated_duration_minutes or "N/A"} minutes</p>')
        html_parts.append(f'<p style="margin: 5px 0;"><strong>Created:</strong> {local_now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
        html_parts.append('</div>')
        
        # Description
        if material.description:
            html_parts.append(f'<div style="background-color: #f5f5f5; padding: 15px; margin-bottom: 20px; border-left: 4px solid #007bff;">')
            html_parts.append(f'<p style="margin: 0; font-style: italic;">{material.description}</p>')
            html_parts.append('</div>')
        
        # Content sections
        html_parts.append('<div style="margin-top: 20px;">')
        for para in paragraphs:
            # Check if paragraph looks like a heading (short, all caps, or ends with colon)
            if len(para) < 100 and (para.isupper() or para.endswith(':')):
                html_parts.append(f'<h2 style="font-size: 14pt; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333;">{para}</h2>')
            # Check if paragraph is a list item
            elif para.startswith('- ') or para.startswith('* ') or para.startswith('1. ') or para.startswith('• '):
                if '<ul>' not in html_parts[-1] if html_parts else True:
                    html_parts.append('<ul style="margin-left: 20px; margin-bottom: 15px;">')
                list_item = para.lstrip('- *• 1234567890. ')
                html_parts.append(f'<li style="margin-bottom: 5px;">{list_item}</li>')
            else:
                # Close any open list
                if html_parts and html_parts[-1].startswith('<li'):
                    html_parts.append('</ul>')
                html_parts.append(f'<p style="margin-bottom: 15px; text-align: justify;">{para}</p>')
        
        # Close any open list
        if html_parts and html_parts[-1].startswith('<li'):
            html_parts.append('</ul>')
        
        html_parts.append('</div>')
        
        # Footer
        html_parts.append('<div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; text-align: center; font-size: 10pt; color: #666;">')
        html_parts.append(f'<p>Training Material Document | Generated by AI | {local_now().strftime("%Y-%m-%d")}</p>')
        html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    async def _save_training_material_to_shared_drive(
        self,
        material: TrainingMaterial,
        db_session: AsyncSession
    ) -> SharedDriveFile | None:
        """Save training material to shared drive as a document."""
        try:
            # Check if file already exists for this topic and department
            existing_file = await db_session.execute(
                select(SharedDriveFile)
                .where(SharedDriveFile.file_name.like(f"%{material.topic}%"))
                .where(SharedDriveFile.file_type == "word")
                .where(SharedDriveFile.department == material.department)
                .limit(1)
            )
            existing = existing_file.scalar_one_or_none()
            
            if existing:
                # Update existing file
                content_html = self._format_training_material_as_html(material)
                existing.content_html = content_html
                existing.file_size = len(content_html.encode('utf-8'))
                existing.updated_at = local_now()
                existing.file_metadata = {
                    "topic": material.topic,
                    "difficulty_level": material.difficulty_level,
                    "estimated_duration_minutes": material.estimated_duration_minutes,
                    "training_material_id": material.id,
                    "updated_at": local_now().isoformat()
                }
                
                # Update filesystem
                os.makedirs(os.path.dirname(existing.file_path), exist_ok=True)
                with open(existing.file_path, 'w', encoding='utf-8') as f:
                    f.write(content_html)
                
                print(f"  ✓ Updated training material in shared drive: {material.topic}")
                return existing
            
            # Create new file
            file_name = f"{material.topic}.html"
            file_path = self._get_training_file_path(material.department, material.topic)
            content_html = self._format_training_material_as_html(material)
            
            drive_file = SharedDriveFile(
                file_name=file_name,
                file_type="word",  # Training materials are stored as Word-like documents
                department=material.department,
                employee_id=None,  # Training materials are not tied to a specific employee
                project_id=None,
                file_path=file_path,
                file_size=len(content_html.encode('utf-8')),
                content_html=content_html,
                file_metadata={
                    "topic": material.topic,
                    "difficulty_level": material.difficulty_level,
                    "estimated_duration_minutes": material.estimated_duration_minutes,
                    "training_material_id": material.id,
                    "created_by_ai": True,
                    "created_at": local_now().isoformat(),
                    "purpose": "Training Material"
                },
                last_updated_by_id=None,
                current_version=1
            )
            
            db_session.add(drive_file)
            await db_session.flush()
            
            # Save to filesystem
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_html)
            
            print(f"  ✓ Saved training material to shared drive: {material.topic}")
            return drive_file
            
        except Exception as e:
            print(f"Error saving training material to shared drive: {e}")
            import traceback
            traceback.print_exc()
            return None

