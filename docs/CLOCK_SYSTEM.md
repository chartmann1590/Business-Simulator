# Clock In/Out System

## Overview

The clock in/out system provides automatic time tracking for employee arrivals and departures, managing the transition between office and home states.

## Features

- **Automatic Clock In**: Employees clock in during morning arrival window (6:45am-7:45am)
- **Automatic Clock Out**: Employees clock out during evening departure window (6:45pm-7:15pm)
- **Staggered Timing**: Employees arrive and depart at different times for realism
- **State Transitions**: Manages transitions between office and home states
- **Time Tracking**: Complete history of all clock events
- **Online Status**: Updates Teams online/offline status based on location

## How It Works

### Morning Arrivals (6:45am-7:45am)

**Timing Windows**:
- **6:45am-7:00am**: 30% of employees arrive
- **7:00am-7:15am**: 40% of employees arrive
- **7:15am-7:30am**: 20% of employees arrive
- **7:30am-7:45am**: Remaining 10% arrive

**Process**:
1. System checks current time during arrival window
2. Selects employees who are at home and not already clocked in
3. Staggers arrivals based on time window
4. Logs "clock_in" event with location "office"
5. Updates employee state:
   - `activity_state` → "working"
   - `online_status` → "online"
6. Creates activity log entry

**Weekend Handling**:
- No clock-ins on weekends (Saturday/Sunday)
- System skips processing on weekends

### Evening Departures (6:45pm-7:15pm)

**Timing Windows**:
- **6:45pm-7:00pm**: 40% of employees leave
- **7:00pm-7:10pm**: 50% of employees leave
- **7:10pm-7:15pm**: Remaining 10% leave

**Process**:
1. System checks current time during departure window
2. Selects employees who are at work (not at home, sleeping, or already leaving)
3. Staggers departures based on time window
4. Logs "clock_out" event with location "office"
5. Updates employee state:
   - `activity_state` → "leaving_work"
   - `online_status` → "offline"
6. Creates activity log entry
7. Employee transitions to "commuting_home" then "at_home"

**Weekend Handling**:
- No clock-outs on weekends
- System skips processing on weekends

### Commuting Process

**States**:
1. `leaving_work` - Employee has clocked out and is leaving office
2. `commuting_home` - Employee is traveling home
3. `at_home` - Employee has arrived home

**Events Logged**:
- `clock_out` - When leaving office
- `left_home` - When leaving home (for morning commute)
- `arrived_home` - When arriving home

## Database Structure

### ClockInOut Table

```sql
CREATE TABLE clock_in_out (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    event_type VARCHAR(50),  -- 'clock_in', 'clock_out', 'arrived_home', 'left_home'
    location VARCHAR(50),    -- 'office' or 'home'
    notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Fields**:
- `employee_id`: Reference to employee
- `event_type`: Type of clock event
- `location`: Where the event occurred
- `notes`: Additional context (optional)
- `timestamp`: When the event occurred

## API Endpoints

### Get Employee Clock History

```
GET /api/clock/employee/{employee_id}
```

**Response**:
```json
{
  "employee_id": 123,
  "events": [
    {
      "id": 1,
      "event_type": "clock_in",
      "location": "office",
      "timestamp": "2024-01-15T07:15:00-05:00",
      "notes": null
    },
    {
      "id": 2,
      "event_type": "clock_out",
      "location": "office",
      "timestamp": "2024-01-15T18:45:00-05:00",
      "notes": null
    }
  ]
}
```

### Get Today's Clock Events

```
GET /api/clock/today
```

**Response**:
```json
{
  "date": "2024-01-15",
  "events": [
    {
      "employee_id": 123,
      "employee_name": "John Doe",
      "event_type": "clock_in",
      "timestamp": "2024-01-15T07:15:00-05:00"
    }
  ],
  "summary": {
    "total_clock_ins": 450,
    "total_clock_outs": 445,
    "employees_at_work": 450
  }
}
```

## Implementation

### ClockManager Class

**File**: `backend/business/clock_manager.py`

**Key Methods**:

```python
async def process_morning_arrivals(self) -> dict:
    """Process morning arrivals (6:45am-7:45am)."""
    
async def process_end_of_day_departures(self) -> dict:
    """Process end-of-day departures (6:45pm-7:15pm)."""
    
async def log_clock_event(
    self,
    employee_id: int,
    event_type: str,
    location: str = None,
    notes: str = None
) -> ClockInOut:
    """Log a clock in/out event."""
```

### Integration with Office Simulator

The clock manager is called periodically by the office simulator:
- Morning arrivals: Every tick during 6:45am-7:45am window
- Evening departures: Every tick during 6:45pm-7:15pm window

## Configuration

### Timezone

All times are in **New York timezone** (America/New_York) as configured in `config.py`.

The `now()` function returns timezone-aware datetimes in New York time.

### Timing Windows

Timing windows can be adjusted in `clock_manager.py`:
- Arrival window: 6:45am-7:45am (configurable)
- Departure window: 6:45pm-7:15pm (configurable)
- Stagger percentages: Adjustable per time window

## State Management

### Employee States

**At Office**:
- `activity_state`: "working", "meeting", "break", "training"
- `online_status`: "online"

**Leaving**:
- `activity_state`: "leaving_work"
- `online_status`: "offline"

**Commuting**:
- `activity_state`: "commuting_home"
- `online_status`: "offline"

**At Home**:
- `activity_state`: "at_home", "sleeping"
- `online_status`: "offline"

## Troubleshooting

### Employees Not Clocking In

**Possible Causes**:
1. Outside arrival window (before 6:45am or after 7:45am)
2. Weekend (no clock-ins on weekends)
3. Employee already at office
4. Employee already clocked in today

**Solution**: Check employee state and current time

### Employees Not Clocking Out

**Possible Causes**:
1. Outside departure window (before 6:45pm or after 7:15pm)
2. Weekend (no clock-outs on weekends)
3. Employee already at home
4. Employee already clocked out today

**Solution**: Check employee state and current time

### Missing Clock Events

**Possible Causes**:
1. System not running during clock windows
2. Database connection issues
3. Employee state conflicts

**Solution**: 
- Check system logs
- Verify database connectivity
- Review employee states

## Best Practices

1. **Consistent Timing**: Ensure system runs continuously during clock windows
2. **State Validation**: Verify employee states before clock events
3. **Error Handling**: Log errors but don't block other employees
4. **Timezone Awareness**: Always use timezone-aware datetimes
5. **Activity Logging**: Create activity entries for all clock events

## Future Enhancements

Potential improvements:
- Flexible work hours (different employees, different schedules)
- Remote work support (clock in from home)
- Overtime tracking
- Break time tracking
- Attendance reports
- Late arrival tracking
- Early departure tracking

