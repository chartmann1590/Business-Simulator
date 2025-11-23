# Boardroom System

## Overview

The boardroom system manages strategic discussions in the boardroom with executives (CEO and Managers). Executives rotate into the boardroom every 30 minutes, and AI-generated strategic discussions occur every 2 minutes. The system tracks boardroom mood based on discussion sentiment and provides a visual boardroom view.

## Features

- **Executive Rotation**: Executives rotate into boardroom every 30 minutes
- **Strategic Discussions**: AI-generated discussions every 2 minutes
- **Boardroom Mood**: Sentiment-based mood tracking
- **Visual Boardroom**: Visual representation of executives around table
- **Discussion Log**: Complete history of all boardroom conversations
- **Strategic Topics**: 40+ strategic topics covered
- **Real-time Updates**: Live boardroom discussions via WebSocket

## How It Works

### Executive Rotation

**Rotation Schedule**:
- Executives rotate into boardroom every 30 minutes
- Up to 7 executives in boardroom at once
- CEO is always present
- Managers rotate in and out

**Selection Process**:
1. System identifies all executives (CEO, CTO, COO, CFO, Managers)
2. Selects up to 7 executives (including CEO)
3. Rotates executives every 30 minutes
4. Tracks who is currently in boardroom

### Strategic Discussions

**Discussion Generation**:
- Discussions generated every 2 minutes
- AI-generated based on:
  - Current business context
  - Strategic topics (40+ topics)
  - Executive personalities
  - Boardroom mood

**Discussion Types**:
- Revenue growth strategies
- Market expansion plans
- Resource allocation
- Product development
- Team management
- Financial planning
- And 35+ more topics

**Discussion Format**:
- Direct messages between executives
- Face-to-face conversation style
- Strategic and business-focused
- Context-aware and realistic

### Boardroom Mood

**Mood Calculation**:
- Based on discussion sentiment
- Analyzes recent discussions
- Calculates overall mood (positive, neutral, negative)
- Updates in real-time

**Mood Factors**:
- Discussion sentiment
- Business performance
- Strategic decisions
- Executive interactions

### Visual Boardroom

**Layout**:
- Executives positioned around table
- Visual representation of boardroom
- Real-time participant updates
- Discussion display

## Database Structure

### Boardroom Discussions

Boardroom discussions are stored as ChatMessage records with special metadata:
- `thread_id`: Boardroom thread identifier
- `sender_id`: Executive sending message
- `recipient_id`: Executive receiving message (optional, can be group)
- `message`: Discussion content
- `timestamp`: When discussion occurred
- `metadata`: Boardroom-specific metadata

### Boardroom Mood

Mood is calculated dynamically from recent discussions, not stored separately.

## API Endpoints

### Get Boardroom Discussions

```
GET /api/boardroom/discussions?limit=50
```

**Response**:
```json
[
  {
    "id": 123,
    "sender_id": 1,
    "sender_name": "CEO Name",
    "recipient_id": 2,
    "recipient_name": "CTO Name",
    "message": "We need to focus on revenue growth. What's your take on expanding into new markets?",
    "timestamp": "2024-01-15T14:00:00-05:00",
    "thread_id": "boardroom_2024-01-15"
  }
]
```

### Get Boardroom Mood

```
GET /api/boardroom/mood
```

**Response**:
```json
{
  "mood": "positive",
  "sentiment_score": 0.75,
  "recent_discussions": 12,
  "last_updated": "2024-01-15T14:00:00-05:00"
}
```

### Get Boardroom Executives

```
GET /api/boardroom/executives
```

**Response**:
```json
{
  "executives": [
    {
      "id": 1,
      "name": "CEO Name",
      "title": "Chief Executive Officer",
      "role": "CEO",
      "in_boardroom": true
    },
    {
      "id": 2,
      "name": "CTO Name",
      "title": "Chief Technology Officer",
      "role": "CTO",
      "in_boardroom": true
    }
  ],
  "total": 7,
  "rotation_time": "2024-01-15T14:30:00-05:00"
}
```

