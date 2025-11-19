"""
PostgreSQL Index Optimization Script
Creates indexes for all foreign keys and frequently queried columns
to improve query performance.
"""
from sqlalchemy import text
from database.database import engine
import asyncio


async def create_optimization_indexes():
    """Create all optimization indexes for PostgreSQL."""
    async with engine.begin() as conn:
        print("Creating PostgreSQL optimization indexes...")
        
        # Employee indexes
        indexes = [
            # Employee table indexes
            ("idx_employees_status", "employees", "status"),
            ("idx_employees_role", "employees", "role"),
            ("idx_employees_department", "employees", "department"),
            ("idx_employees_hierarchy_level", "employees", "hierarchy_level"),
            ("idx_employees_current_room", "employees", "current_room"),
            ("idx_employees_floor", "employees", "floor"),
            ("idx_employees_activity_state", "employees", "activity_state"),
            ("idx_employees_current_task_id", "employees", "current_task_id"),
            ("idx_employees_created_at", "employees", "created_at"),
            ("idx_employees_hired_at", "employees", "hired_at"),
            ("idx_employees_birthday_month_day", "employees", "(birthday_month, birthday_day)"),
            
            # Project indexes
            ("idx_projects_status", "projects", "status"),
            ("idx_projects_priority", "projects", "priority"),
            ("idx_projects_product_id", "projects", "product_id"),
            ("idx_projects_deadline", "projects", "deadline"),
            ("idx_projects_created_at", "projects", "created_at"),
            ("idx_projects_completed_at", "projects", "completed_at"),
            ("idx_projects_last_activity_at", "projects", "last_activity_at"),
            
            # Task indexes
            ("idx_tasks_employee_id", "tasks", "employee_id"),
            ("idx_tasks_project_id", "tasks", "project_id"),
            ("idx_tasks_status", "tasks", "status"),
            ("idx_tasks_priority", "tasks", "priority"),
            ("idx_tasks_created_at", "tasks", "created_at"),
            ("idx_tasks_completed_at", "tasks", "completed_at"),
            
            # Activity indexes
            ("idx_activities_employee_id", "activities", "employee_id"),
            ("idx_activities_activity_type", "activities", "activity_type"),
            ("idx_activities_timestamp", "activities", "timestamp"),
            ("idx_activities_type_timestamp", "activities", "(activity_type, timestamp)"),
            
            # Email indexes
            ("idx_emails_sender_id", "emails", "sender_id"),
            ("idx_emails_recipient_id", "emails", "recipient_id"),
            ("idx_emails_thread_id", "emails", "thread_id"),
            ("idx_emails_timestamp", "emails", "timestamp"),
            ("idx_emails_read", "emails", "read"),
            ("idx_emails_recipient_read", "emails", "(recipient_id, read)"),
            
            # ChatMessage indexes
            ("idx_chat_messages_sender_id", "chat_messages", "sender_id"),
            ("idx_chat_messages_recipient_id", "chat_messages", "recipient_id"),
            ("idx_chat_messages_thread_id", "chat_messages", "thread_id"),
            ("idx_chat_messages_timestamp", "chat_messages", "timestamp"),
            
            # EmployeeReview indexes
            ("idx_employee_reviews_employee_id", "employee_reviews", "employee_id"),
            ("idx_employee_reviews_manager_id", "employee_reviews", "manager_id"),
            ("idx_employee_reviews_review_date", "employee_reviews", "review_date"),
            ("idx_employee_reviews_created_at", "employee_reviews", "created_at"),
            ("idx_employee_reviews_employee_created", "employee_reviews", "(employee_id, created_at)"),
            
            # Notification indexes
            ("idx_notifications_employee_id", "notifications", "employee_id"),
            ("idx_notifications_type", "notifications", "notification_type"),
            ("idx_notifications_read", "notifications", "read"),
            ("idx_notifications_created_at", "notifications", "created_at"),
            ("idx_notifications_employee_read", "notifications", "(employee_id, read)"),
            
            # CustomerReview indexes
            ("idx_customer_reviews_project_id", "customer_reviews", "project_id"),
            ("idx_customer_reviews_product_id", "customer_reviews", "product_id"),
            ("idx_customer_reviews_created_at", "customer_reviews", "created_at"),
            ("idx_customer_reviews_rating", "customer_reviews", "rating"),
            
            # Product indexes
            ("idx_products_status", "products", "status"),
            ("idx_products_category", "products", "category"),
            ("idx_products_created_at", "products", "created_at"),
            
            # ProductTeamMember indexes
            ("idx_product_team_members_product_id", "product_team_members", "product_id"),
            ("idx_product_team_members_employee_id", "product_team_members", "employee_id"),
            
            # Meeting indexes
            ("idx_meetings_organizer_id", "meetings", "organizer_id"),
            ("idx_meetings_status", "meetings", "status"),
            ("idx_meetings_start_time", "meetings", "start_time"),
            ("idx_meetings_end_time", "meetings", "end_time"),
            ("idx_meetings_start_end", "meetings", "(start_time, end_time)"),
            ("idx_meetings_status_start", "meetings", "(status, start_time)"),
            
            # Financial indexes
            ("idx_financials_project_id", "financials", "project_id"),
            ("idx_financials_type", "financials", "type"),
            ("idx_financials_timestamp", "financials", "timestamp"),
            
            # Decision indexes
            ("idx_decisions_employee_id", "decisions", "employee_id"),
            ("idx_decisions_decision_type", "decisions", "decision_type"),
            ("idx_decisions_timestamp", "decisions", "timestamp"),
            
            # BusinessMetric indexes
            ("idx_business_metrics_metric_name", "business_metrics", "metric_name"),
            ("idx_business_metrics_timestamp", "business_metrics", "timestamp"),
            ("idx_business_metrics_name_timestamp", "business_metrics", "(metric_name, timestamp)"),
            
            # BusinessSettings indexes (already has unique on setting_key)
            ("idx_business_settings_updated_at", "business_settings", "updated_at"),
            
            # BusinessGoal indexes
            ("idx_business_goals_is_active", "business_goals", "is_active"),
            ("idx_business_goals_created_at", "business_goals", "created_at"),
            
            # OfficePet indexes
            ("idx_office_pets_floor", "office_pets", "floor"),
            ("idx_office_pets_current_room", "office_pets", "current_room"),
            ("idx_office_pets_favorite_employee_id", "office_pets", "favorite_employee_id"),
            
            # PetCareLog indexes
            ("idx_pet_care_logs_pet_id", "pet_care_logs", "pet_id"),
            ("idx_pet_care_logs_employee_id", "pet_care_logs", "employee_id"),
            ("idx_pet_care_logs_created_at", "pet_care_logs", "created_at"),
            
            # Gossip indexes
            ("idx_gossip_originator_id", "gossip", "originator_id"),
            ("idx_gossip_spreader_id", "gossip", "spreader_id"),
            ("idx_gossip_recipient_id", "gossip", "recipient_id"),
            ("idx_gossip_created_at", "gossip", "created_at"),
            
            # Weather indexes
            ("idx_weather_date", "weather", "date"),
            
            # RandomEvent indexes
            ("idx_random_events_resolved", "random_events", "resolved"),
            ("idx_random_events_start_time", "random_events", "start_time"),
            ("idx_random_events_event_type", "random_events", "event_type"),
            
            # Newsletter indexes
            ("idx_newsletters_issue_number", "newsletters", "issue_number"),
            ("idx_newsletters_published_date", "newsletters", "published_date"),
            ("idx_newsletters_author_id", "newsletters", "author_id"),
            
            # Suggestion indexes
            ("idx_suggestions_status", "suggestions", "status"),
            ("idx_suggestions_employee_id", "suggestions", "employee_id"),
            ("idx_suggestions_category", "suggestions", "category"),
            ("idx_suggestions_created_at", "suggestions", "created_at"),
            
            # SuggestionVote indexes
            ("idx_suggestion_votes_suggestion_id", "suggestion_votes", "suggestion_id"),
            ("idx_suggestion_votes_employee_id", "suggestion_votes", "employee_id"),
            
            # BirthdayCelebration indexes
            ("idx_birthday_celebrations_employee_id", "birthday_celebrations", "employee_id"),
            ("idx_birthday_celebrations_celebration_date", "birthday_celebrations", "celebration_date"),
            ("idx_birthday_celebrations_year", "birthday_celebrations", "year"),
            
            # HolidayCelebration indexes
            ("idx_holiday_celebrations_celebration_date", "holiday_celebrations", "celebration_date"),
            ("idx_holiday_celebrations_holiday_name", "holiday_celebrations", "holiday_name"),
            
            # SharedDriveFile indexes
            ("idx_shared_drive_files_employee_id", "shared_drive_files", "employee_id"),
            ("idx_shared_drive_files_project_id", "shared_drive_files", "project_id"),
            ("idx_shared_drive_files_file_type", "shared_drive_files", "file_type"),
            ("idx_shared_drive_files_department", "shared_drive_files", "department"),
            ("idx_shared_drive_files_updated_at", "shared_drive_files", "updated_at"),
            
            # SharedDriveFileVersion indexes
            ("idx_shared_drive_file_versions_file_id", "shared_drive_file_versions", "file_id"),
            ("idx_shared_drive_file_versions_version_number", "shared_drive_file_versions", "version_number"),
        ]
        
        created_count = 0
        skipped_count = 0
        
        for index_name, table_name, column_expr in indexes:
            try:
                # Check if index already exists
                check_result = await conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE indexname = :index_name
                """), {"index_name": index_name})
                exists = check_result.scalar() > 0
                
                if not exists:
                    await conn.execute(text(f"""
                        CREATE INDEX IF NOT EXISTS {index_name} 
                        ON {table_name} ({column_expr})
                    """))
                    created_count += 1
                    print(f"✅ Created index: {index_name}")
                else:
                    skipped_count += 1
                    print(f"⏭️  Index already exists: {index_name}")
            except Exception as e:
                print(f"❌ Error creating index {index_name}: {e}")
        
        print(f"\n📊 Index creation complete:")
        print(f"   Created: {created_count}")
        print(f"   Already existed: {skipped_count}")
        print(f"   Total: {len(indexes)}")
        
        # Create composite indexes for common query patterns
        composite_indexes = [
            ("idx_employees_status_activity", "employees", "(status, activity_state)"),
            ("idx_employees_floor_room", "employees", "(floor, current_room)"),
            ("idx_projects_status_priority", "projects", "(status, priority)"),
            ("idx_tasks_status_priority", "tasks", "(status, priority)"),
            ("idx_meetings_status_time_range", "meetings", "(status, start_time, end_time)"),
        ]
        
        print("\nCreating composite indexes...")
        for index_name, table_name, column_expr in composite_indexes:
            try:
                check_result = await conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE indexname = :index_name
                """), {"index_name": index_name})
                exists = check_result.scalar() > 0
                
                if not exists:
                    await conn.execute(text(f"""
                        CREATE INDEX IF NOT EXISTS {index_name} 
                        ON {table_name} {column_expr}
                    """))
                    created_count += 1
                    print(f"✅ Created composite index: {index_name}")
                else:
                    skipped_count += 1
                    print(f"⏭️  Composite index already exists: {index_name}")
            except Exception as e:
                print(f"❌ Error creating composite index {index_name}: {e}")
        
        # Analyze tables to update statistics
        print("\n📈 Analyzing tables to update statistics...")
        tables = [
            "employees", "projects", "tasks", "activities", "emails", "chat_messages",
            "employee_reviews", "notifications", "customer_reviews", "products",
            "product_team_members", "meetings", "financials", "decisions",
            "business_metrics", "business_settings", "business_goals"
        ]
        
        for table in tables:
            try:
                await conn.execute(text(f"ANALYZE {table}"))
                print(f"✅ Analyzed: {table}")
            except Exception as e:
                print(f"⚠️  Could not analyze {table}: {e}")
        
        print("\n✨ PostgreSQL optimization complete!")


if __name__ == "__main__":
    asyncio.run(create_optimization_indexes())

