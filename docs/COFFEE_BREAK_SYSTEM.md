# Coffee Break System

## Overview

The coffee break system provides natural break opportunities for employees while preventing abuse through strict timing rules and capacity management.

## Features

- **Automatic Breaks**: Employees automatically take coffee breaks based on work patterns
- **Strict Timing Rules**: Minimum 2 hours between breaks (no exceptions)
- **Manager Restrictions**: Managers have stricter break rules to prevent abuse
- **Meeting Awareness**: Breaks are denied if meetings are scheduled within 30 minutes
- **Capacity Management**: Breaks are denied if breakrooms are at capacity
- **Breakroom Movement**: Employees automatically move to breakrooms during breaks
- **Social Interactions**: Breaks enable social interactions and gossip

## How It Works

### Break Eligibility

**Minimum Time Between Breaks**: 2 hours (absolute minimum, no exceptions)

**Regular Employees**:
- First break: Can take immediately (if no previous break today)
- Subsequent breaks: Every 2-4 hours
  - After 4 hours: Definitely time for a break
  - After 2-4 hours: 30% chance
  - Before 2 hours: No break allowed

**Managers (CEO, CTO, COO, CFO, Managers)**:
- First break: Must wait (no immediate breaks)
- Subsequent breaks: Every 4-6 hours
  - After 6 hours: Definitely time for a break
  - After 4-6 hours: 15% chance (stricter than regular employees)
  - Before 4 hours: No break allowed

### Break Process

**Pre-Break Checks**:
1. **Time Check**: Must be at least 2 hours since last break
2. **Meeting Check**: No meetings scheduled within next 30 minutes
3. **Capacity Check**: Breakroom must have available space
4. **Manager Abuse Check**: Managers checked for excessive break frequency

**Break Execution**:
1. Employee moves to appropriate breakroom
2. `last_coffee_break` timestamp updated
3. Activity log created
4. Employee state updated to "break"
5. Break duration: ~15-30 minutes (simulated)

**Breakroom Selection**:
- Floor 1 employees → Floor 1 breakroom
- Floor 2 employees → Floor 2 breakroom
- Floor 3+ employees → Floor 2 or Floor 1 breakroom (random)
- If preferred breakroom full → Try alternate breakroom
- If both full → Break denied

### Break Denial Reasons

Breaks can be denied for:
1. **Too Soon**: Less than 2 hours since last break
2. **Upcoming Meeting**: Meeting scheduled within 30 minutes
3. **Capacity Full**: All breakrooms at capacity
4. **Manager Abuse**: Manager taking breaks too frequently

## Database Structure

### Employee Break Tracking

**Field**: `last_coffee_break` on `employees` table
- Type: `DateTime(timezone=True)`
- Nullable: Yes (null if no break taken yet)
- Tracks timestamp of last coffee break

### Breakroom Capacity

Breakrooms have defined capacities:
- Floor 1 Breakroom: 20 people
- Floor 2 Breakroom: 20 people
- Total capacity: 40 people across all breakrooms

## API Endpoints

### Get Employee Break Status

```
GET /api/employees/{id}
```

**Response includes**:
```json
{
  "id": 123,
  "name": "John Doe",
  "last_coffee_break": "2024-01-15T14:30:00-05:00",
  "activity_state": "break",
  "current_room": "breakroom"
}
```

### Check Break Eligibility

The system automatically checks eligibility when processing employee actions. No direct API endpoint, but break status is visible in employee details.

## Implementation

### CoffeeBreakManager Class

**File**: `backend/business/coffee_break_manager.py`

**Key Methods**:

```python
async def should_take_coffee_break(self, employee: Employee) -> bool:
    """Determine if an employee should take a coffee break."""
    
async def take_coffee_break(self, employee: Employee) -> Activity:
    """Record a coffee break and move employee to breakroom."""
    
async def check_upcoming_meetings(self, employee: Employee, minutes_ahead: int) -> Optional[Meeting]:
    """Check if employee has meetings coming up."""
    
async def check_breakroom_capacity(self, breakroom_name: str) -> dict:
    """Check if breakroom has available space."""
    
async def check_manager_break_frequency(self, employee: Employee) -> dict:
    """Check if manager is abusing break system."""
```

### Integration with Office Simulator

The coffee break manager is called during employee processing:
- Employees are evaluated for break eligibility
- Breaks are taken automatically when conditions are met
- Break status is tracked and logged

## Configuration

### Timing Rules

Timing rules can be adjusted in `coffee_break_manager.py`:
- Minimum break interval: 2 hours (configurable)
- Regular employee break window: 2-4 hours (configurable)
- Manager break window: 4-6 hours (configurable)
- Break probability: 30% (regular), 15% (managers) (configurable)

### Breakroom Capacities

Breakroom capacities are defined in room configuration:
- Can be adjusted per breakroom
- Affects break availability

## State Management

### Break States

**Taking Break**:
- `activity_state`: "break"
- `current_room`: Breakroom name
- `last_coffee_break`: Updated timestamp

**Break Duration**:
- Breaks last ~15-30 minutes (simulated)
- Employee returns to work after break
- `activity_state` returns to "working"

## Manager Abuse Prevention

### Abuse Detection

Managers are checked for:
- Excessive break frequency
- Breaks too close together
- Breaks during critical work hours

### Abuse Consequences

If abuse detected:
- Break is denied
- Warning logged
- Manager must wait longer before next break

## Meeting Integration

### Meeting Awareness

Before allowing a break:
1. System checks for upcoming meetings
2. If meeting within 30 minutes → Break denied
3. Meeting time displayed in denial message

### Meeting Priority

Meetings take priority over breaks:
- Employees cannot take breaks before meetings
- Breaks are automatically denied if meeting is soon
- Employees return to work before meetings

## Social Interactions

### Breakroom Socializing

During breaks, employees can:
- Engage in gossip
- Have social conversations
- Build relationships
- Share information

### Gossip System Integration

The gossip system is more active during breaks:
- Employees in breakrooms generate more gossip
- Social interactions increase
- Relationship building occurs

## Troubleshooting

### Breaks Not Happening

**Possible Causes**:
1. Too soon since last break (< 2 hours)
2. Upcoming meeting within 30 minutes
3. Breakrooms at capacity
4. Manager restrictions (managers have stricter rules)

**Solution**: Check break eligibility conditions

### Breaks Happening Too Frequently

**Possible Causes**:
1. Timing rules not enforced
2. Manager abuse detection not working
3. Break interval too short

**Solution**: Verify timing rules and abuse detection

### Breakrooms Always Full

**Possible Causes**:
1. Too many employees taking breaks simultaneously
2. Breakroom capacity too low
3. Employees not leaving breakrooms

**Solution**: 
- Increase breakroom capacity
- Stagger break timing more
- Ensure employees leave breakrooms after breaks

## Best Practices

1. **Strict Timing**: Always enforce 2-hour minimum between breaks
2. **Manager Restrictions**: Apply stricter rules for managers
3. **Capacity Management**: Check capacity before allowing breaks
4. **Meeting Awareness**: Always check for upcoming meetings
5. **Abuse Prevention**: Monitor and prevent break abuse
6. **Staggered Breaks**: Distribute breaks throughout the day

## Future Enhancements

Potential improvements:
- Break scheduling (planned breaks)
- Break preferences (coffee vs tea, etc.)
- Breakroom amenities (games, snacks, etc.)
- Break statistics and analytics
- Breakroom reservations
- Team breaks (groups taking breaks together)

