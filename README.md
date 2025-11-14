# Autonomous Office Simulation

A fully autonomous office simulation where AI employees make decisions, work on projects, and grow the business using local Ollama and Llama3.2 LLM.

## Features

- **Fully Autonomous**: The office runs completely on its own - no user interaction required
- **AI-Powered Employees**: Each employee uses LLM to make decisions based on their role, personality, and backstory
- **Employee Hierarchy**: CEO, Managers, and Employees with different decision-making capabilities
- **Real-time Web Interface**: Watch the office operate in real-time through a modern web dashboard
- **Rich Observability**: 
  - Dashboard with key metrics
  - Employee details with backstories
  - Project tracking
  - Financial reports
  - Activity feed

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

1. **Simulation Loop**: Every 8 seconds, the system processes employees
2. **Decision Making**: Each employee evaluates their situation and uses the LLM to make decisions
3. **Role-Based Behavior**:
   - **CEO**: Makes strategic decisions, creates new projects
   - **Managers**: Plan projects, assign tasks, coordinate teams
   - **Employees**: Execute tasks, solve problems, collaborate
4. **Business Growth**: Projects generate revenue, employees complete tasks, business metrics update
5. **Real-time Updates**: All activities are broadcast via WebSocket to the frontend

## Employee System

Each employee has:
- **Name**: Unique identifier
- **Title**: Job title (e.g., "Chief Executive Officer")
- **Backstory**: Personal history that influences decision-making
- **Personality Traits**: Affects how they make decisions
- **Role**: Determines decision-making capabilities

## Observing the Simulation

The web interface provides several views:

- **Dashboard**: Overview of business metrics, recent activities, and goals
- **Employees**: Browse all employees, click to see details, backstories, and activities
- **Projects**: View all projects, their progress, and details
- **Financials**: Comprehensive financial analytics with charts, payroll details, expense breakdowns, and income sources

All views update in real-time as the simulation runs.

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

## License

MIT

