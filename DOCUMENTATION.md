# Business Simulator - Complete Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Backend Components](#backend-components)
4. [Frontend Components](#frontend-components)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [WebSocket Events](#websocket-events)
8. [Setup & Installation](#setup--installation)
9. [Configuration](#configuration)
10. [Development Guide](#development-guide)
11. [Deployment](#deployment)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

The Business Simulator is a fully autonomous office simulation system where AI-powered employees make decisions, work on projects, communicate with each other, and grow the business. The system uses local LLM (Ollama with Llama3.2) to power employee decision-making, creating a realistic simulation of an office environment.

### Key Features

- **Fully Autonomous Operation**: The office runs completely independently without user interaction
- **AI-Powered Employees**: Each employee uses LLM to make contextual decisions based on role, personality, and backstory
- **Employee Hierarchy**: CEO, Managers, and Employees with different decision-making capabilities
- **Multi-Floor Office System**: 4 floors with specialized rooms and intelligent distribution
- **Smart Room Management**: Room capacity tracking, overflow handling, and intelligent movement
- **Real-time Web Interface**: Modern React dashboard with live updates via WebSocket
- **Office Layout System**: Visual representation of employees moving between rooms across all floors
- **Communication System**: Email and chat messaging between employees
- **Project Management**: Employees create, plan, and execute projects with progress tracking
- **Task Management**: Detailed task tracking with progress, assignments, and activity history
- **Financial System**: Comprehensive revenue, expenses, profit tracking with detailed analytics
- **Goal System**: Business goals with progress tracking and completion evaluation
- **Employee Reviews**: Performance review system with ratings and feedback
- **Performance Awards**: Recognition system for top-performing employees with AI-generated congratulatory messages
- **Notification System**: Real-time notifications for important events (reviews, raises, terminations)
- **Boardroom Discussions**: Strategic planning and decision-making sessions
- **Meeting Management**: Meeting scheduling, calendar views, and live meeting transcripts with AI-generated content
- **Customer Reviews**: AI-generated customer reviews for completed projects with ratings and statistics

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Dashboard │  │Employees │  │ Projects │  │Financial│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │OfficeView│  │Communicat│  │WebSocket │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/WebSocket
┌──────────────────────┴──────────────────────────────────┐
│              Backend (FastAPI)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ API Routes   │  │ WebSocket    │  │ Office       │ │
│  │              │  │ Handler      │  │ Simulator    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Employee     │  │ Business     │  │ LLM Client   │ │
│  │ Agents       │  │ Managers     │  │ (Ollama)     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│              Database (SQLite)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │Employees │  │ Projects │  │ Tasks    │  │Financial│ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │Activities│  │ Emails   │  │ Chats    │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.10+
- FastAPI (Web framework)
- SQLAlchemy 2.0 (Async ORM)
- SQLite (Database)
- Ollama (Local LLM)
- WebSockets (Real-time communication)

**Frontend:**
- React 18
- Vite (Build tool)
- Tailwind CSS (Styling)
- React Router (Routing)
- Recharts (Data visualization)
- WebSocket API (Real-time updates)

---

## Backend Components

### Core Modules

#### 1. `main.py`
Entry point for the FastAPI application. Handles:
- Application initialization
- CORS configuration
- Static file serving (avatars, office layouts)
- WebSocket endpoint registration
- Database initialization on startup
- Auto-seeding if database is empty
- Simulation startup

#### 2. `engine/office_simulator.py`
Core simulation engine that:
- Runs the main simulation loop (every 8 seconds)
- Processes employees in batches (3 per tick)
- Manages WebSocket connections for real-time updates
- Coordinates business context gathering
- Handles employee hiring/firing
- Broadcasts activities to connected clients

**Key Methods:**
- `run()`: Main simulation loop
- `simulation_tick()`: Processes one simulation cycle
- `get_business_context()`: Gathers current business state
- `broadcast_activity()`: Sends updates to frontend

#### 3. `employees/`
Employee agent system for decision-making:

**`base.py`**: Base `EmployeeAgent` class
- `evaluate_situation()`: Uses LLM to evaluate current situation
- `execute_decision()`: Executes the decision and creates activities
- Handles task completion, project work, communication
- Integrates with movement system for room transitions

**`roles.py`**: Role-specific agents
- `CEOAgent`: Strategic decisions, project creation, goal setting
- `ManagerAgent`: Tactical decisions, task assignment, team coordination
- `EmployeeAgent`: Operational decisions, task execution, problem solving

**`room_assigner.py`**: Room assignment logic
- Assigns home rooms and floors based on role/title/department
- Distributes employees across 4 floors for optimal space utilization
- Specialized room assignments:
  - CEO → Corner Executive Office (Floor 3)
  - Executives → Executive Suite (Floor 2) or Corner Executive (Floor 3)
  - Sales → Sales Room (Floor 2)
  - HR → HR Room (Floor 2)
  - Design → Design Studio or Innovation Lab (Floor 3)
  - IT → IT Room (Floors 1-2, balanced)
  - Reception → Reception (Floors 1-2, balanced)
  - Storage → Storage (Floors 1-2, balanced)
  - Training → Training Rooms (Floors 1-2, with Floor 4 overflow)
  - Engineering → Focus Pods (Floor 3) or traditional spaces
  - Product → Collaboration Lounge, War Room (Floor 3), or traditional spaces
  - Marketing → Hotdesk (Floor 3), Collaboration Lounge, or traditional spaces
- Manages room assignments for existing employees
- Balances capacity across floors and room types

#### 4. `business/`
Business logic managers:

**`financial_manager.py`**:
- Tracks revenue and expenses
- Calculates profit
- Records financial transactions
- Links finances to projects
- Provides period-based financial analytics

**`project_manager.py`**:
- Creates and manages projects
- Calculates project progress
- Detects stalled projects
- Manages project tasks

**`goal_system.py`**:
- Defines business goals
- Tracks goal progress
- Evaluates goal completion

**`review_manager.py`**:
- Manages employee performance reviews
- Tracks review ratings and feedback
- Generates review recommendations
- Updates performance awards based on review ratings

**`customer_review_manager.py`**:
- Generates AI-powered customer reviews for completed projects
- Creates realistic customer profiles (name, title, company)
- Generates review text using LLM based on project details and rating
- Manages review statistics and aggregations
- Reviews generated 24 hours after project completion (configurable)

**`meeting_manager.py`**:
- Generates and manages meetings with employees
- Creates meeting schedules (3-8 meetings per day)
- Generates AI-powered meeting agendas and outlines
- Manages meeting status (scheduled → in_progress → completed)
- Generates live meeting transcripts with real-time updates
- Creates meeting content every 5 seconds for active meetings
- Supports multiple meeting types (standup, review, strategy, etc.)

**`boardroom_manager.py`**:
- Manages boardroom executive rotation and discussions
- Rotates executives every 30 minutes (up to 7 executives, CEO always stays)
- Generates strategic boardroom discussions every 2 minutes
- Uses LLM to create contextual discussions between executives
- Tracks boardroom state and executive assignments
- Supports 40+ strategic discussion topics

#### 5. `database/`
Database layer:

**`database.py`**:
- Database connection setup
- Async session management
- Table initialization

**`models.py`**: SQLAlchemy models
- `Employee`: Employee data with room tracking
- `Project`: Project information
- `Task`: Task assignments
- `Activity`: Activity log
- `Financial`: Financial transactions
- `Email`: Email messages
- `ChatMessage`: Chat messages
- `Decision`: Employee decisions
- `BusinessMetric`: Business metrics
- `BusinessSettings`: Business configuration
- `EmployeeReview`: Employee performance reviews
- `Notification`: System notifications
- `CustomerReview`: Customer reviews for completed projects
- `Meeting`: Meeting records with schedules, attendees, agendas, and transcripts

#### 6. `api/`
API endpoints:

**`routes.py`**: REST API endpoints
- `/api/employees`: Get all employees
- `/api/employees/{id}`: Get employee details
- `/api/employees/{id}/reviews`: Get employee reviews
- `/api/employees/{id}/reviews` (POST): Create employee review
- `/api/employees/waiting-status`: Get employees in waiting state
- `/api/employees/fix-waiting` (POST): Fix employees stuck in waiting state
- `/api/projects`: Get all projects
- `/api/projects/{id}`: Get project details
- `/api/projects/{id}/activities`: Get project activities
- `/api/tasks`: Get all tasks
- `/api/tasks/{id}`: Get task details
- `/api/tasks/{id}/activities`: Get task activities
- `/api/dashboard`: Dashboard data
- `/api/financials`: Financial data
- `/api/financials/analytics`: Comprehensive financial analytics
- `/api/activities`: Activity feed
- `/api/office-layout`: Office layout with employees
- `/api/emails`: Email messages
- `/api/chats`: Chat messages
- `/api/chats/send` (POST): Send chat message
- `/api/notifications`: Get all notifications
- `/api/notifications/unread-count`: Get unread notification count
- `/api/notifications/{id}/read` (POST): Mark notification as read
- `/api/notifications/read-all` (POST): Mark all notifications as read
- `/api/boardroom/generate-discussions` (POST): Generate boardroom discussions
- `/api/customer-reviews`: Get customer reviews (with optional project filter)
- `/api/customer-reviews/generate` (POST): Generate customer reviews for completed projects
- `/api/customer-reviews/stats`: Get customer review statistics
- `/api/meetings`: Get all meetings
- `/api/meetings/{meeting_id}`: Get specific meeting details
- `/api/employees/{employee_id}/award-message`: Get performance award message for employee
- `/api/employees/{employee_id}/thoughts`: Get AI-generated thoughts from employee's perspective
- `/api/employees/initialize-award` (POST): Initialize performance award system
- `/api/reviews/debug`: Debug endpoint to see all reviews in the database
- `/api/reviews/award-diagnostic`: Diagnostic endpoint to check award assignment

**`websocket.py`**: WebSocket handler
- Manages WebSocket connections
- Broadcasts real-time updates
- Handles connection lifecycle

#### 7. `llm/ollama_client.py`
Ollama LLM client:
- Connects to local Ollama instance
- Sends prompts to LLM
- Returns structured responses
- Handles errors and retries

#### 8. `engine/movement_system.py`
Employee movement system with capacity management:
- `determine_target_room()`: Determines target room based on activity type and description
  - Meetings → Conference Rooms (balanced across floors), Huddle Rooms (Floor 3), or War Room (Floor 3)
  - Breaks → Breakrooms, Lounges, HR Wellness (Floor 3), or Theater (Floor 3)
  - Training → Training Rooms (with Floor 4 overflow support)
  - Storage needs → Storage rooms (on employee's floor)
  - IT work → IT rooms (on employee's assigned floor)
  - Reception work → Reception (on employee's assigned floor)
  - Collaboration → Collaboration Lounge (Floor 3), Conference Rooms, Open Office, or Cubicles
  - Respects employee's floor assignment
- `get_room_capacity()`: Returns capacity for each room (varies by room type and floor)
- `check_room_has_space()`: Checks if a room has available space before allowing entry
- `get_room_occupancy()`: Gets current number of employees in a room
- `update_employee_location()`: Updates employee location with capacity checks
  - Employees wait if target room is full (activity_state = "waiting")
  - Updates floor assignment when moving between floors
  - Handles overflow to cubicles when home rooms are full
- `process_employee_movement()`: Main movement processing function
  - Handles training room time limits (1 hour max)
  - Enforces work area requirements for IT, Reception, and Storage employees
  - Manages random movement for office liveliness
  - Processes waiting employees when rooms become available
- `should_move_to_home_room()`: Determines if employee should return to home room
- `get_random_movement()`: Generates occasional random movement (reduced for IT/Reception/Storage)

### Simulation Flow

1. **Startup**: 
   - Database initialized
   - Employees loaded and assigned to rooms/floors if not already assigned
   - Simulation started
2. **Simulation Loop** (every 8 seconds):
   - Gather business context (revenue, projects, employees, goals)
   - Process up to 3 employees per tick
   - For each employee:
     - Create employee agent based on role
     - Evaluate situation using LLM
     - Execute decision (task work, communication, project creation, etc.)
     - Process movement based on activity:
       - Determine target room based on activity type
       - Check room capacity
       - Update location (or set to waiting if room full)
       - Update floor if moving between floors
     - Record activity in database
   - **Boardroom Discussions** (every 2 minutes / 15 ticks):
     - Check if rotation is needed (every 30 minutes)
     - Select up to 7 executives for boardroom (CEO always included)
     - Generate 3-6 strategic discussions between executive pairs
     - Use LLM to create contextual business discussions
     - Create chat messages with thread IDs
   - Broadcast updates via WebSocket
3. **Employee Decision Making**:
   - Employee agent evaluates current situation (tasks, projects, business state)
   - LLM generates decision based on role, personality, backstory, and context
   - Decision executed (task work, communication, project creation, etc.)
   - Activity recorded in database
4. **Room Movement**:
   - Activity type determines target room
   - Room capacity checked before movement
   - Employees wait if target room is full
   - Floor updated when moving between floors
   - Special handling for IT, Reception, and Storage employees (must stay in work areas)
   - Training room time limits enforced (1 hour max)
5. **Boardroom System**:
   - Executive rotation occurs every 30 minutes
   - Up to 7 executives selected (CEO always stays, others rotate)
   - Strategic discussions generated every 2 minutes
   - 40+ discussion topics covering business strategy, operations, growth, etc.
   - LLM generates contextual messages based on:
     - Executive personalities and roles
     - Current business metrics (revenue, profit, projects, employees)
     - Discussion topic
     - Other executives present in the room
   - Boardroom mood calculated from discussion sentiment
   - Discussions stored as chat messages with thread IDs
6. **Real-time Updates**:
   - All activities broadcast to connected WebSocket clients
   - Frontend receives updates and refreshes UI
   - Room occupancy updates in real-time
   - Boardroom discussions appear in real-time

---

## Frontend Components

### Structure

```
frontend/src/
├── App.jsx                 # Main app component with routing
├── main.jsx                # Entry point
├── index.css               # Global styles
├── components/             # Reusable components
│   ├── EmployeeAvatar.jsx  # Employee avatar display
│   ├── OfficeLayout.jsx    # Office layout visualization
│   ├── RoomDetailModal.jsx # Room detail modal
│   ├── ChatView.jsx        # Chat message view
│   ├── EmailView.jsx       # Email message view
│   ├── BoardroomView.jsx   # Boardroom discussions view
│   ├── EmployeeChat.jsx    # Employee chat component
│   ├── EmployeeChatModal.jsx # Employee chat modal
│   └── Notifications.jsx   # Notifications component
├── pages/                  # Page components
│   ├── Dashboard.jsx      # Main dashboard
│   ├── Employees.jsx      # Employee list
│   ├── EmployeeDetail.jsx # Employee detail page
│   ├── Projects.jsx       # Project list
│   ├── ProjectDetail.jsx  # Project detail page
│   ├── Financials.jsx     # Financial reports
│   ├── OfficeView.jsx     # Office layout view
│   └── Communications.jsx # Email and chat view
├── hooks/                  # Custom React hooks
│   └── useWebSocket.js    # WebSocket connection hook
└── utils/                  # Utility functions
    └── avatarMapper.js    # Avatar path mapping
```

### Key Components

#### `App.jsx`
Main application component with React Router setup:
- Routes to different pages
- Navigation sidebar
- WebSocket connection management

#### `pages/Dashboard.jsx`
Main dashboard showing:
- Business metrics (revenue, profit, expenses)
- Active projects count
- Employee count
- Recent activities feed
- Business goals with progress

#### `pages/Employees.jsx`
Employee management:
- List of all employees
- Filter by status (active/fired)
- Click to view details
- Employee avatars

#### `pages/EmployeeDetail.jsx`
Employee detail view:
- Employee information (name, title, role, backstory)
- Recent activities
- Decisions made
- Current task
- Room location

#### `pages/OfficeView.jsx`
Office layout visualization:
- Multi-floor navigation (Floors 1-4)
- All rooms with images organized by floor
- Employees in each room with real-time location tracking
- Room capacity and current occupancy
- Floor-specific rooms:
  - **Floor 1**: Open Office, Cubicles, Conference Room, Breakroom, Reception, IT Room, Manager Office, Training Room, Lounge, Storage
  - **Floor 2**: Executive Suite, Cubicles, Breakroom, Conference Room, Training Room, IT Room, Storage, Lounge, HR Room, Sales Room
  - **Floor 3**: Innovation Lab, Hotdesk, Focus Pods, Collaboration Lounge, War Room, Design Studio, HR Wellness, Theater, Huddle, Corner Executive
  - **Floor 4**: Training overflow floor with 5 Training Rooms and 5 Cubicle areas
- Click room to see details (employees, capacity, recent activities)
- Terminated employees section
- Real-time updates as employees move between rooms

#### `pages/Projects.jsx`
Project management:
- List of all projects
- Project status and progress
- Filter by status
- Click to view details

#### `pages/ProjectDetail.jsx`
Project detail view:
- Project information
- Tasks and progress
- Financial data
- Timeline

#### `pages/Financials.jsx`
Enhanced financial reports with comprehensive analytics:
- Summary cards: Total Income, Total Expenses (including payroll), Net Profit, Total Payroll
- Financial trends line chart: Income, expenses, and profit over time
- Expense breakdown pie chart: Categorized expenses (Payroll, Facilities, Equipment, Marketing, etc.)
- Income sources pie chart: Revenue breakdown by source
- Payroll by role bar chart: Payroll costs by employee role
- Payroll by department bar chart: Payroll costs by department
- Employee payroll details table: Individual employee salary information
- Period selector: View data for 30, 60, 90, 180, or 365 days
- Financial transactions list: Detailed transaction history

#### `pages/Communications.jsx`
Communication hub:
- Email inbox view
- Chat messages view
- Filter by employee
- Message threads

#### `pages/CustomerReviews.jsx`
Customer reviews dashboard:
- Summary cards (total reviews, average rating, products reviewed, verified purchases)
- Rating distribution pie chart
- Reviews by product bar chart
- Filter by rating and project
- Detailed review cards with customer information and ratings

#### `components/CalendarView.jsx`
Meeting calendar view:
- Day, week, and month views
- Meeting scheduling and status tracking
- Click to view meeting details
- Join live meetings directly from calendar
- Color-coded meeting status (scheduled, in-progress, completed)

#### `components/LiveMeetingView.jsx`
Live meeting interface:
- Video-style grid layout with attendee avatars
- Real-time transcript sidebar
- Live message bubbles appearing above speakers
- Active speaker highlighting
- Auto-scrolling transcript
- Meeting metadata and status

#### `components/MeetingDetail.jsx`
Meeting detail view:
- Meeting information (title, description, agenda, outline)
- Attendee list with avatars
- Meeting transcript (live or final)
- Meeting status and timing

#### `components/PerformanceAwardModal.jsx`
Performance award display:
- Award winner information
- Performance rating badge
- AI-generated congratulatory message from manager
- Award win statistics
- Visual award presentation

#### `components/BoardroomView.jsx`
Boardroom visualization and management:
- Visual boardroom scene with executives positioned around a table
- Executive rotation display (up to 7 executives, CEO always present)
- Real-time boardroom mood indicator based on discussion sentiment
- Discussion log showing all boardroom conversations
- Auto-generation of strategic discussions every 2 minutes
- Executive selection and rotation tracking (30-minute intervals)
- Chat bubble animations for live discussions

#### `pages/Tasks.jsx`
Task management:
- List of all tasks across projects
- Filter by status, priority, employee, or project
- Task progress tracking
- Click to view task details

#### `pages/TaskDetail.jsx`
Task detail view:
- Task information and status
- Assigned employee details
- Associated project information
- Task progress and completion status
- Activity history for the task

#### `hooks/useWebSocket.js`
WebSocket hook for real-time updates:
- Connects to backend WebSocket
- Listens for activity updates
- Provides connection status
- Handles reconnection

---

## Database Schema

### Tables

#### `employees`
- `id`: Primary key
- `name`: Employee name
- `title`: Job title
- `role`: CEO, Manager, or Employee
- `hierarchy_level`: 1 (CEO), 2 (Manager), 3 (Employee)
- `department`: Department name
- `status`: active, busy, idle, fired
- `current_task_id`: Foreign key to tasks
- `personality_traits`: JSON array
- `backstory`: Text description
- `avatar_path`: Path to avatar image
- `current_room`: Current room location (with floor suffix if applicable)
- `home_room`: Assigned home room (with floor suffix if applicable)
- `floor`: Floor number (1, 2, 3, or 4)
- `activity_state`: idle, working, walking, meeting, break, training, waiting
- `has_performance_award`: Boolean (whether employee currently holds performance award)
- `performance_award_wins`: Integer (number of times employee has won the award)
- `hired_at`: Timestamp
- `fired_at`: Timestamp (nullable)
- `created_at`: Timestamp

#### `projects`
- `id`: Primary key
- `name`: Project name
- `description`: Project description
- `status`: planning, active, completed, cancelled
- `priority`: low, medium, high
- `budget`: Budget amount
- `revenue`: Revenue generated
- `deadline`: Deadline (nullable)
- `last_activity_at`: Timestamp
- `created_at`: Timestamp

#### `tasks`
- `id`: Primary key
- `employee_id`: Foreign key to employees
- `project_id`: Foreign key to projects
- `description`: Task description
- `status`: pending, in_progress, completed, cancelled
- `priority`: low, medium, high
- `progress`: 0.0 to 100.0
- `created_at`: Timestamp
- `completed_at`: Timestamp (nullable)

#### `activities`
- `id`: Primary key
- `employee_id`: Foreign key to employees
- `activity_type`: Type of activity
- `description`: Activity description
- `activity_metadata`: JSON metadata
- `timestamp`: Timestamp

#### `financials`
- `id`: Primary key
- `type`: income or expense
- `amount`: Amount
- `description`: Description
- `project_id`: Foreign key to projects (nullable)
- `timestamp`: Timestamp

#### `emails`
- `id`: Primary key
- `sender_id`: Foreign key to employees
- `recipient_id`: Foreign key to employees
- `subject`: Email subject
- `body`: Email body
- `read`: Boolean
- `timestamp`: Timestamp

#### `chat_messages`
- `id`: Primary key
- `sender_id`: Foreign key to employees (nullable)
- `recipient_id`: Foreign key to employees (nullable)
- `message`: Message text
- `thread_id`: Thread identifier for grouping related messages
- `timestamp`: Timestamp

#### `employee_reviews`
- `id`: Primary key
- `employee_id`: Foreign key to employees (employee being reviewed)
- `manager_id`: Foreign key to employees (manager conducting review)
- `review_date`: Review date
- `overall_rating`: Overall rating (1.0 to 5.0)
- `performance_rating`: Performance rating (1.0 to 5.0, nullable)
- `teamwork_rating`: Teamwork rating (1.0 to 5.0, nullable)
- `communication_rating`: Communication rating (1.0 to 5.0, nullable)
- `productivity_rating`: Productivity rating (1.0 to 5.0, nullable)
- `comments`: Review comments (nullable)
- `strengths`: Employee strengths (nullable)
- `areas_for_improvement`: Areas for improvement (nullable)
- `review_period_start`: Start of review period (nullable)
- `review_period_end`: End of review period (nullable)
- `created_at`: Timestamp

#### `customer_reviews`
- `id`: Primary key
- `project_id`: Foreign key to projects
- `customer_name`: Customer name
- `customer_title`: Customer job title
- `company_name`: Customer company name
- `rating`: Rating (1.0 to 5.0)
- `review_text`: Review text content
- `verified_purchase`: Boolean (verified purchase status)
- `helpful_count`: Number of helpful votes
- `created_at`: Timestamp

#### `meetings`
- `id`: Primary key
- `title`: Meeting title
- `description`: Meeting description
- `organizer_id`: Foreign key to employees (meeting organizer)
- `attendee_ids`: JSON array of employee IDs
- `start_time`: Meeting start time
- `end_time`: Meeting end time
- `status`: scheduled, in_progress, completed, cancelled
- `agenda`: Meeting agenda (text)
- `outline`: Meeting outline (text)
- `transcript`: Final meeting transcript (text, nullable)
- `live_transcript`: Live meeting transcript (text, nullable)
- `meeting_metadata`: JSON metadata (live_messages, last_content_update, etc.)
- `created_at`: Timestamp
- `updated_at`: Timestamp

#### `notifications`
- `id`: Primary key
- `notification_type`: Type of notification (review_completed, raise_recommendation, employee_fired, etc.)
- `title`: Notification title
- `message`: Notification message
- `employee_id`: Foreign key to employees (related employee, nullable)
- `review_id`: Foreign key to employee_reviews (related review, nullable)
- `read`: Boolean (read status)
- `created_at`: Timestamp

#### `decisions`
- `id`: Primary key
- `employee_id`: Foreign key to employees
- `decision_type`: strategic, tactical, operational
- `description`: Decision description
- `reasoning`: Decision reasoning
- `timestamp`: Timestamp

#### `business_metrics`
- `id`: Primary key
- `metric_name`: Metric name
- `value`: Metric value
- `timestamp`: Timestamp

#### `business_settings`
- `id`: Primary key
- `setting_key`: Setting key (unique)
- `setting_value`: Setting value
- `updated_at`: Timestamp

---

## API Reference

### Base URL
```
http://localhost:8000/api
```

### Endpoints

#### Employees

**GET `/api/employees`**
Returns list of all employees.

**Response:**
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "title": "Chief Executive Officer",
    "role": "CEO",
    "hierarchy_level": 1,
    "department": "Executive",
    "status": "active",
    "current_room": "manager_office",
    "home_room": "manager_office",
    "activity_state": "working",
    "personality_traits": ["strategic", "decisive"],
    "backstory": "...",
    "avatar_path": "/avatars/office_char_01_manager.png"
  }
]
```

**GET `/api/employees/{employee_id}`**
Returns detailed employee information including activities and decisions.

**Response:**
```json
{
  "id": 1,
  "name": "John Doe",
  "title": "Chief Executive Officer",
  "role": "CEO",
  "activities": [...],
  "decisions": [...]
}
```

#### Projects

**GET `/api/projects`**
Returns list of all projects.

**GET `/api/projects/{project_id}`**
Returns detailed project information including tasks.

#### Dashboard

**GET `/api/dashboard`**
Returns dashboard data including metrics, activities, and goals.

**Response:**
```json
{
  "business_name": "TechFlow Solutions",
  "revenue": 150000.0,
  "profit": 50000.0,
  "expenses": 100000.0,
  "active_projects": 5,
  "employee_count": 20,
  "recent_activities": [...],
  "goals": [...],
  "goal_progress": {...}
}
```

#### Financials

**GET `/api/financials?days=30`**
Returns financial transactions for the specified number of days.

**Response:**
```json
[
  {
    "id": 1,
    "type": "income",
    "amount": 5000.0,
    "description": "Project revenue",
    "project_id": 1,
    "timestamp": "2024-01-01T12:00:00Z"
  }
]
```

**GET `/api/financials/analytics?days=90`**
Returns comprehensive financial analytics including payroll, trends, and breakdowns.

**Response:**
```json
{
  "summary": {
    "total_income": 150000.0,
    "total_expenses": 120000.0,
    "net_profit": 30000.0,
    "payroll": 80000.0,
    "period_days": 90
  },
  "payroll": {
    "total": 80000.0,
    "by_role": {
      "CEO": 37500.0,
      "Manager": 25000.0,
      "Employee": 17500.0
    },
    "by_department": {
      "Engineering": 30000.0,
      "Sales": 20000.0,
      "Marketing": 15000.0
    },
    "employee_count": 15
  },
  "expense_categories": {
    "Payroll": 80000.0,
    "Facilities": 20000.0,
    "Equipment & Software": 15000.0,
    "Marketing": 5000.0
  },
  "income_sources": {
    "Project Revenue": 120000.0,
    "Product Sales": 20000.0,
    "Services": 10000.0
  },
  "daily_trends": [
    {
      "date": "2024-01-01",
      "income": 5000.0,
      "expenses": 3000.0,
      "profit": 2000.0
    }
  ],
  "employee_details": [
    {
      "id": 1,
      "name": "John Doe",
      "role": "CEO",
      "department": "Executive",
      "hierarchy_level": 1,
      "estimated_annual_salary": 150000.0,
      "period_salary": 37500.0
    }
  ]
}
```

#### Activities

**GET `/api/activities?limit=50`**
Returns recent activities.

#### Office Layout

**GET `/api/office-layout`**
Returns office layout with employees in each room.

**Response:**
```json
{
  "rooms": [
    {
      "id": "open_office",
      "name": "Open Office",
      "image_path": "/office_layout/layout01_open_office.png",
      "capacity": 20,
      "employees": [...]
    }
  ],
  "terminated_employees": [...],
  "total_employees": 20
}
```

#### Communications

**GET `/api/emails?limit=100`**
Returns all emails.

**GET `/api/employees/{employee_id}/emails`**
Returns emails for a specific employee.

**GET `/api/chats?limit=200`**
Returns all chat messages.

**GET `/api/employees/{employee_id}/chats`**
Returns chat messages for a specific employee.

**POST `/api/chats/send`**
Send a chat message.

**Request Body:**
```json
{
  "employee_id": 1,
  "message": "Hello, how are you?"
}
```

#### Tasks

**GET `/api/tasks`**
Returns all tasks with employee and project information.

**GET `/api/tasks/{task_id}`**
Returns detailed task information.

**GET `/api/tasks/{task_id}/activities`**
Returns activities related to a specific task.

#### Employee Reviews

**GET `/api/employees/{employee_id}/reviews`**
Returns all reviews for a specific employee.

**POST `/api/employees/{employee_id}/reviews`**
Creates a new employee review.

**Request Body:**
```json
{
  "manager_id": 2,
  "overall_rating": 4.5,
  "performance_rating": 4.0,
  "teamwork_rating": 5.0,
  "communication_rating": 4.5,
  "productivity_rating": 4.0,
  "comments": "Excellent work this quarter",
  "strengths": "Strong communication skills",
  "areas_for_improvement": "Could improve time management",
  "review_period_start": "2024-01-01T00:00:00Z",
  "review_period_end": "2024-03-31T23:59:59Z"
}
```

#### Notifications

**GET `/api/notifications`**
Returns all notifications.

**GET `/api/notifications/unread-count`**
Returns the count of unread notifications.

**POST `/api/notifications/{notification_id}/read`**
Marks a notification as read.

**POST `/api/notifications/read-all`**
Marks all notifications as read.

#### Boardroom

**POST `/api/boardroom/generate-discussions`**
Generates boardroom discussions for strategic planning.

**Request Body (optional):**
```json
{
  "executive_ids": [1, 2, 3, 4, 5, 6, 7]
}
```

If `executive_ids` is not provided, the system automatically selects executives from the current boardroom rotation.

**Response:**
```json
{
  "success": true,
  "message": "Generated 5 boardroom discussions",
  "chats_created": 5
}
```

**How it works:**
- Selects executives currently in the boardroom (rotated every 30 minutes)
- Generates 3-6 strategic discussions between random executive pairs
- Uses LLM to create contextual, business-focused messages
- Covers 40+ strategic topics including revenue growth, market expansion, resource allocation, etc.
- Creates chat messages with thread IDs for conversation tracking

#### Customer Reviews

**GET `/api/customer-reviews?limit=100&project_id=1`**
Returns customer reviews, optionally filtered by project.

**Response:**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "project_name": "Project Alpha",
    "customer_name": "Sarah Johnson",
    "customer_title": "VP of Engineering",
    "company_name": "Acme Tech",
    "rating": 4.5,
    "review_text": "Great product! We've been using it for 3 months...",
    "verified_purchase": true,
    "helpful_count": 5,
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

**POST `/api/customer-reviews/generate?hours_since_completion=24.0`**
Generates customer reviews for completed projects. Reviews are generated 24 hours after project completion by default.

**Response:**
```json
{
  "success": true,
  "message": "Generated 12 customer review(s)",
  "reviews_created": 12
}
```

**GET `/api/customer-reviews/stats`**
Returns statistics about customer reviews.

**Response:**
```json
{
  "total_reviews": 50,
  "average_rating": 4.2,
  "rating_distribution": {
    "5.0": 20,
    "4.0": 15,
    "3.0": 10,
    "2.0": 3,
    "1.0": 2
  },
  "reviews_by_project": {
    "Project Alpha": {
      "count": 8,
      "average_rating": 4.5
    }
  }
}
```

#### Meetings

**GET `/api/meetings`**
Returns all meetings ordered by start time.

**Response:**
```json
[
  {
    "id": 1,
    "title": "Team Standup: Engineering",
    "description": "Daily team synchronization and progress updates",
    "organizer_id": 1,
    "organizer_name": "John Doe",
    "attendee_ids": [1, 2, 3],
    "attendee_names": ["John Doe", "Jane Smith", "Bob Johnson"],
    "start_time": "2024-01-01T09:00:00Z",
    "end_time": "2024-01-01T09:30:00Z",
    "status": "in_progress",
    "agenda": "1. Review yesterday's progress\n2. Discuss blockers\n3. Plan today's work",
    "outline": "I. Introduction\nII. Progress Review\nIII. Action Items",
    "transcript": null,
    "live_transcript": "[09:00:15] John Doe: Let's start the standup...",
    "meeting_metadata": {
      "live_messages": [
        {
          "sender_id": 1,
          "sender_name": "John Doe",
          "message": "Let's start the standup",
          "timestamp": "2024-01-01T09:00:15Z"
        }
      ],
      "last_content_update": "2024-01-01T09:00:20Z"
    }
  }
]
```

**GET `/api/meetings/{meeting_id}`**
Returns detailed information about a specific meeting.

**POST `/api/meetings/generate`**
Generates new meetings for the current day.

**Response:**
```json
{
  "success": true,
  "message": "Generated 5 meetings",
  "meetings_created": 5
}
```

**POST `/api/meetings/generate-now`**
Generates meetings for the last week, today, and creates an in-progress meeting if none exists. Useful for populating meeting data quickly.

**POST `/api/meetings/schedule-in-15min`**
Schedules a meeting to start in 15 minutes with random attendees.

**POST `/api/meetings/schedule-in-1min`**
Schedules a meeting to start in 1 minute with random attendees.

**POST `/api/meetings/force-update`**
Forces immediate update of all in-progress meetings, bypassing background tasks. Useful for testing and debugging.

**POST `/api/meetings/cleanup-missed`**
Cleans up meetings that should have started but are still in "scheduled" status.

**DELETE `/api/meetings/{meeting_id}`**
Deletes a meeting by ID.

**Response:**
```json
{
  "success": true,
  "message": "Meeting 1 deleted successfully"
}
```

#### Performance Awards

**GET `/api/employees/{employee_id}/award-message`**
Returns the performance award message for an employee who currently holds the award.

**GET `/api/employees/{employee_id}/thoughts`**
Returns AI-generated thoughts from the employee's perspective based on their recent activities and current situation.

**Response:**
```json
{
  "employee_id": 1,
  "employee_name": "John Doe",
  "thoughts": "I've been working hard on the new project feature. The team seems to be making good progress, but I'm concerned about the deadline..."
}
```

**GET `/api/reviews/debug`**
Debug endpoint to see all reviews in the database with employee information.

**GET `/api/reviews/award-diagnostic`**
Diagnostic endpoint to check who should have the performance award versus who actually has it. Useful for troubleshooting award assignment issues.

**Response:**
```json
{
  "employee_name": "Jane Smith",
  "manager_name": "John Doe",
  "manager_title": "VP of Engineering",
  "rating": 4.8,
  "award_wins": 2,
  "message": "Congratulations, Jane! Your exceptional performance..."
}
```

**POST `/api/employees/initialize-award`**
Initializes the performance award system by assigning the award to the employee with the highest review rating.

#### Employee Management

**GET `/api/employees/waiting-status`**
Returns employees currently in waiting state (rooms full).

**POST `/api/employees/fix-waiting`**
Fixes employees stuck in waiting state by reassigning them to available rooms.

---

## WebSocket Events

### Connection
Connect to `ws://localhost:8000/ws`

### Message Format
All messages are JSON objects with the following structure:

```json
{
  "type": "activity",
  "data": {
    "activity_type": "task_completed",
    "employee_id": 1,
    "description": "Completed task: Implement feature X",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

### Event Types

- `activity`: New activity occurred
- `employee_update`: Employee status changed
- `project_update`: Project status changed
- `financial_update`: Financial transaction occurred
- `review_completed`: Employee review completed
- `notification`: New notification created

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm
- Ollama installed and running
- Llama3.2 model downloaded

### Quick Setup

#### Windows
```bash
setup.bat
```

#### Linux/Mac
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup

1. **Create Python virtual environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate virtual environment:**
   - Windows: `venv\Scripts\activate.bat`
   - Linux/Mac: `source venv/bin/activate`

3. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Seed the database:**
   ```bash
   cd backend
   python seed.py
   cd ..
   ```

5. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

### Setting up Ollama

1. Install Ollama from https://ollama.ai
2. Pull the Llama3.2 model:
   ```bash
   ollama pull llama3.2
   ```
3. Ensure Ollama is running (default: http://localhost:11434)

### Starting a New Game

To start a completely new simulation with a fresh company, use the new game script:

#### Windows
```bash
new_game.bat
```

#### Linux/Mac
```bash
chmod +x new_game.sh
./new_game.sh
```

#### Manual
```bash
cd backend
python new_game.py
```

**What the script does:**

1. **Backup Option**: Prompts you to backup your current database before wiping
   - Backups are saved to `backend/backups/` with timestamps
   - Includes database file and WAL/SHM files if present

2. **Database Wipe**: Completely clears all data from all tables:
   - Customer reviews
   - Notifications
   - Employee reviews
   - Meetings
   - Chat messages
   - Emails
   - Activities
   - Decisions
   - Tasks
   - Financials
   - Business metrics
   - Business goals
   - Projects
   - Employees
   - Business settings

3. **LLM-Powered Company Generation**: Uses Ollama to generate:
   - **Company Name**: Creative, modern, and memorable
   - **Product/Service**: Specific product name and description
   - **Industry**: Industry sector (SaaS, FinTech, HealthTech, etc.)
   - **Management Team**: 
     - CEO with backstory and personality traits
     - CTO, COO, CFO with individual backstories
     - Product Manager, Marketing Manager, Engineering Manager
     - Initial employees

4. **Database Seeding**: Creates initial data:
   - All employees with generated names, titles, backstories, and personality traits
   - Initial projects related to the generated product
   - Financial records (seed funding, initial expenses)
   - Business settings (company name, product info, industry)

**Features:**
- All company data is generated using LLM (Ollama) for unique, creative businesses
- Robust JSON parsing with multiple fallback strategies
- Validates all required fields are present
- Clear progress messages during generation
- Graceful error handling with fallback data if LLM fails

---

## Configuration

### Environment Variables

Create a `.env` file in the `backend` directory:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
DATABASE_URL=sqlite+aiosqlite:///./office.db
```

### Database Configuration

The default database is SQLite (`office.db`). To use PostgreSQL:

1. Update `DATABASE_URL` in `.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
   ```

2. Install PostgreSQL driver:
   ```bash
   pip install asyncpg
   ```

### Simulation Settings

Simulation settings can be modified in `backend/engine/office_simulator.py`:
- `SIMULATION_TICK_INTERVAL`: Time between simulation ticks (default: 8 seconds)
- `EMPLOYEES_PER_TICK`: Number of employees processed per tick (default: 3)
- `MIN_EMPLOYEES`: Minimum number of employees required (default: 15)

### Room Capacity Settings

Room capacity settings are defined in `backend/engine/movement_system.py` in the `get_room_capacity()` function:

**Floor 1:**
- Open Office: 20
- Cubicles: 15
- Conference Room: 10
- Breakroom: 8
- Reception: 3
- IT Room: 5
- Manager Office: 6
- Training Room: 12
- Lounge: 10
- Storage: 2

**Floor 2:**
- Executive Suite: 8
- Cubicles: 20
- Breakroom: 10
- Conference Room: 12
- Training Room: 15
- IT Room: 6
- Storage: 3
- Lounge: 12
- HR Room: 6
- Sales Room: 10

**Floor 3:**
- Innovation Lab: 12
- Hotdesk: 18
- Focus Pods: 8
- Collaboration Lounge: 15
- War Room: 10
- Design Studio: 8
- HR Wellness: 6
- Theater: 20
- Huddle: 6
- Corner Executive: 4

**Floor 4 (Training Overflow):**
- Training Room 1-5: 20 each
- Cubicles 1-5: 25 each

---

## Development Guide

### Running the Application

#### Start Backend
```bash
cd backend
python main.py
```
Backend runs on http://localhost:8000

#### Start Frontend
```bash
cd frontend
npm run dev
```
Frontend runs on http://localhost:3000

### Project Structure

```
Business-Simulator/
├── backend/              # Python backend
│   ├── api/             # API routes and WebSocket
│   ├── business/        # Business logic managers
│   ├── database/        # Database models and setup
│   ├── employees/       # Employee agent system
│   ├── engine/          # Simulation engine
│   ├── llm/             # LLM client
│   ├── main.py          # FastAPI app entry point
│   ├── requirements.txt # Python dependencies
│   ├── new_game.py      # New game/simulation setup script
│   ├── seed.py          # Initial database seeding script
│   ├── test_meetings.py # Meeting system testing utility
│   ├── force_meeting_update.py # Force meeting update utility
│   └── [other utility scripts] # Additional utility scripts
├── frontend/            # React frontend
│   ├── src/
│   │   ├── components/ # Reusable components
│   │   ├── pages/      # Page components
│   │   ├── hooks/      # React hooks
│   │   └── utils/      # Utility functions
│   └── package.json    # Node dependencies
├── avatars/            # Employee avatar images
├── office_layout/      # Office layout images
├── .gitignore          # Git ignore rules
├── README.md           # Quick start guide
└── DOCUMENTATION.md    # This file
```

### Adding New Features

#### Adding a New API Endpoint

1. Add route in `backend/api/routes.py`:
   ```python
   @router.get("/new-endpoint")
   async def new_endpoint(db: AsyncSession = Depends(get_db)):
       # Implementation
       return {"message": "Success"}
   ```

#### Adding a New Employee Role

1. Create new agent class in `backend/employees/roles.py`
2. Extend `EmployeeAgent` base class
3. Override `evaluate_situation()` and `execute_decision()` methods
4. Register in `create_employee_agent()` function

#### Adding a New Frontend Page

1. Create component in `frontend/src/pages/`
2. Add route in `frontend/src/App.jsx`
3. Add navigation link if needed

### Testing

Currently, the project doesn't include automated tests. To add tests:

1. **Backend tests**: Use `pytest` with `pytest-asyncio`
2. **Frontend tests**: Use `vitest` or `jest` with React Testing Library

---

## Deployment

### Production Build

#### Backend
The backend can be run with uvicorn in production:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For better performance, use a production ASGI server like Gunicorn with Uvicorn workers:
```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Frontend
Build the frontend for production:
```bash
cd frontend
npm run build
```

Serve the built files with a web server (nginx, Apache, etc.) or use a static file server.

### Docker Deployment (Future)

A Docker setup can be created with:
- Backend container (Python + FastAPI)
- Frontend container (Node.js build)
- Database container (PostgreSQL)
- Nginx reverse proxy

### Environment Considerations

- Use PostgreSQL instead of SQLite for production
- Set up proper CORS origins
- Use environment variables for sensitive data
- Enable HTTPS in production
- Set up proper logging
- Configure backup for database

---

## Troubleshooting

### Common Issues

#### Ollama Connection Issues

**Problem**: Employees not making decisions, LLM errors

**Solutions**:
- Verify Ollama is running: `ollama list`
- Check Ollama URL in `.env` or default `http://localhost:11434`
- Verify model is available: `ollama list`
- Test Ollama API: `curl http://localhost:11434/api/generate`

#### Database Issues

**Problem**: Database errors, missing tables

**Solutions**:
- Delete `office.db` and re-run `seed.py`
- Check database path in configuration
- Verify SQLite file permissions
- Check for database locks (close other connections)

#### Frontend Not Updating

**Problem**: UI not showing real-time updates

**Solutions**:
- Check browser console for WebSocket errors
- Verify backend is running on port 8000
- Check CORS settings if accessing from different origin
- Verify WebSocket connection in browser DevTools

#### Employees Not Moving

**Problem**: Employees stuck in one room

**Solutions**:
- Check `movement_system.py` logic
- Verify room assignments in database
- Check activity types triggering movement
- Review employee `activity_state` field
- Check if employees are in "waiting" state (room might be full)
- Verify floor assignments are correct
- Check if IT/Reception/Storage employees are correctly restricted to work areas
- Review room capacity settings

#### Simulation Not Running

**Problem**: No activities, employees idle

**Solutions**:
- Check backend logs for errors
- Verify simulation loop is running
- Check employee status (should be "active")
- Verify LLM is responding
- Check database connection

### Debugging Tips

1. **Enable verbose logging**: Add print statements or use Python logging
2. **Check database directly**: Use SQLite browser to inspect data
3. **Monitor WebSocket**: Use browser DevTools to see WebSocket messages
4. **Test LLM directly**: Use Ollama CLI to test model responses
5. **Check employee agents**: Review decision-making logic in `employees/roles.py`

### Performance Optimization

- Reduce simulation tick frequency if system is slow
- Process fewer employees per tick
- Use database indexes for frequently queried fields
- Optimize LLM prompts for faster responses
- Cache frequently accessed data

---

## License

MIT License

---

## Contributing

When contributing to this project:

1. Follow existing code style
2. Add comments for complex logic
3. Update documentation for new features
4. Test changes thoroughly
5. Keep commits focused and descriptive

---

## Support

For issues and questions:
- Check the troubleshooting section
- Review the code comments
- Check backend logs for errors
- Verify all prerequisites are installed correctly

---

*Last updated: January 2025*

## Utility Scripts

The project includes several utility scripts for testing and debugging:

### `backend/test_meetings.py`
Utility script to check meeting status and test the meeting system:
- Checks in-progress meetings
- Identifies scheduled meetings that should be active
- Tests LLM connection

**Usage:**
```bash
cd backend
python test_meetings.py
```

### `backend/force_meeting_update.py`
Forces an immediate update of in-progress meetings to test the meeting update system.

**Usage:**
```bash
cd backend
python force_meeting_update.py
```

### `backend/generate_meetings_now.py`
Generates meetings immediately for testing purposes.

### `backend/initialize_award.py`
Initializes the performance award system.

### `backend/check_db.py`
Database checking and validation utility.

## Customer Reviews System

The customer reviews system automatically generates realistic customer reviews for completed projects, providing feedback on products and services.

### Features

- **Automatic Generation**: Reviews are generated 24 hours after project completion (configurable)
- **AI-Powered Content**: Review text is generated using LLM based on project details and rating
- **Realistic Profiles**: Each review includes customer name, title, and company name
- **Rating Distribution**: Reviews use a realistic rating distribution (60% 4-5 stars, 30% 3-4 stars, 10% 1-3 stars)
- **Multiple Reviews**: 2-5 reviews generated per project
- **Statistics**: Comprehensive statistics including rating distribution and reviews by project

### How It Works

1. When a project is completed, the system tracks the completion time
2. After 24 hours (configurable), reviews are automatically generated
3. For each review:
   - Customer profile is generated (name, title, company)
   - Rating is assigned based on weighted distribution
   - Review text is generated using LLM with project context
   - Review is saved to database
4. Reviews can be viewed in the Customer Reviews page with filtering and statistics

### API Usage

Generate reviews manually:
```bash
POST /api/customer-reviews/generate?hours_since_completion=0
```

Get all reviews:
```bash
GET /api/customer-reviews?limit=100&project_id=1
```

## Meeting Management System

The meeting management system provides comprehensive meeting scheduling, tracking, and live transcript generation.

### Features

- **Meeting Generation**: Automatically generates 3-8 meetings per day
- **Multiple Meeting Types**: Team Standup, Project Review, Strategy Session, One-on-One, Department Meeting, Client Presentation, Sprint Planning, Retrospective, Budget Review, Performance Review, All-Hands, Training Session
- **AI-Generated Agendas**: Meeting agendas and outlines generated using LLM
- **Live Transcripts**: Real-time meeting transcripts with messages generated every 5 seconds
- **Status Management**: Automatic status updates (scheduled → in_progress → completed)
- **Calendar Views**: Day, week, and month calendar views
- **Live Meeting View**: Video-style interface with attendee avatars and real-time transcripts

### How It Works

1. **Meeting Generation**:
   - Meetings are generated automatically (3-8 per day)
   - Organizer is selected (prefer managers/executives)
   - Attendees are selected (2-8 people including organizer)
   - Meeting type and description are randomly selected
   - Agenda and outline are generated using LLM

2. **Status Updates**:
   - Meetings transition from "scheduled" to "in_progress" at start time
   - Live content is generated every 5 seconds for active meetings
   - Meetings transition to "completed" at end time
   - Final transcript is generated for completed meetings

3. **Live Content Generation**:
   - For in-progress meetings, new messages are generated every 5 seconds
   - Messages are created between random attendee pairs
   - LLM generates contextual messages based on:
     - Meeting agenda
     - Attendee personalities and roles
     - Business context
     - Recent conversation history
   - Messages are stored in `meeting_metadata.live_messages`
   - Live transcript is updated in real-time

### Frontend Components

- **CalendarView**: Calendar interface with day/week/month views
- **LiveMeetingView**: Video-style meeting interface with live transcripts
- **MeetingDetail**: Detailed meeting information view

## Performance Awards System

The performance awards system recognizes top-performing employees based on their review ratings.

### Features

- **Automatic Award Assignment**: Award is assigned to employee with highest review rating
- **Award Tracking**: Tracks number of times each employee has won the award
- **AI-Generated Messages**: Congratulatory messages generated by manager using LLM
- **Visual Presentation**: Award modal with employee information and rating badge

### How It Works

1. When a review is completed, the system checks if the employee's rating qualifies for the award
2. The award is assigned to the employee with the highest current review rating
3. If a new employee earns a higher rating, the award is transferred
4. Award wins are tracked per employee
5. Managers can generate congratulatory messages using the award API

### Database Fields

- `has_performance_award`: Boolean indicating if employee currently holds the award
- `performance_award_wins`: Integer tracking number of award wins

### API Usage

Initialize award system:
```bash
POST /api/employees/initialize-award
```

Get award message:
```bash
GET /api/employees/{employee_id}/award-message
```

## Boardroom System

The boardroom system provides a continuous strategic planning environment where executives (CEO and Managers) engage in AI-generated discussions about business strategy and operations.

### Executive Rotation

- **Rotation Schedule**: Executives rotate every 30 minutes
- **Room Capacity**: Up to 7 executives can be in the boardroom at once
- **CEO Status**: The CEO always remains in the boardroom (does not rotate out)
- **Selection Logic**: 
  - CEO is always included
  - Remaining 6 slots filled by random selection from available Managers
  - On rotation, current executives (except CEO) are excluded from selection to ensure variety
  - If fewer than 7 executives available, all are included

### Discussion Generation

- **Frequency**: Strategic discussions are generated every 2 minutes (15 simulation ticks)
- **Volume**: 3-6 discussions per generation cycle
- **Pair Selection**: Random pairs of executives are selected for each discussion
- **Topic Variety**: 40+ strategic topics including:
  - Strategic planning for revenue growth
  - Resource allocation for projects
  - Market expansion opportunities
  - Operational efficiency improvements
  - Team performance and productivity
  - Budget optimization strategies
  - Technology investment priorities
  - Customer acquisition initiatives
  - Competitive positioning analysis
  - Risk management and mitigation
  - And 30+ more strategic business topics

### LLM-Powered Discussions

Each discussion message is generated using the LLM with the following context:
- **Sender Information**: Name, title, role, personality traits
- **Recipient Information**: Name, title, role, personality traits
- **Room Context**: All executives currently in the boardroom
- **Business Context**: Current revenue, profit, active projects, employee count
- **Discussion Topic**: The specific strategic topic being discussed
- **Tone**: Conversational and direct, as if speaking face-to-face in a boardroom

### Boardroom Mood

The system calculates a "boardroom mood" based on recent discussion sentiment:
- **Positive Mood**: Discussions indicate optimism, growth, success
- **Neutral Mood**: Balanced discussions with mixed sentiment
- **Negative Mood**: Discussions indicate concerns, challenges, risks
- Mood is calculated from the last 20 boardroom messages
- Visual indicator shows mood with emoji and color coding

### Frontend Visualization

The boardroom view (`BoardroomView.jsx`) provides:
- **Visual Scene**: Executives positioned around a boardroom table
- **Executive Display**: Shows current executives in the room with avatars
- **Rotation Timer**: Countdown to next executive rotation
- **Mood Indicator**: Real-time mood display with emoji and description
- **Discussion Log**: Chronological list of all boardroom conversations
- **Chat Bubbles**: Animated chat bubbles appearing above executives during discussions
- **Auto-refresh**: Automatically updates as new discussions are generated

### API Integration

The boardroom system integrates with:
- **Chat Messages**: Discussions are stored as `ChatMessage` records with thread IDs
- **Employee System**: Uses employee data for executive selection and context
- **Business Context**: Pulls current business metrics for discussion context
- **WebSocket**: Boardroom updates broadcast in real-time to connected clients

### Configuration

Boardroom behavior can be adjusted in:
- `backend/business/boardroom_manager.py`: Rotation interval, room capacity, discussion topics
- `backend/engine/office_simulator.py`: Discussion generation frequency (currently every 15 ticks = 2 minutes)

## Office Layout Details

### Floor 1 (Main Floor)
- **Open Office**: 20 capacity - General workspace
- **Cubicles**: 15 capacity - Individual workspaces
- **Conference Room**: 10 capacity - Meetings
- **Breakroom**: 8 capacity - Breaks and meals
- **Reception**: 3 capacity - Front desk
- **IT Room**: 5 capacity - IT operations
- **Manager Office**: 6 capacity - Management workspace
- **Training Room**: 12 capacity - Training sessions
- **Lounge**: 10 capacity - Relaxation area
- **Storage**: 2 capacity - Storage and supplies

### Floor 2 (Executive & Department Floor)
- **Executive Suite**: 8 capacity - Senior executives
- **Cubicles**: 20 capacity - Individual workspaces
- **Breakroom**: 10 capacity - Breaks and meals
- **Conference Room**: 12 capacity - Larger meetings
- **Training Room**: 15 capacity - Training sessions
- **IT Room**: 6 capacity - IT operations
- **Storage**: 3 capacity - Storage and supplies
- **Lounge**: 12 capacity - Relaxation area
- **HR Room**: 6 capacity - Human Resources
- **Sales Room**: 10 capacity - Sales department

### Floor 3 (Innovation & Collaboration Floor)
- **Innovation Lab**: 12 capacity - Research and development
- **Hotdesk**: 18 capacity - Flexible workspace
- **Focus Pods**: 8 capacity - Quiet individual work
- **Collaboration Lounge**: 15 capacity - Team collaboration
- **War Room**: 10 capacity - Strategic planning
- **Design Studio**: 8 capacity - Design work
- **HR Wellness**: 6 capacity - Wellness and relaxation
- **Theater**: 20 capacity - Presentations and events
- **Huddle**: 6 capacity - Quick meetings
- **Corner Executive**: 4 capacity - CEO and top executives

### Floor 4 (Training Overflow Floor)
- **Training Room 1-5**: 20 capacity each - Training overflow
- **Cubicles 1-5**: 25 capacity each - Workspace overflow

### Room Assignment Logic

Employees are assigned to rooms based on:
1. **Role**: CEO → Corner Executive, Executives → Executive Suite
2. **Department**: Sales → Sales Room, HR → HR Room, IT → IT Room
3. **Specialization**: Design → Design Studio, R&D → Innovation Lab
4. **Capacity Balancing**: System distributes employees across floors to balance occupancy
5. **Floor Preference**: Certain roles prefer specific floors (e.g., executives on floors 2-3)

### Movement Rules

- **Meetings**: Automatically routed to Conference Rooms (balanced across floors), Huddle Rooms (small meetings), or War Room (strategic meetings)
- **Breaks**: Can use Breakrooms, Lounges, HR Wellness (Floor 3), or Theater (Floor 3)
- **Training**: Assigned to Training Rooms, with automatic overflow to Floor 4 when needed
- **Work**: Employees work in their home rooms, with overflow to cubicles if home room is full
- **Capacity Enforcement**: Employees wait if target room is full (activity_state = "waiting")
- **Special Employees**: IT, Reception, and Storage employees must stay in their work areas (only leave for breaks/meetings)
- **Floor Transitions**: Employee floor is automatically updated when moving between floors