### Generate Boardroom Discussions

```
POST /api/boardroom/generate-discussions
```

**Request** (optional):
```json
{
  "executive_ids": [1, 2, 3, 4, 5, 6, 7]
}
```

**Response**:
```json
{
  "success": true,
  "discussions_created": 5,
  "message": "Generated 5 boardroom discussions"
}
```

## Frontend Integration

### Boardroom View

**File**: `frontend/src/components/BoardroomView.jsx`

**Features**:
- Visual boardroom layout
- Executives positioned around table
- Real-time discussion display
- Boardroom mood indicator
- Discussion log
- Executive rotation timer

### Dashboard Integration

The boardroom view is integrated into the Dashboard:
- **Boardroom Tab**: Dedicated tab in dashboard
- **Real-time Updates**: Live discussion updates
- **Mood Display**: Current boardroom mood
- **Executive List**: Currently present executives

## Implementation

### BoardroomManager Class

**File**: `backend/business/boardroom_manager.py`

**Key Methods**:

```python
async def generate_boardroom_discussions(self) -> int:
    """Generate strategic discussions in boardroom."""
    
async def get_boardroom_executives(self) -> List[Employee]:
    """Get executives currently in boardroom."""
    
async def rotate_executives(self) -> dict:
    """Rotate executives into/out of boardroom."""
    
async def calculate_boardroom_mood(self) -> dict:
    """Calculate boardroom mood from recent discussions."""
```

### Integration with Office Simulator

The boardroom manager is called:
- **Discussion Generation**: Every 2 minutes (15 simulation ticks)
- **Executive Rotation**: Every 30 minutes
- **Mood Calculation**: Periodically

### Strategic Topics

The system covers 40+ strategic topics including:
- Revenue growth strategies
- Market expansion
- Resource allocation
- Product development
- Team management
- Financial planning
- Customer acquisition
- Technology investments
- Competitive analysis
- Risk management
- And 30+ more topics

## Configuration

### Executive Rotation

- **Frequency**: Every 30 minutes
- **Max Executives**: 7 executives at once
- **CEO Always Present**: CEO never rotates out
- **Manager Rotation**: Managers rotate in and out

### Discussion Generation

- **Frequency**: Every 2 minutes (15 simulation ticks)
- **Topics**: 40+ strategic topics
- **Format**: Direct messages between executives
- **Style**: Face-to-face conversation

### Mood Calculation

- **Update Frequency**: Every discussion generation
- **Sentiment Analysis**: Based on discussion content
- **Mood Levels**: Positive, Neutral, Negative
- **Score Range**: 0.0 to 1.0

## Troubleshooting

### Discussions Not Generating

**Possible Causes**:
1. Discussion generation task not running
2. No executives in boardroom
3. LLM (Ollama) not available
4. Database connection issues

**Solution**: Check background task, verify executives, check Ollama connection

### Executives Not Rotating

**Possible Causes**:
1. Rotation task not running
2. Time calculation issues
3. Executive selection failing

**Solution**: Check rotation task, verify time calculations, check executive selection

### Mood Not Calculating

**Possible Causes**:
1. No recent discussions
2. Sentiment analysis failing
3. Database query issues

**Solution**: Check discussion history, verify sentiment analysis, check database

## Best Practices

1. **Regular Discussions**: Generate discussions every 2 minutes
2. **Executive Rotation**: Rotate executives every 30 minutes
3. **Strategic Topics**: Cover diverse strategic topics
4. **Mood Tracking**: Keep mood calculation up to date
5. **Realistic Conversations**: Generate natural, contextual discussions
6. **CEO Presence**: Always keep CEO in boardroom

## Future Enhancements

Potential improvements:
- Boardroom voting system
- Strategic decision tracking
- Boardroom minutes and summaries
- Executive attendance tracking
- Boardroom agenda management
- Strategic initiative tracking
- Boardroom analytics
- Executive performance in boardroom
- Boardroom recordings
- Strategic roadmap visualization

