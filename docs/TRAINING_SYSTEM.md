# Training System

## Overview

The training system manages employee training sessions with AI-generated training materials. Employees automatically attend training when they enter training rooms, and the system tracks training progress, generates materials, and integrates with the shared drive system.

## Features

- **Automatic Training Sessions**: Training starts when employees enter training rooms
- **AI-Generated Materials**: Training materials created using LLM based on topics and departments
- **Training Topics**: Context-aware training topics based on employee role and department
- **Training Duration**: Automatic session management with 30-minute maximum duration
- **Shared Drive Integration**: Training materials saved to shared drive for access
- **Training Statistics**: Track training sessions, materials usage, and employee progress
- **Department-Specific Training**: Training materials tailored to specific departments

## How It Works

### Training Session Lifecycle

1. **Employee Enters Training Room**:
   - System detects employee entering training room
   - Checks for existing in-progress session
   - Determines training topic based on employee role/department
   - Finds or creates training material for topic
   - Creates new training session

2. **Training Session Active**:
   - Employee is in training room
   - Session status: "in_progress"
   - Training material available
   - Duration tracked

3. **Training Session Ends**:
   - Employee leaves training room, OR
   - 30-minute maximum duration reached
   - Session status: "completed"
   - Duration calculated and saved
   - Employee returns to work area

### Training Topic Selection

Training topics are determined based on:
- **Employee Role**: CEO, Manager, Employee
- **Department**: Engineering, Sales, HR, etc.
- **AI Selection**: LLM selects appropriate topic based on context

**Example Topics**:
- "Advanced Project Management Techniques"
- "Customer Relationship Management"
- "Software Development Best Practices"
- "Leadership and Team Management"
- "Professional Development and Skills Enhancement"

### Training Material Generation

**Material Creation**:
1. System checks for existing material on topic
2. If exists: Reuses material, increments usage count
3. If new: Generates material using LLM
4. Material includes:
   - Title and description
   - Content (HTML format)
   - Difficulty level
   - Estimated duration
   - Department association

**Material Content**:
- AI-generated comprehensive training content
- Department-specific information
- Role-appropriate difficulty level
- Practical examples and exercises

### Shared Drive Integration

Training materials are automatically:
- Saved to shared drive
- Organized by department/employee/project
- Accessible to all employees
- Version controlled

## Database Structure

### TrainingSession Table

```sql
CREATE TABLE training_sessions (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    training_material_id INTEGER REFERENCES training_materials(id),
    training_room VARCHAR(255),
    training_topic VARCHAR(255),
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    status VARCHAR(50),  -- 'in_progress' or 'completed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### TrainingMaterial Table

```sql
CREATE TABLE training_materials (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255),
    topic VARCHAR(255),
    description TEXT,
    content_html TEXT,
    difficulty_level VARCHAR(50),  -- 'beginner', 'intermediate', 'advanced'
    estimated_duration_minutes INTEGER,
    department VARCHAR(255),
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### Get Training Overview

```
GET /api/training/overview
```

**Response**:
```json
{
  "total_sessions": 245,
  "active_sessions": 12,
  "completed_sessions": 233,
  "total_materials": 45,
  "most_used_materials": [
    {
      "id": 1,
      "title": "Advanced Project Management",
      "topic": "Project Management",
      "usage_count": 23,
      "department": "Engineering"
    }
  ],
  "recent_sessions": [
    {
      "id": 123,
      "employee_name": "John Doe",
      "topic": "Software Development Best Practices",
      "status": "in_progress",
      "start_time": "2024-01-15T14:00:00-05:00",
      "duration_minutes": 15
    }
  ]
}
```

### Get Training Materials

```
GET /api/training/materials?topic=Project Management&department=Engineering&limit=50
```

**Response**:
```json
[
  {
    "id": 1,
    "title": "Advanced Project Management Techniques",
    "topic": "Project Management",
    "description": "Comprehensive guide to project management...",
    "difficulty_level": "intermediate",
    "estimated_duration_minutes": 30,
    "department": "Engineering",
    "usage_count": 23,
    "created_at": "2024-01-10T10:00:00-05:00"
  }
]
```

### Get Training Material Details

```
GET /api/training/materials/{material_id}
```

