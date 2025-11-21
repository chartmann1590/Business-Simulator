# Autonomous Office Simulation

A fully autonomous office simulation where AI employees make decisions, work on projects, and grow the business using local Ollama and Llama3.2 LLM.

## Features

- **Fully Autonomous**: The office runs completely on its own - no user interaction required
- **AI-Powered Employees**: Each employee uses LLM to make decisions based on their role, personality, and backstory
- **Employee Hierarchy**: CEO, Managers, and Employees with proper 1:10 manager-to-employee ratio and reporting structure
- **Organizational Structure**: Complete organizational chart with manager-employee relationships
- **Multi-Floor Office System**: 4 floors with specialized rooms and intelligent room assignment
- **Smart Room Management**: Room capacity tracking, overflow handling, and intelligent movement
- **Real-time Web Interface**: Watch the office operate in real-time through a modern web dashboard
- **Rich Observability**: 
  - Dashboard with key metrics and business goals
  - Employee details with backstories, activities, and room locations
  - Product catalog with team members, sales, and customer reviews
  - Project tracking with progress and financial data
  - Task management with detailed task views
  - Comprehensive financial analytics with payroll breakdowns
  - Office layout visualization across all floors
  - Communication hub (email and chat)
  - Employee performance reviews and ratings
  - Performance awards system recognizing top performers
  - Notification system for important events
  - Boardroom discussions for strategic planning
  - Meeting management with calendar view and live transcripts
  - Customer reviews for completed projects
  - Activity feed with real-time updates

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 12+ installed and running
- Ollama installed and running locally
- Llama3.2 model downloaded in Ollama

### Setting up PostgreSQL

1. Install PostgreSQL:
   - **Windows**: Download from https://www.postgresql.org/download/windows/
   - **macOS**: `brew install postgresql`
   - **Linux**: `sudo apt-get install postgresql` (Ubuntu/Debian) or `sudo yum install postgresql` (CentOS/RHEL)

2. Start PostgreSQL service:
   - **Windows**: Check Services panel, start "postgresql" service
   - **macOS**: `brew services start postgresql`
   - **Linux**: `sudo systemctl start postgresql`

3. Setup the database:
   ```bash
   cd backend
   python setup_postgresql.py
   ```
   
   This will create the `office_db` database if it doesn't exist.

4. (Optional) Migrate existing SQLite data:
   If you have an existing SQLite database with data:
   ```bash
   cd backend
   python migrate_data_sqlite_to_postgresql.py
   ```

### Setting up Ollama

1. Install Ollama from https://ollama.ai
2. Pull the Llama3.2 model:
   ```bash
   ollama pull llama3.2
   ```
