"""
Company Reorganization Script
Fixes the organizational structure to have proper 1:10 manager-to-employee ratio
"""
import asyncio
import random
from database.database import async_session_maker
from database.models import Employee, Activity
from sqlalchemy import select, update
from config import now as local_now


async def reorganize_company():
    """
    Reorganize company to proper structure:
    - Keep executives (CEO, CTO, COO, CFO)
    - Maintain 1 manager per 10 employees ratio
    - Assign all employees to managers
    """
    print("=" * 70)
    print("COMPANY REORGANIZATION - Fixing Manager-to-Employee Ratio")
    print("=" * 70)
    print()

    async with async_session_maker() as db:
        # Step 1: Get all active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        all_employees = result.scalars().all()

        # Categorize employees
        executives = []  # CEO, CTO, COO, CFO
        managers = []
        regular_employees = []

        for emp in all_employees:
            if emp.role in ["CEO", "CTO", "COO", "CFO"]:
                executives.append(emp)
            elif emp.role == "Manager":
                managers.append(emp)
            else:
                regular_employees.append(emp)

        print(f"Current Structure:")
        print(f"  Executives (CEO, CTO, COO, CFO): {len(executives)}")
        print(f"  Managers: {len(managers)}")
        print(f"  Regular Employees: {len(regular_employees)}")
        print(f"  Total: {len(all_employees)}")
        print()

        # Step 2: Calculate how many managers we need
        # We have total employees = executives + managers + regular_employees
        # We want: 1 manager per 10 non-executive employees
        # So: num_managers_needed = (total - executives) / 10

        total_employees = len(all_employees)
        num_executives = len(executives)

        # Calculate ideal number of managers (1 per 10 employees, excluding executives)
        # Total non-executive employees will be: total - executives
        # We need: (total - executives - managers_needed) / managers_needed = 10
        # Solving: total - executives = managers_needed + 10 * managers_needed
        # total - executives = 11 * managers_needed
        # managers_needed = (total - executives) / 11

        num_managers_needed = max(1, (total_employees - num_executives) // 11)

        print(f"Target Structure:")
        print(f"  Executives: {num_executives} (unchanged)")
        print(f"  Managers needed: {num_managers_needed}")
        print(f"  Regular Employees: {total_employees - num_executives - num_managers_needed}")
        print(f"  Ratio: ~1 manager per {(total_employees - num_executives - num_managers_needed) / num_managers_needed:.1f} employees")
        print()

        # Step 3: Determine which managers to keep and which to demote
        if len(managers) > num_managers_needed:
            # Too many managers - need to demote some
            managers_to_keep = random.sample(managers, num_managers_needed)
            managers_to_demote = [m for m in managers if m not in managers_to_keep]

            print(f"Reorganization Plan:")
            print(f"  Keeping {len(managers_to_keep)} managers")
            print(f"  Converting {len(managers_to_demote)} managers to employees")
            print()

            # Demote excess managers to employees
            for manager in managers_to_demote:
                manager.role = "Employee"
                manager.hierarchy_level = 3
                manager.title = manager.title.replace("Manager", "Senior").replace("Lead", "Senior")
                regular_employees.append(manager)
                db.add(manager)

                # Log the demotion
                activity = Activity(
                    employee_id=manager.id,
                    activity_type="role_change",
                    description=f" {manager.name} was reorganized from Manager to Senior Employee as part of company restructuring"
                )
                db.add(activity)

            print(f"[OK] Demoted {len(managers_to_demote)} managers to employees")
            print()

        elif len(managers) < num_managers_needed:
            # Not enough managers - need to promote some employees
            num_to_promote = num_managers_needed - len(managers)
            if len(regular_employees) >= num_to_promote:
                employees_to_promote = random.sample(regular_employees, num_to_promote)

                print(f"Reorganization Plan:")
                print(f"  Promoting {len(employees_to_promote)} employees to managers")
                print()

                for employee in employees_to_promote:
                    employee.role = "Manager"
                    employee.hierarchy_level = 2
                    employee.title = f"{employee.department} Manager" if employee.department else "Manager"
                    managers_to_keep = managers + [employee]
                    regular_employees.remove(employee)
                    db.add(employee)

                    # Log the promotion
                    activity = Activity(
                        employee_id=employee.id,
                        activity_type="role_change",
                        description=f" {employee.name} was promoted to Manager as part of company restructuring"
                    )
                    db.add(activity)

                print(f"[OK] Promoted {len(employees_to_promote)} employees to managers")
                print()
            else:
                managers_to_keep = managers
        else:
            # Perfect number of managers
            managers_to_keep = managers
            print("Manager count is already optimal!")
            print()

        # Step 4: Assign CEO/executives their reporting structure
        ceo = None
        for exec in executives:
            if exec.role == "CEO":
                ceo = exec
                exec.manager_id = None  # CEO reports to no one
                exec.hierarchy_level = 1
                db.add(exec)
            else:
                # Other executives report to CEO
                exec.manager_id = ceo.id if ceo else None
                exec.hierarchy_level = 1  # Executives are level 1
                db.add(exec)

        print(f"[OK] Set up executive reporting structure (all report to CEO)")
        print()

        # Step 5: Assign managers to executives
        # Distribute managers evenly across executives
        if ceo:
            for manager in managers_to_keep:
                manager.manager_id = ceo.id
                manager.hierarchy_level = 2
                db.add(manager)

        print(f"[OK] Assigned {len(managers_to_keep)} managers to report to CEO")
        print()

        # Step 6: Assign regular employees to managers
        # Match employees to managers by department/specialization
        # Group employees by department
        employees_by_department = {}
        for emp in regular_employees:
            dept = emp.department or "General"
            if dept not in employees_by_department:
                employees_by_department[dept] = []
            employees_by_department[dept].append(emp)

        # Group managers by department
        managers_by_department = {}
        for manager in managers_to_keep:
            dept = manager.department or "General"
            if dept not in managers_by_department:
                managers_by_department[dept] = []
            managers_by_department[dept].append(manager)

        # Assign employees to managers matching their department
        assignments = {}
        unassigned_employees = []

        for dept, employees in employees_by_department.items():
            # Find managers in the same department
            matching_managers = managers_by_department.get(dept, [])
            
            if matching_managers:
                # Distribute employees evenly among matching managers
                random.shuffle(employees)
                employees_per_manager = len(employees) // len(matching_managers)
                remainder = len(employees) % len(matching_managers)
                
                employee_index = 0
                for i, manager in enumerate(matching_managers):
                    num_employees = employees_per_manager + (1 if i < remainder else 0)
                    assigned_employees = []
                    
                    for _ in range(num_employees):
                        if employee_index < len(employees):
                            emp = employees[employee_index]
                            emp.manager_id = manager.id
                            emp.hierarchy_level = 3
                            db.add(emp)
                            assigned_employees.append(emp)
                            employee_index += 1
                    
                    if manager.name not in assignments:
                        assignments[manager.name] = 0
                    assignments[manager.name] += len(assigned_employees)
            else:
                # No manager in this department - add to unassigned list
                unassigned_employees.extend(employees)

        # Assign unassigned employees to any available manager
        # Try to match by similar department names or assign to general managers
        if unassigned_employees:
            # Find managers with "General" or no specific department
            general_managers = [m for m in managers_to_keep if not m.department or m.department == "General"]
            if not general_managers:
                general_managers = managers_to_keep  # Fallback to all managers
            
            random.shuffle(unassigned_employees)
            employees_per_manager = len(unassigned_employees) // len(general_managers)
            remainder = len(unassigned_employees) % len(general_managers)
            
            employee_index = 0
            for i, manager in enumerate(general_managers):
                num_employees = employees_per_manager + (1 if i < remainder else 0)
                assigned_employees = []
                
                for _ in range(num_employees):
                    if employee_index < len(unassigned_employees):
                        emp = unassigned_employees[employee_index]
                        emp.manager_id = manager.id
                        emp.hierarchy_level = 3
                        db.add(emp)
                        assigned_employees.append(emp)
                        employee_index += 1
                
                if manager.name not in assignments:
                    assignments[manager.name] = 0
                assignments[manager.name] += len(assigned_employees)

        total_assigned = sum(assignments.values())
        print(f"[OK] Assigned {total_assigned} employees to {len(managers_to_keep)} managers (matched by department)")
        print()
        print("Distribution by Manager:")
        for manager_name, count in sorted(assignments.items(), key=lambda x: x[1], reverse=True)[:10]:
            # Find manager to get department info
            manager = next((m for m in managers_to_keep if m.name == manager_name), None)
            dept_info = f" ({manager.department})" if manager and manager.department else ""
            print(f"  {manager_name}{dept_info}: {count} employees")
        if len(assignments) > 10:
            print(f"  ... and {len(assignments) - 10} more managers")
        print()
        
        # Show department matching statistics
        print("Department Matching Statistics:")
        dept_stats = {}
        for emp in regular_employees:
            if emp.manager_id:
                manager = next((m for m in managers_to_keep if m.id == emp.manager_id), None)
                if manager:
                    emp_dept = emp.department or "General"
                    mgr_dept = manager.department or "General"
                    if emp_dept not in dept_stats:
                        dept_stats[emp_dept] = {"matched": 0, "total": 0}
                    dept_stats[emp_dept]["total"] += 1
                    if emp_dept == mgr_dept:
                        dept_stats[emp_dept]["matched"] += 1
        
        for dept, stats in sorted(dept_stats.items()):
            match_rate = (stats["matched"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"  {dept}: {stats['matched']}/{stats['total']} matched ({match_rate:.1f}%)")
        print()

        # Step 7: Commit all changes
        await db.commit()

        print("=" * 70)
        print("REORGANIZATION COMPLETE!")
        print("=" * 70)
        print()
        print("Final Structure:")
        print(f"  Executives: {num_executives}")
        print(f"  Managers: {len(managers_to_keep)}")
        print(f"  Regular Employees: {len(regular_employees)}")
        print(f"  Total: {num_executives + len(managers_to_keep) + len(regular_employees)}")
        print(f"  Manager-to-Employee Ratio: 1:{len(regular_employees) // len(managers_to_keep)}")
        print()
        print("All employees now have proper reporting relationships!")
        print("=" * 70)


async def verify_structure():
    """Verify the reorganization worked correctly."""
    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print()

    async with async_session_maker() as db:
        # Count by role
        from sqlalchemy import func
        result = await db.execute(
            select(Employee.role, func.count(Employee.id))
            .where(Employee.status == "active")
            .group_by(Employee.role)
        )
        roles = result.all()

        print("Role Distribution:")
        for role, count in roles:
            print(f"  {role}: {count}")
        print()

        # Check managers with no reports
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.role == "Manager"
            )
        )
        managers = result.scalars().all()

        managers_with_no_reports = []
        for manager in managers:
            result = await db.execute(
                select(func.count(Employee.id)).where(
                    Employee.manager_id == manager.id,
                    Employee.status == "active"
                )
            )
            report_count = result.scalar()
            if report_count == 0:
                managers_with_no_reports.append(manager.name)

        if managers_with_no_reports:
            print(f"[WARNING]  Warning: {len(managers_with_no_reports)} managers have no direct reports:")
            for name in managers_with_no_reports[:5]:
                print(f"  - {name}")
            if len(managers_with_no_reports) > 5:
                print(f"  ... and {len(managers_with_no_reports) - 5} more")
        else:
            print("[OK] All managers have direct reports")
        print()

        # Check employees with no manager
        result = await db.execute(
            select(Employee).where(
                Employee.status == "active",
                Employee.role == "Employee",
                Employee.manager_id.is_(None)
            )
        )
        orphan_employees = result.scalars().all()

        if orphan_employees:
            print(f"[WARNING]  Warning: {len(orphan_employees)} employees have no manager assigned")
        else:
            print("[OK] All employees have managers assigned")
        print()


if __name__ == "__main__":
    asyncio.run(reorganize_company())
    asyncio.run(verify_structure())
