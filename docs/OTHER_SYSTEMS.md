# Other Systems Documentation

This document covers the smaller systems in the office simulation: Gossip, Weather, Random Events, Newsletter, and Suggestion systems.

## Gossip System

### Overview

The gossip system generates AI-powered workplace gossip and social interactions between employees, creating realistic social dynamics and relationships.

### Features

- **AI-Generated Gossip**: Realistic workplace conversations
- **Social Dynamics**: Relationship building between employees
- **Context-Aware**: Gossip reflects current office events
- **Natural Conversations**: LLM-generated natural dialogue

### How It Works

- Gossip generated periodically during work hours
- Conversations between employees in breakrooms or common areas
- Topics include office events, projects, relationships, and general workplace chatter
- Stored as ChatMessage records with gossip metadata

### API Endpoints

```
GET /api/gossip?limit=50
```

Returns recent gossip conversations.

## Weather System

### Overview

The weather system tracks office weather conditions and affects office mood and employee behavior.

### Features

- **Weather Tracking**: Current weather conditions
- **Mood Impact**: Weather affects office mood
- **Employee Behavior**: Weather influences employee activities
- **Realistic Conditions**: Various weather types (sunny, rainy, cloudy, etc.)

### How It Works

- Weather conditions tracked in database
- Weather affects office mood calculations
- Employees may comment on weather in conversations
- Weather displayed in dashboard

### Database Structure

```sql
CREATE TABLE weather (
    id INTEGER PRIMARY KEY,
    condition VARCHAR(50),  -- 'sunny', 'rainy', 'cloudy', etc.
    temperature FLOAT,
    office_mood_impact FLOAT,  -- -1.0 to 1.0
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### API Endpoints

```
GET /api/weather/current
```

Returns current weather conditions.

## Random Events System

### Overview

The random events system generates dynamic office events that affect productivity and morale, such as power outages, fire drills, pizza parties, and more.

### Features

- **Dynamic Events**: Various event types
- **Impact on Productivity**: Events affect employee productivity
- **Impact on Morale**: Events affect office morale
- **Realistic Scenarios**: Common workplace events

### Event Types

- Power outages
- Fire drills
- Pizza parties
- Office celebrations
- Equipment failures
- Surprise visits
- And more...

### How It Works

- Events generated randomly during work hours
- Events have duration and impact
- Employees react to events
- Events logged in activity feed

### Database Structure

```sql
CREATE TABLE random_events (
    id INTEGER PRIMARY KEY,
    event_type VARCHAR(50),
    title VARCHAR(255),
    description TEXT,
    impact_productivity FLOAT,  -- -1.0 to 1.0
    impact_morale FLOAT,  -- -1.0 to 1.0
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50),  -- 'active', 'completed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### API Endpoints

```
GET /api/events?status=active
```

Returns active or recent random events.

## Newsletter System

### Overview

The newsletter system generates periodic company newsletters with updates, announcements, and company news.

### Features

- **Periodic Generation**: Newsletters generated periodically
- **AI-Generated Content**: Newsletter content created using LLM
- **Company Updates**: Includes company news and updates
- **Employee Announcements**: Highlights employee achievements

### How It Works

- Newsletters generated every few days
- Content includes:
  - Company updates
  - Project milestones
  - Employee achievements
  - Office events
  - Business metrics
- Stored in database for viewing

### Database Structure

```sql
CREATE TABLE newsletters (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### API Endpoints

```
GET /api/newsletters?limit=10
```

Returns recent newsletters.

## Suggestion System

### Overview

The suggestion system allows employees to submit suggestions, vote on suggestions, and receive manager feedback.

### Features

- **Employee Suggestions**: Employees can submit suggestions
- **Voting System**: Employees can vote on suggestions
- **Manager Feedback**: Managers provide feedback on suggestions
- **Status Tracking**: Suggestions tracked (pending, reviewed, implemented, rejected)

### How It Works

- Employees submit suggestions via decision-making
- Suggestions stored in database
- Other employees can vote on suggestions
- Managers review and provide feedback
- Suggestions can be implemented or rejected

### Database Structure

```sql
CREATE TABLE suggestions (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(50),  -- 'pending', 'reviewed', 'implemented', 'rejected'
    manager_feedback TEXT,
    vote_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE suggestion_votes (
    id INTEGER PRIMARY KEY,
    suggestion_id INTEGER REFERENCES suggestions(id),
    employee_id INTEGER REFERENCES employees(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### API Endpoints

```
GET /api/suggestions?status=pending&limit=50
```

Returns suggestions with optional filtering.

```
POST /api/suggestions/{suggestion_id}/vote
```

Vote on a suggestion.

```
POST /api/suggestions/{suggestion_id}/feedback
```

Manager provides feedback on suggestion.

## Frontend Integration

### Dashboard Integration

All these systems are integrated into the Dashboard:
- **Gossip**: Displayed in activity feed
- **Weather**: Weather widget in dashboard
- **Random Events**: Event notifications and activity feed
- **Newsletter**: Newsletter section in dashboard
- **Suggestions**: Suggestions tab in dashboard

### Activity Feed

All systems contribute to the activity feed:
- Gossip conversations
- Weather changes
- Random events
- Newsletter publications
- Suggestion submissions and updates

## Implementation

### System Managers

Each system has a manager class:
- `GossipManager`: `backend/business/gossip_manager.py`
- `WeatherManager`: `backend/business/weather_manager.py`
- `RandomEventManager`: `backend/business/random_event_manager.py`
- `NewsletterManager`: `backend/business/newsletter_manager.py`
- `SuggestionManager`: `backend/business/suggestion_manager.py`

### Integration with Office Simulator

All systems are called periodically:
- **Gossip**: Every few minutes during work hours
- **Weather**: Updated periodically
- **Random Events**: Generated randomly
- **Newsletter**: Generated every few days
- **Suggestions**: Processed periodically

## Configuration

### Generation Frequencies

- **Gossip**: Every 5-10 minutes
- **Weather**: Updated every hour
- **Random Events**: 1-2 events per day
- **Newsletter**: Every 3-5 days
- **Suggestions**: Processed as submitted

### Impact Settings

- **Weather Impact**: Configurable mood impact
- **Event Impact**: Configurable productivity/morale impact
- **Suggestion Voting**: Configurable voting rules

## Troubleshooting

### Systems Not Generating Content

**Possible Causes**:
1. Background tasks not running
2. LLM (Ollama) not available
3. Database connection issues

**Solution**: Check background tasks, verify Ollama connection, check database

### Content Not Appearing in Frontend

**Possible Causes**:
1. API endpoints not working
2. Frontend not polling correctly
3. WebSocket not broadcasting

**Solution**: Check API endpoints, verify frontend polling, check WebSocket

## Best Practices

1. **Realistic Content**: Generate realistic, contextual content
2. **Appropriate Frequency**: Don't overwhelm with too much content
3. **Impact Balance**: Balance positive and negative impacts
4. **Employee Engagement**: Ensure systems engage employees
5. **Performance**: Keep generation efficient

## Future Enhancements

Potential improvements for each system:
- **Gossip**: Gossip networks, relationship graphs
- **Weather**: Weather forecasts, seasonal changes
- **Random Events**: More event types, event scheduling
- **Newsletter**: Newsletter subscriptions, email delivery
- **Suggestions**: Suggestion categories, implementation tracking

