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
- **Notification System**: Real-time notifications for important events (reviews, raises, terminations)
- **Boardroom Discussions**: Strategic planning and decision-making sessions

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
5. **Real-time Updates**:
   - All activities broadcast to connected WebSocket clients
   - Frontend receives updates and refreshes UI
   - Room occupancy updates in real-time

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
│   └── requirements.txt # Python dependencies
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