3. Ensure Ollama is running (default: http://localhost:11434)

## Setup

### Windows

Run the setup script:
```bash
setup.bat
```

### Linux/Mac

Run the setup script:
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup

1. Create Python virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate virtual environment:
   - Windows: `venv\Scripts\activate.bat`
   - Linux/Mac: `source venv/bin/activate`

3. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Setup PostgreSQL database:
   ```bash
   cd backend
   python setup_postgresql.py
   ```

5. Seed the database:
   ```bash
   cd backend
   python seed.py
   ```

6. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

## Running the Simulation

### Start the Backend

1. Activate the virtual environment
2. Navigate to backend directory:
   ```bash
   cd backend
   ```
3. Run the server:
   ```bash
   python main.py
   ```

The backend will start on http://localhost:8000

### Start the Frontend

In a new terminal:

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```

The frontend will start on http://localhost:3000

## Configuration

Create a `.env` file in the `backend` directory (optional):

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/office_db
```

## How It Works

1. **Simulation Loop**: Every 8 seconds, the system processes up to 3 employees per tick
2. **Decision Making**: Each employee evaluates their situation and uses the LLM to make decisions
3. **Role-Based Behavior**:
   - **CEO**: Makes strategic decisions, creates new projects, sets business goals
   - **Managers**: Plan projects, assign tasks, coordinate teams, make tactical decisions
   - **Employees**: Execute tasks, solve problems, collaborate, make operational decisions
4. **Room Assignment**: Employees are intelligently assigned to rooms across 4 floors based on:
   - Role and hierarchy (CEO gets corner executive office on floor 3)
   - Department (Sales → Sales Room, HR → HR Room, IT → IT Room)
   - Specialized needs (Design → Design Studio, R&D → Innovation Lab)
   - Capacity balancing across floors
5. **Movement System**: Employees move between rooms based on activities:
   - Meetings → Conference Rooms, Huddle Rooms, or War Room
   - Breaks → Breakrooms, Lounges, HR Wellness, or Theater
   - Training → Training Rooms (with overflow to floor 4)
   - Work → Home rooms or overflow to cubicles if full
   - Room capacity is respected - employees wait if rooms are full
6. **Business Growth**: Projects generate revenue, employees complete tasks, business metrics update
7. **Boardroom System**: 
   - Executives (CEO and Managers) rotate into boardroom every 30 minutes
   - Strategic discussions generated every 2 minutes using LLM
   - Discussions cover 40+ strategic topics (revenue growth, market expansion, resource allocation, etc.)
   - Boardroom mood calculated from discussion sentiment
8. **Real-time Updates**: All activities are broadcast via WebSocket to the frontend

## Employee System

Each employee has:
- **Name**: Unique identifier
- **Title**: Job title (e.g., "Chief Executive Officer")
- **Backstory**: Personal history that influences decision-making
- **Personality Traits**: Affects how they make decisions
- **Role**: Determines decision-making capabilities (CEO, Manager, Employee)
- **Floor Assignment**: Employees are assigned to floors 1-4 based on their role and department
- **Home Room**: Assigned workspace based on role, title, and department
- **Current Room**: Tracks real-time location as employees move between rooms
- **Activity State**: idle, working, walking, meeting, break, training, waiting, at_home, sleeping, leaving_work, commuting_home
- **Online Status**: Tracks employee online/offline status in Teams
- **Home System**: Employees have homes with family members and pets
- **Sleep Schedule**: Employees and family members have realistic sleep/wake cycles
- **Clock In/Out**: Automatic time tracking for arrivals and departures

## Observing the Simulation

The web interface provides several views:

- **Dashboard**: Overview of business metrics, recent activities, and goals
- **Employees**: Browse all employees, click to see details, backstories, activities, and room locations
- **Products**: View product catalog with team members, sales data, customer reviews, and ratings
- **Projects**: View all projects, their progress, tasks, and financial details
- **Financials**: Comprehensive financial analytics with:
  - Income, expenses, and profit trends
  - Payroll breakdowns by role and department
  - Expense category analysis
  - Income source tracking
  - Period-based filtering (30, 60, 90, 180, 365 days)
- **Office View**: Visual representation of all 4 floors with:
  - Room layouts with employee locations
  - Room capacity and occupancy
  - Floor-by-floor navigation
  - Room detail modals
- **Communications**: Email and chat message hub with filtering
- **Tasks**: View all tasks across projects with filtering and detailed task information
- **Notifications**: Real-time notifications for reviews, raises, terminations, and other events
- **Boardroom**: Strategic discussions and decision-making sessions
  - Executive rotation every 30 minutes (up to 7 executives, CEO always present)
  - AI-generated strategic discussions every 2 minutes
  - Real-time boardroom mood tracking based on discussion sentiment
  - Visual boardroom view with executives positioned around a table
  - Discussion log with all boardroom conversations
- **Meetings**: Calendar view with meeting scheduling and live meeting transcripts
  - Day, week, and month calendar views
  - Scheduled, in-progress, and completed meetings
  - Live meeting view with real-time transcripts and video-style layout
  - AI-generated meeting agendas and outlines
  - Automatic meeting status updates
- **Customer Reviews**: Reviews from customers for completed projects
  - AI-generated realistic customer reviews
  - Rating distribution and statistics
  - Reviews by product/project
  - Filtering by rating and project
- **Performance Awards**: Recognition system for top-performing employees
  - Award based on highest performance review rating
  - AI-generated congratulatory messages from managers
  - Award win tracking
- **Pet Care System**: Office pets that employees can care for
  - Interactive pet care game with happiness, hunger, and energy stats
  - Pet care logs tracking employee interactions
  - Multiple pet types (cats and dogs) with unique personalities
  - **Birthday Celebrations**: Automatic birthday party system
  - Birthday parties scheduled in breakrooms
  - Calendar integration for birthday events
  - Upcoming birthdays tracking
  - **Holiday Celebrations**: Automatic US federal holiday party system
  - Holiday parties scheduled in breakrooms with up to 20 attendees
  - Calendar integration for holiday events with special styling
  - Automatic holiday meeting generation for next 3 years
- **Coffee Breaks**: Natural break system for employees
  - Automatic coffee break scheduling with strict timing rules
  - Manager restrictions to prevent abuse
  - Meeting awareness (breaks denied before meetings)
  - Breakroom capacity management
  - Breakroom movement and social interactions
- **Gossip System**: AI-generated workplace gossip between employees
  - Realistic workplace conversations
  - Social dynamics and relationships
- **Newsletter System**: Company newsletter generation
  - Periodic company updates and announcements
- **Random Events**: Dynamic office events
  - Power outages, fire drills, pizza parties, and more
  - Event impact on productivity and morale
- **Suggestion System**: Employee suggestion box
  - Employees can submit suggestions
  - Voting and manager feedback system
- **Weather System**: Office weather tracking
  - Weather conditions affecting office mood
  - **Shared Drive System**: AI-powered document management
  - AI-generated documents (Word, Spreadsheet, PowerPoint)
  - Version control for all documents
  - Organized by department/employee/project
  - Document viewing and editing interface
  - Recent files tracking
  - **Training System**: Employee training session tracking
  - Automatic training session management
  - AI-generated training materials
  - Training progress and statistics
  - Integration with shared drive
  - **Query Cache System**: Performance optimization
  - In-memory query result caching
  - Reduced database load
  - Faster response times
  - **Home View**: Visual representation of employee homes
    - Interior and exterior views of employee residences
    - Family members (spouses, children) with individual activities
    - Home pets (cats and dogs) with care needs
    - Real-time home conversations and activities
    - Sleep/wake cycle visualization
  - **Clock In/Out System**: Automatic time tracking
    - Morning arrivals (6:45am-7:45am) with staggered timing
    - Evening departures (6:45pm-7:15pm) with staggered timing
    - Clock event history tracking
    - Automatic online/offline status updates
  - **Sleep System**: Realistic sleep schedules with comprehensive metrics
    - Bedtime transitions (10pm-12am) for employees and families
    - Morning wake-ups (employees: 5:30am-6:45am, family: 7:30am-9am)
    - Sleep state tracking for employees, family members, and pets
    - Weekend sleep schedule variations
    - Sleep quality scoring (0-100) based on duration and consistency
    - Sleep debt tracking (cumulative hours of sleep deficit)
    - Weekly sleep hour totals and average sleep patterns
  - **Sick Day Management**: Employee illness tracking and recovery
    - Automatic sick call generation (2-4% of employees per day)
    - Manual sick call-ins via API
    - Automatic recovery after 1-3 days
    - Sick day tracking (monthly and yearly)
    - Company-wide sick day statistics

All views update in real-time as the simulation runs via WebSocket.

## Architecture

- **Backend**: FastAPI with async SQLAlchemy
- **Database**: PostgreSQL 12+ (optimized with indexes, connection pooling, and query caching)
- **LLM**: Ollama API client
- **Frontend**: React with Vite and Tailwind CSS
- **Real-time**: WebSocket for live updates
- **Caching**: In-memory query result caching for improved performance

## Troubleshooting

### Ollama Connection Issues

- Ensure Ollama is running: `ollama list`
- Check Ollama URL in `.env` or default `http://localhost:11434`
- Verify model is available: `ollama list`

### Database Issues

- Ensure PostgreSQL is running and accessible
- Check database connection string in `.env` file
- Verify database `office_db` exists (run `setup_postgresql.py` if needed)
- Check PostgreSQL logs for connection errors
- For performance issues, see [POSTGRESQL_OPTIMIZATIONS.md](POSTGRESQL_OPTIMIZATIONS.md)

### Frontend Not Updating

- Check browser console for WebSocket connection errors
- Verify backend is running on port 8000
- Check CORS settings if accessing from different origin

## Documentation

Comprehensive documentation is available in the `docs/` folder:

- **[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)** - Complete system documentation
- **[docs/ORGANIZATIONAL_STRUCTURE.md](docs/ORGANIZATIONAL_STRUCTURE.md)** - Organizational structure system with manager-employee relationships
- **[docs/CLOCK_SYSTEM.md](docs/CLOCK_SYSTEM.md)** - Clock in/out system for time tracking
- **[docs/SLEEP_SYSTEM.md](docs/SLEEP_SYSTEM.md)** - Sleep schedule management with quality metrics and sleep debt tracking
- **[docs/SICK_DAY_SYSTEM.md](docs/SICK_DAY_SYSTEM.md)** - Sick day management system with automatic call-ins and recovery
- **[docs/COFFEE_BREAK_SYSTEM.md](docs/COFFEE_BREAK_SYSTEM.md)** - Coffee break system with timing rules and capacity management
- **[docs/POSTGRESQL_OPTIMIZATIONS.md](docs/POSTGRESQL_OPTIMIZATIONS.md)** - Database performance optimizations
- **[docs/COMMUNICATION_FIXES.md](docs/COMMUNICATION_FIXES.md)** - Communication system fixes and improvements
- **[docs/DATABASE_CONNECTION_FIX.md](docs/DATABASE_CONNECTION_FIX.md)** - Database connection pool fixes
- **[CLAUDE.md](CLAUDE.md)** - Development guide for AI assistants

## Starting a New Game

To start a completely new simulation with a fresh company, use the new game script:

### Windows
```bash
new_game.bat
```

### Linux/Mac
```bash
chmod +x new_game.sh
./new_game.sh
```

### Manual
```bash
cd backend
python new_game.py
```

The script will:
1. **Optionally backup** your current database (saved to `backend/backups/`)
2. **Wipe all existing data** from the database
3. **Generate a new company** using LLM:
   - Creative company name
   - Product/service name and description
   - Industry sector
   - Management team (CEO, CTO, COO, CFO, and managers) with backstories and personality traits
4. **Seed the database** with the new company data including:
   - Initial employees
   - Starting projects related to the product
   - Initial financial records (seed funding)
   - Business settings

All company data is generated using the LLM (Ollama), ensuring unique and creative businesses each time!

## Utility Scripts

The project includes utility scripts for testing and debugging:

- `new_game.bat` / `new_game.sh` - Start a new game/simulation with fresh company data
- `backend/new_game.py` - New game script (run directly)
- `backend/reorganize_company.py` - Reorganize company structure to maintain 1:10 manager-to-employee ratio
- `backend/add_manager_column.py` - Add manager_id column to employees table
- `backend/backfill_clock_outs.py` - Backfill clock out events
- `backend/check_sleep_status.py` - Check sleep status of employees and families
- `backend/force_employee_reviews.py` - Force employee review generation
- `backend/migrate_pet_roaming.py` - Migrate pet roaming data
- `backend/test_sleep_enforcement.py` - Test sleep system enforcement
- `backend/verify_migrations.py` - Verify database migrations
- `backend/test_meetings.py` - Check meeting status and test meeting system
- `backend/force_meeting_update.py` - Force immediate meeting updates
- `backend/generate_meetings_now.py` - Generate meetings for testing
- `backend/initialize_award.py` - Initialize performance award system
- `backend/create_products.py` - Create product entries
- `backend/create_real_products.py` - Create realistic product data
- `backend/link_reviews_to_products.py` - Link customer reviews to products
- `backend/migrate_add_products.py` - Database migration for products
- `backend/backfill_thread_ids.py` - Ensure all messages have thread IDs
- `backend/check_unreplied_messages.py` - Analyze message reply rates
- `backend/instant_reply_all.py` - Fast fallback responses to all messages
- `backend/force_reply_all_messages.py` - Full LLM responses to all messages
- `backend/fix_stuck_training_sessions.py` - Fix training sessions that are stuck
- `backend/check_db_counts.py` - Check database record counts
- `backend/reset_communications.py` - Reset communication system
- `backend/run_migrations.py` - Run database migrations

## License

MIT

