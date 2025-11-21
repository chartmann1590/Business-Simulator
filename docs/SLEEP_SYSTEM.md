# Sleep System

## Overview

The sleep system manages realistic sleep/wake cycles for employees, family members, and home pets, creating a natural day/night rhythm in the simulation.

## Features

- **Bedtime Transitions**: Staggered bedtime between 10pm-12am
- **Morning Wake-ups**: Employees wake 5:30am-6:45am, family members wake 7:30am-9am
- **Sleep State Tracking**: Tracks sleep state for employees, family members, and pets
- **Coordinated Sleep**: When employees go to sleep, their family members and pets also sleep
- **Weekend Variations**: Family members can wake later on weekends
- **Pet Sleep**: Home pets follow sleep schedules

## How It Works

### Bedtime Process (10pm-12am)

**Staggered Timing**:
- **10:00pm-10:30pm (22:00-22:30)**: 30% go to sleep
- **10:30pm-11:00pm (22:30-23:00)**: 40% go to sleep
- **11:00pm-11:30pm (23:00-23:30)**: 20% go to sleep
- **11:30pm-12:00am (23:30-00:00)**: Everyone remaining goes to sleep
- **12:00am-12:30am (00:00-00:30)**: Final stragglers go to sleep

**Process**:
1. System checks current time during bedtime window
2. Selects employees who are awake
3. Applies staggered probability based on time window
4. Updates employee state:
   - `sleep_state` → "sleeping"
   - `activity_state` → "sleeping"
5. Updates family members:
   - All family members in employee's home also go to sleep
   - `sleep_state` → "sleeping"
6. Updates home pets:
   - All pets in employee's home also go to sleep
   - `sleep_state` → "sleeping"
7. Creates activity log entries

**Late Night Handling**:
- Hours 1-5am: People should already be sleeping (no new bedtimes)
- After 12:30am: No new bedtimes processed

### Morning Wake-ups

**Employee Wake-ups (5:30am-6:45am)**:
- **5:30am-6:00am**: 30% wake up
- **6:00am-6:30am**: 40% wake up
- **6:30am-6:45am**: 30% wake up

**Family Member Wake-ups (7:30am-9:00am)**:
- **7:30am-8:00am**: 30% wake up
- **8:00am-8:30am**: 40% wake up
- **8:30am-9:00am**: 30% wake up

**Weekend Variations**:
- Family members can wake 30-60 minutes later on weekends
- Employees maintain consistent wake-up times

**Process**:
1. System checks current time during wake-up window
2. Selects employees/family members who are sleeping
3. Applies staggered probability based on time window
4. Updates state:
   - `sleep_state` → "awake"
   - `activity_state` → "awake" (for employees)
5. Creates activity log entries

## Database Structure

### Employee Sleep State

**Field**: `sleep_state` on `employees` table
- Values: "awake", "sleeping", "in_bed"
- Default: "awake"

### Family Member Sleep State

**Field**: `sleep_state` on `family_members` table
- Values: "awake", "sleeping"
- Default: "awake"

### Home Pet Sleep State

**Field**: `sleep_state` on `home_pets` table
- Values: "awake", "sleeping"
- Default: "awake"

## API Endpoints

### Get Employee Sleep Status

```
GET /api/employees/{id}
```

**Response includes**:
```json
{
  "id": 123,
  "name": "John Doe",
  "sleep_state": "sleeping",
  "activity_state": "sleeping",
  "family_members": [
    {
      "id": 1,
      "name": "Jane Doe",
      "sleep_state": "sleeping"
    }
  ],
  "home_pets": [
    {
      "id": 1,
      "name": "Fluffy",
      "sleep_state": "sleeping"
    }
  ]
}
```

## Implementation

### SleepManager Class

**File**: `backend/business/sleep_manager.py`

**Key Methods**:

```python
async def process_bedtime(self) -> dict:
    """Process bedtime transitions (10pm-12am)."""
    
async def process_morning_wakeups(self) -> dict:
    """Process morning wake-ups (employees: 5:30am-6:45am, family: 7:30am-9am)."""
```

### Integration with Office Simulator

The sleep manager is called periodically by the office simulator:
- Bedtime: Every tick during 10pm-12:30am window
- Wake-ups: Every tick during wake-up windows

## Configuration

### Timezone

All times are in **New York timezone** (America/New_York) as configured in `config.py`.

### Timing Windows

Timing windows can be adjusted in `sleep_manager.py`:
- Bedtime window: 10pm-12:30am (configurable)
- Employee wake-up: 5:30am-6:45am (configurable)
- Family wake-up: 7:30am-9:00am (configurable)
- Weekend delay: 30-60 minutes (configurable)

## State Management

### Sleep States

**Awake**:
- `sleep_state`: "awake"
- Can perform activities
- Can interact with others

**Sleeping**:
- `sleep_state`: "sleeping"
- Cannot perform activities
- Cannot interact with others
- Activity state also set to "sleeping"

**In Bed** (employees only):
- `sleep_state`: "in_bed"
- Transitional state before sleeping

### Coordinated Sleep

When an employee goes to sleep:
1. All family members in the same home also go to sleep
2. All home pets in the same home also go to sleep
3. All sleep states are updated simultaneously
4. Activity logs are created for all entities

## Home System Integration

The sleep system integrates with the home system:
- Employees have homes with family members and pets
- Sleep schedules are coordinated per household
- Home view shows sleep states in real-time

## Troubleshooting

### Employees Not Going to Sleep

**Possible Causes**:
1. Outside bedtime window (before 10pm or after 12:30am)
2. Employee already sleeping
3. System not running during bedtime window

**Solution**: Check current time and employee state

### Family Members Not Sleeping

**Possible Causes**:
1. Employee not sleeping (family sleeps when employee sleeps)
2. Family member doesn't exist
3. Database issue

**Solution**: Verify employee sleep state and family member records

### Wake-ups Not Happening

**Possible Causes**:
1. Outside wake-up window
2. Employee/family already awake
3. System not running during wake-up window

**Solution**: Check current time and sleep states

## Best Practices

1. **Staggered Timing**: Use staggered probabilities for realistic behavior
2. **Coordinated Sleep**: Ensure family and pets sleep with employees
3. **State Consistency**: Keep sleep_state and activity_state in sync
4. **Activity Logging**: Create activity entries for all sleep transitions
5. **Weekend Handling**: Apply weekend variations for family members

## Future Enhancements

Potential improvements:
- Individual sleep schedules (early birds vs night owls)
- Sleep quality tracking
- Napping support
- Sleep disorders simulation
- Alarm clock system
- Sleep statistics and analytics

