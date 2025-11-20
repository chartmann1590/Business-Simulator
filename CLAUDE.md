# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Autonomous Office Simulation** where AI employees make decisions, work on projects, and grow a business using local Ollama (Llama3.2 LLM). The office runs completely autonomously with no user interaction required. Key features include:

- **Fully autonomous operation**: Employees use LLM for decision-making based on role, personality, and backstory
- **Employee hierarchy**: CEO, Managers (CTO/COO/CFO), and Employees with different capabilities
- **Multi-floor office**: 4 floors with specialized rooms and intelligent assignment
- **Real-time web dashboard**: React frontend with WebSocket updates
- **Rich business simulation**: Projects, tasks, financials, meetings, reviews, communications, and more

## Tech Stack

### Backend
- **FastAPI** (async) with SQLAlchemy ORM
- **PostgreSQL** 12+ with asyncpg driver (connection pooling, query caching, optimized indexes)
- **Ollama API** for LLM integration (Llama3.2)
- **WebSocket** for real-time updates
- **Python 3.10+**

### Frontend
- **React 18** with Vite
- **React Router** for navigation
- **Recharts** for analytics visualizations
- **Tailwind CSS** for styling

## Development Commands

### Backend

```bash
# Setup database (first time)
cd backend
python setup_postgresql.py

# Seed initial data (first time or after reset)
python seed.py

# Start the backend server (runs on http://localhost:8000)
python main.py

# Start a new game with fresh company data
python new_game.py

# Migrate SQLite to PostgreSQL (if needed)
python migrate_data_sqlite_to_postgresql.py

# Utility scripts for testing/debugging
python test_meetings.py              # Check meeting status
python force_meeting_update.py       # Force meeting updates
python generate_meetings_now.py      # Generate test meetings
python initialize_award.py           # Initialize performance awards
python fix_stuck_training_sessions.py  # Fix stuck training sessions
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (runs on http://localhost:3000)
npm run dev

# Build for production
npm build

# Preview production build
npm run preview
```

### Environment Configuration

