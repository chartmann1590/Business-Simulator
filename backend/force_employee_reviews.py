#!/usr/bin/env python3
"""
Force Employee Reviews Script
Generates reviews immediately for all employees who are overdue for reviews.
Overdue = more than 6 hours since last review (or since hire if no reviews exist).

Usage:
    python force_employee_reviews.py [--yes] [--verbose]
    
    --yes: Skip confirmation prompt and generate reviews immediately
    --verbose: Show detailed logging for each review generation
"""

import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import select, desc

# Add parent directory to path to import modules
sys.path.insert(0, '.')

from database.database import async_session_maker
from database.models import Employee, EmployeeReview
from business.review_manager import ReviewManager


async def force_overdue_reviews(skip_confirmation=False, verbose=False):
    """Force generate reviews for all overdue employees."""
    print("=" * 80)
    print("FORCE EMPLOYEE REVIEWS SCRIPT")
    print("=" * 80)
    print()
    
    now = datetime.utcnow()
    hours_threshold = 6.0
    cutoff_date = now - timedelta(hours=hours_threshold)
    
    try:
        async with async_session_maker() as db:
            print(f"[*] Checking for overdue reviews (threshold: {hours_threshold} hours)...")
            print(f"[*] Current time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print()
            
            # Get all active employees (excluding top executives who don't get reviewed)
            result = await db.execute(
                select(Employee).where(
                    Employee.status == "active",
                    Employee.role.notin_(["CEO", "CTO", "COO", "CFO"])  # Executives don't get reviewed
                ).order_by(Employee.name)
            )
            all_employees = result.scalars().all()
            
            print(f"[*] Found {len(all_employees)} active employees eligible for reviews")
            print()
            
            overdue_employees = []
            employees_with_recent_reviews = []
            employees_too_new = []
            
            # Check each employee
            for employee in all_employees:
                # Get last review
                review_result = await db.execute(
                    select(EmployeeReview)
                    .where(EmployeeReview.employee_id == employee.id)
                    .order_by(desc(EmployeeReview.review_date))
                    .limit(1)
                )
                last_review = review_result.scalar_one_or_none()
                
                is_overdue = False
                reason = ""
                
                if not last_review:
                    # No review yet - check if hired long enough ago
                    if employee.hired_at:
                        hired_at_naive = employee.hired_at.replace(tzinfo=None) if employee.hired_at.tzinfo else employee.hired_at
                        hours_since_hire = (now - hired_at_naive).total_seconds() / 3600
                        if hours_since_hire >= hours_threshold:
                            is_overdue = True
                            reason = f"No review yet, hired {hours_since_hire:.1f} hours ago"
                        else:
                            reason = f"Too new - hired {hours_since_hire:.1f} hours ago (need {hours_threshold} hours)"
                    else:
                        # No hire date - consider overdue
                        is_overdue = True
                        reason = "No review yet, no hire date recorded"
                else:
                    # Has review - check if it's old enough
                    if last_review.review_date:
                        review_date = last_review.review_date.replace(tzinfo=None) if last_review.review_date.tzinfo else last_review.review_date
                        hours_since_review = (now - review_date).total_seconds() / 3600
                        if review_date < cutoff_date:
                            is_overdue = True
                            reason = f"Last review {hours_since_review:.1f} hours ago (overdue by {hours_since_review - hours_threshold:.1f} hours)"
                        else:
                            reason = f"Recent review {hours_since_review:.1f} hours ago"
                    else:
                        # Review has no date - use created_at
                        if last_review.created_at:
                            review_date = last_review.created_at.replace(tzinfo=None) if last_review.created_at.tzinfo else last_review.created_at
                            hours_since_review = (now - review_date).total_seconds() / 3600
                            if review_date < cutoff_date:
                                is_overdue = True
                                reason = f"Last review {hours_since_review:.1f} hours ago (overdue by {hours_since_review - hours_threshold:.1f} hours)"
                            else:
                                reason = f"Recent review {hours_since_review:.1f} hours ago"
                
                if is_overdue:
                    overdue_employees.append((employee, reason))
                elif "Too new" in reason:
                    employees_too_new.append((employee, reason))
                else:
                    employees_with_recent_reviews.append((employee, reason))
            
            # Print summary
            print(f"[*] Summary:")
            print(f"   - Overdue for review: {len(overdue_employees)}")
            print(f"   - Recent reviews (not overdue): {len(employees_with_recent_reviews)}")
            print(f"   - Too new (not eligible yet): {len(employees_too_new)}")
            print()
            
            if not overdue_employees:
                print("[✓] No overdue employees found. All employees are up to date!")
                return
            
            # Show overdue employees
            print(f"[!] Found {len(overdue_employees)} overdue employee(s):")
            for employee, reason in overdue_employees:
                print(f"   - {employee.name} ({employee.role}, {employee.department}): {reason}")
            print()
            
            # Ask for confirmation (skip if running non-interactively)
            try:
                print(f"[?] Generate reviews for {len(overdue_employees)} overdue employee(s)? (y/n): ", end="")
                response = input().strip().lower()
                
                if response != 'y' and response != 'yes':
                    print("[*] Cancelled by user.")
                    return
            except EOFError:
                # Running non-interactively (e.g., in a script or CI), auto-confirm
                print("[*] Running non-interactively - auto-confirming review generation...")
                print()
            
            print()
            print("[*] Generating reviews...")
            print()
            
            # Generate reviews for overdue employees
            review_manager = ReviewManager(db)
            reviews_created = []
            reviews_failed = []
            
            for idx, (employee, reason) in enumerate(overdue_employees, 1):
                try:
                    if verbose:
                        print(f"[{idx}/{len(overdue_employees)}] Generating review for {employee.name} ({employee.role}, {employee.department})...")
                        print(f"        Reason: {reason}")
                    else:
                        # Show progress every 10 employees
                        if idx % 10 == 0 or idx == len(overdue_employees):
                            print(f"[{idx}/{len(overdue_employees)}] Processing reviews... (currently: {employee.name})")
                    
                    review = await review_manager._generate_review(employee)
                    
                    if review:
                        reviews_created.append((employee, review))
                        if verbose:
                            print(f"        [+] Successfully created review for {employee.name} (Rating: {review.overall_rating}/5.0)")
                        elif idx % 10 == 0:
                            print(f"        [+] Created {len(reviews_created)} review(s) so far...")
                    else:
                        reviews_failed.append((employee, "No manager/executive available or generation failed"))
                        if verbose:
                            print(f"        [-] Failed to create review for {employee.name}")
                except Exception as e:
                    reviews_failed.append((employee, str(e)))
                    if verbose:
                        print(f"        [-] Error generating review for {employee.name}: {e}")
                        import traceback
                        traceback.print_exc()
                    else:
                        print(f"        [-] Error for {employee.name}: {str(e)[:50]}...")
            
            # Commit all reviews
            if reviews_created:
                try:
                    await db.commit()
                    print()
                    print(f"[+] Successfully committed {len(reviews_created)} review(s) to database")
                    print()
                    
                    # Show details of created reviews
                    print("[*] Review details:")
                    for employee, review in reviews_created:
                        # Get reviewer name
                        reviewer_result = await db.execute(
                            select(Employee).where(Employee.id == review.manager_id)
                        )
                        reviewer = reviewer_result.scalar_one_or_none()
                        reviewer_name = reviewer.name if reviewer else f"ID {review.manager_id}"
                        
                        print(f"   - {employee.name} ({employee.role}):")
                        print(f"     Reviewed by: {reviewer_name}")
                        print(f"     Overall Rating: {review.overall_rating}/5.0")
                        print(f"     Review Date: {review.review_date}")
                        if review.comments:
                            comments_preview = review.comments[:100] + "..." if len(review.comments) > 100 else review.comments
                            print(f"     Comments: {comments_preview}")
                        print()
                    
                    # Update performance award after reviews
                    print("[*] Updating performance award...")
                    try:
                        await review_manager._update_performance_award()
                        await db.commit()
                        print("[+] Performance award updated")
                    except Exception as e:
                        print(f"[-] Error updating performance award: {e}")
                        import traceback
                        traceback.print_exc()
                    
                except Exception as e:
                    print(f"[-] Error committing reviews: {e}")
                    import traceback
                    traceback.print_exc()
                    await db.rollback()
            else:
                print("[!] No reviews were created")
            
            if reviews_failed:
                print()
                print(f"[!] Failed to create {len(reviews_failed)} review(s):")
                for employee, error in reviews_failed:
                    print(f"   - {employee.name}: {error}")
            
            print()
            print("=" * 80)
            print("SCRIPT COMPLETED")
            print("=" * 80)
            
    except Exception as e:
        print(f"[-] Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Force generate employee reviews for overdue employees')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation and generate reviews immediately')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed logging for each review')
    args = parser.parse_args()
    
    asyncio.run(force_overdue_reviews(skip_confirmation=args.yes, verbose=args.verbose))

