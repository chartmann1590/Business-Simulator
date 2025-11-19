"""
Review Manager - Handles periodic employee reviews and performance evaluations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from database.models import Employee, EmployeeReview, Task, Activity, Project, Email, ChatMessage
from database.database import safe_commit, safe_flush
from datetime import datetime, timedelta
import random
from typing import Optional, List
from llm.ollama_client import OllamaClient


class ReviewManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def conduct_periodic_reviews(self, hours_since_last_review: float = 6.0):
        """
        Conduct periodic reviews for employees who haven't been reviewed recently.
        Reviews are conducted every 6 hours by default.
        This function is called frequently to ensure reviews happen promptly.
        """
        now = datetime.utcnow()
        cutoff_date = now - timedelta(hours=hours_since_last_review)
        
        # Get all active employees
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()
        
        # Get employees who need reviews (non-managers, non-executives, non-terminated)
        # Be more lenient - include all employees except executives and terminated employees
        employees_to_review = [
            emp for emp in all_employees 
            if emp.role not in ["CEO", "Manager", "CTO", "COO", "CFO"]
            and emp.status != "fired"
            and not emp.fired_at
        ]
        
        if not employees_to_review:
            print("⚠️  No employees eligible for reviews found")
            return []
        
        print(f"🔍 Checking {len(employees_to_review)} employees for reviews...")
        
        reviews_created = []
        overdue_count = 0
        checked_count = 0
        
        for employee in employees_to_review:
            checked_count += 1
            # Check if employee has been reviewed recently
            result = await self.db.execute(
                select(EmployeeReview)
                .where(EmployeeReview.employee_id == employee.id)
                .order_by(desc(EmployeeReview.review_date))
                .limit(1)
            )
            last_review = result.scalar_one_or_none()
            
            # Check if review is needed - be aggressive about creating overdue reviews
            needs_review = False
            is_overdue = False
            
            if not last_review:
                # New employee - review if hired more than 6 hours ago
                if employee.hired_at:
                    hired_at_naive = employee.hired_at.replace(tzinfo=None) if employee.hired_at.tzinfo else employee.hired_at
                    hours_since_hire = (now - hired_at_naive).total_seconds() / 3600
                    if hours_since_hire >= hours_since_last_review:
                        needs_review = True
                        # Consider overdue if more than 6.5 hours (30 min buffer)
                        if hours_since_hire >= hours_since_last_review + 0.5:
                            is_overdue = True
                else:
                    # Employee has no hire date - review them anyway if they've been active
                    # This handles edge cases where hired_at might be null
                    needs_review = True
                    # Store name early to avoid lazy loading
                    employee_name_temp = employee.name
                    print(f"  ⚠️  Employee {employee_name_temp} has no hire date - scheduling review anyway")
            else:
                # Check if last review was before cutoff
                if last_review.review_date:
                    review_date = last_review.review_date.replace(tzinfo=None) if last_review.review_date.tzinfo else last_review.review_date
                    hours_since_review = (now - review_date).total_seconds() / 3600
                    if review_date < cutoff_date:
                        needs_review = True
                        # Consider overdue if more than 6.5 hours (30 min buffer)
                        if hours_since_review >= hours_since_last_review + 0.5:
                            is_overdue = True
            
            if needs_review:
                # Store employee name early to avoid lazy loading issues in exception handlers
                employee_name = employee.name
                employee_hired_at = employee.hired_at
                employee_role = employee.role
                employee_hierarchy = employee.hierarchy_level
                
                try:
                    print(f"  📋 Generating review for {employee_name} (hired: {employee_hired_at}, role: {employee_role}, hierarchy: {employee_hierarchy})")
                    review = await self._generate_review(employee)
                    if review:
                        reviews_created.append(review)
                        if is_overdue:
                            overdue_count += 1
                        print(f"  ✅ Successfully created review for {employee_name}")
                    else:
                        print(f"  ❌ Failed to create review for {employee_name} - no manager available or generation failed")
                except Exception as e:
                    import traceback
                    from sqlalchemy.exc import OperationalError, PendingRollbackError
                    
                    # Rollback session on any error to prevent it from getting into a bad state
                    try:
                        await self.db.rollback()
                    except Exception as rollback_error:
                        # Rollback might fail if session is already rolled back
                        pass
                    
                    error_msg = str(e).lower()
                    if "database is locked" in error_msg or "locked" in error_msg:
                        print(f"  ⚠️  Database locked while generating review for {employee_name}, will retry later")
                    else:
                        print(f"  ❌ Error generating review for {employee_name}: {e}")
                        print(f"  Traceback: {traceback.format_exc()}")
        
        if reviews_created:
            try:
                # Flush first to ensure all objects are in the session
                await safe_flush(self.db)
                
                # Now commit
                await safe_commit(self.db)
                print(f"✅ Committed {len(reviews_created)} review(s) to database")
                
                # Verify reviews were actually saved by querying them back
                for review in reviews_created:
                    # Query the review back to verify it was saved
                    verify_result = await self.db.execute(
                        select(EmployeeReview).where(EmployeeReview.id == review.id)
                    )
                    verified_review = verify_result.scalar_one_or_none()
                    if verified_review:
                        print(f"  ✓ Verified Review ID {verified_review.id} for employee {verified_review.employee_id} - Date: {verified_review.review_date}, Rating: {verified_review.overall_rating}")
                        print(f"    Comments: {len(verified_review.comments or '')} chars, Strengths: {len(verified_review.strengths or '')} chars")
                    else:
                        print(f"  ❌ WARNING: Review ID {review.id} not found in database after commit!")
                
                if overdue_count > 0:
                    print(f"⚠️  Created {overdue_count} overdue review(s) - reviews are being pushed to managers!")
                
                # ALWAYS update performance award after reviews are committed
                # This ensures the award is transferred to the employee with the highest current rating
                print(f"  [AWARD] Updating performance award after {len(reviews_created)} new review(s)...")
                await self._update_performance_award()
                # Commit award changes
                await safe_commit(self.db)
                print(f"  [AWARD] Award update completed and committed")
            except Exception as e:
                import traceback
                print(f"❌ Error committing reviews: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                await self.db.rollback()
        else:
            if checked_count > 0:
                print(f"ℹ️  No reviews needed at this time (checked {checked_count} employees)")
        
        return reviews_created
    
    async def _generate_review(self, employee: Employee) -> Optional[EmployeeReview]:
        """
        Generate a review for an employee based on their performance metrics.
        """
        # Store employee name early to avoid lazy loading issues later
        employee_name = employee.name
        
        # Find a manager to conduct the review
        result = await self.db.execute(
            select(Employee).where(
                Employee.role.in_(["Manager", "CEO", "CTO", "COO", "CFO"]),
                Employee.status == "active"
            )
        )
        managers = result.scalars().all()
        
        if not managers:
            print(f"  ⚠️  No active managers found to review {employee_name}")
            return None
        
        # Prefer manager in same department
        manager = next((m for m in managers if m.department == employee.department), None)
        if not manager:
            manager = managers[0]
        
        # Store manager name early to avoid lazy loading issues later
        manager_name = manager.name
        
        print(f"  👤 Found {len(managers)} manager(s) - assigning to {manager_name}")
        
        # Determine review period (last 6 hours or since last review)
        review_period_end = datetime.utcnow()
        result = await self.db.execute(
            select(EmployeeReview)
            .where(EmployeeReview.employee_id == employee.id)
            .order_by(desc(EmployeeReview.review_date))
            .limit(1)
        )
        last_review = result.scalar_one_or_none()
        
        if last_review and last_review.review_date:
            review_period_start = last_review.review_date.replace(tzinfo=None) if last_review.review_date.tzinfo else last_review.review_date
        else:
            # If no previous review, use hire date or 6 hours ago
            if employee.hired_at:
                review_period_start = employee.hired_at.replace(tzinfo=None) if employee.hired_at.tzinfo else employee.hired_at
            else:
                review_period_start = datetime.utcnow() - timedelta(hours=6)
        
        # Calculate performance metrics for the review period
        metrics = await self._calculate_performance_metrics(employee, review_period_start)
        
        # Generate ratings based on metrics
        performance_rating = metrics["performance_score"]
        teamwork_rating = metrics["teamwork_score"]
        communication_rating = metrics["communication_score"]
        productivity_rating = metrics["productivity_score"]
        
        # Calculate overall rating (weighted average)
        overall_rating = (
            performance_rating * 0.3 +
            teamwork_rating * 0.2 +
            communication_rating * 0.2 +
            productivity_rating * 0.3
        )
        
        # Round to 1 decimal place, ensure between 1.0 and 5.0
        overall_rating = max(1.0, min(5.0, round(overall_rating, 1)))
        
        # Generate review comments using Ollama (manager conducts the review)
        comments, strengths, areas_for_improvement = await self._generate_review_comments_with_ollama(
            manager, employee, overall_rating, performance_rating, teamwork_rating, 
            communication_rating, productivity_rating, metrics, review_period_start, review_period_end
        )
        
        # Create review with explicit review_date
        review_date = datetime.utcnow()
        review = EmployeeReview(
            employee_id=employee.id,
            manager_id=manager.id,
            review_date=review_date,
            overall_rating=overall_rating,
            performance_rating=performance_rating,
            teamwork_rating=teamwork_rating,
            communication_rating=communication_rating,
            productivity_rating=productivity_rating,
            comments=comments,
            strengths=strengths,
            areas_for_improvement=areas_for_improvement,
            review_period_start=review_period_start,
            review_period_end=review_period_end
        )
        
        self.db.add(review)
        # Flush to get the review ID before using it in activities/notifications
        await safe_flush(self.db)
        
        # Verify the review was added and has an ID
        if not review.id:
            print(f"  ⚠️  Warning: Review for {employee_name} has no ID after flush")
            await safe_flush(self.db)  # Try again
        else:
            print(f"  ✓ Review ID {review.id} created for {employee_name}")
        
        # Create activity log
        from database.models import Activity
        activity = Activity(
            employee_id=employee.id,
            activity_type="performance_review",
            description=f"{employee_name} received a performance review from {manager_name}. Overall rating: {overall_rating}/5.0",
            activity_metadata={
                "review_id": review.id,
                "overall_rating": overall_rating,
                "manager_id": manager.id
            }
        )
        self.db.add(activity)
        
        # Also create activity for the manager (they conducted the review)
        manager_activity = Activity(
            employee_id=manager.id,
            activity_type="conducted_review",
            description=f"{manager_name} conducted a performance review for {employee_name}. Overall rating: {overall_rating}/5.0",
            activity_metadata={
                "review_id": review.id,
                "reviewed_employee_id": employee.id,
                "overall_rating": overall_rating
            }
        )
        self.db.add(manager_activity)
        
        # Create notification for the employee
        from database.models import Notification
        rating_label = "Excellent" if overall_rating >= 4.5 else "Very Good" if overall_rating >= 4.0 else "Good" if overall_rating >= 3.0 else "Needs Improvement" if overall_rating >= 2.0 else "Poor"
        notification = Notification(
            notification_type="review_completed",
            title=f"Performance Review Completed: {employee_name}",
            message=f"{manager_name} completed a performance review for {employee_name}. Overall rating: {overall_rating:.1f}/5.0 ({rating_label})",
            employee_id=employee.id,
            review_id=review.id,
            read=False
        )
        self.db.add(notification)
        
        # Create notification for the manager (reminder they conducted a review)
        manager_notification = Notification(
            notification_type="review_conducted",
            title=f"Review Conducted: {employee_name}",
            message=f"You completed a performance review for {employee_name}. Rating: {overall_rating:.1f}/5.0 ({rating_label})",
            employee_id=manager.id,
            review_id=review.id,
            read=False
        )
        self.db.add(manager_notification)
        
        # If rating is excellent (>= 4.5), consider a raise
        if overall_rating >= 4.5:
            # Check if employee has had consistently good reviews
            result = await self.db.execute(
                select(EmployeeReview)
                .where(EmployeeReview.employee_id == employee.id)
                .order_by(desc(EmployeeReview.review_date))
                .limit(2)
            )
            recent_reviews = result.scalars().all()
            
            # If this is the second excellent review in a row, recommend a raise
            if len(recent_reviews) >= 2:
                prev_review = recent_reviews[1] if len(recent_reviews) > 1 else None
                if prev_review and prev_review.overall_rating >= 4.5:
                    raise_activity = Activity(
                        employee_id=employee.id,
                        activity_type="raise_recommendation",
                        description=f"{employee_name} has received excellent performance reviews and is recommended for a salary increase.",
                        activity_metadata={
                            "review_id": review.id,
                            "overall_rating": overall_rating,
                            "recommended_raise_percentage": 5.0  # 5% raise
                        }
                    )
                    self.db.add(raise_activity)
                    
                    # Create notification for raise recommendation
                    from database.models import Notification
                    raise_notification = Notification(
                        notification_type="raise_recommendation",
                        title=f"Raise Recommended: {employee_name}",
                        message=f"{employee_name} has received two consecutive excellent performance reviews and is recommended for a 5% salary increase.",
                        employee_id=employee.id,
                        review_id=review.id,
                        read=False
                    )
                    self.db.add(raise_notification)
        
        return review
    
    async def _calculate_performance_metrics(self, employee: Employee, review_period_start: datetime = None) -> dict:
        """
        Calculate performance metrics for an employee based on their work.
        """
        # Use review period start if provided, otherwise default to last 6 hours
        if review_period_start:
            cutoff = review_period_start
        else:
            cutoff = datetime.utcnow() - timedelta(hours=6)
        
        result = await self.db.execute(
            select(Task)
            .where(
                Task.employee_id == employee.id,
                Task.status == "completed",
                Task.completed_at >= cutoff
            )
        )
        completed_tasks = result.scalars().all()
        
        # Get all tasks assigned to employee
        result = await self.db.execute(
            select(Task).where(Task.employee_id == employee.id)
        )
        all_tasks = result.scalars().all()
        
        # Calculate task completion rate
        total_tasks = len(all_tasks)
        completed_count = len(completed_tasks)
        completion_rate = (completed_count / total_tasks * 100) if total_tasks > 0 else 0.0
        
        # Get activities (to measure communication and teamwork)
        result = await self.db.execute(
            select(Activity)
            .where(
                Activity.employee_id == employee.id,
                Activity.timestamp >= cutoff
            )
        )
        recent_activities = result.scalars().all()
        
        # Count communication activities (emails, chats, meetings)
        communication_count = sum(
            1 for act in recent_activities 
            if any(keyword in act.activity_type.lower() for keyword in ["email", "chat", "meeting", "communication"])
        )
        
        # Count teamwork activities
        teamwork_count = sum(
            1 for act in recent_activities 
            if any(keyword in act.activity_type.lower() for keyword in ["collaboration", "team", "meeting", "project"])
        )
        
        # Base scores
        performance_score = 3.0  # Average
        teamwork_score = 3.0
        communication_score = 3.0
        productivity_score = 3.0
        
        # Adjust based on metrics
        if completion_rate >= 80:
            performance_score = 4.5
            productivity_score = 4.5
        elif completion_rate >= 60:
            performance_score = 3.5
            productivity_score = 3.5
        elif completion_rate < 40:
            performance_score = 2.0
            productivity_score = 2.0
        
        # Adjust for communication
        if communication_count > 20:
            communication_score = 4.0
        elif communication_count < 5:
            communication_score = 2.5
        
        # Adjust for teamwork
        if teamwork_count > 15:
            teamwork_score = 4.0
        elif teamwork_count < 3:
            teamwork_score = 2.5
        
        # Add some randomness based on personality traits
        if employee.personality_traits:
            traits = employee.personality_traits
            if "proactive" in traits or "hardworking" in traits:
                performance_score = min(5.0, performance_score + 0.3)
                productivity_score = min(5.0, productivity_score + 0.3)
            if "collaborative" in traits or "team player" in traits:
                teamwork_score = min(5.0, teamwork_score + 0.3)
            if "communicative" in traits or "outgoing" in traits:
                communication_score = min(5.0, communication_score + 0.3)
            if "lazy" in traits or "disengaged" in traits:
                performance_score = max(1.0, performance_score - 0.5)
                productivity_score = max(1.0, productivity_score - 0.5)
        
        # Add small random variation
        performance_score += random.uniform(-0.2, 0.2)
        teamwork_score += random.uniform(-0.2, 0.2)
        communication_score += random.uniform(-0.2, 0.2)
        productivity_score += random.uniform(-0.2, 0.2)
        
        # Ensure scores are between 1.0 and 5.0
        performance_score = max(1.0, min(5.0, round(performance_score, 1)))
        teamwork_score = max(1.0, min(5.0, round(teamwork_score, 1)))
        communication_score = max(1.0, min(5.0, round(communication_score, 1)))
        productivity_score = max(1.0, min(5.0, round(productivity_score, 1)))
        
        return {
            "performance_score": performance_score,
            "teamwork_score": teamwork_score,
            "communication_score": communication_score,
            "productivity_score": productivity_score,
            "completion_rate": completion_rate,
            "communication_count": communication_count,
            "teamwork_count": teamwork_count,
            "completed_tasks": completed_count
        }
    
    async def _generate_review_comments_with_ollama(
        self, manager: Employee, employee: Employee, overall_rating: float,
        performance_rating: float, teamwork_rating: float,
        communication_rating: float, productivity_rating: float,
        metrics: dict, review_period_start: datetime, review_period_end: datetime
    ) -> tuple:
        """
        Generate review comments, strengths, and areas for improvement using Ollama.
        The manager conducts the review from their perspective.
        """
        # Store names early to avoid lazy loading issues in exception handlers
        employee_name = employee.name
        manager_name = manager.name
        
        # Get employee's recent work data for context
        result = await self.db.execute(
            select(Task)
            .where(
                Task.employee_id == employee.id,
                Task.created_at >= review_period_start,
                Task.created_at <= review_period_end
            )
            .order_by(desc(Task.created_at))
            .limit(10)
        )
        recent_tasks = result.scalars().all()
        
        # Get recent activities
        result = await self.db.execute(
            select(Activity)
            .where(
                Activity.employee_id == employee.id,
                Activity.timestamp >= review_period_start,
                Activity.timestamp <= review_period_end
            )
            .order_by(desc(Activity.timestamp))
            .limit(10)
        )
        recent_activities = result.scalars().all()
        
        # Build task summary
        task_summary = []
        for task in recent_tasks[:5]:
            status = task.status
            task_summary.append(f"- {task.description[:100]} ({status})")
        task_summary_str = "\n".join(task_summary) if task_summary else "No tasks in this period"
        
        # Build activity summary
        activity_summary = []
        for act in recent_activities[:5]:
            activity_summary.append(f"- {act.activity_type}: {act.description[:80]}")
        activity_summary_str = "\n".join(activity_summary) if activity_summary else "No recent activities"
        
        # Manager personality traits
        manager_personality = ", ".join(manager.personality_traits) if manager.personality_traits else "professional, fair"
        employee_personality = ", ".join(employee.personality_traits) if employee.personality_traits else "balanced"
        
        # Format review period
        period_str = f"{review_period_start.strftime('%Y-%m-%d %H:%M')} to {review_period_end.strftime('%Y-%m-%d %H:%M')}"
        
        # Build prompt for Ollama
        prompt = f"""You are {manager_name}, {manager.title} at a company. You are conducting a performance review for {employee_name}, {employee.title}.

