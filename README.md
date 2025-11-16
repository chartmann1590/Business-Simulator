# Autonomous Office Simulation

A fully autonomous office simulation where AI employees make decisions, work on projects, and grow the business using local Ollama and Llama3.2 LLM.

## Features

- **Fully Autonomous**: The office runs completely on its own - no user interaction required
- **AI-Powered Employees**: Each employee uses LLM to make decisions based on their role, personality, and backstory
- **Employee Hierarchy**: CEO, Managers, and Employees with different decision-making capabilities
- **Multi-Floor Office System**: 4 floors with specialized rooms and intelligent room assignment
- **Smart Room Management**: Room capacity tracking, overflow handling, and intelligent movement
- **Real-time Web Interface**: Watch the office operate in real-time through a modern web dashboard
- **Rich Observability**: 
  - Dashboard with key metrics and business goals
  - Employee details with backstories, activities, and room locations
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
- Ollama installed and running locally
- Llama3.2 model downloaded in Ollama

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

4. Seed the database:
   ```bash
   cd backend
   python seed.py
   ```

5. Install frontend dependencies:
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
DATABASE_URL=sqlite+aiosqlite:///./office.db
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
- **Activity State**: idle, working, walking, meeting, break, training, waiting

## Observing the Simulation

The web interface provides several views:

- **Dashboard**: Overview of business metrics, recent activities, and goals
- **Employees**: Browse all employees, click to see details, backstories, activities, and room locations
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

All views update in real-time as the simulation runs via WebSocket.

## Architecture

- **Backend**: FastAPI with async SQLAlchemy
- **Database**: SQLite (can be easily switched to PostgreSQL)
- **LLM**: Ollama API client
- **Frontend**: React with Vite and Tailwind CSS
- **Real-time**: WebSocket for live updates

## Troubleshooting

### Ollama Connection Issues

- Ensure Ollama is running: `ollama list`
- Check Ollama URL in `.env` or default `http://localhost:11434`
- Verify model is available: `ollama list`

### Database Issues

- Delete `office.db` and re-run `seed.py` to reset
- Check database path in configuration

### Frontend Not Updating

- Check browser console for WebSocket connection errors
- Verify backend is running on port 8000
- Check CORS settings if accessing from different origin

## Documentation

For comprehensive documentation, see [DOCUMENTATION.md](DOCUMENTATION.md)

## Utility Scripts

The project includes utility scripts for testing and debugging:

- `backend/test_meetings.py` - Check meeting status and test meeting system
- `backend/force_meeting_update.py` - Force immediate meeting updates
- `backend/generate_meetings_now.py` - Generate meetings for testing
- `backend/initialize_award.py` - Initialize performance award system

## License

MIT

