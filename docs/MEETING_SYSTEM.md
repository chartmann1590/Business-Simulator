# Meeting System

## Overview

The meeting system manages meeting scheduling, calendar views, and live meeting transcripts. Meetings are automatically generated with AI-created agendas, outlines, and transcripts. The system supports day, week, and month calendar views, and provides live meeting views with real-time transcripts.

## Features

- **Automatic Meeting Generation**: Meetings automatically scheduled throughout the day
- **AI-Generated Content**: Agendas, outlines, and transcripts created using LLM
- **Calendar Views**: Day, week, and month calendar views
- **Live Meeting View**: Real-time meeting transcripts with video-style layout
- **Meeting Status Tracking**: Scheduled, in-progress, and completed meetings
- **Meeting Participants**: Organizer and attendee management
- **Meeting Types**: Various meeting types (Team Sync, Project Review, Strategy, etc.)
- **Meeting Metadata**: Live messages and meeting context

## How It Works

### Meeting Generation

**Automatic Scheduling**:
- Meetings generated daily (3-8 meetings per day)
- Meetings scheduled throughout work hours
- Meeting types vary (Team Sync, Project Review, Strategy Discussion, etc.)
- Participants selected based on roles and departments

**Meeting Creation Process**:
1. System selects meeting type and participants
2. Generates meeting title and description
3. Creates agenda using LLM
4. Creates meeting outline using LLM
5. Schedules meeting with start/end times
6. Sets initial status (scheduled, in-progress, or completed)

### Meeting Lifecycle

**Scheduled**:
- Meeting created with future start time
- Agenda and outline generated
- Participants notified
- Appears in calendar

**In Progress**:
- Meeting start time reached
- Status updated to "in_progress"
- Live transcript generation begins
- Participants can view live meeting

**Completed**:
- Meeting end time reached
- Status updated to "completed"
- Final transcript generated
- Meeting archived

### AI-Generated Content

**Agenda**:
- Meeting topics and discussion points
- Time allocation for each topic
- Participant roles and responsibilities

**Outline**:
- Meeting structure and flow
- Key discussion points
- Expected outcomes

**Transcript**:
- Complete meeting conversation
- Participant contributions
- Decisions and action items
- Generated using LLM for completed meetings

### Live Meeting View

**Real-time Transcripts**:
- Live messages added during meeting
- Video-style layout with participant positions
- Real-time updates via WebSocket
- Meeting status indicators

**Meeting Layout**:
- Participants displayed in video-style grid
- Transcript shown alongside participant view
- Meeting controls (mute, video, etc.) simulated
- Time remaining displayed

## Database Structure

### Meeting Table

```sql
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255),
    description TEXT,
    organizer_id INTEGER REFERENCES employees(id),
    attendee_ids INTEGER[],  -- Array of employee IDs
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50),  -- 'scheduled', 'in_progress', 'completed'
    agenda TEXT,
    outline TEXT,
    transcript TEXT,
    meeting_metadata JSONB,  -- Contains live_messages array
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### Get Meetings

```
GET /api/meetings?status=scheduled&start_date=2024-01-15&end_date=2024-01-20
```

**Response**:
```json
[
  {
    "id": 1,
    "title": "Team Sync: Engineering",
    "description": "Weekly team synchronization and updates",
    "organizer_id": 45,
    "organizer_name": "Jane Manager",
    "attendee_ids": [45, 100, 101, 102],
    "attendees": [
      {"id": 45, "name": "Jane Manager", "title": "Engineering Manager"},
      {"id": 100, "name": "John Doe", "title": "Senior Developer"}
    ],
    "start_time": "2024-01-15T10:00:00-05:00",
    "end_time": "2024-01-15T10:30:00-05:00",
    "status": "scheduled",
    "agenda": "1. Project updates\n2. Blockers and challenges\n3. Next week planning",
    "outline": "Meeting will cover...",
    "transcript": null,
    "created_at": "2024-01-14T10:00:00-05:00"
  }
]
```

### Get Meeting Details

```
GET /api/meetings/{meeting_id}
```

**Response**: Full meeting details including all attendees and complete transcript

### Get Meeting Calendar

```
GET /api/meetings/calendar?view=week&start_date=2024-01-15
```

**Parameters**:
- `view`: "day", "week", or "month"
- `start_date`: Start date for calendar view

**Response**: Meetings organized by date for calendar display

### Schedule Meeting in 15 Minutes

```
POST /api/meetings/schedule-in-15min
```

**Response**:
```json
{
  "success": true,
  "message": "Meeting scheduled successfully",
  "meeting_id": 123,
  "meeting": {
    "title": "Team Sync: Engineering",
    "start_time": "2024-01-15T10:15:00-05:00",
    "end_time": "2024-01-15T10:45:00-05:00"
  }
}
```

### Schedule Meeting in 1 Minute

```
POST /api/meetings/schedule-in-1min
```

**Response**: Similar to schedule-in-15min, but meeting starts in 1 minute

### Get Live Meeting

```
GET /api/meetings/{meeting_id}/live
```

**Response**:
```json
{
  "meeting_id": 123,
  "status": "in_progress",
  "live_messages": [
    {
      "speaker": "Jane Manager",
      "message": "Let's start with project updates.",
      "timestamp": "2024-01-15T10:00:15-05:00"
    }
  ],
  "time_remaining_minutes": 25
}
```

## Frontend Integration

### Meetings Page

**File**: `frontend/src/pages/Meetings.jsx`

**Features**:
- Calendar view (day, week, month)
- Meeting list view
- Meeting filtering (status, date range)
- Meeting creation
- Meeting details modal

### Live Meeting View

**File**: `frontend/src/components/LiveMeetingView.jsx` (if exists)

**Features**:
- Video-style participant layout
- Real-time transcript display
- Meeting controls (simulated)
- Time remaining indicator
- Participant status indicators

### Meeting Detail Modal

**File**: `frontend/src/components/MeetingDetailModal.jsx` (if exists)

**Features**:
- Meeting information
- Agenda and outline
- Complete transcript
- Participant list
- Meeting metadata

## Implementation

### MeetingManager Class

**File**: `backend/business/meeting_manager.py`

**Key Methods**:

```python
async def generate_meetings(self) -> int:
    """Generate important meetings for the day."""
    
