# Organizational Structure Implementation

## Overview
Fixed the company organizational structure to maintain a proper 1:10 manager-to-employee ratio.

## Problem
- Had 491 managers and only 6 employees (completely inverted structure)
- No reporting hierarchy
- Unsustainable and unrealistic organization

## Solution

### 1. Database Changes
**New Field**: `manager_id` on `employees` table
- Tracks direct manager for each employee
- Self-referencing foreign key
- Indexed for performance

**Relationships**:
- `employee.manager` - Access employee's direct manager
- `manager.direct_reports` - Access list of direct reports

### 2. Proper Organizational Structure
**Target Ratio**: 1 manager per 10 employees

**Hierarchy**:
```
Level 1: CEO + Executives (CEO, CTO, COO, CFO)
Level 2: Managers (~45-50 managers)
Level 3: Employees (~445-450 employees)
```

**Reporting Structure**:
- Executives → Report to CEO
- Managers → Report to CEO
- Employees → Report to assigned Manager

### 3. Reorganization Script
**File**: `backend/reorganize_company.py`

**What it does**:
1. Keeps all executives (CEO, CTO, COO, CFO)
2. Calculates optimal number of managers needed
3. Randomly selects managers to keep
4. Converts excess managers to senior employees
5. Distributes employees evenly across managers
6. Updates all reporting relationships

**Usage**:
```bash
cd backend
python reorganize_company.py
```

### 4. Future Prevention
The system will now enforce the 1:10 ratio when:
- Hiring new employees
- Promoting employees to manager
- Demoting managers to employees

## How to Use

### Run Reorganization (First Time)
```bash
# 1. Restart backend to apply migrations
# 2. Run reorganization script
cd backend
python reorganize_company.py
```

### Check Current Structure
```python
import asyncio
from database.database import async_session_maker
from database.models import Employee
from sqlalchemy import select, func

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(Employee.role, func.count(Employee.id))
            .where(Employee.status == 'active')
            .group_by(Employee.role)
        )
        for role, count in result.all():
            print(f"{role}: {count}")

asyncio.run(check())
```

## API Endpoints

### Get Employee with Manager/Reports
```
GET /api/employees/{id}
```
Returns:
```json
{
  "id": 123,
  "name": "John Doe",
  "role": "Manager",
  "manager": {
    "id": 1,
    "name": "Jane CEO"
  },
  "direct_reports": [
    {"id": 456, "name": "Alice Employee"},
    {"id": 789, "name": "Bob Employee"}
  ]
}
```

### Get Company Hierarchy
```
GET /api/company-hierarchy
```
Returns complete organizational tree.

## Dashboard Changes

### Company Overview Tab
- New organizational hierarchy tree visualization
- Shows CEO at top
- Cascading down through all levels
- Interactive nodes
- Shows all ~500 employees

## Employee Detail Pages

### For Managers
- Shows list of direct reports
- Employee count
- Quick links to report profiles

### For Employees
- Shows direct manager
- Manager contact info
- Quick link to manager profile

## Maintenance

### Regular Checks
Run verification periodically:
```bash
cd backend
python reorganize_company.py --verify-only
```

### Re-balance if Needed
If structure gets out of balance:
```bash
cd backend
python reorganize_company.py --rebalance
```

## Notes
- Executives never get demoted
- Manager assignments are random but balanced
- Each manager gets approximately equal number of reports
- Structure is maintained automatically during hiring/firing
