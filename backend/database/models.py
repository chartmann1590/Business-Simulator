from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import FunctionElement
from database.database import Base

# Custom SQL function for timezone-aware now()
class local_now(FunctionElement):
    type = DateTime(timezone=True)
    inherit_cache = True

@compiles(local_now, 'sqlite')
def compile_local_now(element, compiler, **kw):
    return "datetime('now')"

@compiles(local_now, 'postgresql')
def compile_local_now_pg(element, compiler, **kw):
    return "NOW() AT TIME ZONE 'UTC' AT TIME ZONE (SELECT current_setting('timezone'))"

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    role = Column(String, nullable=False)  # CEO, Manager, Employee
    hierarchy_level = Column(Integer, nullable=False)  # 1 = CEO, 2 = Manager, 3 = Employee
    department = Column(String, nullable=True)
    status = Column(String, default="active")  # active, busy, idle, fired
    current_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    personality_traits = Column(JSON, default=list)
    backstory = Column(Text, nullable=True)
    avatar_path = Column(String, nullable=True)
    current_room = Column(String, nullable=True)  # tracks which room employee is currently in
    home_room = Column(String, nullable=True)  # tracks employee's assigned home room
    floor = Column(Integer, default=1)  # floor number (1 or 2)
    activity_state = Column(String, default="working")  # working, walking, meeting, break, training, etc.
    hired_at = Column(DateTime(timezone=True), server_default=func.now())
    fired_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    has_performance_award = Column(Boolean, default=False)  # Tracks if employee has the highest performance review award
    performance_award_wins = Column(Integer, default=0)  # Tracks how many times employee has won the performance award
    birthday_month = Column(Integer, nullable=True)  # Month of birthday (1-12)
    birthday_day = Column(Integer, nullable=True)  # Day of birthday (1-31)
    hobbies = Column(JSON, default=list)  # List of hobbies/interests
    last_coffee_break = Column(DateTime(timezone=True), nullable=True)  # Last coffee break time
    
    tasks = relationship("Task", back_populates="employee", foreign_keys="Task.employee_id")
    decisions = relationship("Decision", back_populates="employee")
    activities = relationship("Activity", back_populates="employee")
    sent_emails = relationship("Email", foreign_keys="Email.sender_id", back_populates="sender")
    received_emails = relationship("Email", foreign_keys="Email.recipient_id", back_populates="recipient")
    sent_chats = relationship("ChatMessage", foreign_keys="ChatMessage.sender_id", back_populates="sender")
    received_chats = relationship("ChatMessage", foreign_keys="ChatMessage.recipient_id", back_populates="recipient")
    reviews_received = relationship("EmployeeReview", foreign_keys="EmployeeReview.employee_id", back_populates="employee")
    reviews_given = relationship("EmployeeReview", foreign_keys="EmployeeReview.manager_id", back_populates="manager")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="planning")  # planning, active, completed, cancelled
    priority = Column(String, default="medium")  # low, medium, high
    budget = Column(Float, default=0.0)
    revenue = Column(Float, default=0.0)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # Product this project is working on
    deadline = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    tasks = relationship("Task", back_populates="project")
    financials = relationship("Financial", back_populates="project")
    customer_reviews = relationship("CustomerReview", foreign_keys="CustomerReview.project_id", back_populates="project")
    product = relationship("Product", foreign_keys=[product_id])

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, in_progress, completed, cancelled
    priority = Column(String, default="medium")
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    employee = relationship("Employee", back_populates="tasks", foreign_keys=[employee_id])
    project = relationship("Project", back_populates="tasks")

class Decision(Base):
    __tablename__ = "decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    decision_type = Column(String, nullable=False)  # strategic, tactical, operational
    description = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    employee = relationship("Employee", back_populates="decisions")

class Financial(Base):
    __tablename__ = "financials"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)  # income, expense
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", back_populates="financials")

class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    activity_type = Column(String, nullable=False)  # decision, task_completed, project_started, etc.
    description = Column(Text, nullable=False)
    activity_metadata = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    employee = relationship("Employee", back_populates="activities")

class BusinessMetric(Base):
    __tablename__ = "business_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class BusinessSettings(Base):
    __tablename__ = "business_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String, nullable=False, unique=True)
    setting_value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BusinessGoal(Base):
    __tablename__ = "business_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    goal_text = Column(Text, nullable=False)
    goal_key = Column(String, nullable=True)  # e.g., "revenue_growth", "profitability", etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_updated_date = Column(DateTime(timezone=True), nullable=True)  # Track when goal was last updated (date only, no time)

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    thread_id = Column(String, nullable=True, index=True)  # Groups all emails between two employees
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    sender = relationship("Employee", foreign_keys=[sender_id], back_populates="sent_emails")
    recipient = relationship("Employee", foreign_keys=[recipient_id], back_populates="received_emails")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Nullable to allow system/user messages (0 or NULL)
    recipient_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Nullable to allow messages to user/manager
    message = Column(Text, nullable=False)
    thread_id = Column(String, nullable=True, index=True)  # Groups all chats between two employees
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    sender = relationship("Employee", foreign_keys=[sender_id], back_populates="sent_chats")
    recipient = relationship("Employee", foreign_keys=[recipient_id], back_populates="received_chats")