Your personality traits: {manager_personality}
Your role: {manager.role}
Your backstory: {manager.backstory or "Experienced manager focused on team development"}

Employee being reviewed:
- Name: {employee_name}
- Title: {employee.title}
- Department: {employee.department}
- Personality: {employee_personality}
- Backstory: {employee.backstory or "Team member"}

Review Period: {period_str}

Performance Ratings (out of 5.0):
- Overall Rating: {overall_rating}/5.0
- Performance: {performance_rating}/5.0
- Teamwork: {teamwork_rating}/5.0
- Communication: {communication_rating}/5.0
- Productivity: {productivity_rating}/5.0

Performance Metrics:
- Task Completion Rate: {metrics.get('completion_rate', 0):.1f}%
- Completed Tasks: {metrics.get('completed_tasks', 0)}
- Communication Activities: {metrics.get('communication_count', 0)}
- Teamwork Activities: {metrics.get('teamwork_count', 0)}

Recent Work:
Tasks:
{task_summary_str}

Recent Activities:
{activity_summary_str}

Write a professional performance review from your perspective as {manager_name}. The review should:

1. Include overall comments (2-3 sentences) about {employee_name}'s performance during this period
2. List 2-3 key strengths (be specific and constructive)
3. List 1-2 areas for improvement (be supportive and actionable)

