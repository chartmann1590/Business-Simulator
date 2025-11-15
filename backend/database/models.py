from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base

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
    activity_state = Column(String, default="idle")  # idle, working, walking, meeting, break, etc.
    hired_at = Column(DateTime(timezone=True), server_default=func.now())
    fired_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    has_performance_award = Column(Boolean, default=False)  # Tracks if employee has the highest performance review award
    performance_award_wins = Column(Integer, default=0)  # Tracks how many times employee has won the performance award
    
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
    deadline = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    tasks = relationship("Task", back_populates="project")
    financials = relationship("Financial", back_populates="project")
    customer_reviews = relationship("CustomerReview", foreign_keys="CustomerReview.project_id", back_populates="project")

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
    customer_name = Column(String, nullable=False)  # AI-generated customer name
    customer_title = Column(String, nullable=True)  # AI-generated customer title/role
    company_name = Column(String, nullable=True)  # AI-generated company name
    rating = Column(Float, nullable=False)  # 1.0 to 5.0
    review_text = Column(Text, nullable=False)  # The actual review content
    verified_purchase = Column(Boolean, default=True)  # Whether this is a verified purchase
    helpful_count = Column(Integer, default=0)  # Number of "helpful" votes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", foreign_keys=[project_id])

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

