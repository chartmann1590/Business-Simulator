# Sick Day Management System

## Overview

The sick day management system provides realistic employee illness tracking, automatic sick call generation, and recovery management. Employees can call in sick, stay home, and the system tracks sick day usage over time.

## Features

- **Automatic Sick Calls**: Randomly generates sick day call-ins (2-4% of employees per day)
- **Manual Sick Calls**: API endpoint for manually calling in employees as sick
- **Sick Day Tracking**: Tracks sick days per month and per year
- **Automatic Recovery**: Employees automatically recover after 1-3 days
- **Sick Day Statistics**: Company-wide statistics and reporting
- **Activity Logging**: All sick calls and returns are logged
- **Notification System**: Notifications for sick calls

## How It Works

### Automatic Sick Call Generation

**Timing**: Weekdays between 5am-8am (when employees would call in before work)

**Sick Rate**: 2-4% of active employees per day (realistic workplace average)

**Process**:
1. System checks current time during sick call window (5am-8am, weekdays only)
2. Selects active employees who are not already sick
3. Applies random sick rate (2-4%)
4. For each employee selected:
   - Randomly selects a sick reason from common reasons
   - Marks employee as sick
   - Updates employee state:
     - `is_sick` → `True`
     - `sick_since` → Current timestamp
     - `sick_reason` → Selected reason
     - `activity_state` → "sick"
     - `online_status` → "offline"
   - Increments sick day counters:
     - `sick_days_this_month` += 1
     - `sick_days_this_year` += 1
   - Creates activity log entry
   - Generates notification

**Common Sick Reasons**:
- Flu symptoms
- Stomach bug
- Migraine
- Cold and fever
- Back pain
- Sinus infection
- Allergies
- Not feeling well
- Doctor's appointment
- Family emergency (sick child)

### Manual Sick Calls

Employees can be manually called in sick via API:
- `POST /api/employees/{employee_id}/call-in-sick`
- Optional reason parameter
- Same process as automatic calls

### Automatic Recovery

**Recovery Process**:
- System automatically recovers employees who have been sick for 1-3 days
- Recovery probability based on time sick:
  - **After 24 hours**: 30% chance to recover
  - **After 48 hours**: 60% chance to recover
  - **After 72 hours**: 100% chance to recover (mandatory recovery)

**Recovery Actions**:
1. Clear sick status:
   - `is_sick` → `False`
   - `sick_since` → `None`
   - `sick_reason` → `None`
2. Update employee state:
   - `activity_state` → "at_home"
   - `online_status` → "online"
3. Create activity log entry
4. Calculate and log sick duration

### Return from Sick

Employees can be manually returned from sick leave:
- `POST /api/employees/{employee_id}/return-from-sick`
- Clears sick status immediately
- Calculates sick duration
- Updates employee state

## Database Structure

### Employee Table Fields

**Sick Day Tracking**:
- `is_sick` (Boolean): Currently sick status
- `sick_since` (DateTime): When employee called in sick
- `sick_reason` (String): Reason for sick day
- `sick_days_this_month` (Integer): Number of sick days this month
- `sick_days_this_year` (Integer): Number of sick days this year

**Indexes**:
- `idx_employees_is_sick`: Partial index on `is_sick = TRUE` for performance

## API Endpoints

### Get Sick Day Statistics

```
GET /api/sick-days/statistics
```

**Response**:
```json
{
  "currently_sick": 12,
  "total_employees": 500,
  "sick_rate": "2.40%",
  "total_sick_days_month": 45,
  "total_sick_days_year": 523,
  "avg_sick_days_per_employee": 1.05
}
```

### Get Sick Employees

```
GET /api/sick-days/employees
```

**Response**:
```json
[
  {
    "id": 123,
    "name": "John Doe",
    "title": "Senior Developer",
    "department": "Engineering",
    "reason": "Flu symptoms",
    "sick_since": "2024-01-15T06:30:00-05:00",
    "hours_sick": 18.5,
    "days_sick": 0.8,
    "sick_days_this_month": 2,
    "sick_days_this_year": 3
  }
]
```

### Call In Sick

```
POST /api/employees/{employee_id}/call-in-sick?reason=Flu symptoms
```

**Response**:
```json
{
  "success": true,
  "message": "John Doe successfully called in sick",
  "notification": {
    "type": "sick_call",
    "employee_id": 123,
    "employee_name": "John Doe",
    "department": "Engineering",
    "reason": "Flu symptoms",
    "timestamp": "2024-01-15T06:30:00-05:00",
    "message": "John Doe (Engineering) called in sick: Flu symptoms",
    "severity": "info"
  },
  "employee_id": 123,
  "reason": "Flu symptoms"
}
```