Write the review in JSON format:
{{
    "comments": "Your overall review comments (2-3 sentences)",
    "strengths": "strength1; strength2; strength3",
    "areas_for_improvement": "area1; area2"
}}

Be professional, fair, and constructive. Match your personality traits when writing the review."""

        try:
            llm_client = OllamaClient()
            response_text = await llm_client.generate_response(prompt)
            
            # Try to parse JSON from response
            import json
            import re
            
            # Extract JSON from response (handle nested braces)
            # Try to find JSON object with balanced braces
            brace_count = 0
            start_idx = response_text.find('{')
            if start_idx != -1:
                for i in range(start_idx, len(response_text)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response_text[start_idx:i+1]
                            json_match = json_str
                            break
                else:
                    json_match = None
            else:
                json_match = None
            
            if json_match:
                try:
                    review_data = json.loads(json_match if isinstance(json_match, str) else json_match.group())
                    comments = review_data.get("comments", "")
                    strengths = review_data.get("strengths", "")
                    areas_for_improvement = review_data.get("areas_for_improvement", "")
                except json.JSONDecodeError:
                    # Fallback: parse manually
                    comments = response_text[:500] if response_text else ""
                    strengths = "Good performance" if overall_rating >= 3.0 else "Room for growth"
                    areas_for_improvement = "Continue developing skills" if overall_rating < 4.0 else "Maintain excellence"
            else:
                # No JSON found, use fallback
                comments = response_text[:500] if response_text else ""
                strengths = "Good performance" if overall_rating >= 3.0 else "Room for growth"
                areas_for_improvement = "Continue developing skills" if overall_rating < 4.0 else "Maintain excellence"
            
            # Convert lists to strings if needed (handle case where LLM returns arrays)
            if isinstance(comments, list):
                comments = "; ".join(str(item) for item in comments) if comments else ""
            if isinstance(strengths, list):
                strengths = "; ".join(str(item) for item in strengths) if strengths else ""
            if isinstance(areas_for_improvement, list):
                areas_for_improvement = "; ".join(str(item) for item in areas_for_improvement) if areas_for_improvement else ""
            
            # Convert to strings if not already
            comments = str(comments) if comments is not None else ""
            strengths = str(strengths) if strengths is not None else ""
            areas_for_improvement = str(areas_for_improvement) if areas_for_improvement is not None else ""
            
            # Ensure we have values - never return empty strings or None
            if not comments or (isinstance(comments, str) and comments.strip() == ""):
                comments = f"{employee_name} has shown {'strong' if overall_rating >= 4.0 else 'satisfactory' if overall_rating >= 3.0 else 'areas needing improvement'} performance this period."
            if not strengths or (isinstance(strengths, str) and strengths.strip() == ""):
                strengths = "Consistent performance" if overall_rating >= 3.0 else "Room for growth"
            if not areas_for_improvement or (isinstance(areas_for_improvement, str) and areas_for_improvement.strip() == ""):
                areas_for_improvement = "Continue to develop skills" if overall_rating < 4.0 else "Maintain current excellence"
            
            # Strip whitespace and ensure non-empty
            comments = comments.strip() if comments else "Performance review completed."
            strengths = strengths.strip() if strengths else "Ongoing development"
            areas_for_improvement = areas_for_improvement.strip() if areas_for_improvement else "Continue professional growth"
            
            print(f"  📝 Generated review content - Comments: {len(comments)} chars, Strengths: {len(strengths)} chars, Areas: {len(areas_for_improvement)} chars")
            
            return comments, strengths, areas_for_improvement
            
        except Exception as e:
            print(f"  ⚠️  Error generating review with Ollama: {e}")
            # Fallback to simple review - ensure non-empty values
            comments = f"{employee_name} has shown {'strong' if overall_rating >= 4.0 else 'satisfactory' if overall_rating >= 3.0 else 'areas needing improvement'} performance this period."
            strengths = "Good performance" if overall_rating >= 3.0 else "Room for growth"
            areas_for_improvement = "Continue developing skills" if overall_rating < 4.0 else "Maintain excellence"
            print(f"  📝 Using fallback review content")
            return comments, strengths, areas_for_improvement
    
    async def get_average_rating(self, employee_id: int) -> Optional[float]:
        """
        Get the average overall rating for an employee across all reviews.
        """
        result = await self.db.execute(
            select(func.avg(EmployeeReview.overall_rating))
            .where(EmployeeReview.employee_id == employee_id)
        )
        avg_rating = result.scalar_one_or_none()
        return avg_rating if avg_rating is not None else None
    
    async def get_recent_reviews(self, employee_id: int, limit: int = 3) -> List[EmployeeReview]:
        """
        Get the most recent reviews for an employee.
        """
        result = await self.db.execute(
            select(EmployeeReview)
            .where(EmployeeReview.employee_id == employee_id)
            .order_by(desc(EmployeeReview.review_date))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def _update_performance_award(self):
        """
        Update the performance award to the employee with the highest recent review rating.
        IMPORTANT: The award is ALWAYS transferred to the employee with the highest current rating
        when new reviews are released. If a different employee now has the highest rating, 
        the award is transferred to them and their win count is incremented.
        
        If multiple employees have the same highest rating, use tiebreaker logic:
        1. Most recent review date (newer review wins)
        2. Employee ID (lower ID wins as final tiebreaker)
        Only one employee can have the award at a time.
        """
        try:
            # Get all active employees who have received reviews
            result = await self.db.execute(
                select(Employee).where(Employee.status == "active")
            )
            all_employees = result.scalars().all()
            
            # Get the most recent review for each employee
            employee_reviews = []
            for employee in all_employees:
                # Get most recent review (order by review_date, fallback to created_at)
                review_result = await self.db.execute(
                    select(EmployeeReview)
                    .where(EmployeeReview.employee_id == employee.id)
                    .order_by(desc(EmployeeReview.review_date), desc(EmployeeReview.created_at))
                    .limit(1)
                )
                latest_review = review_result.scalar_one_or_none()
                
                if latest_review:
                    # Use review_date if available, otherwise use created_at
                    review_date = latest_review.review_date if latest_review.review_date else latest_review.created_at
                    employee_reviews.append({
                        "employee": employee,
                        "review": latest_review,
                        "rating": latest_review.overall_rating,
                        "review_date": review_date
                    })
            
            if not employee_reviews:
                print("  ℹ️  No reviews found - cannot assign performance award")
                return
        
            # Find the highest rating
            max_rating = max(er["rating"] for er in employee_reviews)
            
            # Get all employees with the highest rating
            top_employees = [er for er in employee_reviews if er["rating"] == max_rating]
            
            # Apply tiebreaker logic: most recent review date, then employee ID
            # Sort by review_date descending (newer first), then by employee ID ascending (lower ID first)
            # Python's sort with a tuple key sorts by first element, then second, etc.
            # For descending date order, we negate the timestamp; for ascending ID, we use positive ID
            def sort_key(x):
                review_date = x["review_date"] if x["review_date"] else datetime.min
                try:
                    # Get timestamp for sorting (works for both naive and timezone-aware datetimes)
                    timestamp = review_date.timestamp()
                    # Negate timestamp so newer dates (higher timestamp) come first
                    return (-timestamp, x["employee"].id)
                except (OSError, OverflowError, AttributeError):
                    # Fallback: if timestamp() fails, use a simple numeric representation
                    # Use year/month/day as a sortable number (newer dates have larger numbers)
                    date_value = review_date.year * 10000 + review_date.month * 100 + review_date.day
                    return (-date_value, x["employee"].id)
            
            top_employees.sort(key=sort_key)
            
            # The winner is the first one after sorting
            winner = top_employees[0]["employee"]
            
            # Find current award holder
            result = await self.db.execute(
                select(Employee).where(
                    Employee.has_performance_award == True,
                    Employee.status == "active"
                )
            )
            current_holder = result.scalar_one_or_none()
        
            # If the winner is already the holder, verify they still have the highest rating
            if current_holder and current_holder.id == winner.id:
                # Double-check: verify current holder's rating matches the max rating
                current_holder_rating = None
                for er in employee_reviews:
                    if er["employee"].id == current_holder.id:
                        current_holder_rating = er["rating"]
                        break
                
                # If current holder's rating matches max, they should keep it
                if current_holder_rating is not None and abs(current_holder_rating - max_rating) < 0.01:  # Use small epsilon for float comparison
                    # Ensure the database state is correct - winner should have the award flag set
                    # Even though current_holder says they have it, winner might be a different object instance
                    if not winner.has_performance_award:
                        print(f"  [AWARD] Fixing database inconsistency: {winner.name} should have award but flag is False. Setting it now.")
                        winner.has_performance_award = True
                        await safe_flush(self.db)
                    print(f"  [AWARD] {winner.name} already holds the performance award (rating: {max_rating:.1f}/5.0) - no change needed")
                    return
                else:
                    # Current holder doesn't have max rating - this shouldn't happen, but fix it
                    print(f"  [AWARD] WARNING: {current_holder.name} has award but rating ({current_holder_rating:.1f if current_holder_rating else 'N/A'}) doesn't match max ({max_rating:.1f}). Transferring to {winner.name}.")
                    # Continue with transfer logic below
            
            # Remove award from current holder if different
            if current_holder:
                # Get current holder's rating for logging
                current_holder_rating = None
                for er in employee_reviews:
                    if er["employee"].id == current_holder.id:
                        current_holder_rating = er["rating"]
                        break
                
                current_holder.has_performance_award = False
                if current_holder_rating:
                    print(f"  [AWARD] Performance award transferred from {current_holder.name} (rating: {current_holder_rating:.1f}/5.0) to {winner.name} (rating: {max_rating:.1f}/5.0)")
                else:
                    print(f"  [AWARD] Performance award transferred from {current_holder.name} to {winner.name} (rating: {max_rating:.1f}/5.0)")
                
                # Create notification for previous holder
                from database.models import Notification
                prev_notification = Notification(
                    notification_type="award_transferred",
                    title="Performance Award Transferred",
                    message=f"The performance award has been transferred to {winner.name} who received a higher review rating ({max_rating:.1f}/5.0).",
                    employee_id=current_holder.id,
                    read=False
                )
                self.db.add(prev_notification)
                
                # Create activity log for previous holder
                from database.models import Activity
                prev_activity = Activity(
                    employee_id=current_holder.id,
                    activity_type="award_transferred",
                    description=f"The performance award was transferred from {current_holder.name} to {winner.name}.",
                    activity_metadata={
                        "previous_holder_id": current_holder.id,
                        "new_holder_id": winner.id,
                        "new_holder_rating": max_rating
                    }
                )
                self.db.add(prev_activity)
            else:
                print(f"  [AWARD] Performance award assigned to {winner.name} (rating: {max_rating:.1f}/5.0)")
            
            # Assign award to winner
            # Check if winner already had the award before this update
            # We need to check both current_holder AND the winner's current flag state
            # because there might be database inconsistencies
            winner_already_had_award = (current_holder and current_holder.id == winner.id) or winner.has_performance_award
            
            # Set the award flag
            winner.has_performance_award = True
            
            # Only increment award wins if this is a NEW win (not if they already had it)
            if not winner_already_had_award:
                # Increment award wins count only for new wins
                if not hasattr(winner, 'performance_award_wins') or winner.performance_award_wins is None:
                    winner.performance_award_wins = 0
                winner.performance_award_wins += 1
                print(f"  [AWARD] {winner.name} now has {winner.performance_award_wins} award win(s)")
            else:
                print(f"  [AWARD] {winner.name} retains the award (already had {winner.performance_award_wins or 0} win(s))")
            
            # Create notification for winner
            from database.models import Notification
            winner_notification = Notification(
                notification_type="performance_award",
                title="🏆 Performance Award Earned!",
                message=f"Congratulations! You have earned the Performance Award for having the highest review rating ({max_rating:.1f}/5.0) among all employees. Keep up the excellent work!",
                employee_id=winner.id,
                read=False
            )
            self.db.add(winner_notification)
            
            # Create activity log for winner
            from database.models import Activity
            winner_activity = Activity(
                employee_id=winner.id,
                activity_type="performance_award_earned",
                description=f"{winner.name} earned the Performance Award for having the highest review rating ({max_rating:.1f}/5.0).",
                activity_metadata={
                    "rating": max_rating,
                    "award_type": "performance_award"
                }
            )
            self.db.add(winner_activity)
            
            # Create a general notification for all employees (acknowledgment)
            all_employees_result = await self.db.execute(
                select(Employee).where(Employee.status == "active")
            )
            all_active_employees = all_employees_result.scalars().all()
            
            for emp in all_active_employees:
                if emp.id != winner.id:  # Don't duplicate the winner's notification
                    acknowledgment = Notification(
                        notification_type="award_announcement",
                        title="🏆 Performance Award Announcement",
                        message=f"{winner.name} has earned the Performance Award for having the highest review rating ({max_rating:.1f}/5.0). Congratulations!",
                        employee_id=emp.id,
                        read=False
                    )
                    self.db.add(acknowledgment)
            
            await safe_flush(self.db)
            print(f"  [AWARD] Performance award system updated - {winner.name} is the new award holder (rating: {max_rating:.1f}/5.0)")
            
            # Debug: Print all top employees for verification
            print(f"  [AWARD DEBUG] Top employees with rating {max_rating:.1f}:")
            for i, emp_rev in enumerate(top_employees[:5]):
                print(f"    {i+1}. {emp_rev['employee'].name} (ID: {emp_rev['employee'].id}, Rating: {emp_rev['rating']:.1f}, Review Date: {emp_rev['review_date']})")
        
        except Exception as e:
            import traceback
            print(f"  ❌ [AWARD ERROR] Error updating performance award: {e}")
            print(f"  Traceback: {traceback.format_exc()}")
            # Don't raise - allow the calling code to handle it, but log the error
            raise