class EmployeeReview(Base):
    __tablename__ = "employee_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    review_date = Column(DateTime(timezone=True), server_default=func.now())
    overall_rating = Column(Float, nullable=False)  # 1.0 to 5.0
    performance_rating = Column(Float, nullable=True)  # 1.0 to 5.0
    teamwork_rating = Column(Float, nullable=True)  # 1.0 to 5.0
    communication_rating = Column(Float, nullable=True)  # 1.0 to 5.0
    productivity_rating = Column(Float, nullable=True)  # 1.0 to 5.0
    comments = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    review_period_start = Column(DateTime(timezone=True), nullable=True)  # Start of review period
    review_period_end = Column(DateTime(timezone=True), nullable=True)  # End of review period
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="reviews_received")
    manager = relationship("Employee", foreign_keys=[manager_id], back_populates="reviews_given")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_type = Column(String, nullable=False)  # review_completed, raise_recommendation, employee_fired, etc.
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Related employee if applicable
    review_id = Column(Integer, ForeignKey("employee_reviews.id"), nullable=True)  # Related review if applicable
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    employee = relationship("Employee", foreign_keys=[employee_id])
    review = relationship("EmployeeReview", foreign_keys=[review_id])

class CustomerReview(Base):
    __tablename__ = "customer_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # Which product/service this review is for
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # Which product this review is for
    customer_name = Column(String, nullable=False)  # AI-generated customer name
    customer_title = Column(String, nullable=True)  # AI-generated customer title/role
    company_name = Column(String, nullable=True)  # AI-generated company name
    rating = Column(Float, nullable=False)  # 1.0 to 5.0
    review_text = Column(Text, nullable=False)  # The actual review content
    verified_purchase = Column(Boolean, default=True)  # Whether this is a verified purchase
    helpful_count = Column(Integer, default=0)  # Number of "helpful" votes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", foreign_keys=[project_id])
    product = relationship("Product", foreign_keys=[product_id])

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # e.g., "Software", "Service", "Hardware"
    status = Column(String, default="active")  # active, development, discontinued, planned
    price = Column(Float, default=0.0)  # Base price
    launch_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Many-to-many relationship with employees (team members)
    team_members = relationship("ProductTeamMember", back_populates="product", cascade="all, delete-orphan")
    # Relationship to projects working on this product
    projects = relationship("Project", back_populates="product", foreign_keys="Project.product_id")
    # Customer reviews for this product
    customer_reviews = relationship("CustomerReview", foreign_keys="CustomerReview.product_id", back_populates="product")

class ProductTeamMember(Base):
    __tablename__ = "product_team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    role = Column(String, nullable=True)  # e.g., "Product Manager", "Lead Developer", "Designer"
    responsibility = Column(Text, nullable=True)  # What they're responsible for
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    product = relationship("Product", back_populates="team_members")
    employee = relationship("Employee")

class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    organizer_id = Column(Integer, ForeignKey("employees.id"), nullable=False)  # Meeting organizer
    attendee_ids = Column(JSON, default=list)  # List of employee IDs attending
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="scheduled")  # scheduled, in_progress, completed, cancelled
    agenda = Column(Text, nullable=True)  # Meeting agenda
    outline = Column(Text, nullable=True)  # Meeting outline
    transcript = Column(Text, nullable=True)  # Full meeting transcript (for completed meetings)
    live_transcript = Column(Text, nullable=True)  # Live transcript (for in-progress meetings)
    meeting_metadata = Column(JSON, default=dict)  # Additional metadata (live messages, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    organizer = relationship("Employee", foreign_keys=[organizer_id])

class OfficePet(Base):
    __tablename__ = "office_pets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    pet_type = Column(String, nullable=False)  # cat, dog
    avatar_path = Column(String, nullable=False)  # Path to pet avatar
    current_room = Column(String, nullable=True)  # Current room location
    floor = Column(Integer, default=1)  # Current floor
    personality = Column(Text, nullable=True)  # Pet personality description
    favorite_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Favorite employee
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    favorite_employee = relationship("Employee", foreign_keys=[favorite_employee_id])
    care_logs = relationship("PetCareLog", back_populates="pet")

class PetCareLog(Base):
    __tablename__ = "pet_care_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("office_pets.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    care_action = Column(String, nullable=False)  # feed, play, pet
    pet_happiness_before = Column(Float, nullable=True)  # Pet happiness before care (0-100)
    pet_hunger_before = Column(Float, nullable=True)  # Pet hunger before care (0-100)
    pet_energy_before = Column(Float, nullable=True)  # Pet energy before care (0-100)
    pet_happiness_after = Column(Float, nullable=True)  # Pet happiness after care (0-100)
    pet_hunger_after = Column(Float, nullable=True)  # Pet hunger after care (0-100)
    pet_energy_after = Column(Float, nullable=True)  # Pet energy after care (0-100)
    ai_reasoning = Column(Text, nullable=True)  # AI reasoning for why this employee was chosen
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    pet = relationship("OfficePet", back_populates="care_logs")
    employee = relationship("Employee")