### Return from Sick

```
POST /api/employees/{employee_id}/return-from-sick
```

**Response**:
```json
{
  "success": true,
  "message": "John Doe returned from sick leave",
  "days_sick": 1.5,
  "reason": "Flu symptoms"
}
```

## Implementation

### SickDayManager Class

**File**: `backend/business/sick_day_manager.py`

**Key Methods**:

```python
async def generate_random_sick_calls(self) -> dict:
    """Randomly generate sick day call-ins (2-4% of employees)."""
    
async def call_in_sick(
    self,
    employee: Employee,
    reason: str = None,
    auto_generated: bool = False
) -> dict:
    """Process an employee calling in sick."""
    
async def return_from_sick(self, employee: Employee) -> dict:
    """Process an employee returning from sick leave."""
    
async def auto_recover_sick_employees(self) -> dict:
    """Automatically recover employees who have been sick for 1-3 days."""
    
async def get_sick_employees(self) -> list[dict]:
    """Get all currently sick employees."""
    
async def get_sick_day_statistics(self) -> dict:
    """Get overall sick day statistics for the company."""
    
async def reset_monthly_counters(self) -> dict:
    """Reset monthly sick day counters (run at start of each month)."""
```

### Integration with Office Simulator

The sick day manager is called periodically by the office simulator:
- **Sick call generation**: Every tick during 5am-8am window (weekdays)
- **Auto recovery**: Every tick to check for employees ready to recover
- **Monthly reset**: At start of each month

## Configuration

### Sick Rate

The sick rate can be adjusted in `sick_day_manager.py`:
- Default: 2-4% of employees per day
- Range: `random.uniform(0.02, 0.04)`
- Can be adjusted for different scenarios

### Recovery Timing

Recovery probabilities can be adjusted:
- After 24 hours: 30% chance (configurable)
- After 48 hours: 60% chance (configurable)
- After 72 hours: 100% chance (mandatory)

### Sick Call Window

Sick calls are generated during:
- **Time**: 5am-8am (configurable)
- **Days**: Weekdays only (Monday-Friday)

## State Management

### Sick States

**Healthy**:
- `is_sick`: `False`
- `activity_state`: Normal states (working, at_home, etc.)
- `online_status`: "online" or "offline" (based on location)

**Sick**:
- `is_sick`: `True`
- `activity_state`: "sick"
- `online_status`: "offline"
- `sick_since`: Timestamp of when they called in
- `sick_reason`: Reason for sick day

### Employee Location

When an employee calls in sick:
- If at work: Removed from office (current_room set to None)
- If at home: Stays at home
- Cannot clock in while sick
- Cannot attend meetings while sick

## Frontend Integration

### Employee Detail Page

The employee detail page shows:
- **Sick Status Card**: If employee is currently sick
  - Reason for sick day
  - When they called in sick
  - Sick days this month/year
  - Duration of current illness

### Dashboard Integration

Sick day statistics can be displayed on the dashboard:
- Currently sick count
- Sick rate percentage
- Monthly/yearly totals
- Average sick days per employee

## Monthly Reset

At the start of each month, the system:
1. Resets `sick_days_this_month` to 0 for all employees
2. Keeps `sick_days_this_year` for annual tracking
3. Logs reset activity

## Troubleshooting

### Employees Not Calling In Sick

**Possible Causes**:
1. Outside sick call window (before 5am or after 8am)
2. Weekend (no sick calls on weekends)
3. All employees already sick
4. System not running during window

**Solution**: Check current time and employee states

### Employees Not Recovering

**Possible Causes**:
1. Recovery probability not met yet
2. Employee hasn't been sick long enough
3. System not processing auto recovery

**Solution**: Check recovery probabilities and sick duration

### Sick Day Counters Not Updating

**Possible Causes**:
1. Database migration not run
2. Fields not initialized
3. Transaction not committed

**Solution**: 
- Run migration script: `python migrate_sleep_and_sick_metrics.py`
- Check database schema
- Verify transaction commits

## Best Practices

1. **Realistic Rates**: Keep sick rate at 2-4% for realism
2. **Recovery Timing**: Use 1-3 day recovery window
3. **Monthly Reset**: Reset monthly counters at start of month
4. **Activity Logging**: Log all sick calls and returns
5. **Notification System**: Notify managers of sick calls
6. **Statistics Tracking**: Track sick day usage over time

## Future Enhancements

Potential improvements:
- Sick day policies (limited days per year)
- Doctor's note requirements
- Contagious illness tracking
- Team impact analysis (when manager is sick)
- Sick day patterns and analytics
- Return-to-work interviews
- Wellness program integration