Create `backend/.env` file:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/office_db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
TIMEZONE=America/New_York
```

## Architecture Overview

### Backend Architecture

#### Core Simulation Loop (`backend/engine/office_simulator.py`)
- Main simulation runs every 8 seconds
- Processes up to 3 employees per tick
- Each employee evaluates situation and makes LLM-based decisions
- Handles movement system, room assignment, and activity broadcasting

#### Employee System (`backend/employees/`)
- **`base.py`**: `EmployeeAgent` class - handles decision-making, communication, and message responses
- **`roles.py`**: Role-specific behavior (CEO, Manager, Employee)
- **`room_assigner.py`**: Intelligent room assignment based on hierarchy, department, and capacity

#### Business Systems (`backend/business/`)
- **`project_manager.py`**: Project lifecycle management
- **`financial_manager.py`**: Revenue, expenses, payroll calculations
- **`meeting_manager.py`**: Meeting generation and lifecycle
- **`boardroom_manager.py`**: Executive discussions and strategic planning
- **`review_manager.py`**: Employee performance reviews
- **`customer_review_manager.py`**: AI-generated customer feedback
- **`training_manager.py`**: Training session management
- **`shared_drive_manager.py`**: Document generation and versioning
- **`birthday_manager.py`**, **`holiday_manager.py`**: Celebration systems
- **`clock_manager.py`**: Clock in/out and time tracking system
- **`sleep_manager.py`**: Sleep/wake cycle management for employees and families
- **`communication_manager.py`**: Communication system improvements
- **`activity_broadcaster.py`**: WebSocket activity broadcasting

#### Database (`backend/database/`)
- **`models.py`**: SQLAlchemy models for all entities (27+ tables)
- **`database.py`**: Connection pooling, retry logic, safe commit/flush helpers
- **`query_cache.py`**: In-memory query result caching
- **`bulk_operations.py`**: Batch database operations
- **`optimize_indexes.py`**: Performance optimization indexes

#### API Layer (`backend/api/`)
- **`routes.py`**: REST API endpoints with query caching
- **`websocket.py`**: WebSocket connection management for real-time updates

### Frontend Architecture

#### Pages (`frontend/src/pages/`)
- **Dashboard**: Business metrics, goals, recent activities
- **Employees**: Employee list with detailed views (backstory, tasks, reviews)
- **Products**: Product catalog with team members and reviews
- **Projects**: Project tracking with progress and financials
- **Tasks**: Task management with filtering
- **Financials**: Comprehensive analytics (revenue, expenses, payroll)
- **OfficeView**: Visual office layout across 4 floors
- **HomeView**: Employee home visualization with family and pets
- **Communications**: Email and chat hub
- **NotificationsHistory**: System notifications
- **CustomerReviews**: Customer feedback for completed projects
- **PetCareGame**: Interactive office pet system

#### Components (`frontend/src/components/`)
- **OfficeLayout**: Floor-by-floor room visualization
- **CalendarView**: Meeting calendar (day/week/month views)
- **LiveMeetingView**: Real-time meeting transcripts
- **BoardroomView**: Executive strategic discussions
- **SharedDriveView**: Document browser with version control
- **DocumentViewer**: HTML document viewer/editor
- **Various modals**: Detail views for employees, rooms, training, etc.

### Key Data Flow

1. **Simulation Tick** (every 8 seconds):
   - `OfficeSimulator.run()` → selects employees → creates `EmployeeAgent`
   - Agent evaluates situation → LLM decision → executes decision
   - Activity logged → broadcast via WebSocket → frontend updates

2. **Communication System**:
   - Employees generate emails/chats during decisions (85% chance)
   - Background task checks messages every 2 minutes
   - Recipients respond using LLM-generated content
   - Thread-based conversation tracking

3. **Room Movement**:
   - `movement_system.py` processes walking employees
   - Respects room capacity (employees wait if full)
   - Activity-based routing (meetings → conference rooms, breaks → lounges, training → training rooms)

4. **Business Operations**:
   - CEO creates projects and sets goals
   - Managers assign tasks and coordinate teams
   - Employees complete tasks → project progress → revenue generation
   - Financial records tracked for all transactions

## Database Schema Key Points

### Core Tables
- **employees**: Name, title, role, department, status, personality, backstory, room assignments, floor
- **projects**: Name, description, status, budget, revenue, product_id, deadline
- **tasks**: Description, employee_id, project_id, status, progress
- **decisions**: Employee decisions with reasoning
- **activities**: Activity log (broadcast to frontend)
- **financials**: Income/expense transactions

### Communication
- **emails**: Sender, recipient, subject, body, thread_id
- **chat_messages**: Instant messaging between employees
- **meetings**: Scheduled/in-progress/completed meetings with transcripts

### Reviews & Performance
- **employee_reviews**: Performance ratings, comments, strengths, areas for improvement
- **customer_reviews**: AI-generated customer feedback for products/projects
- **notifications**: System-wide notification system

### Office Management
- **shared_drive_files**: Documents with version control
- **training_sessions**: Training tracking with materials
- **office_pets**: Interactive pet care system
- **birthday_celebrations**, **holiday_celebrations**: Party scheduling

### Key Indexes
The database uses extensive indexing for performance:
- Composite indexes on frequently queried columns
- Status, timestamp, and foreign key indexes
- PostgreSQL-specific optimizations (see `POSTGRESQL_OPTIMIZATIONS.md`)

## Important Patterns & Conventions

### Database Operations
- Always use `async with async_session_maker() as db:` for database sessions
- Use `safe_commit()` or `safe_flush()` from `database.database` for automatic retry on lock errors
- Use `@cached_query(cache_duration=X)` decorator for frequently accessed data
- PostgreSQL connection pooling is pre-configured (50 persistent + 30 overflow = 80 total connections)
- Connection pool auto-recycles every 30 minutes to prevent staleness
- 60-second timeouts for connection acquisition and command execution

### LLM Integration
- All LLM calls go through `llm/ollama_client.py`
- Methods: `generate_decision()`, `generate_email()`, `generate_chat()`, `generate_email_response()`, etc.
- Prompts include personality traits, backstory, and business context for realistic behavior

### WebSocket Broadcasting
- Use `activity_broadcaster.py` functions: `broadcast_activity()`, `broadcast_employee_update()`, etc.
- All significant events should be broadcast to frontend
- Activity format: `{"type": "activity", "data": {...}}`

### Timezone Handling
- Use `config.now()` for timezone-aware current time (default: America/New_York)
- Configure via `TIMEZONE` environment variable
- Database stores UTC, converts on retrieval

### Employee Decision-Making
- Decisions based on role (CEO: strategic, Manager: tactical, Employee: operational)
- Each employee has personality traits and backstory that influence decisions
- 85% chance of communication per decision cycle
- Background task for message responses every 20 seconds (optimized from 2 minutes)
- Employees have online/offline status tracked in Teams

### Room System
- 4 floors with specialized rooms (executives on floor 3, training on floor 4)
- Room capacity tracking and overflow handling
- Activity-based movement (training → training rooms, meetings → conference rooms)
- Home room assignment based on role, title, and department

### Clock In/Out System
- Morning arrivals: 6:45am-7:45am (staggered timing)
- Evening departures: 6:45pm-7:15pm (staggered timing)
- Automatic state transitions: at_home → working → leaving_work → commuting_home → at_home
- Clock events logged in ClockInOut table
- Online status automatically updated (online at work, offline at home)

### Sleep System
- Bedtime: 10pm-12am (staggered for employees and families)
- Employee wake-up: 5:30am-6:45am (weekdays only)
- Family wake-up: 7:30am-9am (all days)
- Sleep state tracked for employees, family members, and pets
- Coordinated sleep: when employee sleeps, family and pets also sleep

### Home System
- Employees have homes with family members (spouses, children) and pets
- Home layout visualization (interior/exterior views)
- Home conversations generated using LLM
- Pet care system with happiness, hunger, and energy stats
- Family member activities and sleep states tracked

## Testing & Debugging

### Common Issues

1. **Stuck Training Sessions**: Run `backend/fix_stuck_training_sessions.py`
2. **Missing Meetings**: Run `backend/generate_meetings_now.py` or `backend/force_meeting_update.py`
3. **Database Lock Errors**: Automatically retried by `safe_commit()`/`safe_flush()`
4. **Ollama Connection**: Ensure Ollama is running on port 11434 with llama3.2 model

### Logging
- Backend logs to `backend/backend.log` (rotating, 5MB max, 10 files)
- Logs include simulation events, LLM calls, database operations
- Use `logger.info()`, `logger.error()` for proper logging (not `print()`)

### Monitoring
- Watch WebSocket console in browser DevTools for real-time events
- Check `backend/backend.log` for backend errors
- Use `test_meetings.py` to verify meeting system

## Documentation

- **README.md**: Setup instructions and feature overview
- **DOCUMENTATION.md**: Comprehensive system documentation (26k+ tokens)
- **POSTGRESQL_OPTIMIZATIONS.md**: Database performance details
- This file (CLAUDE.md): Architecture and development guide

## Performance Considerations

- Query caching reduces database load (15-30 second TTL)
- Connection pooling prevents connection exhaustion
- Bulk operations for batch inserts/updates
- Optimized indexes on all frequently queried columns
- Async/await throughout for non-blocking operations
- Background tasks for periodic operations (reviews, meetings, weather)

## Code Style Notes

- Backend: async/await everywhere, type hints preferred
- Frontend: Functional components with hooks
- Database: Use safe_commit()/safe_flush() wrappers, not raw commit()
- LLM calls: Always include error handling with fallbacks
- Activity broadcasting: Broadcast all user-visible changes immediately