class Gossip(Base):
    __tablename__ = "gossip"
    
    id = Column(Integer, primary_key=True, index=True)
    originator_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Who started the gossip
    spreader_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Who is spreading it
    recipient_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Who hears it
    topic = Column(String, nullable=False)  # Topic of gossip
    content = Column(Text, nullable=False)  # The gossip content
    credibility = Column(Float, default=0.5)  # How credible (0.0 to 1.0)
    spread_count = Column(Integer, default=0)  # How many times it's been spread
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    originator = relationship("Employee", foreign_keys=[originator_id])
    spreader = relationship("Employee", foreign_keys=[spreader_id])
    recipient = relationship("Employee", foreign_keys=[recipient_id])

class Weather(Base):
    __tablename__ = "weather"
    
    id = Column(Integer, primary_key=True, index=True)
    condition = Column(String, nullable=False)  # sunny, rainy, cloudy, stormy, snowy
    temperature = Column(Float, nullable=False)  # Temperature in Fahrenheit
    productivity_modifier = Column(Float, default=1.0)  # Multiplier for productivity (0.5 to 1.5)
    description = Column(Text, nullable=True)  # Weather description
    date = Column(DateTime(timezone=True), nullable=False)  # Date of weather
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RandomEvent(Base):
    __tablename__ = "random_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)  # power_outage, internet_down, fire_drill, etc.
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    impact = Column(String, default="low")  # low, medium, high
    affected_employees = Column(JSON, default=list)  # List of affected employee IDs
    productivity_modifier = Column(Float, default=1.0)  # Productivity impact
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)  # Null if ongoing
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Newsletter(Base):
    __tablename__ = "newsletters"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Who wrote it
    issue_number = Column(Integer, nullable=False)  # Newsletter issue number
    published_date = Column(DateTime(timezone=True), nullable=False)
    read_count = Column(Integer, default=0)  # How many employees read it
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    author = relationship("Employee", foreign_keys=[author_id])

class Suggestion(Base):
    __tablename__ = "suggestions"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    category = Column(String, nullable=False)  # office_improvement, process, culture, etc.
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, reviewed, implemented, rejected
    upvotes = Column(Integer, default=0)  # Number of upvotes from other employees
    reviewed_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Manager who reviewed
    review_notes = Column(Text, nullable=True)
    manager_comments = Column(Text, nullable=True)  # AI-generated manager comments
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    employee = relationship("Employee", foreign_keys=[employee_id])
    reviewer = relationship("Employee", foreign_keys=[reviewed_by_id])
    votes = relationship("SuggestionVote", back_populates="suggestion", cascade="all, delete-orphan")

class SuggestionVote(Base):
    __tablename__ = "suggestion_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    suggestion = relationship("Suggestion", back_populates="votes")
    employee = relationship("Employee")
    
    __table_args__ = (
        UniqueConstraint('suggestion_id', 'employee_id', name='unique_suggestion_vote'),
    )

class BirthdayCelebration(Base):
    __tablename__ = "birthday_celebrations"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    celebration_date = Column(DateTime(timezone=True), nullable=False)  # Date of celebration
    year = Column(Integer, nullable=False)  # Which birthday
    attendees = Column(JSON, default=list)  # List of employee IDs who attended
    celebration_message = Column(Text, nullable=True)  # AI-generated celebration message
    party_room = Column(String, nullable=True)  # Room where party is held
    party_floor = Column(Integer, nullable=True)  # Floor where party is held
    party_time = Column(DateTime(timezone=True), nullable=True)  # Scheduled party time
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    employee = relationship("Employee", foreign_keys=[employee_id])

class SharedDriveFile(Base):
    __tablename__ = "shared_drive_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # word, spreadsheet, powerpoint
    department = Column(String, nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Original creator
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    content_html = Column(Text, nullable=False)  # Current version HTML
    file_metadata = Column(JSON, default=dict)  # Renamed from metadata (reserved in SQLAlchemy)
    last_updated_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    current_version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    employee = relationship("Employee", foreign_keys=[employee_id])
    last_updated_by = relationship("Employee", foreign_keys=[last_updated_by_id])
    project = relationship("Project", foreign_keys=[project_id])
    versions = relationship("SharedDriveFileVersion", back_populates="file", cascade="all, delete-orphan", order_by="SharedDriveFileVersion.version_number.desc()")

class SharedDriveFileVersion(Base):
    __tablename__ = "shared_drive_file_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("shared_drive_files.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content_html = Column(Text, nullable=False)
    file_size = Column(Integer, default=0)
    created_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    change_summary = Column(Text, nullable=True)  # AI-generated summary
    file_metadata = Column(JSON, default=dict)  # Renamed from metadata (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    file = relationship("SharedDriveFile", back_populates="versions")
    created_by = relationship("Employee", foreign_keys=[created_by_id])