**Response**:
```json
{
  "id": 1,
  "title": "Advanced Project Management Techniques",
  "topic": "Project Management",
  "description": "Comprehensive guide...",
  "content_html": "<h1>Training Content...</h1>",
  "difficulty_level": "intermediate",
  "estimated_duration_minutes": 30,
  "department": "Engineering",
  "usage_count": 23,
  "created_at": "2024-01-10T10:00:00-05:00"
}
```

### Get Employee Training Sessions

```
GET /api/training/employees/{employee_id}
```

**Response**:
```json
[
  {
    "id": 123,
    "employee_id": 45,
    "employee_name": "John Doe",
    "training_material_id": 1,
    "training_topic": "Project Management",
    "training_room": "Training Room_floor1",
    "start_time": "2024-01-15T14:00:00-05:00",
    "end_time": "2024-01-15T14:30:00-05:00",
    "duration_minutes": 30,
    "status": "completed"
  }
]
```

## Frontend Integration

### Training Dashboard Tab

**File**: `frontend/src/pages/Dashboard.jsx` (Training tab)

**Features**:
- Training overview statistics
- Active training sessions
- Recent training sessions
- Most used training materials
- Training progress by employee

### Training Detail Modal

**File**: `frontend/src/components/TrainingDetailModal.jsx`

**Features**:
- Training material content display
- Training session history
- Employee training progress
- Material usage statistics

## Implementation

### TrainingManager Class

**File**: `backend/business/training_manager.py`

**Key Methods**:

```python
async def start_training_session(
    self,
    employee: Employee,
    training_room: str,
    db_session: AsyncSession
) -> TrainingSession:
    """Start a new training session when employee enters training room."""
    
async def end_training_session(
    self,
    employee: Employee,
    db_session: AsyncSession
) -> TrainingSession:
    """End training session when employee leaves training room."""
    
async def _determine_training_topic(
    self,
    employee: Employee,
    db_session: AsyncSession
) -> str:
    """Determine training topic based on employee role and department."""
    
async def _get_or_create_training_material(
    self,
    topic: str,
    department: str | None,
    db_session: AsyncSession
) -> TrainingMaterial:
    """Get existing material or create new one using AI."""
    
async def _generate_training_material(
    self,
    topic: str,
    department: str | None,
    db_session: AsyncSession
) -> TrainingMaterial:
    """Generate training material using LLM."""
```

### Integration with Movement System

The training system integrates with the movement system:
- Detects when employees enter training rooms
- Automatically starts training sessions
- Detects when employees leave training rooms
- Automatically ends training sessions

### Integration with Shared Drive

Training materials are saved to shared drive:
- Materials accessible to all employees
- Organized by department
- Version controlled
- Searchable and filterable

## Configuration

### Training Room Detection

Training rooms are identified by:
- Room name: "Training Room" or "Training Room_floorX"
- Floor-specific training rooms supported

### Training Duration

- **Maximum Duration**: 30 minutes per session
- **Automatic End**: Session ends after 30 minutes
- **Employee Return**: Employee automatically returns to work area

### Training Material Generation

- **AI-Powered**: All materials generated using LLM
- **Topic-Based**: Materials organized by topic
- **Department-Specific**: Materials tailored to departments
- **Reusable**: Existing materials reused when available

## Troubleshooting

### Training Sessions Not Starting

**Possible Causes**:
1. Employee not entering training room
2. Training room name mismatch
3. Movement system not detecting room entry
4. Database connection issues

**Solution**: Check room names, verify movement system, check database

### Training Materials Not Generating

**Possible Causes**:
1. LLM (Ollama) not available
2. AI generation failing
3. Database transaction issues

**Solution**: Check Ollama connection, verify AI generation logic, check database

### Training Sessions Not Ending

**Possible Causes**:
1. Employee not leaving training room
2. 30-minute limit not enforced
3. Movement system not detecting room exit

**Solution**: Check movement system, verify duration enforcement, check room exit detection

## Best Practices

1. **Topic Selection**: Use context-aware topic selection
2. **Material Reuse**: Reuse existing materials when possible
3. **Department-Specific**: Create department-specific materials
4. **Duration Management**: Enforce 30-minute maximum
5. **Shared Drive**: Save all materials to shared drive
6. **Statistics Tracking**: Track usage and progress

## Future Enhancements

Potential improvements:
- Training certifications
- Training assessments and quizzes
- Training schedules and calendars
- Multi-employee training sessions
- Training completion tracking
- Training effectiveness metrics
- Training recommendations
- Training paths and curricula
- Training video support
- Interactive training content

