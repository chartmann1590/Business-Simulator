# Organizational Structure System

## Overview

The organizational structure system maintains a proper hierarchical structure with a 1:10 manager-to-employee ratio, ensuring realistic and sustainable organizational management.

## Problem Statement

Previously, the system had an inverted organizational structure with 491 managers and only 6 employees, which was:
- Unsustainable and unrealistic
- Lacked proper reporting hierarchy
- Created management overhead without clear structure

## Solution

### Database Changes

**New Field**: `manager_id` on `employees` table
- Tracks direct manager for each employee
- Self-referencing foreign key to `employees.id`
- Indexed for performance
- Nullable (CEO has no manager)

**Relationships**:
- `employee.manager` - Access employee's direct manager
- `manager.direct_reports` - Access list of direct reports (backref)

### Organizational Structure

**Target Ratio**: 1 manager per 10 employees

**Hierarchy Levels**:
```
Level 1: CEO + Executives (CEO, CTO, COO, CFO)
Level 2: Managers (~45-50 managers)
Level 3: Employees (~445-450 employees)
```

**Reporting Structure**:
- Executives → Report to CEO
- Managers → Report to CEO
- Employees → Report to assigned Manager

### Reorganization Script

**File**: `backend/reorganize_company.py`

**What it does**:
1. Keeps all executives (CEO, CTO, COO, CFO) - never demoted
2. Calculates optimal number of managers needed based on employee count
3. Randomly selects managers to keep (maintains 1:10 ratio)
4. Converts excess managers to senior employees
5. Distributes employees evenly across managers
6. Updates all reporting relationships
7. Maintains department assignments

**Usage**:
```bash
cd backend
python reorganize_company.py
```

**Options**:
- `--verify-only` - Check current structure without making changes
- `--rebalance` - Re-balance existing structure if it gets out of sync

### Migration

**File**: `backend/add_manager_column.py`

Adds the `manager_id` column to the employees table if it doesn't exist.

**Usage**:
```bash
cd backend
python add_manager_column.py
```

## API Endpoints

### Get Employee with Manager/Reports

```
GET /api/employees/{id}
```

**Response**:
```json
{
  "id": 123,
  "name": "John Doe",
  "title": "Senior Developer",
  "role": "Employee",
  "department": "Engineering",
  "manager": {
    "id": 45,
    "name": "Jane Manager",
    "title": "Engineering Manager"
  },
  "direct_reports": [],
  "hierarchy_level": 3
}
```

### Get Company Hierarchy

```
GET /api/company-hierarchy
```

**Response**:
```json
{
  "hierarchy": {
    "id": 1,
    "name": "CEO Name",
    "role": "CEO",
    "children": [
      {
        "id": 2,
        "name": "CTO Name",
        "role": "CTO",
        "children": []
      },
      {
        "id": 45,
        "name": "Manager Name",
        "role": "Manager",
        "direct_reports_count": 10,
        "children": [
          {
            "id": 100,
            "name": "Employee Name",
            "role": "Employee",
            "children": []
          }
        ]
      }
    ]
  },
  "stats": {
    "total": 500,
    "executives": 4,
    "managers": 50,
    "employees": 446,
    "ratio": "1:8.9"
  }
}
```

## Frontend Integration

### Organization Chart Component

**File**: `frontend/src/components/OrganizationChart.jsx`

**Features**:
- Interactive tree visualization
- Expand/collapse nodes
- Color-coded by role (CEO/Executives: purple, Managers: blue, Employees: gray)
- Click to navigate to employee detail page
- Shows direct reports count
- Auto-expands first 2 levels
- Refresh button to reload hierarchy

**Usage**:
```jsx
import OrganizationChart from '../components/OrganizationChart'

<OrganizationChart />
```

### Dashboard Integration

The organization chart is displayed in the Dashboard's "Company Overview" tab, showing the complete organizational structure.

### Employee Detail Pages

**For Managers**:
- Shows list of direct reports
- Employee count
- Quick links to report profiles
- Manager hierarchy visualization

**For Employees**:
- Shows direct manager
- Manager contact info
- Quick link to manager profile
- Reporting chain visualization

## Maintenance

### Regular Checks

Run verification periodically to ensure structure is maintained:
```bash
cd backend
python reorganize_company.py --verify-only
```

### Re-balance if Needed

If structure gets out of balance (e.g., after hiring/firing):
```bash
cd backend
python reorganize_company.py --rebalance
```

### Automatic Maintenance

The system automatically maintains the structure when:
- Hiring new employees (assigned to managers with fewer reports)
- Promoting employees to manager (checks ratio)
- Demoting managers to employees (redistributes reports)
- Firing employees (rebalances remaining employees)

## Implementation Details

### Database Schema

```sql
ALTER TABLE employees 
ADD COLUMN manager_id INTEGER REFERENCES employees(id);

CREATE INDEX idx_employees_manager_id ON employees(manager_id);
```

### SQLAlchemy Model

```python
class Employee(Base):
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    manager = relationship("Employee", remote_side=[id], foreign_keys=[manager_id], backref="direct_reports")
```

### Query Optimization

The hierarchy endpoint uses optimized queries:
- Single query with recursive CTE (PostgreSQL) or Python-based tree building
- Cached results for 15 seconds
- Efficient loading of relationships

## Best Practices

1. **Maintain Ratio**: Always keep 1:10 manager-to-employee ratio
2. **Even Distribution**: Distribute employees evenly across managers
3. **Department Awareness**: Consider department when assigning managers
4. **Never Demote Executives**: CEO, CTO, COO, CFO are permanent
5. **Regular Verification**: Run verification checks periodically

## Troubleshooting

### Structure Out of Balance

If the structure becomes unbalanced:
1. Run `reorganize_company.py --verify-only` to check current state
2. Run `reorganize_company.py --rebalance` to fix it
3. Check logs for any errors during reorganization

### Missing Manager Assignments

If employees have no manager assigned:
1. Check that managers exist in the system
2. Run reorganization script to assign managers
3. Verify `manager_id` column exists in database

### Performance Issues

If hierarchy queries are slow:
1. Ensure `manager_id` column is indexed
2. Check query cache is working
3. Consider increasing cache duration for hierarchy endpoint

## Future Enhancements

Potential improvements:
- Multi-level management (managers reporting to managers)
- Department-specific hierarchies
- Manager performance metrics based on team size
- Automatic promotion/demotion based on performance
- Team restructuring recommendations