async def generate_meetings_for_date_range(
    self,
    start_date: datetime,
    end_date: datetime
) -> int:
    """Generate meetings for a date range."""
    
async def _generate_meeting_agenda(
    self,
    meeting_type: str,
    description: str,
    organizer: Employee,
    attendees: List[Employee],
    business_context: Dict
) -> Tuple[str, str]:
    """Generate meeting agenda and outline using LLM."""
    
async def _generate_final_transcript_for_meeting(
    self,
    title: str,
    description: str,
    organizer: Employee,
    attendees: List[Employee],
    start_time: datetime,
    end_time: datetime
) -> str:
    """Generate final transcript for completed meeting."""
    
async def update_meeting_status(self) -> dict:
    """Update meeting statuses (scheduled -> in_progress -> completed)."""
```

### Integration with Office Simulator

The meeting manager is called:
- **Daily Generation**: Once per day (generates meetings for the day)
- **Status Updates**: Periodically to update meeting statuses
- **Transcript Generation**: When meetings complete

## Configuration

### Meeting Generation

- **Frequency**: Once per day
- **Count**: 3-8 meetings per day
- **Timing**: Throughout work hours (8am-6pm)
- **Duration**: 15-60 minutes per meeting

### Meeting Types

- Team Sync
- Project Review
- Strategy Discussion
- Status Update
- Planning Session

### Meeting Participants

- **Organizer**: 1 employee (usually manager)
- **Attendees**: 1-5 additional employees
- **Selection**: Based on roles, departments, and availability

## Troubleshooting

### Meetings Not Generating

**Possible Causes**:
1. Daily generation task not running
2. Too many existing meetings
3. LLM (Ollama) not available
4. Database connection issues

**Solution**: Check background task, verify meeting count, check Ollama connection

### Meeting Status Not Updating

**Possible Causes**:
1. Status update task not running
2. Time comparison issues
3. Database transaction issues

**Solution**: Check status update task, verify time comparisons, check database

### Transcripts Not Generating

**Possible Causes**:
1. LLM (Ollama) not available
2. Transcript generation failing
3. Meeting not completing properly

**Solution**: Check Ollama connection, verify transcript generation logic, check meeting completion

## Best Practices

1. **Meeting Variety**: Generate diverse meeting types
2. **Participant Selection**: Select relevant participants
3. **Agenda Quality**: Generate comprehensive agendas
4. **Transcript Accuracy**: Generate realistic transcripts
5. **Status Management**: Keep meeting statuses up to date
6. **Calendar Integration**: Ensure meetings appear in calendar

## Future Enhancements

Potential improvements:
- Meeting reminders and notifications
- Meeting recordings
- Meeting notes and action items
- Meeting recurrence (recurring meetings)
- Meeting room booking
- Meeting conflict detection
- Meeting attendance tracking
- Meeting feedback and ratings
- Meeting templates
- Meeting analytics

